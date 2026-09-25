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
import json
import os
import time

import media_meta as mm

#: 三个槽位 + 中文名（顺序即界面展示顺序）
SLOTS = ("poster", "thumb", "fanart")
SLOT_CN = {"poster": "海报", "thumb": "缩略图", "fanart": "背景图"}

#: v1.33.0（反馈 1）：结果文件信封格式号 —— 与 duplicates.py 同一套约定。
EXPORT_FORMAT = 1

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
    """该槽位所有可能的本地图路径（按优先级），含数据库里记的那一条。

    **刻意不做跨槽位兜底**（v1.30.0 定的口径）：poster 只认海报类文件名，
    不会拿 `<番号>-thumb.jpg` 去顶。早先 poster 的候选里带上了 thumb 文件，
    结果「海报被截断、缩略图却是好的」这种情况会被判成 OK —— 恰好把用户截图里
    那张灰海报放过去了。宁可报出来让用户决定，也不要替他「假装有图」。
    """
    out = []
    dbp = (media or {}).get(slot) or ""
    if dbp:
        out.append(dbp)
    d = media_dir(media)
    stem = stem_of(media)
    names = []
    if stem:
        if slot == "poster":
            names += [f"{stem}-poster.jpg", f"{stem}-poster.png",
                      f"{stem}.jpg", f"{stem}.png"]
        elif slot == "thumb":
            names += [f"{stem}-thumb.jpg", f"{stem}-thumb.png"]
        else:
            names += [f"{stem}-fanart.jpg", f"{stem}-fanart.png",
                      f"{stem}-backdrop.jpg", f"{stem}-backdrop.png"]
    names += {
        "poster": ["poster.jpg", "poster.png", "folder.jpg", "cover.jpg"],
        "thumb": ["thumb.jpg", "thumb.png"],
        "fanart": ["fanart.jpg", "fanart.png", "backdrop.jpg", "background.jpg"],
    }[slot]
    if d and os.path.isdir(d):
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
        # v1.32.0（反馈 1）：本次用的算法与 AI 复核统计（结构同 duplicates.DupReport）
        self.algo = "normal"
        self.ai = {}

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
                "algo": self.algo,
                "ai_done": int((self.ai or {}).get("done") or 0),
                "ai_failed": int((self.ai or {}).get("failed") or 0),
                "ai_skipped": int((self.ai or {}).get("skipped") or 0),
                "ai_model": str((self.ai or {}).get("model") or ""),
                "ai_note": str((self.ai or {}).get("note") or ""),
                "by_slot": {s: {"missing": c[(s, MISSING)], "broken": c[(s, BROKEN)]}
                            for s in SLOTS}}


def review_with_ai(report, model=None, fast=True, progress=None, stop=None,
                   limit=None):
    """对一次图像检测的结果做 **AI 复核**（v1.32.0，反馈 1）。

    思路与「重复检测」「演员检测」完全一致：普通算法（结构校验）先把问题缩到
    「确实缺图 / 确实结构破损」这一批，本地离线 AI 再逐条判**这条值不值得用户动手**。

    为什么这个复核特别有用：真机上「缺缩略图」能占问题总数的七八成，但缩略图只在
    少数界面用到、优先级极低 —— 让 AI 把它们标成「可忽略」，用户就能直奔真正
    影响观感的海报与背景图。

    ⚠ 只读：AI 结论写进 `prob["ai"]`，**绝不自动调用 `replace_image`**。
    """
    import aireview as ar

    if report is None:
        return {"ai": False, "note": "没有可复核的结果。", "done": 0, "failed": 0,
                "skipped": 0, "jobs": 0, "fast": bool(fast), "kind": "图像检测"}
    report.algo = "ai"
    probs = list(report.problems or [])
    if limit is None:
        limit = ar.MAX_ITEMS

    # 「拿不准」的判据：**缺缩略图**与「其它槽位缺图」最典型，破损总是值得看
    # （破损是结构坏了，确实该换）；缺 thumb 基本可以交给 AI 压低优先级。
    def _unsure(p):
        if p.get("state") == BROKEN:
            return True
        return p.get("slot") == "thumb" or bool(p.get("path"))

    def _prompt(p):
        return ar.imagedetect_prompt({
            "slot": p.get("slot"), "slot_cn": p.get("slot_cn"),
            "state": p.get("state"),
            "state_cn": STATE_CN.get(p.get("state"), p.get("state") or ""),
            "detail": p.get("detail"),
            "file_size": p.get("file_size"), "dimension": p.get("dimension"),
            "aspect": p.get("aspect"),
        })

    def _apply(p, text):
        advice, conf, why = ar.verdict_to_img(text)
        p["ai"] = {"advice": advice, "confidence": conf, "reason": why,
                   "raw": str(text or "")[:400]}

    res = ar.review_batch("图像检测", probs, _prompt, _apply, model=model,
                          fast=bool(fast), fast_filter=_unsure,
                          progress=progress, stop=stop, limit=limit)
    report.ai = res
    return res


