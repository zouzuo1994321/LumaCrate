# -*- coding: utf-8 -*-
"""把 exe 里 `_scan_begin` / `_on_scan_tick` 的字节码反汇编出来，和源码对照。

目的：证明「exe 里到底有没有 setVisible / _on_busy」—— 排除「打包进了旧代码」。
"""
import dis
import types

EXE = r"E:\【01】自研软件\【26-19】本地影视中心\流明盒-v1.46.13-2610290115.exe"

from PyInstaller.archive.readers import CArchiveReader

arc = CArchiveReader(EXE)
z = arc.open_embedded_archive("PYZ.pyz")
code = z.extract("main_window")


def find(c, name, depth=0):
    if depth > 8:
        return None
    for k in c.co_consts:
        if isinstance(k, types.CodeType):
            if k.co_name == name:
                return k
            r = find(k, name, depth + 1)
            if r:
                return r
    return None


for fn in ("_scan_begin", "_on_scan_tick", "_scan_own_busy"):
    c = find(code, fn)
    print("=" * 20, fn, "->", "FOUND" if c else "MISSING")
    if c:
        print("  names:", [n for n in c.co_names if n in
                           ("setVisible", "setText", "setToolTip", "_set_scan_text",
                            "_on_busy", "_scan_own_busy", "elidedText", "fontMetrics")])
        print("  consts:", [k for k in c.co_consts if isinstance(k, str)][:8])
        print("  varnames:", c.co_varnames)
print("DONE")
