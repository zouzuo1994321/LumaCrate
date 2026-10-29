# -*- coding: utf-8 -*-
"""修 README 里被 shell 反引号吃掉的那段（改用脚本文件写，避免 bash 做命令替换）。"""
import re

P = r"E:\【01】自研软件\【26-19】本地影视中心\README.md"
s = open(P, encoding="utf-8").read()

new = (
    "（最新 346/346，v1.46.13）。含 ㉔ 段：扫描（`scanner.on_item` 逐条回报且含「已存在」、"
    "`ScanWorker` 按传入顺序逐条扫、`quiet=True` 后台扫描不上报）、底部扫描状态"
    "（文字三态 / 进度条定量 25% / 扫描独占与归还 BusyBar）、以及一批**静默失效高危点**的"
    "结构断言（`_on_scan_live` 认得出套了一层容器的网格、空库建页可升级为窗口化、"
    "`_wall_page` 传 `count_fn`、`_page` 挂 `title_lbl`、首页自适应节流、QSS 不多出第二条进度条）。"
    "更早的 ㉓ 段"
)

# 定位被啃坏的片段：从「（最新 346/346」到「更早的 ㉓ 段」
pat = re.compile(r"（最新 346/346.*?更早的 ㉓ 段", re.S)
m = pat.search(s)
print("matched:", bool(m))
if m:
    s = s[:m.start()] + new + s[m.end():]
    open(P, "w", encoding="utf-8").write(s)
    print("fixed")
else:
    print("NOT_FOUND")
