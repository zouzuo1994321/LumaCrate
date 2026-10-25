# -*- coding: utf-8 -*-
"""通用封存脚本：按 version.py 当前版本，打「源码 zip + 封存说明」到 history/。

用法：
    python dev/_scratch/archive_version.py [--note "本版摘要"]
封存内容：src 全量 + build_exe.py + README×2 + requirements + logo×2 + 性能基线.md
        + docs/ + dev 全部 .py + dev/screenshots 当前版本前缀的预览图
        + dev/_scratch 当前版本相关探针。已存在同名 zip 时先删再建。
"""
import ctypes
import hashlib
import os
import re
import sys
import zipfile

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
import version as ver   # noqa: E402

STEM = f"{ver.APP_NAME}-{ver.VERSION}-{ver.BUILD}"
HIST = os.path.join(ROOT, "history")
ZIP = os.path.join(HIST, f"{STEM}-源码.zip")
NOTE = os.path.join(HIST, f"{STEM}-封存说明.txt")
DEV = os.path.join(ROOT, "dev")
k = ctypes.windll.kernel32

note_text = ""
if "--note" in sys.argv:
    note_text = sys.argv[sys.argv.index("--note") + 1]


def del_file(p):
    k.SetFileAttributesW(p, 0x80)
    return bool(k.DeleteFileW(p))


TOP_FILES = ["build_exe.py", "README.md", "README_EN.md", "requirements.txt",
             "logo.ico", "logo-4.png", "性能基线.md"]
# 当前版本预览图前缀：v1436 → v1436_
vtag = "v" + re.sub(r"\D", "", ver.VERSION)          # v1436
try:
    minor_tag = "v%d%d%d%d_" % (ver.PRODUCT_GENERATION, ver.MAJOR_ITER,
                               ver.MINOR_ITER // 10, ver.MINOR_ITER % 10)
except Exception:
    minor_tag = vtag + "_"

if os.path.exists(ZIP):
    print("删除旧包:", del_file(ZIP))

n, raw = 0, 0
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    base = STEM + "/"

    def add(fp, arc):
        global n, raw
        zf.write(fp, base + arc)
        n += 1
        raw += os.path.getsize(fp)

    for dp, dn, fn in os.walk(os.path.join(ROOT, "src")):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            if f.endswith((".pyc", ".pyo")):
                continue
            fp = os.path.join(dp, f)
            add(fp, os.path.relpath(fp, ROOT).replace(os.sep, "/"))
    for f in TOP_FILES:
        add(os.path.join(ROOT, f), f)
    for sub in ("docs",):
        d = os.path.join(ROOT, sub)
        if os.path.isdir(d):
            for dp, dn, fn in os.walk(d):
                for f in fn:
                    fp = os.path.join(dp, f)
                    add(fp, os.path.relpath(fp, ROOT).replace(os.sep, "/"))
    for dp, dn, fn in os.walk(DEV):
        dn[:] = [d for d in dn if d not in ("__pycache__", "build_work")]
        for f in fn:
            if f.endswith(".py"):
                fp = os.path.join(dp, f)
                add(fp, os.path.relpath(fp, ROOT).replace(os.sep, "/"))
    ss = os.path.join(DEV, "screenshots")
    if os.path.isdir(ss):
        for f in sorted(os.listdir(ss)):
            if f.startswith((minor_tag, vtag + "_")) and f.endswith(".png"):
                add(os.path.join(ss, f), "dev/screenshots/" + f)
print("zip: %d 个文件，原始 %.1f MB，压缩后 %.1f MB"
      % (n, raw / 1048576, os.path.getsize(ZIP) / 1048576))

h = hashlib.sha256()
with open(os.path.join(ROOT, STEM + ".exe"), "rb") as f:
    for c in iter(lambda: f.read(1 << 20), b""):
        h.update(c)
sha = h.hexdigest()

note = f"""流明盒 LumaCrate {ver.VERSION} 封存说明
================================
外部版本：{ver.VERSION}
内部构建：{ver.BUILD}
封存日期：{__import__('datetime').date.today().isoformat()}

一、程序（exe）
- 工作副本：{STEM}.exe（工程根目录）
- 留档副本：history/{STEM}.exe（逐字节一致）
- SHA-256：{sha}

二、源代码
- 留档：history/{STEM}-源码.zip（顶层目录 {STEM}/）
- 内容：src 全量、build_exe.py、README.md/README_EN.md、requirements.txt、
  logo.ico/logo-4.png、性能基线.md、docs/（审计报告与计划）、dev/ 全部脚本、
  dev/screenshots 中本版预览图、dev/_scratch 探针
- 不含：settings.json、index_data/、cache/、history/ 与旧归档、__pycache__

三、重新打包
1. 解压 zip，进入 {STEM}/ 目录
2. Python 3.13 + PySide6 环境执行：python build_exe.py
3. 产物：{STEM}.exe

四、本版摘要
{note_text or '（未填写）'}
"""
with open(NOTE, "w", encoding="utf-8") as f:
    f.write(note)
print("note:", os.path.basename(NOTE))
print("ARCHIVE_OK", ver.VERSION, ver.BUILD, sha[:16])
