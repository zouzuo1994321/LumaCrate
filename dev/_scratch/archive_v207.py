# -*- coding: utf-8 -*-
"""v2.0.7 封存：调通用 `archive_version.py`，带上本版摘要。

为什么要包一层：`--note` 的正文里有 `>` `<` 等字符，直接在 bash 里传会被当成
重定向；写成脚本再 runpy 最稳。
"""
import runpy
import sys

NOTE = (
    "① 「别名改成白色」：演员详情页那行别名原为链接蓝 #66a9ff，改为近白 #fafafa"
    "（与正文同一个白，不再暗示「可以点」）。"
    "② 「详细页底部职务名翻成中文，并按 女>男>未知、演员>导演 排序」："
    "新增 ui_hero.role_label() 把 Actor/Director/女優 等统一成「演员/导演」，"
    "认得出来的才翻、认不出来的原样显示；新增 ui_hero.cast_sort_key() 按"
    "「性别档 → 职务档 → person_order」重排显示顺序 —— **只改显示，不动库里的 "
    "person_order**，所以反复进出详情页不会把数据洗坏。"
    "③ 「首页列表每一列：左边漏斗（筛选）、右边三角（正/倒序）」："
    "表头换成自绘的 FilterHeaderView（不叠 QToolButton —— 表头会随列宽拖动 / "
    "换位 / 横向滚动一直动，叠按钮必然错位），点击分区判漏斗/三角/其它三档；"
    "点漏斗在列正下方弹 ColumnFilterPopup（Qt.Popup，点外面或 Esc 自动关），"
    "按列类型自动三形态：文本列给输入框、数值列给「= ≥ ≤」+数值、"
    "枚举列（收藏/类型）给一排胶囊；点三角排序、再点翻转。"
    "筛选条件落盘 settings.home_filters、排序落盘 home_sort；"
    "已筛选那列的漏斗变成主题色实心，一眼看出「这列在筛」。"
    "冒烟 694/694（新增 ㉝ 段 43 条）；真机 30/30（LIVE_V207_ALL_OK）。"
)

sys.argv = ["archive_version.py", "--note", NOTE]
runpy.run_path(r"E:/【01】自研软件/【26-19】本地影视中心/dev/_scratch/archive_version.py",
               run_name="__main__")
