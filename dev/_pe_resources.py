# -*- coding: utf-8 -*-
"""纯 Python 解析 PE 资源目录，列出 exe 里的 RT_ICON / RT_GROUP_ICON。

不依赖 pefile / Windows API，用于确认 PyInstaller 的 --icon 是否真的写进了 PE。
用法：python _pe_resources.py <exe> [exe2 ...]
"""
import struct
import sys

RT_ICON = 3
RT_GROUP_ICON = 14
RT_VERSION = 16
NAMES = {RT_ICON: "RT_ICON", RT_GROUP_ICON: "RT_GROUP_ICON", RT_VERSION: "RT_VERSION"}


def _u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def _u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def parse(path):
    b = open(path, "rb").read()
    if b[:2] != b"MZ":
        return {"error": "not MZ"}
    e_lfanew = _u32(b, 0x3C)
    if b[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        return {"error": "not PE"}
    coff = e_lfanew + 4
    nsec = _u16(b, coff + 2)
    opt_size = _u16(b, coff + 16)
    opt = coff + 20
    magic = _u16(b, opt)
    dd_off = opt + (112 if magic == 0x20B else 96)   # PE32+ / PE32
    res_rva = _u32(b, dd_off + 8 * 2)                # 目录项 2 = Resource
    res_size = _u32(b, dd_off + 8 * 2 + 4)
    secs = []
    s = opt + opt_size
    for i in range(nsec):
        o = s + 40 * i
        name = b[o:o + 8].rstrip(b"\0").decode("latin1")
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", b, o + 8)
        secs.append((name, vaddr, vsize, rawptr, rawsize))

    def rva2off(rva):
        for _n, va, vs, rp, rs in secs:
            if va <= rva < va + max(vs, rs):
                return rp + (rva - va)
        return None

    out = {}
    if not res_rva:
        return {"error": "no resource directory"}

    # 坑：IMAGE_RESOURCE_DIRECTORY_ENTRY.OffsetToData 是**相对资源目录基址**的偏移，
    #     不是 RVA —— 当 RVA 用会让 walk 一步都走不动（notepad.exe 都解析出「资源目录为空」）。
    def walk(rel, depth, path_ids):
        off = rva2off(res_rva + rel)
        if off is None:
            return
        named = _u16(b, off + 12)
        ids = _u16(b, off + 14)
        for i in range(named + ids):
            e = off + 16 + 8 * i
            name_or_id = _u32(b, e)
            data_off = _u32(b, e + 4)
            is_dir = bool(data_off & 0x80000000)
            sub = data_off & 0x7FFFFFFF
            if is_dir:
                walk(sub, depth + 1, path_ids + [name_or_id])
            else:
                # 叶子：IMAGE_RESOURCE_DATA_ENTRY 也在相对基址处
                do = rva2off(res_rva + sub)
                if do is None:
                    continue
                _drva = _u32(b, do)
                size = _u32(b, do + 4)
                typ = path_ids[0]
                out.setdefault(typ, []).append((path_ids[1] if len(path_ids) > 1 else 0, size))

    walk(0, 0, [])
    return {"res_rva": res_rva, "res_size": res_size,
            "resources": {NAMES.get(k, k): v for k, v in out.items()}}


def main(paths):
    rc = 0
    for p in paths:
        r = parse(p)
        print("=" * 60)
        print("文件:", p.rsplit("/", 1)[-1])
        if "error" in r:
            print("  错误:", r["error"])
            rc = 1
            continue
        print("  资源目录 RVA=0x%X  size=%d" % (r["res_rva"], r["res_size"]))
        res = r["resources"]
        if not res:
            print("  资源目录为空")
        for k, v in sorted(res.items(), key=lambda kv: str(kv[0])):
            print("  %-14s 条目 %d 个 -> %s" % (k, len(v), v[:12]))
        gi = res.get("RT_GROUP_ICON")
        ic = res.get("RT_ICON")
        ok = bool(gi) and bool(ic)
        print("  图标判定:", "ICON EMBEDDED ✅（%d 组 / %d 档）" % (len(gi), len(ic))
              if ok else "NO ICON ❌")
        if not ok:
            rc = 2
    return rc


if __name__ == "__main__":
    args = sys.argv[1:] or [r"Z:/【01】自研软件/【26-19】本地影视中心/本地影视中心-v1.23.0-2609200030.exe"]
    sys.exit(main(args))
