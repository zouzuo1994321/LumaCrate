# -*- coding: utf-8 -*-
"""追加 v1.46.8 工作日志，并给 MEMORY.md 加一条长期规则。

用脚本文件而不是 `python -c "..."`：上次长文本里的反引号被 bash 当命令替换吃掉了。
"""
import io

DAY = r"E:/【01】自研软件/【26-19】本地影视中心/.workbuddy/memory/2026-10-23.md"
MEM = r"E:/【01】自研软件/【26-19】本地影视中心/.workbuddy/memory/MEMORY.md"

NOTE = r'''

## v1.46.8（反馈：右下角进度条「载入 / 缓存中」的朱红高亮没了）

### 排查顺序（很值得复用）
1. **先量像素证明 QSS 没问题**：离屏三态 = 空闲 0 / 不确定态 220 / 45% 时 192 →
   样式、`unpolish/polish`、属性选择器全对 → 问题不在渲染层。
2. **再换 QStyle 复验**：Fusion / Windows / windowsvista 三档都一样亮
   （216/220/192）→ 排除「真机原生样式不吃 QSS chunk」这个常见猜测。
3. **再打调用时间线**：monkeypatch `set_busy` + `LazyGrid._render` 记录时间戳，
   发现 `set_busy(-1,'缓存中')` 确实调用了，但 25ms 后 `busy` 仍是 False。
4. **最后上真机 PrintWindow 抓窗口**，才看到决定性证据：底部写着
   「正在载入列表… 16200 / 48708」，而进度条是**空槽** —— 那行字来自
   `ui_home.HomeListView.self.status`，**与 set_busy 完全无关**。

### 四层根因（缺一条都还是看不见）
1. **太快**：虚拟网格建一屏卡（40~54 张）只要几毫秒，`set_busy(-1)` 紧跟
   `set_busy(None)` → 朱红还没绘制就回落。
2. **画不出来**（最隐蔽）：`_render()` 是**同步查库**（真库 4.8 万片实测 1.3s），
   期间事件循环被卡死；而 `update()` 只是往队列里排一个重绘请求 → 高亮根本没机会
   画到屏幕上，等事件循环回来时已经 `set_busy(None)` 了。**必须 `repaint()`**。
3. **滚动全程没上报**：`_render()` 只有「首屏首次建卡」才 `set_busy(-1)`，
   之后滚到哪都不报 → 滚动换页时进度条永远空槽。
4. **最大的载入根本没接**：首页读 4.8 万条 + 分 244 批填表，`ui_home` 只更新自己的
   `self.status`，从没调 `set_busy`。真机上最常见的「正在载入」就是这一条。

### 修法
- `BUSY_MIN_MS = 420`：点亮不足 420ms 就收到空闲 → 用定时器推迟回落（仍有 1.5s 兜底）。
- 点亮改走 **`bar.repaint()`**（同步绘制，110×6 微秒级），保证朱红在阻塞前落到屏幕。
- `_render()` 在**查库之前**就 `set_busy(-1, "载入中"/"缓存中")`；`_pump` 每批都报。
- `ui_home`：`_load()` 查询前 `_busy(-1,"载入列表")`，`_apply_view()` 报 0，
  `_fill_chunk()` 每批报 `int(filled*100/n)`，填完/视图作废/空列表都 `_busy(None)`。
  延迟 `import main_window` 避免循环依赖。
- tooltip 显示「载入中 / 缓存中 / 45%」等具体状态。

### 真机验证（**新增可复用工具**）
- `dev/_scratch/grab_window.py`：`PrintWindow(hwnd, hdc, 2)` 抓窗口自身 + 朱红像素统计。
  用法 `--tag v1.46.8 --exe <exe> --click 93,313`；`93,313` 是离屏实测的侧栏
  「全部」按钮中心（窗口 1920×1080 下），点它才会触发 4.8 万条载入。
- 结果：状态栏高亮像素 **120 → 288 逐帧递增**（进度条随百分比填充），
  真机截图 `dev/screenshots/v1468_real_busybar.png`。
- 注意：用户把高亮色设成了 `#e2659a`（粉色），所以真机看到的是**粉色**不是朱红
  —— 这是正确跟随主题，别误判成缺陷。
- **教训**：`PIL.ImageGrab` + `SetForegroundWindow` 不可信 —— 非前台进程无法强制
  置前，窗口被别的程序遮挡时抓到的是**别人的界面**（第一次真机验证就抓到一张
  「任务」管理窗口，白欢喜一场）。抓窗口一律 `PrintWindow`。

### 验证与交付
- 冒烟 **235/235**（⑲ 段 12 条：三态像素 / 快闪 30ms 仍亮 / 700ms 回落 /
  busy 属性回落 / BUSY_MIN_MS / 滚动上报「缓存中」/ 源码级 repaint /
  首页上报进度 / ui_home 接入）；单测 **28/28**。
- 预览图：`v1468_busybar_states.png`（离屏四态）、`v1468_real_busybar.png`（真机）。
- 真机：ALIVE_OK / VER_OK（流明盒 v1.46.8 (Build 2610230110)）/ 未捕获异常 0 /
  sysmon 单例 1 / 零残留。
- 封存 `history/流明盒-v1.46.8-2610230110-*`（428 文件，SHA-256 前 16 位 `f64344918ebb5a9c`）。
'''

