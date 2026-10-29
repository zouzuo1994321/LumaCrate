# -*- coding: utf-8 -*-
"""v1.46.14 封存：给 archive_version.py 传本版摘要。"""
import runpy
import sys

NOTE = (
    "一条反馈（两张截图，都是详情页「我的评分」对话框）。"
    "①「窗口有点错位」：根因是数值框右侧的上下微调按钮区在本机暗色主题下**一个箭头都画不出来** —— "
    "style.qss 里 `QSpinBox/QDoubleSpinBox::up-button`/`::down-button` 的底色、左边框、圆角都生效了，"
    "但紧跟其后的 `::up-arrow/::down-arrow { color: … }` 这条**着色彩没起作用**（原注释写的是"
    "「原生箭头是单色位图，用 color 就能重新着色」，在本机实测不成立），于是整块按钮区只剩"
    "「一条竖分隔线 + 一块更深/更亮的竖条」，还把右侧圆角盖住 —— 看上去就像一块贴歪了的面板压在输入框上。"
    "评分只需要改小数点后一位（键盘 ↑↓ / 滚轮照常可调），所以直接 `setButtonSymbols(NoButtons)` "
    "把整块按钮区去掉，恢复成干净的圆角框（顺带不必再赌 QSS 的箭头渲染）。"
    "②「左右都留空、压缩窗口宽度」：实测 302×128 —— 数值框 `setFixedWidth(140)`、按钮行前面又塞了"
    "`addStretch(1)`，而窗口宽度实际是被最长那行提示文字（「范围 0–10，保留 1 位小数；「清除」可去掉已有评分。」）"
    "撑开的 → 数值框右边空 130px、按钮左边空 82px。改法：数值框改 `QSizePolicy.Expanding`（min 120）"
    "**撑满整行**；「清除」贴左（次要/清空动作与确认动作分开，防误点），中间 `addSpacing(24)` + stretch；"
    "提示文字收成「范围 0–10，保留 1 位小数。」，后半句挪进「清除」的 tooltip。改后 **240×128**（高多 1px 是"
    "真机渲染与离屏渲染的取整差），四个方向的死白全部消失。"
    "验证：冒烟 **360/360**（新增 ㉕ 段 14 条：`buttonSymbols==NoButtons`、`Expanding` 且 `maximumWidth` 不再是 140、"
    "数值框贴到右内边距（right==223/240）、`sizeHint().width()<=248`、清除贴左（x==16）、清除与取消间距 ≥20px、"
    "确定贴右、顺序正确、提示文字不再重复「清除」且 tooltip 有、`stepBy(1)` 仍 +0.1、确定回写 6.3、清除置空、"
    "空评分打开显示 0.0）；`dev/test_v119_logic.py` ALL PASS（反馈 100 的回写语义没回归）。"
    "真机 windows 平台渲染尺寸 240×129，出图 `v14614_rate_dialog.png` / `v14614_rate_body.png` / "
    "改前改后对比 `v14614_rate_before_after.png`。打包 exe `流明盒-v1.46.14-2610290116.exe`（56 MB）"
    "真机验收 7/7：标题 v1.46.14 (Build 2610290116) / 不 Hung / 可抓图 / rc=0 / app.log 零未捕获异常。"
    "备忘：本次只动 `ui_hero.RateDialog`（外加 import `QAbstractSpinBox`），没有碰扫描与状态栏那条链路。"
)

sys.argv = ["archive_version.py", "--note", NOTE]
runpy.run_path(r"E:/【01】自研软件/【26-19】本地影视中心/dev/_scratch/archive_version.py",
               run_name="__main__")
