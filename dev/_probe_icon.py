# -*- coding: utf-8 -*-
"""v1.23.0 exe 图标资源探针：解析 PE 的 RT_GROUP_ICON / RT_ICON，确认 --icon 真的写进了 PE。

坑：MAKEINTRESOURCE(i) 是「指针值 == i」，不是「指向 i 的指针」。
    ctypes.cast(pointer(WORD(i)), LPCWSTR) 传进去的是堆地址（>65535），
    IS_INTRESOURCE 判定失败 → FindResourceW 永远找不到。要用 c_wchar_p(i)。
"""
import ctypes
import os
import sys

from ctypes import wintypes

RT_ICON = 3
RT_GROUP_ICON = 14
LOAD_LIBRARY_AS_IMAGE_RESOURCE = 0x00000020
k32 = ctypes.windll.kernel32


def mi(i):
    """MAKEINTRESOURCE：指针值等于 id 本身。"""
    return ctypes.c_wchar_p(i)


def probe(exe):
    h = k32.LoadLibraryExW(exe, None, LOAD_LIBRARY_AS_IMAGE_RESOURCE)
    if not h:
        print("LoadLibraryExW 失败", ctypes.get_last_error())
        return 1
    try:
        grp = []
        for rid in range(1, 64):
            hr = k32.FindResourceW(h, mi(rid), RT_GROUP_ICON)
            if hr:
                grp.append((rid, k32.SizeofResource(h, hr)))
        icons = []
        for rid in range(1, 128):
            hr = k32.FindResourceW(h, mi(rid), RT_ICON)
            if hr:
                icons.append((rid, k32.SizeofResource(h, hr)))
        print("文件:", os.path.basename(exe))
        print("大小: %.1f MB" % (os.path.getsize(exe) / 1048576.0))
        print("RT_GROUP_ICON:", grp)
        print("RT_ICON 个数:", len(icons))
        for rid, sz in icons:
            print("   id=%-3d %d bytes" % (rid, sz))
        ok = bool(grp) and bool(icons)
        print("判定:", "ICON EMBEDDED ✅" if ok else "NO ICON ❌")
        return 0 if ok else 2
    finally:
        k32.FreeLibrary(h)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else \
        r"Z:/【01】自研软件/【26-19】本地影视中心/本地影视中心-v1.23.0-2609200030.exe"
    sys.exit(probe(path))
