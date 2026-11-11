# -*- coding: utf-8 -*-
"""顶层浮层的圆角收尾（v2.0.12）。

## 问题：圆角外那一圈黑框

QSS 给 `QMenu` / `QDialog` 这类东西写了 `border-radius`，但**它们是顶层窗口**，
而窗口表面（backing store）永远是不透明的。`QStyleSheetStyle` 只把 background
画在圆角路径**里面**，路径外面**没有任何东西去绘制** → 露出窗口表面本身，
在 Windows 上就是**纯黑**。用户看到的就是「圆角外有黑框」。

同一条根因还干掉半透明：`rgba(24, 24, 27, 232)` 会被压在黑底上合成，
整体比设计值暗一大截（这也是「弹层比设计稿黑」的老问题）。

## 修法

给这些窗口开 `WA_TranslucentBackground`：圆角外真的透明，rgba 底也真的叠在
「后面那块界面」上。

三个硬前提（缺一条就白改）：

1. **必须在窗口创建之前设**。Show 之后再 `setAttribute(WA_TranslucentBackground)`
   Qt 不会重建平台窗口，等于没设 → 所以菜单统一走 `uiwin.menu()` 建，
   别在别处直接 `QMenu(parent)`。
2. **必须加 `FramelessWindowHint`**：有系统边框时，边框/标题区仍是实心，圆角被它压住。
3. **必须加 `NoDropShadowWindowHint`**：半透明窗口 + 系统投影时，DWM 按**矩形**外围
   画阴影 → 圆角外又出现一圈更深的方形晕，用户照样会说「有黑框」。
   代价是没有系统投影；界面语言本来就靠 1px 亮描边分隔，观感没差。
4. 顺手关掉 `autoFillBackground`：它会拿调色板把**整个矩形**刷一遍，圆角又变回黑角。

## 不是浮层就别用

主窗（`MainWindow`）**不要**开：它整窗不透明（磨砂是应用内自绘的，见 veil.py），
一旦开成半透明，DWM 会把窗口当图层合成，滚动时反而露黑背。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu


def bare(w):
    """把顶层浮层改成「圆角外真透明」。返回入参，方便链式写。"""
    w.setWindowFlags(w.windowFlags() | Qt.FramelessWindowHint
                     | Qt.NoDropShadowWindowHint)
    w.setAttribute(Qt.WA_TranslucentBackground, True)
    w.setAutoFillBackground(False)
    return w


def menu(parent=None):
    """建一个「圆角外透明」的右键菜单。子菜单要再套一次 `bare()`。"""
    return bare(QMenu(parent))
