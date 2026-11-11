# -*- coding: utf-8 -*-
"""v2.0.12 README 同步（避免 bash 把反引号当命令替换）。"""
import io

P = r"E:\【01】自研软件\【26-19】本地影视中心\README.md"
BT = chr(96)          # 反引号，绕开 shell
s = io.open(P, encoding="utf-8").read()
orig = s

# --- 1) 下载名 ---
s = s.replace(BT + "流明盒-v2.0.11-2611100132.exe" + BT,
              BT + "流明盒-v2.0.12-2611100133.exe" + BT)

# --- 2) 「怎么用」新增一条 ---
anchor = ("- **输入框首字不再缩进一大截（v2.0.11）**")
new_bullet = (
    "- **圆角外面那圈黑框没了（v2.0.12）**：右键菜单、替换 / 添加演职员的弹层、表头筛选面板、"
    "悬停缩略图 —— 这些地方原本在**圆角以外**露出一圈**纯黑**。根因不是圆角画错，是**圆角外没人画**："
    "它们都是**顶层窗口**，而窗口表面永远不透明，样式表只把底色涂进圆角路径里，路径外就露出窗口本身（黑）。"
    "现在这些浮层改成**窗口本身半透明**（`WA_TranslucentBackground` + 去掉系统投影），圆角外真的透出后面的界面；"
    "带系统标题栏的普通对话框（列设置 / 关于 / 删除媒体库…）则去掉圆角 —— 原生标题栏本来就是方的，"
    "硬加圆角只会把客户区四角削成黑洞。表格左上/右上那个「深色三角」也一并修了：表头首末列补了 13px 顶部圆角，"
    "不再压在表格的圆角缺口上。\n"
)
i = s.find(anchor)
assert i > 0, "找不到「怎么用」锚点"
# 插到「输入框首字」那条之前（同一列表）
s = s[:i] + new_bullet + s[i:]

# --- 3) 迭代记录新增一行（表格第一行数据之前） ---
tbl_hdr = "| v2.0.11 | 2611100132 | 2026-11-10 |"
row = (
    "| v2.0.12 | 2611100133 | 2026-11-10 | **修复** | v2.0.11 交付后的 **1 条反馈**"
    "（用户附 3 张截图：右键菜单、替换弹层、表头单元格）：「**不少圆角外有黑框**尝试修复」。"
    "**根因不是圆角画错，而是圆角外没有任何东西去画** —— `QMenu` / 无边框 `QDialog` 都是**顶层窗口**，"
    "窗口表面（backing store）永远不透明，`QStyleSheetStyle` 只把 background 画在**圆角路径里面**，"
    "路径外露出窗口表面 = 纯黑；同一条根因还让 `rgba(24,24,27,232)` 这种半透明底被压在黑底上合成，"
    "整体比设计值更暗。① 新增 **`src/uiwin.py`**：`bare(w)` = `FramelessWindowHint | NoDropShadowWindowHint | "
    "WA_TranslucentBackground | autoFillBackground(False)`，`menu(parent)` 建菜单。三条都不能少 —— "
    "**必须在窗口创建之前设**（Show 之后再设 Qt 不重建平台窗口，等于没设，所以菜单全部改走 `uiwin.menu()`，"
    "9 处 `QMenu(self)` 全部替换，`addMenu` 出来的「扫描」子菜单再套一次 `bare()`）；"
    "`NoDropShadowWindowHint` 也不能省，半透明窗口 + 系统投影时 DWM 按**矩形**外围画阴影，"
    "圆角外又是一圈更深的方形晕。② 发现并绕开一个坑：**半透明顶层窗口的根控件不画 QSS 底色** —— "
    "矩阵实测（QFrame/QDialog × 类型选择器/objectName 选择器 × 开关 WA_StyledBackground）全部 `grab()` 整块 "
    "`alpha=0`，只有子控件在画。于是圆角与底色改由**内层容器**承担：`PersonSearchDialog` 套 `#PSDBody`（10px）、"
    "`ColumnFilterPopup` 套 `#ColFilterBody`（8px）、`HoverPreview` 套 `#HoverCard`（16px），"
    "并去掉 `setAutoFillBackground(True)`（它按调色板把整个矩形刷一遍，圆角又变黑角）。"
    "③ 全局 `QDialog{border-radius:16px}` **删掉** —— 带原生标题栏的对话框窗口是方形，圆角只把客户区四角"
    "削成黑洞（列设置 / 关于 / 删除媒体库 / 文件夹扫描 / 清理 等 9 个对话框全部中招）。"
    "④ 表格的 14px 圆角被**方形半透明表头**压出深色楔形（缺口里只剩「页面色 + 4.5% 白」）："
    "`QHeaderView::section:first/:last` 补 **13px** 顶部圆角（表头在 1px 边框内侧，13+1=14 与表格同心）。"
    "验收：离屏冒烟 783 → **812/812**（新增 ㊳ 段 29 条：`uiwin.menu()` 四个窗口属性、源码级「无裸 QMenu」、"
    "三浮层的内层容器与圆角值、**grab 像素**「角 alpha=0 / 内部 alpha=255」、全局 QDialog 无 radius、"
    "表头首末列 13px、表头缺口像素 = 页面底色）；取证探针 `probe_v2012_ui`（属性 + 源码）与 "
    "`probe_v2012_bg`（三浮层底色）全绿；`probe_v2012_live` 开**真窗口**用 `QScreen.grabWindow(0)` 抓"
    "合成后的像素 —— 亮蓝底上，修复前圆角外是 `#000000`，修复后是蓝底/边框抗锯齿混色（菜单 `#1f7ae0`、"
    "弹层 `#1f79de`、筛选浮层 `#2e5686`），原生对话框客户区四角 `#18181b`（面板色，不再是黑）。"
    "注：`QToolTip` 同为「顶层 + 圆角」，但 Qt 不给 show 之前的时机，实测它渲染成方形深色块"
    "（黑角与自身底色几乎无差、肉眼看不出来），本轮不动。 |\n"
)
i = s.find(tbl_hdr)
assert i > 0, "找不到迭代记录锚点"
s = s[:i] + row + s[i:]

# --- 4) 冒烟表：当前分数与 ㊳ 说明 ---
s = s.replace("（最新 783/783，v2.0.11）", "（最新 812/812，v2.0.12）")
old38_tail = "含 ㊲ 段（v2.0.11："
i = s.find(old38_tail)
assert i > 0, "找不到冒烟表锚点"
s = s.replace(old38_tail,
              "含 ㊳ 段（v2.0.12：`uiwin.menu()` 的四个窗口属性、"
              "四个文件源码级「没有裸 `QMenu(`」、三个浮层的内层容器与圆角值、"
              "grab 像素「角 alpha=0 / 内部 alpha=255」、全局 `QDialog` 无 radius、"
              "表头首末列 13px 圆角、表头缺口像素 = 页面底色）；含 ㊲ 段（v2.0.11：", 1)

io.open(P, "w", encoding="utf-8", newline="").write(s)
print("changed bytes:", len(s) - len(orig))
print("v2.0.12 出现次数:", s.count("v2.0.12"))
print("812/812:", s.count("812/812"), "| ㊳:", s.count("㊳"))
print("旧下载名残留:", s.count("v2.0.11-2611100132.exe"))
