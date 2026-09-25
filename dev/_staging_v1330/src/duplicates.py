# -*- coding: utf-8 -*-
"""重复影片检测 —— 跨目录去重（v1.23.0，借鉴 NFO 画像矿工 nfo_profiler 的 dedupe 思路）。

判定思路
--------
1. **身份键**：优先番号（从**视频文件名** / 标题 / 排序名里提取，归一成 ``abc123`` 形式）；
   没有番号的回退「标题 + 年份」。
2. **跨目录才算重复**：把成员按「所在文件夹」归并 ——
   * 同一文件夹里的多份：几乎都是**一部片子被切成多段**（CD1/CD2、part1/part2），
     属正常情况，**不计入重复**，只在结果里单列为「已排除·同目录分片」；
   * 分布在**不同文件夹**的同键项：判为**重复收藏**，需要报告出来。
3. **可回收空间**：同一组每个文件夹算「一份」，保留最大的那一份，
   其余份数体积之和即为可回收空间。
4. **置信度**：番号一致 = 高；标题+年份一致 = 中；仅有标题 = 低；
   各份体积完全一致再上调一级（极高）。

本模块零第三方依赖（导出 CSV / JSON，不含 XLSX）。

Copyright  2026 肆月Aperture　本软件为开源软件，没有授权禁止用于商业用途。
"""

from __future__ import annotations

import csv
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

import database as db

COPYRIGHT_NOTICE = "Copyright  2026 肆月Aperture　本软件为开源软件，没有授权禁止用于商业用途。"

# v1.33.0（反馈 1）：结果文件信封格式号（四个检测页共用同一套约定）。
# 导入时先验 `_kind` 再解析 —— 报「这不是重复检测的结果文件」比报
# `KeyError: 'groups'` 好懂得多。字段有破坏性改动就 +1。
EXPORT_FORMAT = 1


# ---------------------------------------------------------------------------
# 归一化
# ---------------------------------------------------------------------------

#: 标题里只保留 中/日/英/数字 作为比较键
_NON_KEY_RE = re.compile(r"[^0-9a-z\u4e00-\u9fff\u3040-\u30ff]+")
#: 标题开头的番号（如 "DDK-173 関西弁の…"）→ 去掉，避免番号不同的片子被标题前缀误伤
_HEAD_NUM_RE = re.compile(r"^\s*[\[\(【]?\s*[a-z]{1,8}\s*[-_]?\s*\d{2,6}\s*[\]\)】]?\s*[-:：\s]*")
#: 从文件名 / 标题里提取番号
_NUM_RE = re.compile(r"([a-z]{2,10})\s*[-_]?\s*(\d{2,6})(?!\d)")


def norm_num(value: Any) -> str:
    """把番号归一化成 ``abc123`` 形式；无法识别时返回空串。"""
    s = str(value or "").strip().lower()
    if not s:
        return ""
    s = re.sub(r"[^0-9a-z]+", "", s)
    if not s or not re.match(r"^[a-z]+\d+$", s):   # 必须 字母+数字 才算有效番号
        return ""
    return s


def _num_from_text(text: Any) -> str:
    """从文件名 / 标题里提取番号键（优先整体归一化，回退到「字母+数字」正则）。"""
    s = str(text or "").strip().lower()
    if not s:
        return ""
    base = os.path.splitext(os.path.basename(s))[0]
    key = norm_num(base)
    if key:
        return key
    m = _NUM_RE.search(s)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    return ""


def extract_num(*candidates: Any) -> str:
    """从文件名 / 标题里提取番号键（按候选顺序取第一个命中的）。"""
    for c in candidates:
        k = _num_from_text(c)
        if k:
            return k
    return ""


def norm_title(value: Any) -> str:
    """标题比较键：去掉开头番号与所有标点/空白，仅保留文字与数字。"""
    s = str(value or "").strip().lower()
    if not s:
        return ""
    s = _HEAD_NUM_RE.sub("", s)
    s = _NON_KEY_RE.sub("", s)
    return s


