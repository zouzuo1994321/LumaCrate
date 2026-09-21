# -*- coding: utf-8 -*-
"""把 v1.25.0 真机验收踩到的两个新坑补进 local-media-center-release 技能。

坑 1（最贵）：点「执行写入」这类破坏性按钮会弹**模态确认框**，主窗与工具窗都被置
disabled，之后所有 `PostMessage` 点击全部静默失效 —— 脚本不报错、日志一路写
「抓取成功」，但截图全是同一张、目标文件一个字节没变。
坑 2：工具窗口导航**插入**新页后，缓存的点击坐标整体下移一格 → 点错页；
即使同一页，加了新控件也会让页内按钮坐标漂移（实测「检测本地 AI 引擎」
从 (230,182) 漂到 (254,212)）。
"""
import os

SKILL = r"C:\Users\zouzu\.workbuddy\skills\local-media-center-release\SKILL.md"

ADD = '''
## 十六、模态确认框会「静默废掉」整段真机验收（v1.25.0，改 `live_verify.py` 前必读）

### 16.1 症状极具误导性：日志全绿、文件没变

v1.25.0 给「标签优化」页加了「执行写入」，而它是个破坏性动作，代码里先弹
`QMessageBox` 确认。真机验收点下去之后：

- 日志每一步都写 `[抓取] 1000x900 -> …png True`，**一个警告都没有**；
- 截图 38 与 37 **逐字节相同**（抓的是被压在确认框下面的工具窗自己的像素）；
- 后续「演员刮削 / 重复检测 / 开始检测」三下点击**全部无效**，截图全是同一页；
- 目标 nfo **一个字节没变**、没有 `.bak` 文件。

### 16.2 判据：用 `IsWindowEnabled` 抓「有没有模态」

模态框会把**父窗口置灰**，这是最直接的证据（`dev/_scratch/probe_modal.py` 那类枚举即可）：

```
hwnd=2230542 pid=20344 enabled=False 1016x939 class='Qt6112QWindowIcon' title='工具'
hwnd=461234  pid=20344 enabled=False 1936x1119 class='Qt6112QWindowIcon' title='本地影视中心  v1.25.0 (Build 2609210034)'
```

**两个窗口 `enabled=False` = 有模态框挂着。** 只看截图看不出来（确认框是独立窗口，
`grabWindow(dlg)` 走 PrintWindow 会把遮挡物渲染掉），必须查这个属性。

### 16.3 修法（已落在 `dev/live_verify.py`）

- `find_modal(exe_name, extra, exclude=(), timeout=8)`：在本进程里找**除主窗/工具窗外**的可见顶层窗口。
  **门槛必须放低到 `w>150 and h>80`** —— 复用 `find_window_ex` 的 `w>300 and h>200` 会漏掉
  ~420x180 的确认框，于是「找不到」被误当成「没有确认框」。
- 先 `grab` 一张确认框存 `38a_*_confirm.png` 留证，再 `press_ok(mb)` 按回车——
  Qt 的默认按钮就是「确定」。**别用鼠标点**：按钮在框内的位置随文案长度变，写死坐标容易失手。
- 通用规则：**凡是被点击的按钮是「破坏性/需要二次确认」的动作，点完都要走一遍
  `find_modal` → 截图 → `press_ok`**，否则它后面那一整段验收都是废的。

### 16.4 附带：缓存坐标的两类漂移

- **导航插页整体下移**：v1.25.0 在工具导航里插入「标签优化」（在「智能推荐」之后），
  `lmc_ui_coords.json` 里「服务管理 / 重复检测 / 数据与日志」的 y 全部 +39。
  **只要 `ui_settings.ORDER` 变了，就必须重跑 `dev/_scratch/ui_coords.py`**，否则点错页
  （而「重复检测」那一步还会真等 85 秒，白等一轮）。
- **同页新增控件导致页内漂移**：「检测本地 AI 引擎」从 `(230,182)` 漂到 `(254,212)`，
  只因为该页上方多了「调用模型」输入框那一行。所以**坐标文件不是「测一次管很久」的东西**，
  改过设置页布局就重跑一次，成本约 10 秒。
- `ui_coords.py` 里取控件**一律按属性名**（`dlg.btn_to_scan`）而不是按文案匹配
  （`"扫描并预览" in b.text()`）—— 文案改一个字就静默失配，按属性取至少会
  `AttributeError` 或打印 `[警告] … 不存在`。

'''

with open(SKILL, encoding="utf-8", newline="") as f:
    s = f.read()
if "## 十六、模态确认框会" in s:
    print("[跳过] 第十六节已存在")
else:
    if not s.endswith("\n"):
        s += "\n"
    s += ADD.lstrip("\n")
    with open(SKILL, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    print("[OK] 已追加第十六节，技能现", len(s), "字符")

b = open(SKILL, "rb").read()
print("CRLF =", b.count(b"\r\n"))
