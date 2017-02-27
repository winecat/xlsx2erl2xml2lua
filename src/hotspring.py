#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
温泉数据配置转换生成器

@author: King
@deprecated: 2012-4-18
'''
# 导入要用到的函数
from libs.utils import load_excel, load_sheel, module_header, module_hrl_header, gen_erl, gen_hrl, format_float, dict_var

# Erlang模块名称定义，也是文件名
module_name = "data_hotspring"
module_hrl_name = "hotspring"

 # 导入**.xlsx，文件统一放置在docs目录
work_book = load_excel(ur"温泉数据")

# Erlang模块头说明，主要说明该文件作用，会自动添加-module(module_name).
# module_header函数隐藏了第三个参数，是指作者，因此也可以module_header(ur"礼包数据", module_name, "King")
data = module_header(ur"温泉基础数据配置", module_name)
data_hrl = module_hrl_header(ur"温泉基础数据配置头文件", module_hrl_name)

# Erlang需要导出的函数接口, append与erlang的++也点类似，用于python的list操作
data.append("""-include("common.hrl").
-export([get_award/2, get_act_award/1, get_hotspring_xy/2]).
""")

# 读取领取条件Sheel的内容，第一行标题行会省略不读，但一定要定义标题，方便理解
@load_sheel(work_book, ur"基础配置")
def hrl(content=0):
    type_name, type_value, memo = content
    if type_name == "hotspring_open_time":
        hotspring_open_times = []
        for value in type_value.split(","):
            hotspring_open_time = []
            for v in value.split("-"):
                h, m = v.split(":")
                hotspring_open_time.append("{{{0},{1},0}}".format(int(h), int(m)))
            hotspring_open_times.append("{{{0}}}".format(",".join(hotspring_open_time)))
        type_value = "[{0}]".format(",".join(hotspring_open_times))
    else:
        type_value = format_float(type_value)

    if type_name.endswith("tips"):
        return ["-define({0}, <<\"{1}\">>). %% {2}".format(type_name, type_value, memo)]
    return ["-define({0}, {1}). %% {2}".format(type_name, type_value, memo)]

data_hrl.extend(hrl())
data_hrl.append("""
-define(hotspring_mark_close, 0). %% 关闭温泉
-define(hotspring_mark_open, 1).  %% 开启倒计时
-define(hotspring_mark_enter, 2). %% 进入温泉

-define(hotspring_enable, true).

-define(hotspring_cycle, 60000). %% 60秒加一次灵力
-define(hotspring_steps, 30).  %% 30分钟/30次
-define(hotspring_act_cd_time, util:unixtime() + ?hotspring_act_cd).

-define(hotspring_type_vip, 1).
-define(hotspring_type_normal, 2).

-define(get_scene_xy(SpringType),
    case SpringType of
        ?hotspring_type_vip -> ?hotspring_vip_scene_xy;
        ?hotspring_type_normal -> ?hotspring_normal_scene_xy;
        _ -> ?hotspring_normal_scene_xy
    end).

-define(in_hotspring_scene(SceneId), SceneId =:= ?hotspring_scene).

%% 互动类型
-define(hotspring_back_rubbing, 1). %% 搓背
-define(hotspring_back_rubbing_name, "搓背"). %% 搓背
-define(hotspring_back_rubbing_tips, "~s拿起毛巾和香皂，为几天没洗澡的~s搓背。").
-define(hotspring_back_rubbing_tips2, "~s拿起毛巾和香皂，为几天没洗澡的~s搓背，获得 ~s。").

-define(hotspring_massage, 2). %% 按摩
-define(hotspring_massage_name, "按摩"). %% 按摩
-define(hotspring_massage_tips, "~s抬起手，温柔地为~s捶背揉肩。").
-define(hotspring_massage_tips2, "~s抬起手，温柔地为~s捶背揉肩，获得 ~s。").

-define(hotspring_paddle, 3). %%戏水
-define(hotspring_paddle_name, "戏水"). %%戏水
-define(hotspring_paddle_tips, "~s咧开嘴傻笑，和~s玩了水仗。").
-define(hotspring_paddle_tips2, "~s咧开嘴傻笑，和~s玩了水仗，获得 ~s。").

-define(hotspring_act_exp_tips(Exp), util:color(exp, util:message("~p 经验", [Exp]))).
-define(hotspring_act_spt_tips(Spt), util:color(spt, util:message("~p 灵力", [Spt]))).

-define(in_hotspring_action(ActionType), ActionType =:= ?hotspring_back_rubbing orelse ActionType =:= ?hotspring_massage orelse ActionType =:= ?hotspring_paddle).

%% 温泉状态
-record(hotspring, {acc = 0}).

%% 互动数据结构
-record(hotspring_act, {
    interactive_time = 0 %% 互动时间
    ,back_rubbing_times  = 0 %% 搓背次数
    ,massage_times = 0 %% 按摩次数
    ,paddle_times = 0 %% 戏水次数
    ,interactive_expire = 0 %% 互动的冷却时间
}).
""")

data.append("%% @spec get_award(RS, SpringType) -> {Exp, Spt, Attainment}")
data.append("%% %doc 获取奖励经验和灵力")
data.append("""get_award(RS, SpringType) ->
    {ExpAddition, SptAddition, AttainmentAddition} = get_award_vip(SpringType, RS#role_state.vip_type),
    {BaseExp, BaseSpt, BaseAttainment} = get_base_award(?role_attr(RS).lev),
    {round(BaseExp * ExpAddition), round(BaseSpt * SptAddition), round(BaseAttainment * AttainmentAddition)}.
""")

data.append("%% @spec get_award_vip(SpringType, VipType) -> {ExpAddition, SptAddition, AttainmentAddition}")
data.append("%% %doc 获取奖励经验和灵力")

vars_list = ['spring_type', 'spring_name', 'vip_type', 'exp_addition', 'spt_addition', 'attainment_addition']

@load_sheel(work_book, ur"奖励加成", vars_list)
def award(content=0):
    global vip_type
    for index, var in dict_var.iteritems():
        globals()[var] = format_float(content[index])
    
    if vip_type == 'None':
        vip_type = '_'
    return ["get_award_vip({0}, {1}) -> {{{2}, {3}, {4}}}; %% {5}".format(spring_type, vip_type, exp_addition, spt_addition, attainment_addition, spring_name)]

data.extend(award())
data.append("get_award_vip(_, _) -> {0, 0, 0}.")

data.append("\n%% @spec get_base_award(Lev) -> {Exp, Spt, Attainment}")
data.append("%% %doc 获取基本奖励经验和灵力")

@load_sheel(work_book, ur"奖励基数")
def base_award(content=0):
    lev, exp, spt, attainment = format_float(content[0]), format_float(content[1]), format_float(content[2]), format_float(content[3])
    return ["get_base_award({0}) -> {{{1}, {2}, {3}}};".format(lev, exp, spt, attainment)]

data.extend(base_award())
data.append("get_base_award(_) -> {0, 0, 0}.")

data.append("\n%% @spec get_act_award(Lev) -> Exp")
data.append("%% %doc 获取互动奖励经验和灵力")

@load_sheel(work_book, ur"互动奖励")
def base_award(content=0):
    lev, exp = format_float(content[0]), format_float(content[1])
    return ["get_act_award({0}) -> {1};".format(lev, exp)]

data.extend(base_award())
data.append("get_act_award(_) -> 0.")


@load_sheel(work_book, ur"进vip池坐标")
def get_hotspring_xy1(content=0):
    num, xy = int(content[0]), (content[1])
    return ["get_hotspring_xy(1,{0}) -> [{1}];".format(num, xy)]

@load_sheel(work_book, ur"进普通池坐标")
def get_hotspring_xy2(content=0):
    num, xy = int(content[0]), (content[1])
    return ["get_hotspring_xy(2,{0}) -> [{1}];".format(num, xy)]

data.append("\n%% @spec get_hotspring_xy(Type,Num) -> Xy")
data.append("%% %doc 进入温泉随机坐标")
data.append("%%进vip池坐标")
data.extend(get_hotspring_xy1())
data.append("%%进普通池坐标")
data.extend(get_hotspring_xy2())
data.append("get_hotspring_xy(_,_) -> [0,0].")



# 生成Erlang文件，如果要生成头文件，请使用gen_hrl，参数与gen_erl一致
gen_erl(module_name, data)
gen_hrl(module_hrl_name, data_hrl)