def title_key(title: Any, clean_title: Any, year: Any) -> str:
    """标题 + 年份 身份键（无年份时退化为纯标题）。"""
    t = norm_title(clean_title) or norm_title(title)
    if not t:
        return ""
    y = str(year or "").strip()
    if y.isdigit() and len(y) == 4:
        return f"{t}::{y}"
    return f"{t}::"


def human_size(n: Any) -> str:
    """字节 → 人类可读（GB / MB）。"""
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return "0 B"
    if n <= 0:
        return "—"
    gb = n / 1073741824.0
    if gb >= 1:
        return f"{gb:.2f} GB"
    mb = n / 1048576.0
    if mb >= 1:
        return f"{mb:.1f} MB"
    return f"{n / 1024.0:.0f} KB"


def _runtime_sec(value: Any) -> int:
    """把 ``HH:MM:SS`` / ``MM:SS`` 时长文本转成秒；无法解析返回 0。"""
    s = str(value or "").strip()
    if not s:
        return 0
    parts = s.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 1:
        return nums[0]
    return 0


def human_duration(sec: Any) -> str:
    try:
        sec = int(sec or 0)
    except (TypeError, ValueError):
        return "—"
    if sec <= 0:
        return "—"
    h, m = divmod(sec // 60, 60)
    return f"{h}小时{m}分" if h else f"{m}分"


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class DupMember:
    """重复组里的一个成员（= 一条 media 记录）。"""
    movie_id: int = 0
    path: str = ""
    folder: str = ""
    nfo_name: str = ""
    num: str = ""
    title: str = ""
    year: int = 0
    resolution: str = ""
    video_size: int = 0
    duration_sec: int = 0
    dateadded: str = ""
    source: str = ""
    original_filename: str = ""

    @property
    def size(self) -> int:
        return int(self.video_size or 0)

    @property
    def size_text(self) -> str:
        """人类可读体积（UI 树/导出都要用，别再各写一份）。"""
        return human_size(self.video_size)

    @property
    def duration_text(self) -> str:
        return human_duration(self.duration_sec)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "movie_id": self.movie_id, "path": self.path, "folder": self.folder,
            "nfo_name": self.nfo_name, "num": self.num, "title": self.title,
            "year": self.year, "resolution": self.resolution,
            "video_size": self.video_size, "size_text": human_size(self.video_size),
            "duration_sec": self.duration_sec, "duration_text": human_duration(self.duration_sec),
            "dateadded": self.dateadded, "source": self.source,
            "original_filename": self.original_filename,
        }


@dataclass
class DupGroup:
    """一个重复组：身份键相同、且分布在 >= 2 个不同文件夹。"""
    key: str = ""
    kind: str = "num"                 # num | title
    label: str = ""
    confidence: str = "高"            # 极高 / 高 / 中 / 低
    members: List[DupMember] = field(default_factory=list)
    note: str = ""
    total_bytes: int = 0
    redundant_bytes: int = 0
    by_folder: Dict[str, List[DupMember]] = field(default_factory=dict)
    # v1.32.0（反馈 1）：AI 复核结论。只在用户选了「AI 算法」且本机 Ollama 可用时才有值，
    # 结构是 ``{"advice": …, "confidence": …, "reason": …, "raw": …}``。**纯建议** ——
    # 本软件从不在任何情况下代用户删文件，AI 判定只是把「哪份更像正本」的意见摆出来。
    ai: Dict[str, Any] = field(default_factory=dict)

    @property
    def ai_advice(self) -> str:
        return str((self.ai or {}).get("advice") or "")

    @property
    def copies(self) -> int:
        return len(self.by_folder)

    @property
    def redundant_copies(self) -> int:
        return max(0, self.copies - 1)

    @property
    def folders(self) -> List[str]:
        return list(self.by_folder.keys())

    @property
    def total_text(self) -> str:
        return human_size(self.total_bytes)

    @property
    def redundant_text(self) -> str:
        return human_size(self.redundant_bytes)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key, "kind": self.kind, "label": self.label,
            "confidence": self.confidence, "note": self.note,
            "copies": self.copies, "redundant_copies": self.redundant_copies,
            "total_bytes": self.total_bytes, "total_text": self.total_text,
            "redundant_bytes": self.redundant_bytes, "redundant_text": self.redundant_text,
            "folders": self.folders,
            "ai": dict(self.ai or {}),
            "members": [m.as_dict() for m in self.members],
        }


