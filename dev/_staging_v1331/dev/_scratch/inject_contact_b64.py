# -*- coding: utf-8 -*-
"""把 contact_b64.txt 的真实 logo 数据注入 main_window.py 的 _CONTACT_LOGO_B64。

就地替换占位 base64（那 3 行 iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB...），
直接操作文本以避免 Read/Edit 大段往返。
"""
import io
import re

SRC = r"C:\Users\zouzu\AppData\Local\Temp\lmc_v1310\src\main_window.py"
B64 = r"C:\Users\zouzu\AppData\Local\Temp\lmc_v1310\dev\_scratch\contact_b64.txt"

with io.open(B64, "r", encoding="utf-8") as f:
    blob = f.read().rstrip("\n")

# contact_b64.txt 顶格部分是 `        "kind": (` 起；直接整块粘进 dict
lines = blob.split("\n")
dict_lines = []
for ln in lines:
    if ln.startswith("#"):
        dict_lines.append("        " + ln.strip())
    else:
        dict_lines.append(ln)
dict_body = "\n".join(dict_lines)

with io.open(SRC, "r", encoding="utf-8") as f:
    src = f.read()

start_mark = "    _CONTACT_LOGO_B64 = {\n"
i = src.index(start_mark) + len(start_mark)
j = src.index("\n    }\n", i)
new = src[:i] + dict_body + src[j:]

with io.open(SRC, "w", encoding="utf-8") as f:
    f.write(new)

print("injected: dict body %d chars" % len(dict_body))