MEM_ADD = r'''
## 状态栏进度条 / 「耗时操作可见性」（v1.46.8 定的，通用）
- 状态栏 `_busy_bar`（`QProgressBar#BusyBar`）由全局 `set_busy(-1 | 0..100 | None)` 驱动。
  **任何超过 ~200ms 的载入都必须上报**，否则用户只会看到空槽。
- **`update()` 不够，必须 `repaint()`**：`update()` 只是排队，事件循环一旦被同步查询
  卡住，重绘永远轮不到 → 高亮「设了但没画出来」。`repaint()` 同步绘制，
  110×6 的控件代价可忽略。**点亮一律放在耗时操作之前**。
- `BUSY_MIN_MS = 420`：点亮不足 420ms 就收到空闲时用定时器推迟回落，
  否则「建一屏卡只要几毫秒」的高亮等于没亮过。1.5s 无更新兜底不变。
- 已接入上报的载入点：`LazyGrid._render`（首屏「载入中」/ 滚动换窗「缓存中」）、
  `_pump`（每批）、`ui_home`（`_load` 不确定态 + `_fill_chunk` 逐批 0~100「载入列表」）。
  **新增任何「读库 → 填 UI」的路径，都要接一条 set_busy。**
- 真机像素验证工具：`dev/_scratch/grab_window.py`（`PrintWindow` 抓窗口自身，
  `--tag v1.46.8 --click 93,313` 点侧栏「全部」触发载入）。
  **不要用 `PIL.ImageGrab` 截屏**：`SetForegroundWindow` 对非前台进程无效，
  窗口被遮挡时抓到的是别人的界面。
- 用户高亮色可在「设置 → 外观」改（当前 `#e2659a` 粉色），进度条跟随主题色，
  看到粉色不要当成缺陷。
'''

with io.open(DAY, "a", encoding="utf-8") as fh:
    fh.write(NOTE)

with io.open(MEM, "r", encoding="utf-8") as fh:
    mem = fh.read()
if "状态栏进度条 / 「耗时操作可见性」" not in mem:
    with io.open(MEM, "a", encoding="utf-8") as fh:
        fh.write(MEM_ADD)
    print("MEMORY.md 已追加")
else:
    print("MEMORY.md 已有该段，跳过")

print("day len", len(io.open(DAY, encoding="utf-8").read()))
print("mem len", len(io.open(MEM, encoding="utf-8").read()))
