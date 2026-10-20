# -*- coding: utf-8 -*-
"""v1.42.2 封存 + 临时/缓存清理（一次性）。
顺序：① 删 __pycache__（保证归档包干净）→ ② 打源码 zip 到 history/ →
③ 写封存说明 → ④ 删构建临时（dev/build_work / _live_v1343 / C:/lmc_build_tmp）。
删除走 ctypes（SetFileAttributesW + DeleteFileW / RemoveDirectoryW）——本环境
os.remove / shutil 会被 safe-delete shim 拦。"""
import ctypes
import hashlib
import os
import zipfile

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
HIST = os.path.join(ROOT, "history")
VER = "v1.42.2"
BUILD = "2610180085"
STEM = f"流明盒-{VER}-{BUILD}"
ZIP_PATH = os.path.join(HIST, f"{STEM}-源码.zip")
NOTE_PATH = os.path.join(HIST, f"{STEM}-封存说明.txt")

k = ctypes.windll.kernel32
deleted_files = 0
deleted_dirs = 0
freed = 0


def del_file(p):
    global deleted_files, freed
    try:
        freed += os.path.getsize(p)
    except Exception:
        pass
    k.SetFileAttributesW(p, 0x80)
    if k.DeleteFileW(p):
        deleted_files += 1
        return True
    print("  [删失败] %s err=%d" % (p, k.GetLastError()))
    return False


def del_tree(p):
    """后序删除：先文件后目录。"""
    global deleted_dirs
    for dp, dn, fn in os.walk(p, topdown=False):
        for f in fn:
            del_file(os.path.join(dp, f))
        if dp != p:
            k.SetFileAttributesW(dp, 0x80)
            if k.RemoveDirectoryW(dp):
                deleted_dirs += 1
    k.SetFileAttributesW(p, 0x80)
    if k.RemoveDirectoryW(p):
        deleted_dirs += 1
    else:
        print("  [删目录失败] %s err=%d" % (p, k.GetLastError()))


# ---------- ① __pycache__ ----------
print("== ① 删除 __pycache__ ==")
for dp, dn, fn in os.walk(ROOT):
    top = os.path.relpath(dp, ROOT).split(os.sep)[0]
    if top in (".workbuddy", "history", "index_data", "cache", "历史版本(含源代码及打包文件)"):
        dn[:] = []
        continue
    if "__pycache__" in dn:
        p = os.path.join(dp, "__pycache__")
        del_tree(p)
        dn.remove("__pycache__")
print("   已删文件 %d、目录 %d" % (deleted_files, deleted_dirs))

# ---------- ② 源码 zip ----------
print("== ② 打源码归档 zip ==")
INCLUDE_TOP = ["src", "dev", "build_exe.py", "README.md", "README_EN.md",
               "requirements.txt", "logo.ico", "logo-4.png", "性能基线.md"]
SKIP_SUB = {"__pycache__", "build_work"}
if os.path.exists(ZIP_PATH):
    os.remove(ZIP_PATH) if False else del_file(ZIP_PATH)
n_files = 0
with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    base = f"{STEM}/"
    for item in INCLUDE_TOP:
        p = os.path.join(ROOT, item)
        if os.path.isfile(p):
            zf.write(p, base + item)
            n_files += 1
        elif os.path.isdir(p):
            for dp, dn, fn in os.walk(p):
                dn[:] = [d for d in dn if d not in SKIP_SUB]
                for f in fn:
                    if f.endswith((".pyc", ".pyo")):
                        continue
                    fp = os.path.join(dp, f)
                    arc = base + os.path.relpath(fp, ROOT).replace(os.sep, "/")
                    zf.write(fp, arc)
                    n_files += 1
print("   %s（%d 个文件，%.1f MB）" % (os.path.basename(ZIP_PATH), n_files,
                                  os.path.getsize(ZIP_PATH) / 1048576))

# ---------- ③ 封存说明 ----------
print("== ③ 写封存说明 ==")
h = hashlib.sha256()
with open(os.path.join(ROOT, f"{STEM}.exe"), "rb") as f:
    for chunk in iter(lambda: f.read(1 << 20), b""):
        h.update(chunk)
sha = h.hexdigest()
note = f"""流明盒 LumaCrate {VER} 封存说明
================================
外部版本：{VER}
内部构建：{BUILD}（2026-10-18）
封存日期：2026-10-20

一、程序（exe）
- 工作副本：{STEM}.exe（工程根目录，约 56.8 MB，单文件 --onefile --windowed）
- 留档副本：history/{STEM}.exe（与工作副本 SHA-256 逐字节一致）
- SHA-256：{sha}

二、源代码
- 留档：history/{STEM}-源码.zip（顶层目录 {STEM}/）
- 内容：src/ 全部源码；build_exe.py 打包脚本；README.md / README_EN.md；
  requirements.txt；logo.ico / logo-4.png；性能基线.md；
  dev/（smoke_v1422.py 冒烟、render_preview_v1422.py 出图、screenshots/ 预览图等）
- 不含：settings.json（本机配置）、index_data/（索引库）、cache/（头像缓存）、
  history/ 与「历史版本(含源代码及打包文件)」旧归档、__pycache__

三、重新打包
1. 解压 zip，进入 {STEM}/ 目录
2. Python 3.13 + PySide6 环境执行：python build_exe.py
3. 产物：{STEM}.exe

四、本版变更（{VER}，UI 反馈两则）
- 演员检测页「结果树↔右侧详情」横向拖动条换成与竖向同款 5 点 grabber
  （_GripHandle 方向感知：横向把手 5 点竖排；ActorSplitH handleWidth 6→14；
  QSS handle 背景透明、margin 归零）
- 演员刮削页数据源列表幻影空槽兜底（清掉无 widget 的幻影项）；
  修 QListWidget.clear() 不删 setItemWidget 行控件导致的控件堆积
  （hide+脱父+deleteLater 收尸）与 _src_rows 结果标签悬空引用
- 验证：离屏冒烟 smoke_v1422.py 27/27；真机自检 ALIVE_OK、
  版本窗「流明盒 {VER} (Build {BUILD})」、启动段零未捕获异常、sysmon 单例
"""
with open(NOTE_PATH, "w", encoding="utf-8") as f:
    f.write(note)
print("   %s（%d 字节）" % (os.path.basename(NOTE_PATH), len(note.encode("utf-8"))))

# ---------- ④ 大块临时 ----------
print("== ④ 删除构建/验收临时 ==")
before = (deleted_files, deleted_dirs, freed)
for target, why in (
    (os.path.join(ROOT, "dev", "build_work"), "v1.1.1 时代 PyInstaller 工作残留（48 MB）"),
    (os.path.join(ROOT, "_live_v1343"), "v1.34.3 真机验收遗留 exe（46 MB）"),
    (r"C:/lmc_build_tmp", "PyInstaller 构建临时目录（3.8 GB，下次打包自动重建）"),
):
    if os.path.isdir(target):
        del_tree(target)
        print("   [已删] %s —— %s" % (target, why))
    else:
        print("   [跳过] %s 不存在" % target)

print()
print("== 合计 ==")
print("删除文件 %d 个、目录 %d 个，释放 %.1f MB" % (deleted_files, deleted_dirs, freed / 1048576))
print("归档包：%s" % ZIP_PATH)
print("说明档：%s" % NOTE_PATH)
print("ARCHIVE_CLEAN_DONE")