@dataclass
class DupReport:
    """一次重复检测的完整结果。"""
    groups: List[DupGroup] = field(default_factory=list)
    multipart: List[DupGroup] = field(default_factory=list)   # 同目录多份（已排除）
    scanned: int = 0
    elapsed: float = 0.0
    generated_at: str = ""
    # v1.24.0（反馈 1）：索引还在、磁盘上文件已被删掉的数量。这些行**不参与比对**，
    # 否则「重复的片子我已经删掉了，检测结果里还有」会一直复现。
    missing: int = 0
    multipart_excluded: bool = True
    # v1.32.0（反馈 1）：本次检测用的算法与 AI 复核统计。
    # `algo` = "normal" | "ai"；`ai` 是 aireview.review_batch 的返回，
    # 含 `note`（AI 不可用时的原因原文）/ `done` / `failed` / `skipped`。
    algo: str = "normal"
    ai: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "scanned": self.scanned,
            "missing": self.missing,
            "multipart_excluded": self.multipart_excluded,
            "dup_groups": len(self.groups),
            "dup_movies": sum(len(g.members) for g in self.groups),
            "redundant_copies": sum(g.redundant_copies for g in self.groups),
            "redundant_bytes": sum(g.redundant_bytes for g in self.groups),
            "redundant_text": human_size(sum(g.redundant_bytes for g in self.groups)),
            "multipart_groups": len(self.multipart),
            "multipart_movies": sum(len(g.members) for g in self.multipart),
            "elapsed": round(self.elapsed, 2),
            "algo": self.algo,
            "ai_done": int((self.ai or {}).get("done") or 0),
            "ai_failed": int((self.ai or {}).get("failed") or 0),
            "ai_skipped": int((self.ai or {}).get("skipped") or 0),
            "ai_model": str((self.ai or {}).get("model") or ""),
            "ai_note": str((self.ai or {}).get("note") or ""),
        }

    def as_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary(),
            "algo": self.algo,
            "ai": dict(self.ai or {}),
            "groups": [g.as_dict() for g in self.groups],
            "multipart": [g.as_dict() for g in self.multipart],
            "copyright": COPYRIGHT_NOTICE,
        }


# ---------------------------------------------------------------------------
# 检测器
# ---------------------------------------------------------------------------

# 「不存在」比例超过这个值时，判定为盘未挂载 / 离线，不做剔除（见 _prune_missing）
_MISSING_GUARD = 0.90


def _safe(progress, a, b, msg):
    if not progress:
        return
    try:
        progress(a, b, msg)
    except Exception:
        pass


def _prune_missing(rows, progress=None):
    """剔掉「索引里有记录、磁盘上文件已经不存在」的行（v1.24.0 反馈 1）。

    这是「重复的片子我已经删掉了，但检测结果里还有」的根因：检测一向只读索引，
    被删掉的副本仍以索引行的形式参与比对，于是伪重复组一直在。

    **防误伤**：如果「不存在」的比例超过 `_MISSING_GUARD`（默认 90%），
    基本可以断定是盘没挂载 / 网络位置离线，而不是用户删了文件 ——
    这时**不做剔除**，只在报告里标注，免得把整库判成空。
    """
    if not rows:
        return rows, 0, False
    alive, missing = [], 0
    for i, r in enumerate(rows):
        p = r.get("file_path") or ""
        if not p or os.path.exists(p):
            alive.append(r)
        else:
            missing += 1
        if (i + 1) % 4000 == 0:
            _safe(progress, i + 1, len(rows),
                  f"正在校验文件是否还在（{i + 1}/{len(rows)}）…")
    if missing > len(rows) * _MISSING_GUARD:
        _safe(progress, len(rows), len(rows),
              "⚠ 绝大多数文件都访问不到，判定为磁盘未挂载 → 本次不做剔除")
        return rows, missing, True
    return alive, missing, False


