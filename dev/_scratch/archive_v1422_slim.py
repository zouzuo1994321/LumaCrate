# -*- coding: utf-8 -*-
"""v1.42.2 归档包瘦身重建 + _scratch 冗余 exe 清理。
首版 zip 把 100+ MB 历史预览图和 _scratch 遗留物也打进去了（165 MB）——
「源代码留档」不需要这些。重建为：源码 + 打包脚本 + 文档 + dev 全部 .py
+ 本版预览图 4 张 + 本版 v1422 探针/自检脚本。"""
import ctypes
import os
import zipfile

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
HIST = os.path.join(ROOT, "history")
DEV = os.path.join(ROOT, "dev")
STEM = "流明盒-v1.42.2-2610180085"
ZIP_PATH = os.path.join(HIST, STEM + "-源码.zip")
NOTE_PATH = os.path.join(HIST, STEM + "-封存说明.txt")

k = ctypes.windll.kernel32


def del_file(p):
    k.SetFileAttributesW(p, 0x80)
    ok = k.DeleteFileW(p)
    print("   [%s] %s" % ("已删" if ok else "失败", p))
    return ok


# ---------- ① 删 _scratch 里的冗余旧 exe（v1.7.0，已两处归档） ----------
print("== ① 清理 _scratch 冗余 exe ==")
stray = os.path.join(DEV, "_scratch", "本地影视中心-v1.7.0-2609180007.exe")
if os.path.exists(stray):
    print("   大小 %.1f MB" % (os.path.getsize(stray) / 1048576))
    del_file(stray)
else:
    print("   (不存在)")

# ---------- ② 重建瘦身 zip ----------
print("== ② 重建源码归档 zip ==")
if os.path.exists(ZIP_PATH):
    del_file(ZIP_PATH)

TOP_FILES = ["build_exe.py", "README.md", "README_EN.md", "requirements.txt",
             "logo.ico", "logo-4.png", "性能基线.md"]
n = 0
total_raw = 0
with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    base = STEM + "/"

    def add(fp, arc):
        global n, total_raw
        zf.write(fp, base + arc)
        n += 1
        total_raw += os.path.getsize(fp)

    # src/ 全量
    for dp, dn, fn in os.walk(os.path.join(ROOT, "src")):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            if f.endswith((".pyc", ".pyo")):
                continue
            fp = os.path.join(dp, f)
            add(fp, os.path.relpath(fp, ROOT).replace(os.sep, "/"))
    # 根级文件
    for f in TOP_FILES:
        add(os.path.join(ROOT, f), f)
    # dev/ 全部 .py（开发脚本：冒烟/出图/真机验收/探针）
    for dp, dn, fn in os.walk(DEV):
        dn[:] = [d for d in dn if d not in ("__pycache__", "build_work")]
        for f in fn:
            if f.endswith(".py"):
                fp = os.path.join(dp, f)
                add(fp, os.path.relpath(fp, ROOT).replace(os.sep, "/"))
    # 本版预览图（dev/screenshots/v1422_*.png）
    ss = os.path.join(DEV, "screenshots")
    for f in sorted(os.listdir(ss)):
        if f.startswith("v1422_") and f.endswith(".png"):
            add(os.path.join(ss, f), "dev/screenshots/" + f)

print("   %s：%d 个文件，原始 %.1f MB，压缩后 %.1f MB"
      % (os.path.basename(ZIP_PATH), n, total_raw / 1048576,
         os.path.getsize(ZIP_PATH) / 1048576))

# ---------- ③ 重写封存说明 ----------
print("== ③ 重写封存说明 ==")
import hashlib
_h = hashlib.sha256()
with open(os.path.join(ROOT, STEM + ".exe"), "rb") as f:
    for chunk in iter(lambda: f.read(1 << 20), b""):
        _h.update(chunk)
sha = _h.hexdigest()
note = """流明盒 LumaCrate v1.42.2 封存说明
================================
外部版本：v1.42.2
内部构建：2610180085（2026-10-18）
封存日期：2026-10-20

一、程序（exe）
- 工作副本：流明盒-v1.42.2-2610180085.exe（工程根目录，约 56.8 MB，单文件 --onefile --windowed）
- 留档副本：history/流明盒-v1.42.2-2610180085.exe（与工作副本 SHA-256 逐字节一致）
- SHA-256：{sha}

二、源代码
- 留档：history/流明盒-v1.42.2-2610180085-源码.zip（顶层目录 流明盒-v1.42.2-2610180085/）
- 内容：
  · src/ 全部源码
  · build_exe.py 打包脚本
  · README.md / README_EN.md / requirements.txt
  · logo.ico / logo-4.png / 性能基线.md
  · dev/ 下全部 .py 开发脚本（各版冒烟 smoke_*.py、出图 render*/preview*、
    真机验收 live_verify*、探针 probe*）
  · dev/screenshots/v1422_*.png 本版预览图 4 张
  · dev/_scratch/ 下 v1422 系列探针与 exe 自检脚本（含 archive_v1422.py 本封存脚本）
- 不含：settings.json（本机配置）、index_data/（索引库）、cache/（头像缓存）、
  history/ 与「历史版本(含源代码及打包文件)」旧归档、__pycache__、
  历史预览图（保留在工作目录 dev/screenshots*/）

三、重新打包
1. 解压 zip，进入 流明盒-v1.42.2-2610180085/ 目录
2. Python 3.13 + PySide6 环境执行：python build_exe.py
3. 产物：流明盒-v1.42.2-2610180085.exe

四、本版变更（v1.42.2，UI 反馈两则）
- 演员检测页「结果树↔右侧详情」横向拖动条换成与竖向同款 5 点 grabber
  （_GripHandle 方向感知：横向把手 5 点竖排；ActorSplitH handleWidth 6→14；
  QSS handle 背景透明、margin 归零）
- 演员刮削页数据源列表幻影空槽兜底（清掉无 widget 的幻影项）；
  修 QListWidget.clear() 不删 setItemWidget 行控件导致的控件堆积
  （hide+脱父+deleteLater 收尸）与 _src_rows 结果标签悬空引用
- 验证：离屏冒烟 smoke_v1422.py 27/27；真机自检 ALIVE_OK、
  版本窗「流明盒 v1.42.2 (Build 2610180085)」、启动段零未捕获异常、sysmon 单例
""".format(sha=sha)
with open(NOTE_PATH, "w", encoding="utf-8") as f:
    f.write(note)
print("   %s（%d 字节）" % (os.path.basename(NOTE_PATH), len(note.encode("utf-8"))))
print("ARCHIVE_SLIM_DONE")