def scan(rows, progress=None, library="", slots=SLOTS):
    """扫描一批 media 行，产出 ImageReport。

    `rows` 需要含 id/title/file_path/nfo_path/poster/thumb/fanart 这些列。
    `progress(done, total, msg)` 用于驱动界面进度（可为 None）。

    v1.32.0（反馈 1）：每条问题额外带上 `file_size` / `dimension` / `aspect` ——
    「图片检测」的 AI 复核要靠这些量判断「是不是占位图 / 比例是不是异常」，
    普通算法顺手就能拿到（一次 `os.path.getsize` + 惰性 Qt 读尺寸），
    不值得让 AI 那边再回头去摸一次磁盘。
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
            size, dim = _probe_geometry(r["path"])
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
                "file_size": size,
                "dimension": dim,
                "aspect": _aspect_of(dim, slot),
            })
        if progress and (i % 50 == 0 or i == total):
            progress(i, total, f"正在检测 {i} / {total} 部…")
    rep.elapsed = time.time() - t0
    return rep


def _probe_geometry(path):
    """返回 `(字节数, "宽x高")`；拿不到的部分给 0 / 空串。**绝不抛异常**。"""
    if not path or not os.path.exists(path):
        return 0, ""
    try:
        size = int(os.path.getsize(path))
    except OSError:
        size = 0
    dim = ""
    try:
        from PySide6.QtGui import QImageReader      # 惰性 import：本模块不依赖 Qt
        rd = QImageReader(path)
        sz = rd.size()
        if sz.isValid() and sz.width() > 0 and sz.height() > 0:
            dim = "%dx%d" % (sz.width(), sz.height())
    except Exception:
        dim = ""
    return size, dim


def _aspect_of(dim, slot):
    """把尺寸翻成人话（`竖版` / `横版` / `方图`），并标出与槽位期望是否相符。

    海报是竖版、缩略图与背景图是横版 —— 比例反了多半是刮削时抓错了图，
    这是 AI 判「要不要处理」的一条好线索。
    """
    try:
        w, h = (int(x) for x in str(dim).lower().split("x", 1))
    except Exception:
        return ""
    if w <= 0 or h <= 0:
        return ""
    want_portrait = (slot == "poster")
    is_portrait = h > w * 1.05
    is_landscape = w > h * 1.05
    if abs(w - h) <= max(w, h) * 0.05:
        shape = "方图"
    elif is_portrait:
        shape = "竖版"
    else:
        shape = "横版"
    ok = (shape == "方图") or (is_portrait == want_portrait)
    return shape + ("（与槽位相符）" if ok else "（与槽位不符，可能抓错图）")


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


# v1.33.0（反馈 1）：结果导出 / 导入 —— 全库图像检测要逐张读文件，真机 49668 张跑一次
# 不便宜。当天没处理完的，导出成文件，明天导入接着处理，不必重新扫描。
# 信封格式与 duplicates.py 完全一致（同一套约定，四个检测页共用）。
def export_json(report, path: str) -> str:
    """把 `ImageReport` 导出为 JSON（含每条问题的 AI 结论）。"""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    payload = {
        "_app": "LumaCrate",
        "_kind": "imagedetect",
        "_format": EXPORT_FORMAT,
        "report": {
            "problems": [dict(p) for p in (report.problems or [])],
            "scanned": int(report.scanned or 0),
            "elapsed": float(report.elapsed or 0.0),
            "algo": str(report.algo or "normal"),
            "ai": dict(report.ai or {}),
            "summary": report.summary(),
        },
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return path


def import_json(path: str) -> "ImageReport":
    """从 `export_json` 产出的文件恢复 `ImageReport`（v1.33.0 反馈 1）。

    兼容两代：带信封的新格式，以及直接 dump `{problems:…}` 的裸格式。
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        raise ValueError("文件内容不是 JSON 对象")
    if "_kind" in raw:
        if raw.get("_kind") != "imagedetect":
            raise ValueError("这不是「图像检测」的结果文件（_kind=%r）" % raw.get("_kind"))
        if int(raw.get("_format") or 0) > EXPORT_FORMAT:
            raise ValueError("结果文件来自更新的版本（格式 %s），请升级软件后再导入"
                             % raw.get("_format"))
        data = raw.get("report") or {}
    else:
        data = raw
    if "problems" not in data:
        raise ValueError("文件里没有检测结果（缺 problems）")
    rep = ImageReport()
    rep.problems = [dict(p) for p in (data.get("problems") or [])]
    rep.scanned = int(data.get("scanned") or 0)
    rep.elapsed = float(data.get("elapsed") or 0.0)
    rep.algo = str(data.get("algo") or "normal")
    rep.ai = dict(data.get("ai") or {})
    return rep
