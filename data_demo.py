#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
配置转换生成器

@author: dzw
@deprecated: 2013-10-16
'''
# 导入要用到的函数
from libs.utils import load_excel, load_sheel, module_header, gen_erl, gen_xml
from libs.convert import convert_excel_sheet, fill_template_str, smart_replace 
from collections import defaultdict
from collections import OrderedDict
import os.path

###### 通用定义 ##########################################
excel_file = ur"demo"					# excel 文件名
excel_sheet = ur"sheet1"				# excel 页名

erl_file = "demo_data"					# erlang 文件名
erl_include = "common.hrl gamedef.hrl"	# include文件名

xml_file = "demo"						# xml文件名

###### 全局变量 ##########################################
 
## erlang
erldata = module_header(excel_sheet, erl_file, "ForGame_JY", excel_file + ".xlsx", os.path.basename(__file__))
erldata.append("""
-export([
	all/0, 
	get_data/1
	]).
""")
if erl_include != "":
	erldata.append("")
	arr = erl_include.split(" ")
	for i in range(0, len(arr)):
		erldata.append("-include(\"" + arr[i] + "\").")
erldata.append("""
%% @doc 根据ID取XX数据
%% -spec get_one(Id :: integer()) -> {ok, #demo_record{}} | {false, Reason ::any()}.
""")
		
## xml
xmldata = []

## 其它
idlist = []	 # id列表 用于拼凑all()函数
getone_list = []

########## 模板定义 ##########################
erl_one_template = """
get_one(_Id = $$id$$) ->
	{
		ok,
		#demo_record
		{
			id = $$id$$,
			lev = $$lev$$,
			fac = $$fac$$,
			is_good = $$is_good$$,
			name = $$name$$,
			extra = $$extra$$,
			value = $$value$$,
			reward = $$reward$$,
			cost = $$cost$$,
			adds = $$adds$$,
			cond = $$cond$$
		}
	};
"""	

xml_one_template="""
<pet>
	<id>$$id$$</id>
	<lev>$$lev$$</lev>
	<fac>$$fac$$</fac>
	<is_good>$$is_good$$</is_good>
	<name>$$name$$<name>
	<extra>$$extra$$</extra>
	<value>$$value$$</value>
	<reward>$$reward$$</reward>
	<cost>$$cost$$</cost>
	<adds>$$adds$$</adds>
	<cond>$$cond$$</cond>
</pet>
"""

########## 一个sheet扫描开始 ##################
@convert_excel_sheet(excel_file, excel_sheet)
def ConvertOneLine(ED, XD):
	# ED: erlang dict (name->value)
	# XD: xml dict (name->value)
	global erl_data
	global xml_data
	global idlist
	global getone_list
	
	getone_list.append(fill_template_str(erl_one_template, ED))
	idlist.append(ED["id"])
	
	xmldata.append(fill_template_str(xml_one_template, XD))
	return[]
	
########## 一个sheet扫描完成 ##################

## 拼凑erlang文件内容
getone_list.append("""
get_one(_) ->
	{false, <<"Not_Found">>}.
""")

allstr = "all() -> [\n"
for kk in range(0, len(idlist)):
	allstr += "\t"
	if (kk != 0 ):
		allstr += ","
	allstr += idlist[kk] + "\n"
allstr += "\t].\n"
erldata.append(allstr)

erldata.extend(getone_list)

## 拼凑xml文件内容

## 生成
gen_erl(erl_file, erldata)
gen_xml(xml_file, xmldata)


