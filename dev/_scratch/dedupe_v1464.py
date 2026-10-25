# -*- coding: utf-8 -*-
"""去掉 v1.46.4 补丁被重复应用产生的重复块（保留第一份）。"""
import io
import ast


def dedupe(path, start_marker, end_marker):
    s = io.open(path, encoding="utf-8").read()
    n = s.count(start_marker)
    if n <= 1:
        return n
    first = s.find(start_marker)
    keep_end = s.find(end_marker, first)
    keep_end += len(end_marker)
    head, block, tail = s[:first], s[first:keep_end], s[keep_end:]
    # tail 里再出现的整块（含 start..end）删掉
    while True:
        i = tail.find(start_marker)
        if i < 0:
            break
        j = tail.find(end_marker, i)
        if j < 0:
            break
        tail = tail[:i] + tail[j + len(end_marker):]
    io.open(path, "w", encoding="utf-8", newline="\n").write(head + block + tail)
    new = io.open(path, encoding="utf-8").read()
    ast.parse(new)
    return new.count(start_marker)


MW = r"E:/【01】自研软件/【26-19】本地影视中心/src/main_window.py"
SM = r"E:/【01】自研软件/【26-19】本地影视中心/src/sysmon.py"

print("busy_bar blocks ->", dedupe(
    MW,
    "        # v1.46.4（反馈 1）：信息栏右侧**常驻**灰色进度条",
    "        self._busy_idle_timer.timeout.connect(lambda: self._on_busy(None, \"\"))"))
print("_on_busy defs ->", dedupe(
    MW,
    "    # ---------- 状态栏进度条（v1.46.4）----------",
    "    def busy(self, progress=None, text=\"\"):\n        set_busy(progress, text)\n"))
print("proc_mem defs ->", dedupe(
    SM,
    "    def proc_mem(self):",
    "        return None\n\n    def gpu(self):"))
