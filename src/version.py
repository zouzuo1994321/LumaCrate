# -*- coding: utf-8 -*-
"""
版本号规范
==========
内部版本号(BUILD): YYMMDDNNNN
    例如 2609170001 表示 2026-09-17 的第 0001 次构建。
    每次打包自增末四位计数（跨日连续自增，不按日归零；日期段取当天日期）。

外部版本号(VERSION): v1.1.1
    第一位 = 产品代(大重构才变)
    第二位 = 大版本迭代(功能性新增)
    第三位 = 小版本迭代(bug 修复 / 小改进)
"""

# 外部版本号 v1.28.0
PRODUCT_GENERATION = 1   # 产品代
MAJOR_ITER = 28          # 大版本迭代 -> 第二位（侧栏「数据统计」/「实时状态」可在
                         #                「设置 → 外观」里开关；侧栏 logo 点开项目主页；
                         #                底部状态栏点开作者 GitHub 主页）
MINOR_ITER = 0           # 小版本迭代 -> 第三位

VERSION = f"v{PRODUCT_GENERATION}.{MAJOR_ITER}.{MINOR_ITER}"

# 内部构建号 YYMMDDNNNN (2026-09-21 第三十八次构建，末四位按「每次打包自增」连续计数)
# 0034：v1.25.0 六条反馈（标签优化页为新增模块）
# 0035：0034 打包后从 app.log 捡到 QTimer 已析构崩溃（v1.24.1 起就存在），修复后重打
# 0036：v1.26.0 四条反馈（开关轨道不跟高亮色 / 底部开源声明 / 副标题裁字 + 性能基准）
# 0037：v1.27.0 两条反馈（更名「流明盒 / LumaCrate」+ Slogan 进启动画面与「关于」/
#       侧栏新增「实时状态」面板；真机缺陷：采集线程改进程级单例）
# 0038：v1.28.0 三条反馈（侧栏「数据统计」/「实时状态」可在「外观」里开关 /
#       侧栏 logo 点开项目主页 / 底部状态栏点开作者主页）
BUILD_DATE = "260921"
BUILD_SEQ = "0038"
BUILD = f"{BUILD_DATE}{BUILD_SEQ}"

# 完整标识
# v1.27.0：品牌更名 —— 中文「流明盒」/ 英文「LumaCrate」。
# （原名 本地影视中心 / LocalMediaCenter。命名思路：流明 = lumen，光的计量单位；
#   盒 = crate，收纳箱。把收藏的每一道光都收进一个盒子里。）
APP_NAME = "流明盒"
APP_NAME_EN = "LumaCrate"
# v1.27.0：Slogan —— 启动画面与「关于」对话框共用，改这里两处一起变。
SLOGAN_CN = "所有流明 · 尽收盒中"
SLOGAN_EN = "Every lumen, in one crate."
COPYRIGHT = "Copyright  2026 肆月Aperture"
LICENSE_NOTE = "本软件为开源软件，没有授权禁止用于商业用途。"
FULL_VERSION = f"{VERSION} (Build {BUILD})"

# v1.28.0（反馈 2 / 3）：两个外链的真源 —— 侧栏品牌区与底部状态栏分别指向它们。
# 改这里两处一起变（与 APP_NAME 同理，只留一个真源）。
REPO_URL = "https://github.com/zouzuo1994321/LumaCrate"
AUTHOR_URL = "https://github.com/zouzuo1994321"
