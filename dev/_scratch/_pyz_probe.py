# -*- coding: utf-8 -*-
"""直接从 exe 的 PYZ 里解出 main_window 的 code object，确认打包进去的是哪一版。

一次性 exe 的 .pyc 不打到磁盘（PyInstaller 6 从内嵌 PYZ 直接加载），所以只能读归档。
"""
import os
import sys
import types

EXE = r"E:\【01】自研软件\【26-19】本地影视中心\流明盒-v1.46.13-2610290115.exe"

from PyInstaller.archive.readers import CArchiveReader

arc = CArchiveReader(EXE)
names = list(arc.toc.keys())
print("toc entries:", len(names))
pyzs = [n for n in names if n.lower().endswith(".pyz") or "PYZ" in n.upper()]
print("pyz:", pyzs)

pyz_name = pyzs[0]
z = arc.open_embedded_archive(pyz_name)
mods = list(z.toc.keys())
print("modules:", len(mods))
print("has main_window:", "main_window" in mods, "scanner:", "scanner" in mods)

code = z.extract("main_window")
print("code type:", type(code))


def all_strings(c, acc, depth=0):
    """函数名 / 变量名**不在** co_consts 里（在 co_name / co_varnames / co_names），
    只扫 co_consts 会误判「打包里没有这个函数」。"""
    if depth > 14:
        return
    acc.add(c.co_name)
    acc.update(c.co_varnames)
    acc.update(c.co_names)
    acc.update(k for k in c.co_consts if isinstance(k, str))
    for k in c.co_consts:
        if isinstance(k, types.CodeType):
            all_strings(k, acc, depth + 1)


acc = set()
all_strings(code, acc)
for pr in ("ScanNote", "_upgrade_virtual", "_scan_own_busy", "_live_next_at", "ScanBar",
           " · 共 ", "个路径", "正在统计文件数", "扫描新添加和修改的", "路径 i/n",
           "live_reload", "count_fn", "findChildren", "title_lbl"):
    print("  %-18s %s" % (pr, "<FOUND>" if pr in acc else "-"))
print("DONE")
