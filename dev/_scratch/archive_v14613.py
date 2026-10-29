# -*- coding: utf-8 -*-
"""v1.46.13 封存：给 archive_version.py 传本版摘要。"""
import runpy
import sys

NOTE = (
    "三条反馈，全部围绕扫描（用户附了三张图）。"
    "①「扫描新添加和修改的」要按媒体库路径列表自上而下：核实 `ScanWorker.run()` 本来就是 "
    "`for i, p in enumerate(roots, 1)` 串行、`update_library` 也保持 ↑↓ 顺序 —— 顺序没错，"
    "错的是**界面不说自己在扫第几个**，且旧 `tick` 的分子是「进度消息条数」（只在 was_new 时发）、"
    "分母却是全部视频文件 → 4.8 万片里新增 10 个永远是 0%，看着像没动。改法：每条路径开始强推一次 "
    "tick，文案带「路径 i/n · 目录名」；分子改由新加的 `scanner.on_item` 提供（**每个处理过的文件都算**），"
    "与分母同口径。"
    "② 实时显示新扫出来的文件：查出三处真缺陷 —— (a) `_on_scan_live` 只刷首页，影片墙完全不刷，"
    "而且从 `scroll.widget()` 上取 `lazy_grid` 恒为 None（`_page()` 中间还套了一层 host），"
    "必须 `findChildren(LazyGrid)`；(b) 首页 `live_refresh()` 同步读全库却固定 1.2s 触发 → "
    "改成按实测耗时 ×3 自适应（1.2~8s）；(c) 空库建页时 `_virtual = bool(virtual) and total > 0` "
    "→ False，而「新建库 → 立刻扫描」正是最常见路径 → `live_reload()` 第一行就 return，"
    "新增 `_upgrade_virtual(total)` 就地升级。墙侧另加 2.0s 节流 + 清 `_win_key` 强制重取。"
    "③ 底部显示扫描情况 + 在进度条上显示进度：进度条**不另起一条** —— 用户标红的就是原来那条 "
    "BusyBar，扫描期间由扫描**独占**它（`_scan_own_busy()` 临时 disconnect BusyBus，用 "
    "`_busy_bus_on` 成对记账，否则重复 disconnect 会抛 libpyside RuntimeWarning），"
    "否则影片墙「缓存中」的 set_busy(-1) 会和扫描百分比互相抢；`total=0` 走循环块、有分母转定量。"
    "文字是一行常驻 `QLabel#ScanNote`（520px 内、超了 ElideMiddle），平时隐藏。"
    "验证：冒烟 346/346（新增 ㉔ 段 25 条，含 on_item 新旧条目/路径序号透传/quiet 不上报/"
    "底部三态/扫描独占 BusyBar/结束后归还，以及一批 inspect.getsource 结构断言）；"
    "离屏探针 46/46；真机源码态 3 路径 ×1500 项：order=[1/3,2/3,3/3]、墙 1→1906→3787→4500、"
    "进度条 4%→95%；打包 exe 真机（真实鼠标点右键菜单）3×3000=9000 项："
    "扫描中一帧读到「扫描 演示库 · 路径 2/3 · path-2 · 3000/9000 · 新增 3000」+ 朱红 33%、"
    "墙同时已铺满「演示库（2077 部）」、侧栏库名右侧进度环在转；扫描完成弹框「电影 9000 部」；"
    "两次运行 rc=0、app.log 零未捕获异常。"
    "踩坑备忘：打包后抓「扫描中」的图，扫描太快（360 个小文件 <1s）会直接进入「扫描完成」模态框、"
    "主窗口冻结在最后一帧 —— 会误判成「底部什么都不显示」；必须造足够大的库（9000 项 ≈ 15s）"
    "才能抓到扫描中的帧。"
)

sys.argv = ["archive_version.py", "--note", NOTE]
runpy.run_path(r"E:/【01】自研软件/【26-19】本地影视中心/dev/_scratch/archive_version.py",
               run_name="__main__")
