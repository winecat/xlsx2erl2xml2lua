#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@author: dzw
@deprecated: 2013-11-7 17:07:43
'''
from libs.utils import load_excel, load_sheel, module_header, gen_erl, gen_xml, prev, replace_quote
from openpyxl.reader.excel import load_workbook
from collections import defaultdict
from collections import OrderedDict
import time
import types
import os
import sys
import locale
import platform
import unicodedata
import collections
# import inspect

reload(sys)
sys.setdefaultencoding('utf-8') #IGNORE:E1101
locale.setlocale(locale.LC_ALL, "")

########## 转换一个excel sheet ##########################
## excel_file 	EXCEL文件名
## excel_sheet  EXCEL sheet 名
## ConvertOneLineFun 转换一行的回调函数

class convert_excel_sheet(object):
	def __init__(self, excel_file, excel_sheet):
		self.excel_file = excel_file
		self.excel_sheet = excel_sheet
		self.is_finish = 0 			# parse结束标记
		self.line_index = 0			# excel当前行 0开始
		self.field_count = 0 		# 字段数
		self.field_name_dict = {}	# 各字段name列表 下标->name
		self.field_type_dict = {}	# 各字段type列表 下标->type
		self.field_merge_dict = {}	# 各字段merge列表 下标->merge 表示该字段是否按合并单元格方式来读 (为空则向上找第一个非空值) 
		self.field_for_dict = {}	# 各字段for列表 下标->for 表示该字段用于服务端或是客户端 一般用不到
		self.field_pre_dict = {}	# 各字段pre列表 下标->pre 在按type进行转换前的预格式化处理 用$$@$$表示EXCEL实际填的值
	
	def __call__(self, func):
		work_book = load_excel(self.excel_file)
		
		@load_sheel(work_book, self.excel_sheet)
		def content_line_parser(content, all_content, row):
			self.line_index = self.line_index + 1
			
			# 扫描除去标题行的第一行 生成字段名和类型字典
			if self.line_index == 1:
				(self.field_count, self.field_name_dict, self.field_type_dict, self.field_merge_dict, self.field_for_dict, self.field_pre_dict) = scan_get_name_type_arr(content)
				return[]
			
			# 如已扫描结束 直接return
			if self.is_finish == 1:
				return []
				
			# 如是忽略的行 直接return
			if is_skip_row(content, self.field_count):
				return []
			
			# 是否结束行
			if not self.field_merge_dict[0]:
				# 第1列为空 则整个EXCEL结束
				if content[0] == None:
					self.is_finish = 1
					return []
			else:
				# 第一列是合并单元格 允许为空 故转而检测所有列为空时认为整个EXCEL结束
				if is_empty_row(content, self.field_count):
					self.is_finish = 1
					return []
			
			# 处理合并单元格 (#name:type 标记的字段)
			for ff in range(0, self.field_count):
				if content[ff] == None and self.field_merge_dict[ff]:
					content[ff] = prev(all_content, row, ff)
			
			# 解析一个数据行
			# ED - erlang name-value字典
			# XD - xml name-value字典
			(ED, XD, LD) = scan_get_value_arr(content, self.field_count, self.field_name_dict, self.field_type_dict, self.field_for_dict, self.field_pre_dict)
			
			# 转换处理
			func(ED, XD, LD)
			
			return []
		content_line_parser()

class convert_excel_sheet2(object):	# 支持一条数据记录占excel多行 但不支持合并单元格
	def __init__(self, excel_file, excel_sheet):
		self.excel_file = excel_file
		self.excel_sheet = excel_sheet
		self.is_finish = 0 			# parse结束标记
		self.line_index = 0			# excel当前行 0开始
		self.field_count = 0 		# 字段数
		self.field_name_dict = {}	# 各字段name列表 下标->name
		self.field_type_dict = {}	# 各字段type列表 下标->type
		self.field_merge_dict = {}	# 各字段merge列表 下标->merge 表示该字段是否按合并单元格来读 (为空则向上找第一个非空值) 
		self.field_for_dict = {}	# 各字段for列表 下标->for 表示该字段用于服务端或是客户端 一般用不到
		self.field_pre_dict = {}	# 各字段pre列表 下标->pre 在按type进行转换前的预格式化处理 用$$@$$表示EXCEL实际填的值
		self.sum_content = {}		# 累计多行的content
	
	def __call__(self, func):
		work_book = load_excel(self.excel_file)
		
		@load_sheel(work_book, self.excel_sheet)
		def content_line_parser(content, all_content, row):
			self.line_index = self.line_index + 1
			
			# 扫描除去标题行的第一行 生成字段名和类型字典
			if self.line_index == 1:
				(self.field_count, self.field_name_dict, self.field_type_dict, self.field_merge_dict, self.field_for_dict, self.field_pre_dict) = scan_get_name_type_arr(content)
				return[]
			
			# 如已扫描结束 直接return
			if self.is_finish == 1:
				return []
			
			is_skip = is_skip_row(content, self.field_count)
			is_empty = is_empty_row(content, self.field_count)
			is_new = (not is_skip and content[0] != None and str(content[0]).strip() != "")
			
			if is_skip or is_empty or is_new:
				# 解析累计值
				if self.sum_content != {}:
					# ED - erlang name-value字典
					# XD - xml name-value字典
					# LD - lua name-value字典
					(ED, XD, LD) = scan_get_value_arr(self.sum_content, self.field_count, self.field_name_dict, self.field_type_dict, self.field_for_dict, self.field_pre_dict)
					func(ED, XD, LD)
					self.sum_content = {}
				if is_skip:
					return []
				if is_empty:
					self.is_finish = 1
					return []
				elif is_new:
					for i in range(0, self.field_count):
						self.sum_content[i] = ("" if content[i] == None else str(content[i]).strip())
			else:
				# 继续累计
				for i in range(0, self.field_count):
					if content[i] != None and str(content[i]).strip() != "":
						if self.sum_content[i] != "":
							self.sum_content[i] = self.sum_content[i] + "\n" + str(content[i]).strip()
						else:
							self.sum_content[i] = str(content[i]).strip()
							
			# 如果是最后一行 要立即解析
			if row == len(all_content) - 1:	
				if self.sum_content != {}:
					(ED, XD, LD) = scan_get_value_arr(self.sum_content, self.field_count, self.field_name_dict, self.field_type_dict, self.field_for_dict, self.field_pre_dict)
					func(ED, XD, LD)
					self.sum_content = {}
						
			return []
		content_line_parser()

def is_skip_row(content, fieldcount):
	# 规定以下特殊的行用于作华丽分割线
	# 只有一个单元格内容是~或- 其它都是None
	flag_count = 0
	for i in range(0, fieldcount):
		if content[i] != None and content[i] != "~" and content[i] != "-":
			return False
		elif content[i] != None:
			flag_count += 1
	return flag_count == 1
	
def is_empty_row(content, fieldcount):
	# 检测是否整行为空
	is_all_none = True
	for ff in range(0, fieldcount):
		if content[ff] != None and str(content[ff]) != "":
			is_all_none = False
			break
	return is_all_none

### 一个excel整个扫描 返回 (erl_dict_list, xml_dict_list)
def excel_sheet_to_dictlist(excel_file, excel_sheet):
	the_ed_list = []
	the_xd_list = []
	the_ld_list = []

	@convert_excel_sheet(excel_file, excel_sheet)
	def ConvertOneLine(ED, XD, LD):
		the_ed_list.append(ED)
		the_xd_list.append(XD)
		the_ld_list.append(LD)
		return[]

	return (the_ed_list, the_xd_list, the_ld_list)

def excel_sheet_to_dictlist2(excel_file, excel_sheet):
	the_ed_list = []
	the_xd_list = []
	the_ld_list = []

	@convert_excel_sheet2(excel_file, excel_sheet)
	def ConvertOneLine(ED, XD, LD):
		the_ed_list.append(ED)
		the_xd_list.append(XD)
		the_ld_list.append(LD)
		return[]

	return (the_ed_list, the_xd_list, the_ld_list)


######## 扫描生成字段name和type数组 ####
## excel第一行为标题
## excel第二行为name:type
## 本函数传入excel第二行content
## 返回(字段数, name[], type[], for[])

def scan_get_name_type_arr(content):
	field_count = 0
	name_dict = {}
	type_dict = {}
	merge_dict = {}
	for_dict = {}
	pre_dict = {}

	for i in range(0, 256):
		if i >= len(content) or content[i] == None or content[i] == "":	 ### 遇到空列 结束
			field_count = i
			break
		desc_arr = strip_split(content[i], "\n")		# 除了name:type描述, 预留扩展其它描述
		
		arr = desc_arr[0].split(':')
		if len(arr) >= 2:
			name_dict[i] = arr[0]			# name
			type_dict[i] = arr[1]			# type
		else:
			name_dict[i] = arr[0]
			type_dict[i] = "int"
			
		if name_dict[i][0] == '#':			# is_merge cell field
			merge_dict[i] = True
			name_dict[i] = name_dict[i][1:]
		else:
			merge_dict[i] = False
			
		if name_dict[i][0:2] == '__':		# for server only
			for_dict[i] = 2
			name_dict[i] = name_dict[i][2:]
		elif name_dict[i][0:1] == '_':		# for client only
			for_dict[i] = 1
			name_dict[i] = name_dict[i][1:]
		elif name_dict[i][0:1] == '~':		# for temp only
			for_dict[i] = 0
			name_dict[i] = name_dict[i][1:]
		else:								# for both server & client by default 
			for_dict[i] = 3
			
		if len(desc_arr) >= 2:
			if desc_arr[1][0:4] == "pre:":
				pre_dict[i] = desc_arr[1][4:].strip()	# pre
			else:
				pre_dict[i] = ""
		else:
			pre_dict[i] = ""
			
	return (field_count, name_dict, type_dict, merge_dict, for_dict, pre_dict)		### 返回 字段总数, name[], type[], for[] (for[]仅用于SERVER_LIST CLIENT_LIST LUA_LIST)

######## 扫描生成字段value数组 ####
### 传入excel第三行起的content
### 返回 name_erl_value_dict, name_xml_value_dict
### name_erl_value_dict: erlang名字值对应字典
### name_xml_value_dict: xml名字值对应字典

def scan_get_value_arr(content, field_count, name_dict, type_dict, for_dict, pre_dict):
	erl_value_dict = {}			## 下标对应erl_value
	name_erl_value_dict = {}	## 字段名对应erl_value
	xml_value_dict = {}			## 下标对应xml_value
	name_xml_value_dict = {}	## 字段名对应xml_value
	lua_value_dict = {}			## 下标对应lua_value
	name_lua_value_dict = {}	## 字段名对应xml_value
	
	name_meta_dict = {}			## excel原始数据
	for i in range(0, field_count):	
		cell_value = ("" if content[i] == None else str(content[i]).strip())
		name_meta_dict[name_dict[i]] = cell_value
	
	for i in range(0, field_count):
		# excel单元格实际填的值
		cell_value = ("" if content[i] == None else str(content[i]).strip())
		
		# 经过pre预处理后的值
		pred_value = cell_value
		if pre_dict[i] <> "":
			pred_value = pre_dict[i].replace("\\n", "\n")
			pred_value = pred_value.replace("$$@$$", cell_value)
			pred_value = fill_template_str(pred_value, name_meta_dict)
		
		# 转化为erlang值 放到字典
		erl_value = str_to_erl_value((content[i-1] if type_dict[i] == 'spec' else type_dict[i]), pred_value)
		erl_value_dict[i] = erl_value
		name_erl_value_dict[name_dict[i]] = erl_value
		
		# 转化为xml值 放到字典
		xml_value = str_to_xml_value((content[i-1] if type_dict[i] == 'spec' else type_dict[i]), pred_value)
		xml_value_dict[i] = xml_value
		name_xml_value_dict[name_dict[i]] = xml_value
		
		# 转化为lua值 放到字典
		lua_value = str_to_lua_value((content[i-1] if type_dict[i] == 'spec' else type_dict[i]), pred_value)
		lua_value_dict[i] = lua_value
		name_lua_value_dict[name_dict[i]] = lua_value
	
	# 自动生成两个内置数据: SERVER_LIST CLIENT_LIST
	# SERVER_LIST : name=value, name=value, ...
	# CLIENT_LIST: <name>value</name> <name>value</name>
	# LUA_LIST: name=value, name=value, ...
	is_first = 1
	server_list = ""
	for i in range(0, len(for_dict)):
		if for_dict[i] == 3 or for_dict[i] == 2:
			if is_first == 0:
				server_list += "\n,"
			server_list += "{0} = {1}".format(name_dict[i], erl_value_dict[i])
			is_first = 0
	name_erl_value_dict["SERVER_LIST"] = server_list
	
	is_first = 1
	client_list = ""
	for i in range(0, len(for_dict)):
		if for_dict[i] == 3 or for_dict[i] == 1 :
			if is_first == 0:
				client_list += "\n"
			client_list += "<{0}>{1}</{0}>".format(name_dict[i], xml_value_dict[i])
			is_first = 0
	name_xml_value_dict["CLIENT_LIST"] = client_list
	
	is_first = 1
	lua_list = ""
	for i in range(0, len(for_dict)):
		if for_dict[i] == 3 or for_dict[i] == 2:
			if is_first == 0:
				lua_list += "\n,"
			lua_list += "{0} = {1}".format(name_dict[i], erl_value_dict[i])
			is_first = 0
	name_lua_value_dict["LUA_LIST"] = lua_list
	
	# print "******************"
	# print field_count
	# print name_dict
	# print type_dict
	# print erl_value_dict
	# print name_erl_value_dict
	# print xml_value_dict
	# print name_xml_value_dict
	# print "******************"
	
	return (name_erl_value_dict, name_xml_value_dict, name_lua_value_dict)

######## 模板替换 ##################
## 传入模板字符串template_str, 和name-value字典
## 把 $$name$$ 替换为对应的value
## 返回替换后的字符串

def fill_template_str(template_str, name_value_dict):
	# print "**********************"
	# print name_value_dict
	# print name_dict
	# print "**********************"
	
	outstr = template_str
	for k in name_value_dict.keys():  
		to_replace = "$$" + k + "$$"
		outstr = smart_replace(outstr, to_replace, name_value_dict[k])
		
	return inner_format(outstr)

# 辅助函数
# 字符串宽度 (汉字按2计 英文按1计)
def get_hz_string_width(text):
	w = 0  
	for ch in text:  
		if isinstance(ch, unicode):  
			if unicodedata.east_asian_width(ch) != 'Na':
				w += 2
			else:  
				w += 1
		else:  
			w += 1
	return w

# 解释替换内部格式串 @@[Fmt,Arg,Arg..]XXX@@
def inner_format(outstr):
	ReplaceOk = True
	while ReplaceOk:
		ReplaceOk = False
		pos1 = outstr.find("@@[")
		if pos1 >= 0:
			pos2 = outstr.find("]", pos1 + 1)
			pos3 = outstr.find("@@", pos1 + 1)
			if pos2 > pos1 and pos3 > pos2:
				newstr = do_inner_format(outstr[pos1 + 3 : pos2], outstr[pos2 + 1:pos3])
				outstr = outstr[0:pos1] + newstr + outstr[pos3+2:]
				ReplaceOk = True
				
	return outstr
	
def do_inner_format(Fmt, str):
	arr = strip_split(Fmt, ",")
	if arr[0] == "W":
		return do_inner_format_W(int(arr[1]), str)
	elif arr[0] == 'lower':
		return do_inner_format_lower(str)
	elif arr[0] == 'upper':
		return do_inner_format_upper(str)
	return str

def do_inner_format_W(Width, str):
	w = get_hz_string_width(str)
	if w >= Width:
		return str
	return str + "{{0:{0}}}".format(Width - w).format("")
	
def do_inner_format_lower(str):
	return str.lower()

def do_inner_format_upper(str):
	return str.upper()
			
# 替换 (根据to_replace在str中的位置,调整newstr,以适合缩进)
def smart_replace(str, to_replace, newstr):
	index = str.find(to_replace)
	if index < 0:
		return str
	blank = ""
	for i in range(1, index + 1):
		if str[index - i] == "\r" or str[index - i] == "\n" or index - i == 0 : # 向前找到换行
			if str[index - i] == '\t' or str[index - i] == ' ':
				blank += str[index - i]
			for j in range(index - i + 1, index + 1):        # 再向后找到非空格 从而计算出缩进
				if str[j] == '\t' or str[j] == ' ':
					blank += str[j]
				else:
					break
			# blank = str[index - i + 1 : index]
			break
			
	return str.replace(to_replace, newstr.replace("\n", "\n" + blank))

# split并且strip并去掉为空的项
def strip_split(str, splitter):
	arr = str.split(splitter)
	n = len(arr)
	for i in range(0, n):
		index = n - 1 - i
		arr[index] = arr[index].strip()
		if arr[index] == "":
			del arr[index]
	return arr

# split(忽略()内的分隔符)并且strip并去掉为空的项
def count_char(str, ch):
	count = 0
	for i in range(0, len(str)):
		if str[i] == ch:
			count = count + 1
	return count

def strip_split2(str, splitter):
	arr = []
	s = str
	pos = s.find(splitter)
	while pos >= 0:
		sub = s[0:pos]
		if count_char(sub, '(') == count_char(sub, ')'):
			arr.append(sub)
			s = s[pos + len(splitter):]
			pos = s.find(splitter)
		else:
			pos = s.find(splitter, pos + len(splitter))
	
	if s != "":
		arr.append(s)
	
	n = len(arr)
	for i in range(0, n):
		index = n - 1 - i
		arr[index] = arr[index].strip()
		if arr[index] == "":
			del arr[index]
	return arr
	
# str->int
def to_int(str):
	return int(eval(str))

# str->float
def to_float(str):
	return float(eval(str))
	
# 单元格值去None去前后空格
def strip_none(excel_content_value):
	return ("" if excel_content_value == None else str(excel_content_value).strip())
	
# key-value list解析出value
def kvlist_getvalue(kvliststr, key, default):
	pattern = "{" + key + ","
	pos = kvliststr.find(pattern)
	if pos >= 0:
		# print "******"
		# print kvliststr
		vstart = pos + len(pattern)
		vend = kvliststr.find("}", vstart)
		if vend > 0:
			return kvliststr[vstart:vend].strip()
	return default

###### 树状(分层)输出 ##############################################
### KeyNameList 用于分层次的字段列表,如 ["main_id", "sub_id"]
### DictList 字典列表 (见convert_excel_sheet)
### fun 回调函数, 形式如 fun(Layer, Dict, Flag)
###      Layer 第几层节点 0 1 ...
###		 Index 第几个节点（同一父节点下）
###      Dict 节点对应的记录
###      Flag: 1节点开始  -1节点结束  0输出叶子节点
### 
class tree_output(object):
	def __init__(self, KeyNameList, DictList):
		self.KeyNameList = KeyNameList
		self.DictList = DictList
	def __call__(self, fun):
		Tree = self.build_tree(self.KeyNameList, self.DictList)
		self.travel_tree(Tree, fun)
	def build_tree(self, KeyNameList, DictList):
		Tree = collections.OrderedDict() if len(KeyNameList) > 0 else []
		for row in range(0, len(DictList)):
			SubTree = Tree
			for index in range(0, len(KeyNameList)):
				Key = DictList[row][KeyNameList[index]]
				if not Key in SubTree.keys():
					SubTree[Key] = {"face":DictList[row], "childs":collections.OrderedDict() if index < len(KeyNameList) - 1 else []} 
				SubTree = SubTree[Key]["childs"]
			SubTree.append(DictList[row])
		return Tree
	def travel_tree(self, Tree, fun):
		self.do_travel_tree(Tree, 0, fun)
	def do_travel_tree(self, Tree, Layer, fun):
		if type(Tree) == type(collections.OrderedDict()):
			keyindex = 0
			for key in Tree.keys():
				fun(Layer, keyindex, Tree[key]["face"], 1)
				self.do_travel_tree(Tree[key]["childs"], Layer + 1, fun)
				fun(Layer, keyindex, Tree[key]["face"], -1)
				keyindex += 1
		else:
			for i in range(0, len(Tree)):
				fun(Layer, i, Tree[i], 0)

def indent_str(N):
	s = ""
	for i in range(0, N):
		s += "\t"
	return s

######## 按type转换一个字段 ##########
def str_to_erl_value(ftype, strvalue):
	if ftype == "meta":									# 完全按照填写
		return to_meta_erl(strvalue)
	elif ftype == "int" or ftype[0:4] == "int(":		# int 或 int(默认值)
		can_trunc, defvalue, minvalue, maxvalue = parse_int_type(ftype)
		return to_int_erl(strvalue, can_trunc, defvalue, minvalue, maxvalue)
	elif ftype == "float" or ftype[0:6] == "float(":	# float 或 float(默认值)
		defvalue = parse_float_type(ftype)
		return to_float_erl(strvalue, defvalue)
	elif ftype == "bool" or ftype[0:5] == "bool(":		# bool 或 bool(默认值)
		defvalue = parse_bool_type(ftype, "erl")
		return to_bool_erl(strvalue, defvalue)
	elif ftype == "str" or ftype == "string":			# 字符串 str 或 string
		return to_str_erl(strvalue)
	elif ftype == "pair":								# 键值对 pair
		return to_pair_erl(strvalue)
	elif ftype == "arr" or ftype[0:4] == "arr(":		# 简单数组 arr 或 arr(子类型, 分割符)
		subtype, splitter = parse_arr_type(ftype)
		return to_arr_erl(strvalue, subtype, splitter)
	elif ftype[0:5] == "list(":							# 列表 list(子类型, 分割符, XML节点名)
		subtype, splitter, nodename = parse_list_type(ftype)
		return to_list_erl(strvalue, subtype, nodename, splitter)
	elif ftype == "loss":								# 专用 #loss{}
		return to_loss_erl(strvalue)
	elif ftype == "gain":								# 专用 #gain{}
		return to_gain_erl(strvalue)
	elif ftype == "condition":							# 专用 #condition{}
		return to_condition_erl(strvalue)
	elif ftype == "attr":								# 专用 {?ATTR_XXX, 值}
		return to_attr_erl(strvalue)
	elif ftype == "date":								# 专用 {YY, MM, DD, HH, MM, SS}
		return to_date_erl(strvalue)
	elif ftype == "bejeweled_gain":						# 宝石迷阵奖励专用 {Weight, #gain{}}
		return to_bejeweled_gain_erl(strvalue)
	elif ftype == "weight_gain":						# 权重奖励 {Weight, #gain{}}
		return to_weight_gain_erl(strvalue)
	elif ftype == "weight_tuple":						# 权重奖励 {Weight, {ItemBaseId, Num, Bind}}
		return to_weight_tuple_erl(strvalue)
	elif ftype == "tuple":						        # 物品tuple {ItemBaseId, Num, Bind}
		return to_tuple_erl(strvalue)
	elif ftype == "key":
		return to_pair_erl(strvalue)
	elif ftype == "daily_act_date":						# 日常活动开启时间专用
		return to_daily_act_date_erl(strvalue)
	else:
		return strvalue

def str_to_xml_value(ftype, strvalue):
	if ftype == "meta":									# 完全按照填写
		return to_meta_xml(strvalue)
	elif ftype == "int" or ftype[0:4] == "int(":		# int 或 int(默认值)
		can_trunc, defvalue, minvalue, maxvalue = parse_int_type(ftype)
		return to_int_xml(strvalue, can_trunc, defvalue, minvalue, maxvalue)
	elif ftype == "float" or ftype[0:6] == "float(":	# float 或 float(默认值)
		defvalue = parse_float_type(ftype)
		return to_float_xml(strvalue, defvalue)
	elif ftype == "bool" or ftype[0:5] == "bool(":		# bool 或 bool(默认值)
		defvalue = parse_bool_type(ftype, "xml")
		return to_bool_xml(strvalue, defvalue)
	elif ftype == "str" or ftype == "string":			# str 或 string
		return to_str_xml(strvalue)
	elif ftype == "pair":								# 键值对 pair
		return to_pair_xml(strvalue)
	elif ftype == "arr" or ftype[0:4] == "arr(":		# 简单数组 arr 或 arr(子类型, 分割符)
		subtype, splitter = parse_arr_type(ftype)
		return to_arr_xml(strvalue, subtype, splitter)
	elif ftype[0:5] == "list(":							# 列表 list 或 list(子类型, 分割符, XML节点名)
		subtype, splitter, nodename = parse_list_type(ftype)
		return to_list_xml(strvalue, subtype, nodename, splitter)
	elif ftype == "loss":								# 专用 #loss
		return to_loss_xml(strvalue)
	elif ftype == "gain":								# 专用 #gain
		return to_gain_xml(strvalue)
	elif ftype == "condition":							# 专用 #condition
		return to_condition_xml(strvalue)
	elif ftype == "attr":								# 专用 {?ATTR_XXX, 值}
		return to_attr_xml(strvalue)
	elif ftype == "date":								# 专用 YY-MM-DD-HH-MM-SS
		return to_date_xml(strvalue)
	elif ftype == "weight_gain":						# 权重奖励 {Weight, #gain{}}
		return to_weight_gain_xml(strvalue)
	elif ftype == "weight_tuple":						# 权重奖励 {Weight, {ItemBaseId, Num, Bind}}
		return to_weight_tuple_xml(strvalue)
	elif ftype == "tuple":						        # 物品tuple {ItemBaseId, Num, Bind}
		return to_tuple_xml(strvalue)
	elif ftype == "key":								# 键值对 pair
		return to_key_xml(strvalue)
	elif ftype == "daily_act_date":						# 日常活动开启时间专用
		return to_daily_act_date_xml(strvalue)
	else:
		return strvalue

def str_to_lua_value(ftype, strvalue):
	if ftype == "meta":									# 完全按照填写
		return to_meta_lua(strvalue)
	elif ftype == "int" or ftype[0:4] == "int(":		# int 或 int(默认值)
		can_trunc, defvalue, minvalue, maxvalue = parse_int_type(ftype)
		return to_int_lua(strvalue, can_trunc, defvalue, minvalue, maxvalue)
	elif ftype == "float" or ftype[0:6] == "float(":	# float 或 float(默认值)
		defvalue = parse_float_type(ftype)
		return to_float_lua(strvalue, defvalue)
	elif ftype == "bool" or ftype[0:5] == "bool(":		# bool 或 bool(默认值)
		defvalue = parse_bool_type(ftype, "erl")
		return to_bool_lua(strvalue, defvalue)
	elif ftype == "str" or ftype == "string":			# 字符串 str 或 string
		return to_str_lua(strvalue)
	elif ftype == "pair":								# 键值对 pair
		return to_pair_lua(strvalue)
	elif ftype == "arr" or ftype[0:4] == "arr(":		# 简单数组 arr 或 arr(子类型, 分割符)
		subtype, splitter = parse_lua_type(ftype)
		return to_arr_lua(strvalue, subtype, splitter)
	elif ftype[0:5] == "list(":							# 列表 list(子类型, 分割符, XML节点名)
		subtype, splitter, nodename = parse_list_type(ftype)
		return to_list_lua(strvalue, subtype, nodename, splitter)
	elif ftype == "loss":								# 专用 #loss{}
		return to_loss_lua(strvalue)
	elif ftype == "gain":								# 专用 #gain{}
		return to_gain_lua(strvalue)
	elif ftype == "condition":							# 专用 #condition{}
		return to_condition_lua(strvalue)
	elif ftype == "attr":								# 专用 {?ATTR_XXX, 值}
		return to_attr_lua(strvalue)
	elif ftype == "date":								# 专用 {YY, MM, DD, HH, MM, SS}
		return to_date_lua(strvalue)
	elif ftype == "weight_gain":						# 权重奖励 {Weight, #gain{}}
		return to_weight_gain_lua(strvalue)
	elif ftype == "weight_tuple":						# 权重奖励 {Weight, {ItemBaseId, Num, Bind}}
		return to_weight_tuple_lua(strvalue)
	elif ftype == "tuple":						        # 物品tuple {ItemBaseId, Num, Bind}
		return to_tuple_lua(strvalue)
	elif ftype == "key":
		return to_pair_lua(strvalue)
	elif ftype == "daily_act_date":						# 日常活动开启时间专用
		return to_daily_act_date_lua(strvalue)
	else:
		return strvalue
######## 各种type的转换实现 ##########

### meta #####
## 完全按照手填
## type : meta
## 
def to_meta_erl(strvalue):
	return strvalue

def to_meta_xml(strvalue):
	return strvalue

def to_meta_lua(strvalue):
	return replace_quote(strvalue)

### int #####
## 整数型
## type:  int 或 int(默认值，最小值，最大值) 或 int(#默认值，最小值，最大值)
##
def parse_int_type(ftype):
	if ftype[0:4] == "int(":
		endpos = ftype.find(")")
		extarr = strip_split(ftype[4:endpos], ",")
		defvalue = extarr[0]
		can_trunc = False
		if defvalue[0] == '#':
			defvalue = defvalue[1:]
			can_trunc = True
		minvalue = (extarr[1] if len(extarr) >= 2 else "")
		maxvalue = (extarr[2] if len(extarr) >= 3 else "")
		return (can_trunc, defvalue, minvalue, maxvalue)
	else:
		return (False, "0", "", "")

def to_int_erl(strvalue, can_trunc, defvalue, minvalue, maxvalue):
	if strvalue == "":
		return defvalue
	if strvalue.find(":") >= 0:
		arr = strvalue.split(":")
		strvalue = arr[0]
	value = to_int(strvalue)
	if not can_trunc:
		if to_int(strvalue) != to_float(strvalue):	## 防止策划以为支持浮点数
			exit("*** error! {0} is NOT integer".format(strvalue))
	if minvalue != "" and value < to_int(minvalue):
		exit("*** error! int value = {0} < min_value {1}".format(value, minvalue))
	if maxvalue != "" and value > to_int(maxvalue):
		exit("*** error! int value = {0} > max_value {1}".format(value, maxvalue))
	return "{0:d}".format(value)
	
def to_int_xml(strvalue, can_trunc, defvalue, minvalue, maxvalue):
	if strvalue == "":
		return defvalue
	if strvalue.find(":") >= 0:
		arr = strvalue.split(":")
		strvalue = arr[0]
	value = to_int(strvalue)
	if minvalue != "" and value < to_int(minvalue):
		exit("*** error! int value = {0} < min_value {1}".format(value, minvalue))
	if maxvalue != "" and value > to_int(maxvalue):
		exit("*** error! int value = {0} > max_value {1}".format(value, maxvalue))
	return "{0:d}".format(value)

def to_int_lua(strvalue, can_trunc, defvalue, minvalue, maxvalue):
	if strvalue == "":
		return defvalue
	if strvalue.find(":") >= 0:
		arr = strvalue.split(":")
		strvalue = arr[0]
	value = to_int(strvalue)
	if not can_trunc:
		if to_int(strvalue) != to_float(strvalue):	## 防止策划以为支持浮点数
			exit("*** error! {0} is NOT integer".format(strvalue))
	if minvalue != "" and value < to_int(minvalue):
		exit("*** error! int value = {0} < min_value {1}".format(value, minvalue))
	if maxvalue != "" and value > to_int(maxvalue):
		exit("*** error! int value = {0} > max_value {1}".format(value, maxvalue))
	return "{0:d}".format(value)

### float #####
## 浮点型
## type: float 或 float(默认值)
##
def parse_float_type(ftype):
	if ftype[0:6] == "float(":
		endpos = ftype.find(")")
		return ftype[6:endpos]
	else:
		return "0.0"
		
def to_float_erl(strvalue, defvalue):
	if strvalue == "":
		return defvalue
	return "{0}".format(float(strvalue))

def to_float_xml(strvalue, defvalue):
	if strvalue == "":
		return defvalue
	return "{0}".format(float(strvalue))

def to_float_lua(strvalue, defvalue):
	if strvalue == "":
		return defvalue
	return "{0}".format(float(strvalue))

### bool #####
## 布尔型
## type: bool 或 bool(默认值)
##
def parse_bool_type(ftype, which):
	if ftype[0:5] == "bool(":
		endpos = ftype.find(")")
		defvalue = ftype[6:endpos]
		if which == "erl":
			return "true" if defvalue == "true" or defvalue == "1" else "false"
		else:
			return "1" if defvalue =="true" or defvalue == "1" else "0"
	else:
		if which == "erl":
			return "false"
		else:
			return "0"

def to_bool_erl(strvalue, defvalue):
	if strvalue == "":
		return defvalue
	if int(eval(strvalue)) == 1:
		return "true"
	return "false"

def to_bool_xml(strvalue, defvalue):
	if strvalue == "":
		return defvalue
	if int(eval(strvalue)) == 1:
		return "1"
	return "0"

def to_bool_erl(strvalue, defvalue):
	if strvalue == "":
		return defvalue
	if int(eval(strvalue)) == 1:
		return true
	return false

### str #####
def to_str_erl(strvalue):
	return "<<\"" + strvalue + "\">>"

def to_str_xml(strvalue):
	return strvalue

def to_str_lua(strvalue):
	return "\"" + replace_quote(strvalue) + "\""

### pair | key #####
## 键值对
## type : pair | key
##
## excel: key#value
## erlang: {key, value}
## xml: <key>value</key> | <key value="Key">Value</key>
## 
def to_pair_erl(strvalue):
	arr = strip_split(strvalue, "#")
	if len(arr) != 2:
		exit("*** error! to_pair_erl {0}".format(arr))
	return "{{{0}, {1}}}".format(arr[0], arr[1])


def to_pair_xml(strvalue):
	arr = strip_split(strvalue, "#")
	if len(arr) != 2:
		exit("*** error! to_pair_xml {0}".format(arr))
	if arr[0][0] == "?":
		arr[0] = arr[0][1:]
	return "<{0}>{1}</{0}>".format(arr[0], arr[1])

def to_pair_lua(strvalue):
	arr = strip_split(strvalue, "#")
	if len(arr) != 2:
		exit("*** error! to_pair_lua {0}".format(arr))
	if arr[0].isdigit():
		return "[{0}] = {1}".format(arr[0], arr[1])
	else:
		return "{0} = {1}".format(arr[0].replace("?", ""), arr[1])
	
def to_key_xml(strvalue):
	arr = strip_split(strvalue, "#")
	if len(arr) != 2:
		exit("*** error! to_key_xml {0}".format(arr))
	if arr[0][0] == "?":
		arr[0] = arr[0][1:]
	return """<key value="{0}">{1}</key>""".format(arr[0], arr[1])
	
### arr #####
## 逗号(或指定分隔符)分割的简单数组
## type:  arr   或 arr(子类型, 分割符)
##
## excel: A,B
## erlang: [A,B]
## xml: 
##       <item>A</item>
##       <item>B</item>
##
def parse_arr_type(ftype):
	if ftype[0:4] == "arr(":
		endpos = ftype.rfind(")")
		desc = ftype[4:endpos]
		arr = strip_split2(desc, ",")
		splitter = (arr[1] if len(arr)>=2 else ",")
		splitter = "\n" if splitter == "\\n" else splitter
		return arr[0], splitter
	else:
		return "int", ","

def to_arr_erl(strvalue, subtype, splitter):
	itemarr = strip_split(strvalue.lstrip('[').rstrip(']'), splitter)
	retvalue = "["
	for kk in range(0, len(itemarr)):
		if kk > 0:
			retvalue += ", "
		retvalue += str_to_erl_value(subtype, itemarr[kk])
	retvalue += "]"
	return retvalue

def parse_lua_type(ftype):
	if ftype[0:4] == "arr(":
		endpos = ftype.rfind(")")
		desc = ftype[4:endpos]
		arr = strip_split2(desc, ",")
		splitter = (arr[1] if len(arr)>=2 else ",")
		splitter = "\n" if splitter == "\\n" else splitter
		return arr[0], splitter
	else:
		return "int", ","

def to_arr_lua(strvalue, subtype, splitter):
	itemarr = strip_split(strvalue.lstrip('[').rstrip(']'), splitter)
	retvalue = "["
	for kk in range(0, len(itemarr)):
		if kk > 0:
			retvalue += ", "
		retvalue += str_to_lua_value(subtype, itemarr[kk])
	retvalue += "]"
	return retvalue


def to_arr_xml(strvalue, subtype, splitter):
	itemarr = strip_split(strvalue.lstrip('[').rstrip(']'), splitter)
	retvalue = ""
	for kk in range(0, len(itemarr)):
		retvalue += "<item>{0}</item>".format(str_to_xml_value(subtype, itemarr[kk])) 
	return retvalue	

### list(type) ###	
## \n分隔的list 每一项是指定的type
## type: list(type) 或 list(type, splitter, nodename) 
## 
def parse_list_type(ftype):
	if ftype[0:5] == "list(":
		endpos = ftype.rfind(")")
		desc = ftype[5:endpos]
		arr = strip_split2(desc, ",")
		subtype = arr[0]
		splitter = arr[1] if len(arr) >= 2 and arr[1] != "\\n" else "\n"
		nodename = arr[2] if len(arr) >= 3 else ""
		return subtype, splitter, nodename
	else:
		return "int", "\n", ""

def to_list_erl(strvalue, type, nodename, splitter):
	arr = strip_split(strvalue, ("\n" if splitter == "" else splitter))
	if len(arr) <= 0:
		return "[]"
	outstr = "["
	for i in range(0, len(arr)):
		if i > 0:
			outstr = outstr + ", "
		outstr = outstr + str_to_erl_value(type, arr[i])
	outstr = outstr + "]"
	return outstr

def to_list_lua(strvalue, type, nodename, splitter):
	arr = strip_split(strvalue, ("\n" if splitter == "" else splitter))
	if len(arr) <= 0:
		return "{}"
	outstr = "{"
	for i in range(0, len(arr)):
		if i > 0:
			outstr = outstr + ", "
		outstr = outstr + str_to_lua_value(type, arr[i])
	outstr = outstr + "}"
	return outstr

def to_list_xml(strvalue, type, nodename, splitter):
	arr = strip_split(strvalue, ("\n" if splitter == "" else splitter))
	if len(arr) <= 0:
		return ""
	outstr = "\n"
	for i in range(0, len(arr)):
		outstr += "\t"
		if nodename == "":
			outstr = outstr + str_to_xml_value(type, arr[i]) + "\n"
		else:
			outstr = outstr + "<" + nodename + ">" + str_to_xml_value(type, arr[i]) + "</" + nodename + ">" + "\n"
	return outstr
	
### loss ####
## 用于配置消耗
## excel: 标签#值 或 ID#值
## erlang: #loss{}
## xml: <loss><item_id></item_id><num></num></loss>
## 
## excel            erlang                          xml
## gold#100			#loss{label=gold, val=100}      <loss><item_id>1</item_id><num>100</num></loss>
## bgold#100        #loss{label=bgold, val=100}     <loss><item_id>2</item_id><num>100</num></loss>
## coin#100         #loss{label=coin, val=100}      <loss><item_id>3</item_id><num>100</num></loss>
## exp#100          #loss{label=exp, val=100}       <loss><item_id>4</item_id><num>100</num></loss>
## scope#100        #loss{label=scope, val=100}     <loss><item_id>5</item_id><num>100</num></loss>
## cd#100			#loss{label=eqm_cooldown, val=100} <loss><item_id>6</item_id><num>100</num></loss>
## 1#100			#loss{label=gold, val=100}      <loss><item_id>1</item_id><num>100</num></loss>         ## 铜币等也可使用虚拟物品ID
## 10000#1			#loss{label=items_bind_fst, val={?storage_bag, [{10000, 1}]}}     <loss><item_id>10000</item_id><num>1</num></loss>
## 
## ## 注意: 一行只能配一个物品!
## 

def to_loss_erl(str):
	outstr = ""
	arr = strip_split(str, "#")
	if arr[0].isdigit():	# 一般物品  id#num
		outstr = "#loss{{item_id={0}, quantity={1}, bind = {2}}}".format(to_int(arr[0]), to_int(arr[1]), to_int(arr[2] if len(arr) >= 3 else "0"))
	else: #虚拟物品 label#val
		exit("*** error! to_loss_erl, item_id error {0}".format(arr[0]))
	return outstr

def to_loss_lua(str):
	outstr = ""
	arr = strip_split(str, "#")
	if arr[0].isdigit():	# 一般物品  id#num
		outstr = "{{item_id={0}, quantity={1}, bind = {2}}}".format(to_int(arr[0]), to_int(arr[1]), to_int(arr[2] if len(arr) >= 3 else "0"))
	else: #虚拟物品 label#val
		exit("*** error! to_loss_lua, item_id error {0}".format(arr[0]))
	return outstr

def to_loss_xml(str):
	outstr = ""
	arr = strip_split(str, "#")
	if arr[0].isdigit():	# 一般物品 id#num
		outstr += "<loss><item_id>{0}</item_id><num>{1}</num></loss>".format(arr[0], arr[1])
	else: #虚拟物品 label#val
		exit("*** error! to_loss_xml, item_id error {0}".format(arr[0]))
	return outstr

### gain ####
## 用于配置奖励
## excel: 标签#值#是否绑定 或 ID#值#是否绑定
## erlang: #gain{}
## xml: <gain><item_id></item_id><num></num><is_bind></is_bind></gain>
## 
## excel            erlang                          xml
## gold#100			#gain{label=gold, val=100}      <gain><item_id>1</item_id><num>100</num><is_bind>0</is_bind></gain>  注:is_bind对虚拟物品无实际意义
## bgold#100        #gain{label=bgold, val=100}     <gain><item_id>2</item_id><num>100</num><is_bind>1</is_bind></gain>
## coin#100         #gain{label=coin, val=100}      <gain><item_id>3</item_id><num>100</num><is_bind>1</is_bind></gain>
## exp#100          #gain{label=exp, val=100}       <gain><item_id>4</item_id><num>100</num><is_bind>0</is_bind></gain>
## scope#100        #gain{label=scope, val=100}     <gain><item_id>5</item_id><num>100</num><is_bind>0</is_bind></gain>
## cd#100       	#gain{label=eqm_cooldown, val=100}     <gain><item_id>6</item_id><num>100</num><is_bind>0</is_bind></gain>
## 1#100			#gain{label=gold, val=100}      <gain><item_id>1</item_id><num>100</num><is_bind>0</is_bind></gain>  ## 铜币等也可使用虚拟物品ID
## 10000#99#1       #gain{label=item, val={?storage_bag, {10000, 99, 1}}}     <gain><item_id>10000</item_id><num>99</num><is_bind>1</is_bind></gain></gain>
##
## 注意: 一行只能配一个物品!
## 
def to_gain_erl(str):
	outstr = ""
	arr = strip_split(str, "#")
	if arr[0].isdigit():	# 一般物品 id#num#bind
		outstr = "#gain{{item_id={0}, quantity={1}, bind = {2}}}".format(to_int(arr[0]), to_int(arr[1]), to_int(arr[2] if len(arr) >= 3 else "0"))
	else: #虚拟物品 label#val
		exit("*** error! to_gain_erl, item_id error {0}".format(arr[0]))
	return outstr

def to_gain_lua(str):
	outstr = ""
	arr = strip_split(str, "#")
	if arr[0].isdigit():	# 一般物品 id#num#bind
		outstr = "{{item_id={0}, quantity={1}, bind = {2}}}".format(to_int(arr[0]), to_int(arr[1]), to_int(arr[2] if len(arr) >= 3 else "0"))
	else: #虚拟物品 label#val
		exit("*** error! to_gain_lua, item_id error {0}".format(arr[0]))
	return outstr

def to_gain_xml(str):
	outstr = ""
	arr = strip_split(str, "#")
	if arr[0].isdigit():	# 一般物品  id#num#bind
		outstr += "<gain><item_id>{0}</item_id><num>{1}</num><is_bind>{2}</is_bind></gain>".format(arr[0], arr[1], arr[2] if len(arr) >= 3 else 0)
	else: #虚拟物品 label#val
		exit("*** error! to_gain_xml, item_id error {0}".format(arr[0]))
	return outstr

### condition ####
## 用于配置条件
## type : condition
##
## excel: label#value 或 label#target#value
## erlang: #condition{label = lev, target_value = 1}
## xml: <condition><label></label><target_value></target_value></condition>
## 
## excel            erlang                         					 xml
## lev#99			#condition{label = lev, target_value = 99}		 <condition><label>1</label><target_value>99</target_value></condition>
def to_condition_erl(str):
	arr = strip_split(str, "#")
	label = ""
	if arr[0].isdigit():
		label = get_condition_label(int(arr[0]))
	else:
		label = arr[0]
	if len(arr) == 2:
		return "#condition{{label = {0}, target_value = {1}}}".format(label, arr[1])
	elif len(arr) == 3:
		return "#condition{{label = {0}, target = {1}, target_value = {2}}}".format(label, arr[1], arr[2])
	elif len(arr) == 4:
		return "#condition{{label = {0}, target = {1}, target_ext = {2}, target_value = {3}}}".format(label, arr[1], arr[2], arr[3])
	else:
		exit("*** error! to_condition_erl {0}".format(str))	
def to_condition_xml(str):
	arr = strip_split(str, "#")
	label_code = ""
	if arr[0].isdigit():
		label_code = int(arr[0])
	else:
		label_code = get_condition_code(arr[0])
	if len(arr) == 2:
		return "<condition><label>{0}</label><target>0</target><target_ext>0</target_ext><target_value>{1}</target_value></condition>".format(label_code, arr[1])
	elif len(arr) == 3:
		return "<condition><label>{0}</label><target>{1}</target><target_ext>0</target_ext><target_value>{2}</target_value></condition>".format(label_code, arr[1], arr[2])
	elif len(arr) == 4:
		return "<condition><label>{0}</label><target>{1}</target><target_ext>{2}</target_ext><target_value>{3}</target_value></condition>".format(label_code, arr[1], arr[2], arr[3])
	else:
		exit("*** error! to_condition_xml {0}".format(str))

def to_condition_lua(str):
	arr = strip_split(str, "#")
	label = ""
	if arr[0].isdigit():
		label = get_condition_label(int(arr[0]))
	else:
		label = arr[0]
	if len(arr) == 2:
		return "{{label = {0}, target_value = {1}}}".format(label, arr[1])
	elif len(arr) == 3:
		return "{{label = {0}, target = {1}, target_value = {2}}}".format(label, arr[1], arr[2])
	elif len(arr) == 4:
		return "{{label = {0}, target = {1}, target_ext = {2}, target_value = {3}}}".format(label, arr[1], arr[2], arr[3])
	else:
		exit("*** error! to_condition_lua {0}".format(str))	

### ATTR ####
## 用于配置属性
## type : attr
##
## excel: attr_code#value
## erlang: {?ATTR_XXX, Value}
## xml: <attr><type></type><val></val></attr>
## 
## excel            erlang                         			xml
## 1#100            {?ATTR_DMG, 100}                        <attr><type>1</type><val>100</val></attr>
##
def to_attr_erl(str):
	arr = strip_split(str, "#")
	if len(arr) == 2:
		return "{{{0}, {1}}}".format(get_attr_name(int(arr[0])), arr[1])
	else:
		exit("*** error! to_attr_erl {0}".format(str))
		
def to_attr_xml(str):
	arr = strip_split(str, "#")
	if len(arr) == 2:
		return "<attr><type>{0}</type><val>{1}</val></attr>".format(arr[0], arr[1])
	else:
		exit("*** error! to_attr_xml {0}".format(str))
		
def to_attr_lua(str):
	arr = strip_split(str, "#")
	if len(arr) == 2:
		return "{{type={0}, value={1}}}".format(arr[0], arr[1])
	else:
		exit("*** error! to_attr_lua {0}".format(str))
### date ####
## 用于配置日期
## type : date
##
## excel: YY#MM#DD#HH#MM#SS
## erlang: {YY, MM, DD, HH, MM, SS}
## xml: YY-MM-DD-HH-MM-SS
## 
## excel            				erlang                         			xml
## 2013#12#24#0#0#0            {2013, 12, 24, 0, 0, 0}                2013-12-24-0-0-0
##
def to_date_erl(str):
	if str == "":
		return "{0, 0, 0, 0, 0, 0}"
	arr = strip_split(str, "#")
	if len(arr) == 3:
		return "{{{0}, {1}, {2}, 0, 0, 0}}".format(arr[0], arr[1], arr[2])
	elif len(arr) == 6:
		return "{{{0}, {1}, {2}, {3}, {4}, {5}}}".format(arr[0], arr[1], arr[2], arr[3], arr[4], arr[5])
	else:
		exit("*** error! to_date_erl {0}".format(str))
def to_date_xml(str):
	if str == "":
		return "0-0-0-0-0-0"
	arr = strip_split(str, "#")
	if len(arr) == 3:
		return "<date>{0}-{1}-{2}-0-0-0</date>".format(arr[0], arr[1], arr[2])
	elif len(arr) == 6:
		return "<date>{0}-{1}-{2}-{3}-{4}-{5}</date>".format(arr[0], arr[1], arr[2], arr[3], arr[4], arr[5])
	else:
		exit("*** error! to_date_xml {0}".format(str))

def to_date_lua(str):
	if str == "":
		return "{0, 0, 0, 0, 0, 0}"
	arr = strip_split(str, "#")
	if len(arr) == 3:
		return "{{{0}, {1}, {2}, 0, 0, 0}}".format(arr[0], arr[1], arr[2])
	elif len(arr) == 6:
		return "{{{0}, {1}, {2}, {3}, {4}, {5}}}".format(arr[0], arr[1], arr[2], arr[3], arr[4], arr[5])
	else:
		exit("*** error! to_date_lua {0}".format(str))

### weight_gain ####
## excel: #权重值#标签#值#是否绑定 或 #权重值#ID#值#是否绑定
## erlang: {WeightVal, #gain{}}
## xml: <weight_gain><weight></weight><item_id></item_id><num></num><is_bind></is_bind></weight_gain>
def to_weight_gain_erl(str):
	outstr = ""
	arr = strip_split(str, "#")
	if arr[1].isdigit():	# 一般物品 id#num#bind
		outstr = "#gain{{item_id={0}, quantity={1}, bind = {2}}}".format(to_int(arr[1]), to_int(arr[2]), to_int(arr[3] if len(arr) >= 4 else "0"))
	else: #虚拟物品 label#val
		exit("*** error! to_weight_gain_erl, item_id error {0}".format(arr[0]))
	return outstr


def to_weight_gain_xml(str):
	outstr = ""
	arr = strip_split(str, "#")
	if arr[1].isdigit():	# 一般物品  id#num#bind
		outstr += "<weight_gain><weight>{0}</weight><item_id>{1}</item_id><num>{2}</num><is_bind>{3}</is_bind></weight_gain>".format(arr[0], arr[1], arr[2], arr[3] if len(arr) >= 4 else 0)
	else: #虚拟物品 label#val
		exit("*** error! to_weight_gain_xml, item_id error {0}".format(arr[0]))
	return outstr

def to_weight_gain_lua(str):
	outstr = ""
	arr = strip_split(str, "#")
	if arr[1].isdigit():	# 一般物品 id#num#bind
		outstr = "{{item_id={0}, quantity={1}, bind = {2}}}".format(to_int(arr[1]), to_int(arr[2]), to_int(arr[3] if len(arr) >= 4 else "0"))
	else: #虚拟物品 label#val
		exit("*** error! to_weight_gain_erl, item_id error {0}".format(arr[0]))
	return outstr


### weight_tuple ####
## excel: #权重值#物品Id#数量#是否绑定
## erlang: {Weight, {ItemId, Num, Bind}}
## xml: <weight_tuple><weight></weight><item_id></item_id><num></num><is_bind></is_bind></weight_tuple>
## lua: {item_id={0}, quantity={1}, bind = {2}}
def to_weight_tuple_erl(str):
	outstr = ""
	arr = strip_split(str, "#")
	if arr[1].isdigit():	# 一般物品 id#num#bind
		outstr = "{{{0}, {{{1}, {2}, {3}}}}}".format(arr[0], arr[1], arr[2], arr[3] if len(arr) >= 4 else 0)
	else: #虚拟物品 label#val
		exit("*** error! to_weight_tuple_erl, Weight error {0}".format(arr[0]))
	return outstr


def to_weight_tuple_xml(str):
	outstr = ""
	arr = strip_split(str, "#")
	if arr[1].isdigit():	# 一般物品  id#num#bind
		outstr += "<weight_tuple><weight>{0}</weight><item_id>{1}</item_id><num>{2}</num><is_bind>{3}</is_bind></weight_tuple>".format(arr[0], arr[1], arr[2], arr[3] if len(arr) >= 4 else 0)
	else: #虚拟物品 label#val
		exit("*** error! to_weight_tuple_xml, Weight error {0}".format(arr[0]))
	return outstr

def to_weight_tuple_lua(str):
	outstr = ""
	arr = strip_split(str, "#")
	if arr[1].isdigit():	# 一般物品 id#num#bind
		outstr = "{{item_id={0}, quantity={1}, bind = {2}}}".format(to_int(arr[1]), to_int(arr[2]), to_int(arr[3] if len(arr) >= 4 else "0"))
	else: #虚拟物品 label#val
		exit("*** error! to_weight_tuple_lua, Weight error {0}".format(arr[0]))
	return outstr

### tuple ####
## excel: 物品Id#数量#是否绑定
## erlang: {ItemId, Num, Bind}
## xml: <tuple><item_id></item_id><num></num><is_bind></is_bind></tuple>
## lua: {item_id={0}, quantity={1}, bind = {2}}
def to_tuple_erl(str):
	outstr = ""
	arr = strip_split(str, "#")
	if arr[1].isdigit():	# 一般物品 id#num#bind
		outstr = "{{{0}, {1}, {2}}}".format(arr[0], arr[1], arr[2] if len(arr) >= 3 else 0)
	else: #虚拟物品 label#val
		exit("*** error! to_weight_tuple_erl, Weight error {0}".format(arr[0]))
	return outstr


def to_tuple_xml(str):
	outstr = ""
	arr = strip_split(str, "#")
	if arr[1].isdigit():	# 一般物品  id#num#bind
		outstr += "<tuple><item_id>{0}</item_id><num>{1}</num><is_bind>{2}</is_bind></tuple>".format(arr[0], arr[1], arr[2] if len(arr) >= 3 else 0)
	else: #虚拟物品 label#val
		exit("*** error! to_weight_tuple_xml, Weight error {0}".format(arr[0]))
	return outstr

def to_tuple_lua(str):
	outstr = ""
	arr = strip_split(str, "#")
	if arr[1].isdigit():	# 一般物品 id#num#bind
		outstr = "{{item_id={0}, quantity={1}, bind = {2}}}".format(to_int(arr[0]), to_int(arr[1]), to_int(arr[2] if len(arr) >= 3 else "0"))
	else: #虚拟物品 label#val
		exit("*** error! to_weight_tuple_lua, Weight error {0}".format(arr[0]))
	return outstr

### daily_act_date ####
## 用于配置日常活动开启日期
## type : daily_act_date
##
## excel: WW1#HH1#MM1#SS1-WW2#HH2#MM2#SS2-WW3#HH3#MM3#SS3
## erlang: #daily_activity_time{
##				pre_weektime = {WW1, HH1, MM1, SS1}, 	#准备阶段开始时间
##				open_weektime = {WW2, HH2, MM2, SS2}, 	#开启阶段开始时间
##				stop_weektime = {WW3, HH3, MM3, SS3}}	#结束阶段开始时间
## xml: WW1#HH1#MM1#SS1-WW2#HH2#MM2#SS2-WW3#HH3#MM3#SS3
## 
## WW#HH#MM#SS格式及意义为： 0 <= WW <= 8; 0 <= HH <= 23; 0 <= HH <= 59; 0 <= SS <= 59
## excel            				erlang                         			                意义
## 2#17#0#0            				{2, 17, 0, 0}                			              每周二17点
## 0#0#0#0                          {0, 0, 0, 0}                						  无此阶段
## 8#18#0#0 						{8, 0, 0, 0} 										  每天18点
def to_daily_act_date_erl(str):
	str = str.replace(" ", "")
	date_arr = strip_split(str, "-")
	if len(date_arr) != 3:
		exit("*** error! to_daily_act_date_erl {0}".format(str))
	date_list = []	
	for date in date_arr:
		arr = strip_split(date, "#")
		if len(arr) == 4:
			weekday = int(arr[0])
			if weekday >= 0 and weekday <= 8:
				date_list.append("{{{0}, {1}, {2}, {3}}}".format(arr[0], arr[1], arr[2], arr[3]))
			else:
				exit("*** error! to_daily_act_date_erl {0}".format(arr))
		else:
			exit("*** error! to_daily_act_date_erl {0}".format(arr))
	return "#daily_activity_time{{pre_weektime = {0}, open_weektime = {1}, stop_weektime = {2}}}".format(date_list[0], date_list[1], date_list[2])

def to_daily_act_date_xml(str):
	# 客户端没有解析的需求
	return str

def to_daily_act_date_lua(str):
	str = str.replace(" ", "")
	date_arr = strip_split(str, "-")
	if len(date_arr) != 3:
		exit("*** error! to_daily_act_date_lua {0}".format(str))
	date_list = []	
	for date in date_arr:
		arr = strip_split(date, "#")
		if len(arr) == 4:
			weekday = int(arr[0])
			if weekday >= 0 and weekday <= 8:
				date_list.append("{{{0}, {1}, {2}, {3}}}".format(arr[0], arr[1], arr[2], arr[3]))
			else:
				exit("*** error! to_daily_act_date_lua {0}".format(arr))
		else:
			exit("*** error! to_daily_act_date_lua {0}".format(arr))
	return "daily_activity_time{{pre_weektime = {0}, open_weektime = {1}, stop_weektime = {2}}}".format(date_list[0], date_list[1], date_list[2])


## 返回获取所有Id列表的erlang函数
def make_all_ids_fun(fun, desc, ids):
	return """
%% -------------------------------------------------------------------
%% @doc """ + desc + """\n-spec """ + fun + """() -> [integer()].
%% -------------------------------------------------------------------\n""" + fun + "() -> [" + (",".join(ids)) + "].\n\n"


### 扩展其它type ####
## 每个type需给出详细格式说明:
## excel :
## erlang:
## xml:
## lua:


### 游戏相关辅助函数 ##############################################
## 注意保持和游戏一致 !!
## 定义了就不要改动   !!
## 
## 为了防止不一致, 转换脚本里如果用到的游戏宏定义, 应同时生成对应的静态检查erlang代码 !!
##

# 静态检查 VIRTUAL_ITEM_ID_XXX
def static_check_VIRTUAL_ITEM_ID_XXX():
	return """
-compile({nowarn_unused_function, {static_check_VIRTUAL_ITEM_ID_XXX, 0}}).
static_check_VIRTUAL_ITEM_ID_XXX() ->
	?UNSTD_STATIC_CHECK(?VIRTUAL_ITEM_ID_GOLD =:= 1),
	?UNSTD_STATIC_CHECK(?VIRTUAL_ITEM_ID_COIN =:= 2),
	?UNSTD_STATIC_CHECK(?VIRTUAL_ITEM_ID_EXP =:= 3),
	?UNSTD_STATIC_CHECK(?VIRTUAL_ITEM_ID_BODY =:= 4),
	?UNSTD_STATIC_CHECK(?VIRTUAL_ITEM_ID_COUNT =:= 5),
	?UNSTD_STATIC_CHECK(?VIRTUAL_ITEM_ID_UNIQUE_ITEM =:= 6),
	?UNSTD_STATIC_CHECK(?VIRTUAL_ITEM_ID_EXP_POOL =:= 7),
	?UNSTD_STATIC_CHECK(?VIRTUAL_ITEM_ID_MAX =:= 8),
	ok.
"""

# 虚拟物品id -> is_bind
# is_bind 对虚拟物品实际无意义
def get_virtual_item_bind(label):
	if label == "gold":
		return 0
	else:
		return 1

#-------------------------------
# d代号与ATTR宏对应字典
attr_dict = {
	 1 	: "?ATTR_PHYSIC"
	,2  : "?ATTR_STRENGTH"
	,3  : "?ATTR_BRAINS"
	,4  : "?ATTR_LIFE"
	,5  : "?ATTR_DMG"
	,6  : "?ATTR_DEFENCE"
	,7  : "?ATTR_DEFENCE_MP"
	,8  : "?ATTR_HIT"
	,9  : "?ATTR_EVASION"
	,10 : "?ATTR_CRIT"
	,11 : "?ATTR_TENACITY"
	,12 : "?ATTR_ASPD"
	,13 : "?ATTR_SPEED"
	,14 : "?ATTR_MP_MAX"
}

# 由代号得到属性宏名字
def get_attr_name(code):
	if attr_dict.get(code) != None:
		return attr_dict[code]
	else:
		exit("*** error! get_attr_name {0}".format(code))

# 得到 ATTR_XXX 宏对应的值
def get_ATTR_XXX_value(name):
	for (k,v) in attr_dict.iteritems():
		if v == name:
			return k
	exit("*** error! get_ATTR_XXX_value {0}".format(name))

# 静态检查 ATTR_XXX
def static_check_ATTR_XXX():
	return """
-compile({nowarn_unused_function, {static_check_ATTR_XXX, 0}}).
static_check_ATTR_XXX() ->
	?UNSTD_STATIC_CHECK(?ATTR_PHYSIC =:= 1),
	?UNSTD_STATIC_CHECK(?ATTR_STRENGTH =:= 2),
	?UNSTD_STATIC_CHECK(?ATTR_BRAINS =:= 3),
	?UNSTD_STATIC_CHECK(?ATTR_LIFE =:= 4),
	?UNSTD_STATIC_CHECK(?ATTR_DMG =:= 5),
	?UNSTD_STATIC_CHECK(?ATTR_DEFENCE =:= 6),
	?UNSTD_STATIC_CHECK(?ATTR_DEFENCE_MP =:= 7),
	?UNSTD_STATIC_CHECK(?ATTR_HIT =:= 8),
	?UNSTD_STATIC_CHECK(?ATTR_EVASION =:= 9),
	?UNSTD_STATIC_CHECK(?ATTR_CRIT =:= 10),
	?UNSTD_STATIC_CHECK(?ATTR_TENACITY =:= 11),
	?UNSTD_STATIC_CHECK(?ATTR_ASPD =:= 12),
	?UNSTD_STATIC_CHECK(?ATTR_SPEED =:= 13),
	?UNSTD_STATIC_CHECK(?ATTR_HP_MAX =:= 14),
	?UNSTD_STATIC_CHECK(?ATTR_MAX =:= 15),
	ok.
"""

#-------------------------------

#-------------------------------
# 序号与条件标签对应字典
conditon_dict = {
	 1 	: "lev"
	,2  : "coin"
	,3  : "get_coin"
	,4  : "get_item"
	,5  : "use_item"
	,6  : "kill_npc"
	,7  : "vip"
	,8  : "get_task"
	,9  : "get_task_type"
	,10 : "finish_task"
	,11 : "finish_task_type"
	,12 : "buy_item_store"
	,13 : "buy_item_shop"
	,14 : "make_friend"
	,15 : "has_pet"
	,16 : "reach_achieve"
	,17 : "reach_ach_points"
	,18 : "pass_dungeon"
	,19 : "on_daily_rank"
	,20 : "pass_turn"
	,21 : "pet_lev"
	,22 : "role_skill_num"
	,23 : "matrix_pet_num"
	,24 : "do_arena_num"
	,25 : "do_trial_num"
	,26 : "do_explore_num"
	,27 : "hunt_lev"
	,28 : "eqm_stren_num"
	,29 : "bejeweled_num"
	,30 : "escort_num"
	,31 : "open_ui_num"
	,32 : "pet_evolve_num"
	,33 : "wanted_num"
	,34 : "eqm_upgrate_num"
    ,35 : "body"
    ,36 : "hunt_up_num"
    ,37 : "pet_up_num"
    ,38 : "guild_donate"
    ,39 : "chest_buy_num"
    ,40 : "exp_train_get_num"
    ,41 : "enter_dungeon_num"
    ,42 : "enter_map"
}

# 由 conditon 代号得到其标签
def get_condition_label(code):
	if conditon_dict.get(code) != None:
		return conditon_dict[code]
	else:
		exit("*** error! get_conditon_label {0}".format(code))

def get_condition_code(label):
	for (k,v) in conditon_dict.iteritems():
		if v == label:
			return k
	exit("*** error! get_condition_code {0}".format(label))

# 静态检查 condition
def static_check_condition():
	return """
-compile({nowarn_unused_function, {static_check_condition, 0}}).
static_check_condition() ->
	?RECORD_FIELDS_CHECK(cond_trigger_mapping, 17),
	ok.
"""

#-------------------------------
# 商城type 商城区域
shop_type_dict = {
	1 : "?SHOP_TYPE_COMMON",
}

shop_zone_dict = {
	1 : "?SHOP_ZONE_GOLD",
	2 : "?SHOP_ZONE_COIN",
}

def get_shop_type_macro(type_str):
	shop_type = to_int(type_str)
	for (k,v) in shop_type_dict.iteritems():
		if k == shop_type:
			return v
	exit("*** error! get_shop_type_macro {0}".format(shop_type))

def get_shop_zone_macro(zone_str):
	zone = to_int(zone_str)
	for (k,v) in shop_zone_dict.iteritems():
		if k == zone:
			return v
	exit("*** error! get_shop_zone_macro {0}".format(zone))

def static_check_shop_type_zone():
	return """
%% -------------------------------------------------------------------
%% 静态检查 商店类型 商店区域
%% -------------------------------------------------------------------
-compile({nowarn_unused_function, {static_check_shop_type_zone, 0}}).
static_check_shop_type_zone() ->
	?UNSTD_STATIC_CHECK(1 == ?SHOP_TYPE_COMMON),
	?UNSTD_STATIC_CHECK(2 == ?SHOP_TYPE_MAX),

	?UNSTD_STATIC_CHECK(1 == ?SHOP_ZONE_GOLD),
	?UNSTD_STATIC_CHECK(2 == ?SHOP_ZONE_COIN),
	?UNSTD_STATIC_CHECK(3 == ?SHOP_ZONE_MAX),
	ok.
"""

#-------------------------------
# 装备类型宏转ID
def eqm_type_macro2id(eqm_type_macro):
	if eqm_type_macro == "?ITEM_TYPE_CLAW":  ## 利爪
		return 1
	elif eqm_type_macro == "?ITEM_TYPE_COLLARS":  ## 项圈
		return 2
	elif eqm_type_macro == "?ITEM_TYPE_SHOE":  ## 兽鞋
		return 4
	elif eqm_type_macro == "?ITEM_TYPE_JEWELRY":  ## 吊饰
		return 5
	elif eqm_type_macro == "?ITEM_TYPE_HELMET":  ## 头盔
		return 6
	elif eqm_type_macro == "?ITEM_TYPE_ARMOR":  ## 护甲
		return 7
	else:
		exit("*** error! eqm_type = %s"%eqm_type_macro)

#-------------------------------
# 物品品质宏转ID
def item_quality_macro2id(item_quality_macro):
	if item_quality_macro == "?QUALITY_TYPE_WHITE":  ## 白
		return 0
	elif item_quality_macro == "?QUALITY_TYPE_GREEN":  ## 绿
		return 1
	elif item_quality_macro == "?QUALITY_TYPE_BLUE":  ## 蓝
		return 2    
	elif item_quality_macro == "?QUALITY_TYPE_PURPLE":  ## 紫
		return 3
	else:
		exit("*** error! item_quality = %s"%item_quality_macro)

def static_check_quality_type():
	return """
-compile({nowarn_unused_function, {static_check_quality_type, 0}}).
static_check_quality_type() ->
	?UNSTD_STATIC_CHECK(0 == ?QUALITY_TYPE_WHITE),
	?UNSTD_STATIC_CHECK(1 == ?QUALITY_TYPE_GREEN),
	?UNSTD_STATIC_CHECK(2 == ?QUALITY_TYPE_BLUE),
	?UNSTD_STATIC_CHECK(3 == ?QUALITY_TYPE_PURPLE),
	?UNSTD_STATIC_CHECK(4 == ?QUALITY_TYPE_MAX),
	ok.
"""	

