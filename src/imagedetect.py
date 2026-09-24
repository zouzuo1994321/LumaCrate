# -*- coding: utf-8 -*-
"""图像检测（v1.30.0）
=====================
找出媒体库里的「缺图 / 破损图」，并把用户选定的图片按 tinyMediaManager 约定的
三个标准文件名落盘、同步数据库：

    <番号>-poster.jpg    海报（竖版）
    <番号>-thumb.jpg     缩略图（横版）
    <番号>-fanart.jpg    背景图（横版）

为什么「破损」不能用 Qt 判（实测，`dev/_scratch/probe_broken_img.py`）
--------------------------------------------------------------------
把一张正常 JPEG 砍掉 45% / 75% 之后再让 Qt 读：

    QImageReader.read() -> 非空 1920x1080，error()=UnknownError
    QPixmap(path).isNull() -> False

也就是 libjpeg 的**容错解码**会把缺的部分填灰，Qt 认为它「没问题」——
用户截图里那张「整块灰色 + 顶上一条真图」的海报正是这个现象。
所以本模块用**纯 Python 结构校验**（不依赖 Pillow）：

    JPEG: 必须以 SOI(FF D8) 开头、以 EOI(FF D9) 结尾（去掉尾部填充字节后）
    PNG : 必须有 8 字节签名、结尾 32 字节内必须有 IEND
    另外：文件 < 1KB 一律视为可疑；再用 Qt 解码 null 兜底一次（PNG 中段损坏时它有效）。

分层：`check_image()` / `scan()` 是纯计算（可直接单测），唯一一次 Qt 调用在
`_qt_decode_ok()` 里，且是**惰性 import**，模块本身不 import Qt。
"""
import os
import time

import media_meta as mm

#: 三个槽位 + 中文名（顺序即界面展示顺序）
SLOTS = ("poster", "thumb", "fanart")
SLOT_CN = {"poster": "海报", "thumb": "缩略图", "fanart": "背景图"}

#: 状态
OK, MISSING, BROKEN = "ok", "missing", "broken"
STATE_CN = {MISSING: "缺图", BROKEN: "破损"}

_MIN_BYTES = 1024            # 小于 1KB 的图一律可疑（截断/占位）
_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def media_dir(media) -> str:
    """影片所在目录（优先 file_path，其次 nfo_path）。"""
    fp = (media or {}).get("file_path") or ""
    if fp:
        return os.path.dirname(fp)
    np_ = (media or {}).get("nfo_path") or ""
    return os.path.dirname(np_) if np_ else ""


def stem_of(media) -> str:
    """番号 / 文件名主干（`<番号>-poster.jpg` 里的 `<番号>`）。"""
    for key in ("file_path", "nfo_path"):
        p = (media or {}).get(key) or ""
        if p:
            s = os.path.splitext(os.path.basename(p))[0]
            if s:
                return s
    return ""


def target_path(media, slot) -> str:
    """该槽位的标准落盘路径：`<目录>/<番号>-<slot>.jpg`。"""
    d = media_dir(media)
    stem = stem_of(media)
    if not d or not stem:
        return ""
    return os.path.join(d, f"{stem}-{slot}.jpg")


def candidate_paths(media, slot):
    """该槽位所有可能的本地图路径（按优先级），含数据库里记的那一条。"""
    out = []
    dbp = (media or {}).get(slot) or ""
    if dbp:
        out.append(dbp)
    d = media_dir(media)
    stem = stem_of(media)
    if d and os.path.isdir(d):
        names = []
        if stem:
            if slot == "poster":
                names += [f"{stem}-poster.jpg", f"{stem}-poster.png", f"{stem}.jpg",
                          f"{stem}.png", f"{stem}-thumb.jpg", f"{stem}-thumb.png"]
            elif slot == "thumb":
                names += [f"{stem}-thumb.jpg", f"{stem}-thumb.png"]
            else:
                names += [f"{stem}-fanart.jpg", f"{stem}-fanart.png",
                          f"{stem}-backdrop.jpg", f"{stem}-backdrop.png"]
        generic = {
            "poster": ["poster.jpg", "poster.png", "folder.jpg", "cover.jpg", "thumb.jpg"],
            "thumb": ["thumb.jpg", "thumb.png", "poster.jpg"],
            "fanart": ["fanart.jpg", "fanart.png", "backdrop.jpg", "background.jpg"],
        }[slot]
        names += generic
        for n in names:
            p = os.path.join(d, n)
            if p not in out:
                out.append(p)
    return out


def structural_ok(path):
    """纯 Python 结构校验。返回 (ok, detail)。

    JPEG 必须 SOI 开头 + EOI 结尾；PNG 必须签名 + IEND。别的格式只做存在性 + 大小。
    """
    try:
        size = os.path.getsize(path)
    except OSError as e:
        return False, f"无法读取（{e.__class__.__name__}）"
    if size <= 0:
        return False, "空文件（0 字节）"
    if size < _MIN_BYTES:
        return False, f"文件过小（{size} 字节）"
    try:
        with open(path, "rb") as f:
            head = f.read(16)
            f.seek(max(0, size - 64))
            tail = f.read()
    except OSError as e:
        return False, f"无法读取（{e.__class__.__name__}）"
    if head[:2] == b"\xff\xd8":
        if not tail.rstrip(b"\x00 \r\n\t").endswith(b"\xff\xd9"):
            return False, "JPEG 缺少结束标记（文件被截断）"
        return True, "ok"
    if head[:8] == _PNG_SIG:
        if b"IEND" not in tail:
            return False, "PNG 缺少 IEND 块（文件被截断）"
        return True, "ok"
    return True, "ok"                      # 其它格式（webp/bmp/gif）不细判


