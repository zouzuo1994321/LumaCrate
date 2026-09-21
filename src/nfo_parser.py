# -*- coding: utf-8 -*-
"""
nfo 解析器
==========
刮削功能完全阉割：本模块只读取已经被 Emby / TinyMediaManager / Kodi 刮削好的 .nfo。
支持 movie.nfo / tvshow.nfo / episode.nfo (Kodi & Emby 格式)。
"""
import os
import re
import xml.etree.ElementTree as ET
from typing import Optional


def _strip_ns(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _text(el: ET.Element, tag: str) -> Optional[str]:
    found = el.find(tag)
    if found is not None and found.text:
        return found.text.strip()
    return None


def _local_image(nfo_dir: str, name: Optional[str]) -> Optional[str]:
    """把 nfo 里相对路径/URL 的图片解析为本地绝对路径(若存在)。"""
    if not name:
        return None
    if name.startswith("http://") or name.startswith("https://"):
        return name  # 远程图保留 URL
    cand = os.path.join(nfo_dir, name)
    return cand if os.path.exists(cand) else None


def _parse_actors(root: ET.Element, nfo_dir: str):
    actors = []
    for a in root.findall("actor"):
        name = _text(a, "name")
        if not name:
            continue
        thumb = _local_image(nfo_dir, _text(a, "thumb"))
        role = _text(a, "role") or ""
        ptype = _text(a, "type") or "Actor"
        actors.append({"name": name, "role": role, "thumb": thumb, "type": ptype})
    return actors


def _parse_directors(root: ET.Element):
    """导演：Kodi/Emby nfo 用 <director>姓名</director> 重复节点。"""
    out = []
    for d in root.findall("director"):
        name = (d.text or "").strip()
        if name:
            out.append({"name": name, "type": "Director", "thumb": None, "role": "导演"})
    # 个别刮削器写成 <director name="..."></director>
    for d in root.findall("director"):
        name = (d.get("name") or "").strip()
        if name and name not in {x["name"] for x in out}:
            out.append({"name": name, "type": "Director", "thumb": None, "role": "导演"})
    return out


def _fmt_runtime(v: Optional[str]) -> Optional[str]:
    """nfo 中 runtime 通常为分钟数；格式化为 HH:MM:SS。"""
    try:
        total = int(float(v))
    except (TypeError, ValueError):
        return None
    h, m = divmod(total, 60)
    return f"{h:02d}:{m:02d}:00"


def _tmdb_id(root: ET.Element) -> Optional[str]:
    for u in root.findall("uniqueid"):
        if (u.get("type") or "").lower() == "tmdb" and u.text:
            return u.text.strip()
    return _text(root, "tmdbid")


def _collection(root: ET.Element) -> Optional[str]:
    s = root.find("set")
    if s is not None:
        return _text(s, "name")
    return _text(root, "set")


# 纯技术标签（类型/标签里需过滤掉的编码 / 分辨率 / 音轨词）
_TECH_GENRE_RE = re.compile(
    r"(?i)^(\d{3,4}p|4k|8k|uhd|fhd|hd|sd|hdr10?|hdr10\+|sdr|avc1?|h26[45]|hevc|x26[45]|av1|"
    r"aac|ac3|eac3|dts|dts-?hd|dts-?x|truehd|atmos|flac|mp3|opus|10bit|8bit|hi10p|"
    r"web-?dl|web-?rip|webdl|bluray|blu-ray|bdrip|brrip|remux|hdtv|dvdrip|unknown)$"
)


def _rating(root: ET.Element):
    """评分：优先 <ratings><rating> 中 10 分制(aspect=10)或 default，其次 <rating> 文本。"""
    ten, dflt, any_ = [], [], []
    for r in root.findall("ratings/rating"):
        val = _to_float(_text(r, "value"))
        if val is None:
            continue
        mx = _to_float(r.get("max")) or 10
        any_.append(val)
        if mx == 10:
            ten.append(val)
        if (r.get("default") or "").lower() == "true":
            dflt.append(val)
    if ten:
        return ten[0]
    if dflt:
        return dflt[0]
    if any_:
        return any_[0]
    return _to_float(_text(root, "rating"))


def _genre_list(root: ET.Element):
    out = []
    for g in root.findall("genre"):
        t = (g.text or "").strip()
        if not t or _TECH_GENRE_RE.match(t):
            continue
        out.append(t)
    return out


def _premiere(root: ET.Element):
    """上映日期：<premiered> / <release> 归一化为 YYYY-MM-DD。"""
    p = _text(root, "premiered") or _text(root, "release")
    if not p:
        return None
    m = re.match(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", p)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r"(\d{4})", p)
    return m.group(1) if m else p


def _resolution(root: ET.Element) -> str:
    """从 <fileinfo><streamdetails><video> 推断画质徽章。"""
    v = root.find("fileinfo/streamdetails/video")
    if v is None:
        return ""
    h = _to_int(_text(v, "height"))
    if h:
        if h >= 2000:
            return "4K"
        if h >= 1000:
            return "1080P"
        if h >= 700:
            return "720P"
    res = (_text(v, "resolution") or "").lower()
    if res in ("2160", "2160p", "4k"):
        return "4K"
    if res in ("1080", "1080p"):
        return "1080P"
    if res in ("720", "720p"):
        return "720P"
    return ""


def _studio(root: ET.Element):
    for tag in ("studio", "maker", "publisher", "label"):
        v = _text(root, tag)
        if v:
            return v
    return None


def _extra(root: ET.Element) -> dict:
    countries = [_t.text.strip() for _t in root.findall("country") if _t.text]
    return {
        "runtime": _fmt_runtime(_text(root, "runtime")),
        "country": " / ".join(countries) if countries else None,
        "studio": _studio(root),
        "certification": _text(root, "mpaa") or _text(root, "certification"),
        "tmdb_id": _tmdb_id(root),
        "collection": _collection(root),
        "premiere": _premiere(root),
        "user_rating": _to_float(_text(root, "userrating")),
        "resolution": _resolution(root),
    }


def parse_movie(nfo_path: str) -> dict:
    root = ET.parse(nfo_path).getroot()
    root = _strip_root(root)
    d = os.path.dirname(nfo_path)
    year = None
    y = _text(root, "year")
    if y and y.isdigit():
        year = int(y)
    premiered = _text(root, "premiered") or _text(root, "release")
    if year is None and premiered:
        m = re.match(r"(\d{4})", premiered)
        if m:
            year = int(m.group(1))
    return {
        "kind": "movie",
        "title": _text(root, "title") or os.path.basename(d),
        "sort_title": _text(root, "sorttitle"),
        "year": year,
        "plot": _text(root, "plot") or _text(root, "tagline"),
        "rating": _rating(root),
        "poster": _local_image(d, _text(root, "thumb")) or _local_image(d, "poster.jpg"),
        "fanart": _local_image(d, _text(root, "fanart")) or _local_image(d, "fanart.jpg"),
        "genres": ",".join(_genre_list(root)),
        "actors": _parse_actors(root, d),
        "directors": _parse_directors(root),
        "nfo_path": nfo_path,
        "nfo_dir": d,
        **_extra(root),
    }


def parse_tvshow(nfo_path: str) -> dict:
    root = ET.parse(nfo_path).getroot()
    root = _strip_root(root)
    d = os.path.dirname(nfo_path)
    year = None
    y = _text(root, "year")
    if y and y.isdigit():
        year = int(y)
    premiered = _text(root, "premiered") or _text(root, "release")
    if year is None and premiered:
        m = re.match(r"(\d{4})", premiered)
        if m:
            year = int(m.group(1))
    return {
        "kind": "tvshow",
        "title": _text(root, "title") or os.path.basename(d),
        "sort_title": _text(root, "sorttitle"),
        "year": year,
        "plot": _text(root, "plot"),
        "rating": _rating(root),
        "poster": _local_image(d, _text(root, "thumb")) or _local_image(d, "poster.jpg"),
        "fanart": _local_image(d, _text(root, "fanart")) or _local_image(d, "fanart.jpg"),
        "genres": ",".join(_genre_list(root)),
        "actors": _parse_actors(root, d),
        "directors": _parse_directors(root),
        "nfo_path": nfo_path,
        "nfo_dir": d,
        **_extra(root),
    }


def parse_episode(nfo_path: str, parent_title: str = "", parent_id: int = None) -> dict:
    root = ET.parse(nfo_path).getroot()
    root = _strip_root(root)
    d = os.path.dirname(nfo_path)
    return {
        "kind": "episode",
        "title": _text(root, "title") or os.path.basename(nfo_path),
        "sort_title": None,
        "year": None,
        "plot": _text(root, "plot"),
        "rating": _to_float(_text(root, "rating")),
        "poster": _local_image(d, _text(root, "thumb")),
        "fanart": None,
        "season": _to_int(_text(root, "season")),
        "episode": _to_int(_text(root, "episode")),
        "genres": "",
        "actors": _parse_actors(root, d),
        "directors": _parse_directors(root),
        "nfo_path": nfo_path,
        "nfo_dir": d,
        "parent_title": parent_title,
        "parent_id": parent_id,
    }


def parse_any(nfo_path: str) -> dict:
    """按根节点类型自动分派（movie / tvshow / episodedetails）。

    v1.11.0 新增：供「演职员关联回填」（scanner.backfill_people_links）使用 ——
    旧索引里 media_people 没有导演关联，需要按 nfo 重新解析演员+导演补写。
    """
    try:
        root = _strip_root(ET.parse(nfo_path).getroot())
    except Exception:
        return {}
    tag = _strip_ns(root.tag).lower()
    if tag == "tvshow":
        return parse_tvshow(nfo_path)
    if tag == "episodedetails":
        return parse_episode(nfo_path)
    return parse_movie(nfo_path)


def _strip_root(root: ET.Element) -> ET.Element:
    """去掉命名空间，便于按标签名查找。"""
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _to_float(v: Optional[str]):
    try:
        return float(v) if v else None
    except (TypeError, ValueError):
        return None


def write_user_rating(nfo_path: str, value) -> bool:
    """把用户评分写回 nfo 的 <userrating>（Kodi/Emby 字段）。

    仅改动 <userrating> 节点，保留其它内容；value 为 None 时删除该节点。
    返回是否写入成功。
    """
    if not nfo_path or not os.path.exists(nfo_path):
        return False
    try:
        tree = ET.parse(nfo_path)
        root = tree.getroot()
        # 移除已有的 <userrating>（忽略命名空间），避免重复
        for el in list(root):
            if _strip_ns(el.tag) == "userrating":
                root.remove(el)
        if value is not None:
            ur = ET.SubElement(root, "userrating")
            ur.text = f"{float(value):.1f}"
        try:
            ET.indent(tree, space="  ")
        except Exception:
            pass
        tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
        return True
    except Exception:
        return False


def _to_int(v: Optional[str]):
    try:
        return int(v) if v else None
    except (TypeError, ValueError):
        return None


def read_genres(nfo_path: str):
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


def write_genres(nfo_path: str, genres) -> bool:
    """把标签写回 nfo 的 `<genre>` 节点（v1.25.0「标签优化」用）。

    只动 `<genre>`：先摘掉全部已有 `<genre>`，再**在原来第一个 `<genre>` 的位置**把新的插回去 ——
    这样文件其它部分（演员 / 评分 / 图片引用 / 简介 / uniqueid…）连缩进都不受影响。
    传空列表即清空标签（节点全部移除，不留空 `<genre/>`）。返回是否写入成功。
    """
    if not nfo_path or not os.path.exists(nfo_path):
        return False
    items = [str(g).strip() for g in (genres or []) if str(g).strip()]
    try:
        tree = ET.parse(nfo_path)
        root = tree.getroot()
        kids = list(root)
        first = next((i for i, el in enumerate(kids) if _strip_ns(el.tag) == "genre"), None)
        for el in kids:
            if _strip_ns(el.tag) == "genre":
                root.remove(el)
        pos = len(list(root)) if first is None else min(first, len(list(root)))
        for off, g in enumerate(items):
            el = ET.Element("genre")
            el.text = g
            root.insert(pos + off, el)
        try:
            ET.indent(tree, space="  ")
        except Exception:
            pass
        tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
        return True
    except Exception:
        return False
