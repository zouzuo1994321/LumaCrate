# -*- coding: utf-8 -*-
"""封存 v1.43.5：源码 zip（含 docs 审计/计划）+ 封存说明（含 exe SHA-256）。
不做任何功能改动；只读打包。"""
import ctypes
import hashlib
import os
import zipfile

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
HIST = os.path.join(ROOT, "history")
VER, BUILD = "v1.43.5", "2610230091"
STEM = f"流明盒-{VER}-{BUILD}"
ZIP = os.path.join(HIST, f"{STEM}-源码.zip")
NOTE = os.path.join(HIST, f"{STEM}-封存说明.txt")
DEV = os.path.join(ROOT, "dev")
k = ctypes.windll.kernel32


def del_file(p):
    k.SetFileAttributesW(p, 0x80)
    return bool(k.DeleteFileW(p))


TOP_FILES = ["build_exe.py", "README.md", "README_EN.md", "requirements.txt",
             "logo.ico", "logo-4.png", "性能基线.md"]

if os.path.exists(ZIP):
    print("已存在旧包，先删:", del_file(ZIP))

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
            if f.startswith(("v1430_", "v1431_", "v1432_", "v1433_", "v1434_", "v1435_")) \
                    and f.endswith(".png"):
                add(os.path.join(ss, f), "dev/screenshots/" + f)
print("zip: %d 个文件，原始 %.1f MB，压缩后 %.1f MB"
      % (n, raw / 1048576, os.path.getsize(ZIP) / 1048576))

h = hashlib.sha256()
with open(os.path.join(ROOT, STEM + ".exe"), "rb") as f:
    for c in iter(lambda: f.read(1 << 20), b""):
        h.update(c)
sha = h.hexdigest()

note = f"""流明盒 LumaCrate {VER} 封存说明
================================
外部版本：{VER}
内部构建：{BUILD}（2026-10-23）
封存日期：2026-10-23
封存原因：本轮「只检查不修改」——在进入下一轮开发前固定源码与产物的可回溯快照。

一、程序（exe）
- 工作副本：{STEM}.exe（工程根目录，约 56.8 MB，单文件 --onefile --windowed）
- 留档副本：history/{STEM}.exe（与工作副本逐字节一致）
- SHA-256：{sha}

二、源代码
- 留档：history/{STEM}-源码.zip（顶层目录 {STEM}/）
- 内容：
  · src/ 全部源码（30 个模块）
  · build_exe.py 打包脚本
  · README.md / README_EN.md / requirements.txt
  · logo.ico / logo-4.png / 性能基线.md
  · docs/审计报告-v1.43.5.md（本轮全量体检结论）
  · docs/开发计划-v1.44.md（后续路线）
  · dev/ 下全部 .py 开发脚本（各版冒烟 / 出图 / 真机验收 / 探针）
  · dev/screenshots/ v1.43.x 的预览图（v1430 ~ v1435）
  · dev/_scratch/ v1435 审计与验证脚本（audit_*_v1435.py、exe_selfcheck_v1435.py 等）
- 不含：settings.json（本机配置）、index_data/（索引库与本机日志）、cache/、
  history/ 与「历史版本(含源代码及打包文件)」旧归档、__pycache__

三、重新打包
1. 解压 zip，进入 {STEM}/ 目录
2. Python 3.13 + PySide6 环境执行：python build_exe.py
3. 产物：{STEM}.exe

四、本轮状态（v1.43.5）
- 发布门槛冒烟 dev/smoke_v1430.py：92/92 通过
- 真机自检：ALIVE_OK、版本窗「流明盒 {VER} (Build {BUILD})」、零未捕获异常、sysmon 单例、零残留
- 未决问题（详见 docs/审计报告-v1.43.5.md）：
  BUG-01 影片墙主排序未走 idx_wall_*（首屏 106/302ms、深翻页 1574/744ms；强指索引可降到 0.7/103ms）
  BUG-02 演员库首屏 473ms（works 聚合排序）
  BUG-03 偏好导入无法恢复/清空 0 分
  BUG-04 gfriends 索引默认缓存到 ~/.lmacrate
  BUG-05 ThePornDB token 明文落盘
  BUG-06 版权行改到右下（v1.43.5 副作用，待确认版式）
  BUG-07 60 个历史冒烟脚本需归档
  BUG-08 README / 旧归档目录说明待整理

五、本版（v1.43.5）改动摘要
- 「窗口透明度」滑块把手：16px 正圆 → 18×12 圆角扁平方形（radius 4）
- 底部版权改为 addPermanentWidget 常驻 QLabel（#FooterNote），不再被临时消息顶掉
"""
with open(NOTE, "w", encoding="utf-8") as f:
    f.write(note)
print("note:", os.path.basename(NOTE), len(note.encode("utf-8")), "bytes")
print("ARCHIVE_V1435_DONE")
