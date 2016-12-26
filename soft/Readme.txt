简要说明：
Excel转Erlang工具库，目前仅支持office 2007格式，是基于Python编写的一系列小工具，编写前可以参考gift.py的写法，里面要详细说明，请参考，谢谢。

生成器所需工具及库如下：
python 2.7
pywin32
setuptools 0.6c11
openpyxl 1.5.6
上面也是安装顺序，设置环境变量，然后安装文件时解压文件到安装目录C:\Python27\Lib\site-packages下，然后进入目录执行python setup.py install即可进行安装
然后，要解决一个编码问题，将以下代码
#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import sys
reload(sys)
sys.setdefaultencoding('utf-8') #IGNORE:E1101

import locale
locale.setlocale(locale.LC_ALL, "")
保存为sitecustomize.py，并放到C:\Python27\Lib\site-packages

				write in 2012.03.02 23:59:59 by King
