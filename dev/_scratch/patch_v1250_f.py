# -*- coding: utf-8 -*-
"""v1.25.0 补丁 F —— 修「标签优化」会悄悄删掉技术标签的契约漏洞。

问题（写 smoke 时发现的根因）：
    `TagOptimizer.plan_one()` 的 `before` 来自 `nfo_parser.parse_any()` 的 `genres`，
    而那个字段是**给卡片徽章用的、已经滤掉技术标签**（1080p / HEVC / WEB-DL…）。
    于是 `plan_one` 根本不知道磁盘上还有 `<genre>1080p</genre>`，
    `apply()` 写回时它就被删了 —— 与本模块文档里「**原有标签一个不丢**」的承诺矛盾。

修法：
    1) nfo_parser 增加 `read_genres()`：读**全部** `<genre>` 原文，不过滤；
    2) tagopt.plan_one 的 `before` 改从 `read_genres()` 取（取不到才退回旧路径）；
    3) 共现的种子词排除技术标签，保持喂给算法的输入与修前一致。
"""
import io
import os

ROOT = r"Z:/【01】自研软件/【26-19】本地影视中心"
SRC = os.path.join(ROOT, "src")


def patch(rel, label, old, new, count=1):
    p = os.path.join(SRC, rel)
    s = io.open(p, encoding="utf-8", newline="").read()
    got = s.count(old)
    if got != count:
        raise SystemExit(f"[ABORT] {rel} / {label}: 锚点命中 {got} 次（期望 {count}）\n---\n{old[:400]}")
    s = s.replace(old, new, count)
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    print(f"[OK] {rel} / {label}")


# --------------------------------------------------------------------------- 1
READ_GENRES = '''def read_genres(nfo_path: str):
    """读出一个 nfo 里**全部** `<genre>` 原文（不过滤技术标签，保持文件顺序）。

    v1.25.0「标签优化」用：`parse_*()` 返回的 `genres` 会顺手滤掉 1080p / HEVC 这类
    技术标签（那是给卡片徽章用的），但**写回标签**时必须以磁盘上的原文为准 ——
    否则「补全标签」这种只该做加法的操作，会把 `<genre>1080p</genre>` 一起写没。
    """
    if not nfo_path or not os.path.exists(nfo_path):
        return []
    try:
        root = _strip_root(ET.parse(nfo_path).getroot())
    except Exception:
        return []
    out = []
    for g in root.findall("genre"):
        t = (g.text or "").strip()
        if t and t not in out:
            out.append(t)
    return out


def write_genres(nfo_path: str, genres) -> bool:'''

patch("nfo_parser.py", "read_genres",
      "def write_genres(nfo_path: str, genres) -> bool:",
      READ_GENRES)

# --------------------------------------------------------------------------- 2
patch("tagopt.py", "plan_one: before 取磁盘原文",
      '''        title = str(info.get("title") or "")
        out["title"] = title
        before = [clean_tag(t) for t in str(info.get("genres") or "").split(",")]
        before = [t for t in before if t]
        out["before"] = before
        after = list(before)''',
      '''        title = str(info.get("title") or "")
        out["title"] = title
        # v1.25.0：`before` 取**磁盘上的原文**（含 1080p / HEVC 这类技术标签）。
        # parse_*() 的 genres 是给卡片徽章用的、已经滤过技术标签；拿它当 before 的话，
        # 「补全标签」会把 <genre>1080p</genre> 一起写没，违反本模块「原有标签一个不丢」的承诺。
        before = []
        for t in (nfo_parser.read_genres(nfo) or []):
            t = clean_tag(t)
            if t and t not in before:
                before.append(t)
        if not before:                      # 兜底：read_genres 读不到时退回旧路径
            before = [clean_tag(t) for t in str(info.get("genres") or "").split(",")]
            before = [t for t in before if t]
        out["before"] = before
        after = list(before)''')

# --------------------------------------------------------------------------- 3
patch("tagopt.py", "共现种子排除技术标签",
      "        plain_seed = [t for t in after if not t.startswith(PREFIXES)][:60]",
      "        # 种子词别喂技术标签（1080p / HEVC…）—— 共现里它们只会污染候选\n"
      "        plain_seed = [t for t in after\n"
      "                      if not t.startswith(PREFIXES) and not is_tech(t)][:60]")

print("\n[ALL DONE]")