def find_duplicates(*, library: Optional[str] = None, use_num: bool = True,
                    use_title: bool = True, min_confidence: str = "低",
                    exclude_multipart: bool = True, verify_exists: bool = True,
                    progress=None) -> DupReport:
    """执行一次重复检测，返回 :class:`DupReport`。

    v1.24.0（反馈 1/2）新增两个开关：
    - `verify_exists=True`：先校验磁盘上文件是否还在，**只对存在的文件做比对**；
    - `exclude_multipart=True`：把「同一目录下的多份」当分片自动排除（默认，与旧版一致）；
      关掉后同目录多份也会当成重复组列出来，方便你自己判断。
    """
    t0 = time.time()
    rows = db.dedupe_rows(library or None)
    report = DupReport(scanned=len(rows),
                       multipart_excluded=bool(exclude_multipart),
                       generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    _safe(progress, 0, len(rows), "读取作品元数据…")
    if verify_exists:
        rows, report.missing, _bulk = _prune_missing(rows, progress)
        _safe(progress, 0, len(rows), f"有效作品 {len(rows)} 部，开始比对…")

    buckets: Dict[Tuple[str, str], List[DupMember]] = {}
    for i, r in enumerate(rows):
        path = r.get("file_path") or ""
        num_key = extract_num(path, r.get("sort_title") or "", r.get("title") or "") if use_num else ""
        if num_key:
            kind, key = "num", num_key
        elif use_title:
            kind, key = "title", title_key(r.get("title"), r.get("sort_title"), r.get("year"))
        else:
            continue
        if not key:
            continue
        m = DupMember(
            movie_id=int(r.get("id") or 0),
            path=path,
            folder=os.path.dirname(path),
            nfo_name=os.path.basename(path),
            num=num_key,
            title=(r.get("title") or r.get("sort_title") or ""),
            year=int(r.get("year") or 0),
            resolution=r.get("quality") or "",
            video_size=int(r.get("file_size") or 0),
            duration_sec=_runtime_sec(r.get("runtime")),
            dateadded="",
            source=r.get("library") or "",
            original_filename=os.path.basename(path),
        )
        buckets.setdefault((kind, key), []).append(m)
        if (i + 1) % 5000 == 0:
            _safe(progress, i + 1, len(rows), f"已比对 {i + 1}/{len(rows)} 部作品…")

    rank = {"极高": 3, "高": 2, "中": 1, "低": 0}
    min_rank = rank.get(min_confidence, 0)
    groups: List[DupGroup] = []
    multipart: List[DupGroup] = []

    for (kind, key), members in buckets.items():
        if len(members) < 2:
            continue
        by_folder: Dict[str, List[DupMember]] = {}
        for m in members:
            by_folder.setdefault(m.folder, []).append(m)

        first = members[0]
        if first.num and norm_num(first.num) == key:
            label = first.num.upper()
        else:
            label = first.title[:36] if first.title else key
        g = DupGroup(key=key, kind=kind, label=label,
                     members=sorted(members, key=lambda x: (-x.size, x.path)),
                     by_folder=by_folder)
        g.total_bytes = sum(m.size for m in members)
        biggest = max(sum(m.size for m in v) for v in by_folder.values())
        g.redundant_bytes = max(0, g.total_bytes - biggest)
        g.confidence, g.note = _judge(kind, members, by_folder)

        if rank.get(g.confidence, 0) < min_rank:
            continue
        if len(by_folder) <= 1 and exclude_multipart:
            g.note = "同目录多份，判定为分片（多段），已排除"
            multipart.append(g)
        elif len(by_folder) <= 1:
            # 开关关掉：同目录多份也当重复组列出，并标明「同目录」方便人工判断
            g.note = "同目录多份（未按分片排除 —— 你在设置里关掉了该开关）"
            groups.append(g)
        else:
            groups.append(g)

    groups.sort(key=lambda g: (-g.redundant_bytes, -g.copies, g.label))
    multipart.sort(key=lambda g: (-g.total_bytes, g.label))
    report.groups = groups
    report.multipart = multipart
    report.elapsed = time.time() - t0
    _safe(progress, len(rows), len(rows),
          f"完成：{len(groups)} 组重复，{len(multipart)} 组同目录分片")
    return report


def review_with_ai(report, model=None, fast=True, progress=None, stop=None,
                   limit=None):
    """对一次重复检测的结果做 **AI 复核**（v1.32.0，反馈 1）。

    与「演员检测」同一套模式：普通算法负责把候选缩到可复核的规模，本地离线 AI
    逐组复核「这真的是同一部片子的多份副本吗、该保留哪一份」，结论**只写进
    `group.ai`，只用于界面加一列建议** —— 本模块不会因此删除或移动任何文件。

    :param fast: 极速模式（默认开）。只复核普通算法自己拿不准的组 ——
        「极高 / 高」置信度（番号一致、体积还完全一致）根本没有可判的余地，
        送去让模型再确认一遍纯属浪费；AI 一慢就从「偶尔卡几秒」变成「整页几分钟」。
    :param limit: 最多复核多少组（`None` 用 `aireview.MAX_ITEMS`）。
    """
    import aireview as ar

    if report is None:
        return {"ai": False, "note": "没有可复核的结果。", "done": 0, "failed": 0,
                "skipped": 0, "jobs": 0, "fast": bool(fast), "kind": "重复检测"}
    report.algo = "ai"
    groups = list(report.groups or [])
    if limit is None:
        limit = ar.MAX_ITEMS

    # 「拿不准」的判据：置信度不到「高」，或者各份体积/时长不一致（存在画质差异）
    def _unsure(g):
        if str(g.confidence) not in ("高", "极高"):
            return True
        sizes = {m.size for m in g.members if m.size > 0}
        durs = {m.duration_sec for m in g.members if m.duration_sec > 0}
        return len(sizes) > 1 or len(durs) > 1

    def _prompt(g):
        folders = list(g.by_folder.keys())
        # 目录名脱敏：只给「目录 1 / 目录 2」，绝不把用户的盘符与目录名送进模型
        alias = {f: "目录 %d" % (i + 1) for i, f in enumerate(folders)}
        info = {
            "label": g.label,
            "label_masked": "序号 1 起（原标识 %d 个字符）" % len(str(g.label or "")),
            "members": [{
                "size": m.size, "duration": m.duration_text,
                "resolution": m.resolution, "folder_alias": alias.get(m.folder, ""),
            } for m in g.members],
        }
        return ar.dedupe_prompt(info)

    def _apply(g, text):
        advice, conf, why = ar.verdict_to_dup(text)
        g.ai = {"advice": advice, "confidence": conf, "reason": why,
                "raw": str(text or "")[:400]}

    res = ar.review_batch("重复检测", groups, _prompt, _apply, model=model,
                          fast=bool(fast), fast_filter=_unsure,
                          progress=progress, stop=stop, limit=limit)
    report.ai = res
    return res


def _judge(kind: str, members: Sequence[DupMember],
           by_folder: Dict[str, List[DupMember]]) -> Tuple[str, str]:
    """给出置信度与说明文字。"""
    notes: List[str] = []
    sizes = {m.size for m in members if m.size > 0}
    durs = {m.duration_sec for m in members if m.duration_sec > 0}
    res = {m.resolution for m in members if m.resolution}

    if kind == "num":
        conf = "高"
    elif all(m.year for m in members):
        conf = "中"
    else:
        conf = "低"

    if len(sizes) == 1 and sizes:
        conf = "极高"
        notes.append("各份体积完全一致")
    elif len(durs) == 1 and durs:
        notes.append("时长一致")
    if len(res) > 1:
        notes.append("画质不同：" + " / ".join(sorted(res)))
    if len(sizes) > 1:
        lo, hi = min(sizes), max(sizes)
        if lo > 0 and hi / max(lo, 1) > 1.5:
            notes.append(f"体积差异较大（{human_size(lo)} ~ {human_size(hi)}），可能是不同版本")
    if len(by_folder) > 1:
        notes.insert(0, f"分布在 {len(by_folder)} 个目录")
    return conf, "；".join(notes) or "元数据一致"


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------

GROUP_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("label", "标识"), ("key", "身份键"), ("kind", "匹配依据"), ("confidence", "置信度"),
    ("copies", "份数"), ("redundant_copies", "冗余份数"), ("total_text", "总体积"),
    ("redundant_text", "可回收空间"), ("note", "说明"), ("folders", "所在目录"),
)