def _qt_decode_ok(path):
    """Qt 解码兜底（PNG 中段损坏等）；Qt 不可用时直接放行。"""
    try:
        from PySide6.QtGui import QImageReader
    except Exception:
        return True
    try:
        r = QImageReader(path)
        return not r.read().isNull()
    except Exception:
        return True


def check_image(path):
    """检查单张图。返回 (state, detail)。"""
    if not path:
        return MISSING, "未找到任何图片"
    if not os.path.exists(path):
        return MISSING, "文件不存在"
    ok, detail = structural_ok(path)
    if not ok:
        return BROKEN, detail
    if not _qt_decode_ok(path):
        return BROKEN, "解码失败（内容损坏）"
    return OK, "ok"


def resolve(media, slot):
    """判定某个槽位。返回 dict(path, state, detail)。

    优先级：数据库里记的路径 → 同目录候选（`<番号>-poster.jpg` 等）。
    """
    cands = candidate_paths(media, slot)
    first_bad = None
    for p in cands:
        if not p or not os.path.exists(p):
            continue
        state, detail = check_image(p)
        if state == OK:
            return {"path": p, "state": OK, "detail": "ok"}
        if first_bad is None:
            first_bad = {"path": p, "state": state, "detail": detail}
    if first_bad is not None:
        return first_bad
    return {"path": "", "state": MISSING, "detail": "未找到任何图片"}


class ImageReport:
    """一次图像检测的结果。"""

    def __init__(self):
        self.problems = []          # 每个问题一条
        self.scanned = 0
        self.elapsed = 0.0

    def counts(self):
        c = {(s, MISSING): 0 for s in SLOTS}
        c.update({(s, BROKEN): 0 for s in SLOTS})
        for p in self.problems:
            c[(p["slot"], p["state"])] = c.get((p["slot"], p["state"]), 0) + 1
        return c

    def summary(self):
        c = self.counts()
        miss = sum(c[(s, MISSING)] for s in SLOTS)
        brk = sum(c[(s, BROKEN)] for s in SLOTS)
        return {"scanned": self.scanned, "missing": miss, "broken": brk,
                "total": miss + brk, "elapsed": round(self.elapsed, 1),
                "by_slot": {s: {"missing": c[(s, MISSING)], "broken": c[(s, BROKEN)]}
                            for s in SLOTS}}


def scan(rows, progress=None, library="", slots=SLOTS):
    """扫描一批 media 行，产出 ImageReport。

    `rows` 需要含 id/title/file_path/nfo_path/poster/thumb/fanart 这些列。
    `progress(done, total, msg)` 用于驱动界面进度（可为 None）。
    """
    rep = ImageReport()
    rows = list(rows or [])
    total = len(rows)
    t0 = time.time()
    for i, m in enumerate(rows, 1):
        if library and (m.get("library") or "") != library:
            continue
        rep.scanned += 1
        for slot in slots:
            r = resolve(m, slot)
            if r["state"] == OK:
                continue
            rep.problems.append({
                "media_id": m.get("id"),
                "title": m.get("title") or "",
                "file_path": m.get("file_path") or "",
                "library": m.get("library") or "",
                "slot": slot,
                "slot_cn": SLOT_CN.get(slot, slot),
                "state": r["state"],
                "path": r["path"],
                "detail": r["detail"],
                "target": target_path(m, slot),
            })
        if progress and (i % 50 == 0 or i == total):
            progress(i, total, f"正在检测 {i} / {total} 部…")
    rep.elapsed = time.time() - t0
    return rep


def replace_image(media, slot, src_path):
    """把 `src_path` 复制成该槽位的标准文件并返回 (ok, target, err)。

    先校验源图能通过结构检查（避免把另一张坏图传进去）。
    """
    if slot not in SLOTS:
        return False, "", f"未知槽位：{slot}"
    if not src_path or not os.path.exists(src_path):
        return False, "", "源文件不存在"
    state, detail = check_image(src_path)
    if state != OK:
        return False, "", f"源文件不是有效图片（{detail}）"
    target = target_path(media, slot)
    if not target:
        return False, "", "该影片缺少文件路径，无法确定落盘位置"
    folder = os.path.dirname(target)
    if not os.path.isdir(folder):
        return False, "", f"影片目录不存在：{folder}"
    try:
        with open(src_path, "rb") as fi, open(target, "wb") as fo:
            fo.write(fi.read())
    except OSError as e:
        return False, "", f"写入失败：{e}"
    return True, target, ""


def local_images(media):
    """常用图名的本地解析（复用 media_meta 的口径，供界面显示当前图）。"""
    d = media_dir(media)
    stem = stem_of(media)
    base = os.path.basename((media or {}).get("file_path") or "")
    poster, fanart = mm.find_local_images(d, base or None)
    thumb = ""
    if d and stem:
        for n in (f"{stem}-thumb.jpg", f"{stem}-thumb.png", "thumb.jpg"):
            p = os.path.join(d, n)
            if os.path.exists(p):
                thumb = p
                break
    return {"poster": (media or {}).get("poster") or poster or "",
            "thumb": (media or {}).get("thumb") or thumb or "",
            "fanart": (media or {}).get("fanart") or fanart or ""}
