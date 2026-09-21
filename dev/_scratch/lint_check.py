# -*- coding: utf-8 -*-
"""编译 + 换行（LF/CRLF）体检：Edit/Write 工具在本项目会把 LF 转 CRLF，必须逐次确认。"""
import os
import py_compile

ROOT = r"Z:/【01】自研软件/【26-19】本地影视中心"
SRC = os.path.join(ROOT, "src")
CRLF = b"\r\n"

bad = []
n = 0
for f in sorted(os.listdir(SRC)):
    p = os.path.join(SRC, f)
    if not os.path.isfile(p):
        continue
    raw = open(p, "rb").read()
    if f.endswith((".py", ".qss")):
        n += 1
        c = raw.count(CRLF)
        if c:
            bad.append("CRLF %s = %d" % (f, c))
    if f.endswith(".py"):
        try:
            py_compile.compile(p, doraise=True)
        except Exception as e:
            bad.append("COMPILE %s: %s" % (f, str(e)[:200]))

print("检查文件数：", n)
print("问题：", bad if bad else "无")

print()
for f in ("config.py", "style.qss", "main_window.py", "recommend.py", "ui_home.py",
          "nfo_parser.py", "database.py", "tagopt.py", "ui_settings.py"):
    raw = open(os.path.join(SRC, f), "rb").read()
    print("%-16s %8d B  CRLF=%d" % (f, len(raw), raw.count(CRLF)))