MEMBER_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("label", "所属组"), ("num", "番号"), ("title", "标题"), ("year", "年份"),
    ("size_text", "体积"), ("duration_text", "时长"), ("folder", "所在目录"),
    ("original_filename", "视频文件"), ("path", "完整路径"),
)


def export_csv(report: DupReport, path: str) -> str:
    """导出重复清单为 CSV（UTF-8 BOM，Excel 直接双击不乱码）。"""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["# 流明盒 · 重复影片检测报告"])
        w.writerow([f"# 生成时间：{report.generated_at}"])
        w.writerow([f"# {COPYRIGHT_NOTICE}"])
        s = report.summary()
        w.writerow(["# 统计", "重复组", s["dup_groups"], "冗余份数", s["redundant_copies"],
                    "可回收空间", s["redundant_text"], "同目录分片组", s["multipart_groups"]])
        w.writerow([])
        w.writerow(["—— 重复组汇总 ——"])
        w.writerow([c[1] for c in GROUP_COLUMNS])
        for g in report.groups:
            d = g.as_dict()
            d["folders"] = " | ".join(g.folders)
            d["kind"] = "番号" if g.kind == "num" else "标题+年份"
            w.writerow([d.get(k, "") for k, _ in GROUP_COLUMNS])
        w.writerow([])
        w.writerow(["—— 成员明细 ——"])
        w.writerow([c[1] for c in MEMBER_COLUMNS])
        for g in report.groups:
            for m in g.members:
                d = m.as_dict()
                d["label"] = g.label
                w.writerow([d.get(k, "") for k, _ in MEMBER_COLUMNS])
        if report.multipart:
            w.writerow([])
            w.writerow(["—— 已排除：同目录分片 ——"])
            w.writerow(["标识", "身份键", "份数", "总体积", "所在目录", "说明"])
            for g in report.multipart:
                w.writerow([g.label, g.key, len(g.members), g.total_text,
                            g.folders[0] if g.folders else "", g.note])
    return path


def export_json(report: DupReport, path: str) -> str:
    """导出为 JSON（含完整分组与成员信息）。"""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    # v1.33.0（反馈 1）：加一层信封，标明来源与格式版本 —— 导入时先验这个再解析，
    # 免得用户把别的 JSON 选进来后报一个看不懂的 KeyError。
    # 同时把顶层标量**平铺**到 report 里（`as_dict()` 只把它们塞在 `summary` 下），
    # 否则导入回来 `scanned` / `missing` / `generated_at` 全是默认值，汇总行会写成
    # 「核对 0 部作品」，用户以为文件坏了。
    _rep = report.as_dict()
    _s = _rep.get("summary") or {}
    for _k in ("scanned", "elapsed", "generated_at", "missing", "multipart_excluded"):
        _rep.setdefault(_k, _s.get(_k))
    payload = {
        "_app": "LumaCrate",
        "_kind": "duplicates",
        "_format": EXPORT_FORMAT,
        "report": _rep,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return path


# v1.33.0（反馈 1）：四个检测页共用的导出信封格式号。导入时报「格式不匹配」比报
# 「KeyError: 'groups'」好懂得多。以后字段有破坏性改动就 +1。
# （定义已提到文件顶部，与 COPYRIGHT_NOTICE 放在一起。）


def _member_from_dict(d: Dict[str, Any]) -> DupMember:
    return DupMember(
        movie_id=int(d.get("movie_id") or 0),
        path=str(d.get("path") or ""),
        folder=str(d.get("folder") or ""),
        nfo_name=str(d.get("nfo_name") or ""),
        num=str(d.get("num") or ""),
        title=str(d.get("title") or ""),
        year=int(d.get("year") or 0),
        resolution=str(d.get("resolution") or ""),
        video_size=int(d.get("video_size") or 0),
        duration_sec=int(d.get("duration_sec") or 0),
        dateadded=str(d.get("dateadded") or ""),
        source=str(d.get("source") or ""),
        original_filename=str(d.get("original_filename") or ""),
    )


def _group_from_dict(d: Dict[str, Any], excluded: bool) -> DupGroup:
    members = [_member_from_dict(x) for x in (d.get("members") or [])]
    # `by_folder` 是普通字段（真扫描里由 scan() 填），导出时没写进去 —— 这里按
    # 每条的 `folder` 重建，`copies` / `folders` / `redundant_copies` 都是它的
    # property，重建好就全对了。
    by_folder: Dict[str, List[DupMember]] = {}
    for m in members:
        by_folder.setdefault(m.folder or "(未知目录)", []).append(m)
    return DupGroup(
        key=str(d.get("key") or ""),
        kind=str(d.get("kind") or "num"),
        label=str(d.get("label") or ""),
        confidence=str(d.get("confidence") or "高"),
        members=members,
        note=str(d.get("note") or ""),
        total_bytes=int(d.get("total_bytes") or 0),
        redundant_bytes=int(d.get("redundant_bytes") or 0),
        by_folder=by_folder,
        ai=dict(d.get("ai") or {}),
    )


def import_json(path: str) -> DupReport:
    """从 `export_json` 产出的文件恢复 `DupReport`（v1.33.0 反馈 1）。

    为什么要它：真机全库跑一次重复检测要 70 多秒，用户当天没处理完、明天想接着看时
    只能从头再扫一遍。导入后结果树、汇总、导出、**AI 复核**都能继续用 —— `ai` 字段
    也一并还原，所以上次跑过的 AI 结论不会丢。

    兼容两代文件：新格式是带 `_kind` 信封的 `{"report": …}`，v1.32.0 直接 dump 的
    裸 `report.as_dict()` 也认（用户手里可能有旧文件）。
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        raise ValueError("文件内容不是 JSON 对象")
    if "_kind" in raw:                                  # 新格式：带信封
        if raw.get("_kind") != "duplicates":
            raise ValueError("这不是「重复检测」的结果文件（_kind=%r）" % raw.get("_kind"))
        if int(raw.get("_format") or 0) > EXPORT_FORMAT:
            raise ValueError("结果文件来自更新的版本（格式 %s），请升级软件后再导入"
                             % raw.get("_format"))
        data = raw.get("report") or {}
    else:                                               # 旧格式：裸报告
        data = raw
    if "groups" not in data and "multipart" not in data:
        raise ValueError("文件里没有检测结果（缺 groups / multipart）")
    rep = DupReport(
        groups=[_group_from_dict(g, False) for g in (data.get("groups") or [])],
        multipart=[_group_from_dict(g, True) for g in (data.get("multipart") or [])],
        scanned=int(data.get("scanned") or 0),
        elapsed=float(data.get("elapsed") or 0.0),
        generated_at=str(data.get("generated_at") or ""),
        missing=int(data.get("missing") or 0),
        multipart_excluded=bool(data.get("multipart_excluded", True)),
        algo=str(data.get("algo") or "normal"),
        ai=dict(data.get("ai") or {}),
    )
    return rep


__all__ = [
    "DupMember", "DupGroup", "DupReport", "find_duplicates",
    "export_csv", "export_json", "import_json", "EXPORT_FORMAT",
    "human_size", "human_duration",
    "norm_num", "extract_num", "title_key", "COPYRIGHT_NOTICE",
]
