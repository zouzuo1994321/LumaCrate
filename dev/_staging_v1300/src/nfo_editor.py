# -*- coding: utf-8 -*-
"""nfo 编辑器（v1.30.0）
=====================
把一部影片的 .nfo **读成可编辑的字典**、再**原地写回**（只动被编辑的节点，
其它内容连缩进都不受影响；写前自动留一份 `*.nfo.bak-<时间戳>`）。

设计口径与 `nfo_parser` 一致：刮削功能是阉割的，本模块只负责「人工手动改」。
字段覆盖 tinyMediaManager / Kodi 的常用集，含多值（标签 / 国家 / 导演）与演员块
（`<actor><name>..<role>..`；写回时**按姓名复用原节点**，从而保住 `<thumb>` 头像）。

纯计算 + 磁盘 IO（唯一例外是 `save()` 里的 `database.update_media_fields`，
为的是让索引与磁盘同步），不 import Qt，便于离屏单测。
"""
import os
import re
import time
import xml.etree.ElementTree as ET

import database as db

#: (键, 中文标签, 类型)。类型：text / multiline / multi / int
#: multi = 多个同名节点（genre / country / director）；actor 单独处理。
FIELDS = [
    ("title",         "标题",       "text"),
    ("originaltitle", "原始标题",   "text"),
    ("sorttitle",     "排序标题",   "text"),
    ("year",          "年份",       "text"),
    ("premiered",     "上映日期",   "text"),
    ("runtime",       "时长（分钟）", "text"),
    ("rating",        "评分",       "text"),
    ("userrating",    "用户评分",   "text"),
    ("mpaa",          "分级",       "text"),
    ("studio",        "片商",       "text"),
    ("set",           "合集",       "text"),
    ("country",       "国家",       "multi"),
    ("genre",         "标签",       "multi"),
    ("director",      "导演",       "multi"),
    ("tagline",       "标语",       "text"),
    ("plot",          "简介",       "multiline"),
    ("outline",       "概要",       "multiline"),
]
MULTI_KEYS = [k for k, _l, t in FIELDS if t == "multi"]
FIELD_LABEL = {k: l for k, l, _t in FIELDS}


def _strip_ns(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _kids(root, tag):
    return [el for el in list(root) if _strip_ns(el.tag) == tag]


def _first(root, tag):
    got = _kids(root, tag)
    return got[0] if got else None


def _txt(root, tag):
    el = _first(root, tag)
    return (el.text or "").strip() if el is not None and el.text else ""


def _read_tree(nfo_path):
    if not nfo_path or not os.path.exists(nfo_path):
        return None
    try:
        tree = ET.parse(nfo_path)
    except Exception:
        return None
    root = tree.getroot()
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return tree, root


def read_fields(nfo_path):
    """读出一个 nfo 的可编辑字段。文件不存在/损坏 → 返回空表（不抛）。"""
    got = _read_tree(nfo_path)
    if got is None:
        return {}
    _tree, root = got
    out = {}
    for key, _label, kind in FIELDS:
        if kind == "multi":
            out[key] = [(_t.text or "").strip() for _t in _kids(root, key) if (_t.text or "").strip()]
        elif key == "set":
            s = _first(root, "set")
            out[key] = _txt(s, "name") if s is not None else _txt(root, "set")
        else:
            out[key] = _txt(root, key)
    # 演员
    actors = []
    for a in _kids(root, "actor"):
        name = _txt(a, "name")
        if name:
            actors.append({"name": name, "role": _txt(a, "role")})
    out["actor"] = actors
    return out


def from_media(media):
    """给界面用的初值：**优先 nfo 文件**，没有 nfo 就退回数据库里已有的值。"""
    m = dict(media or {})
    data = {}
    nfo_path = m.get("nfo_path") or ""
    data.update(read_fields(nfo_path))
    data.setdefault("actor", [])
    # 数据库兜底（nfo 里没有的项用索引里的值填上，用户看到的是「现在生效的」）
    def _fill(key, value):
        if value in (None, ""):
            return
        cur = data.get(key)
        if isinstance(cur, list):
            if not cur:
                data[key] = [value] if key != "actor" else cur
        elif not cur:
            data[key] = str(value)

    _fill("title", m.get("title"))
    _fill("sorttitle", m.get("sort_title"))
    _fill("year", m.get("year"))
    _fill("premiered", m.get("premiere"))
    _fill("rating", m.get("rating"))
    _fill("userrating", m.get("user_rating"))
    _fill("studio", m.get("studio"))
    _fill("set", m.get("collection"))
    _fill("plot", m.get("plot"))
    _fill("mpaa", m.get("certification"))
    if not data.get("country") and m.get("country"):
        data["country"] = [c.strip() for c in str(m["country"]).split("/") if c.strip()]
    if not data.get("genre") and m.get("genres"):
        data["genre"] = [g.strip() for g in str(m["genres"]).split(",") if g.strip()]
    if not data.get("runtime") and m.get("runtime"):
        mm_ = _minutes(m.get("runtime"))
        data["runtime"] = str(mm_) if mm_ is not None else str(m.get("runtime"))
    data["nfo_path"] = nfo_path
    data["nfo_exists"] = bool(nfo_path and os.path.exists(nfo_path))
    return data


def _minutes(runtime):
    """'HH:MM:SS' → 分钟（nfo 里 runtime 是分钟）。"""
    try:
        parts = str(runtime).split(":")
        if len(parts) == 3:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(float(runtime))
    except (TypeError, ValueError):
        return None


def _hhmmss(minutes):
    try:
        total = int(float(minutes))
    except (TypeError, ValueError):
        return None
    h, m = divmod(total, 60)
    return f"{h:02d}:{m:02d}:00"


# ---------------- 写回 ----------------

def _set_scalar(root, tag, value):
    """写入单值节点：存在就改文本，不存在就追加（放在文件末尾，与 Kodi 习惯一致）。"""
    els = _kids(root, tag)
    if value in (None, ""):
        for el in els:
            root.remove(el)
        return
    if els:
        els[0].text = str(value)
        for extra in els[1:]:
            root.remove(extra)
    else:
        el = ET.Element(tag)
        el.text = str(value)
        root.append(el)


def _set_set(root, value):
    """`<set><name>X</name></set>` 特殊结构。"""
    s = _first(root, "set")
    if value in (None, ""):
        if s is not None:
            root.remove(s)
        for el in _kids(root, "set"):
            root.remove(el)
        return
    if s is None:
        s = ET.Element("set")
        root.append(s)
    nm = _first(s, "name")
    if nm is None:
        nm = ET.SubElement(s, "name")
    nm.text = str(value)
    s.text = None


def _set_multi(root, tag, values):
    """多值节点：**在原来第一个的位置**插回，其余内容与缩进不受影响。"""
    items = [str(v).strip() for v in (values or []) if str(v).strip()]
    kids = list(root)
    first = next((i for i, el in enumerate(kids) if _strip_ns(el.tag) == tag), None)
    for el in kids:
        if _strip_ns(el.tag) == tag:
            root.remove(el)
    pos = len(list(root)) if first is None else min(first, len(list(root)))
    for off, v in enumerate(items):
        el = ET.Element(tag)
        el.text = v
        root.insert(pos + off, el)


def _set_actors(root, actors):
    """重建 `<actor>` 块；**同名的复用原节点**（保住 <thumb>/<type>）。"""
    old = {}
    for a in _kids(root, "actor"):
        nm = _txt(a, "name")
        if nm and nm not in old:
            old[nm] = a
    for a in _kids(root, "actor"):
        root.remove(a)
    for item in (actors or []):
        name = str((item or {}).get("name") or "").strip()
        if not name:
            continue
        el = old.get(name)
        if el is None:
            el = ET.Element("actor")
            n = ET.SubElement(el, "name")
            n.text = name
        role = str((item or {}).get("role") or "").strip()
        r = _first(el, "role")
        if role:
            if r is None:
                r = ET.SubElement(el, "role")
            r.text = role
        elif r is not None:
            el.remove(r)
        root.append(el)


def write_fields(nfo_path, data, backup=True):
    """把字段写回 nfo（原地，只动被编辑的节点）。返回 (ok, err)。"""
    if not nfo_path:
        return False, "该影片没有 nfo 路径"
    if not os.path.exists(nfo_path):
        return False, f"nfo 文件不存在：{nfo_path}"
    got = _read_tree(nfo_path)
    if got is None:
        return False, "nfo 解析失败（文件可能损坏）"
    tree, root = got
    for key, _label, kind in FIELDS:
        val = (data or {}).get(key)
        if kind == "multi":
            _set_multi(root, key, val or [])
        elif key == "set":
            _set_set(root, val)
        else:
            _set_scalar(root, key, val)
    _set_actors(root, (data or {}).get("actor") or [])
    bak = ""
    if backup:
        bak = f"{nfo_path}.bak-{time.strftime('%Y%m%d%H%M%S')}"
        try:
            with open(nfo_path, "rb") as fi, open(bak, "wb") as fo:
                fo.write(fi.read())
        except OSError:
            bak = ""
    try:
        try:
            ET.indent(tree, space="  ")
        except Exception:
            pass
        tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
    except Exception as e:
        return False, f"写入失败：{type(e).__name__}: {e}"
    return True, bak


def save(media, data):
    """保存：写 nfo（带备份） + 同步数据库。返回结果摘要 dict。"""
    m = dict(media or {})
    nfo_path = m.get("nfo_path") or ""
    ok, bak = write_fields(nfo_path, data)
    res = {"nfo_path": nfo_path, "nfo_ok": ok, "backup": bak if ok else "",
           "db_ok": False, "err": ""}
    if not ok:
        res["err"] = bak
    # 同步数据库（不管 nfo 写没写成失败都尽量同步 —— 至少让索引与用户看到的一致）
    fields = {}
    if data.get("title"):
        fields["title"] = str(data["title"]).strip()
    if data.get("sorttitle"):
        fields["sort_title"] = str(data["sorttitle"]).strip()
    y = str(data.get("year") or "").strip()
    if y.isdigit():
        fields["year"] = int(y)
    if data.get("premiered"):
        fields["premiere"] = str(data["premiered"]).strip()
    if isinstance(data.get("genre"), list):
        fields["genres"] = ",".join(str(g).strip() for g in data["genre"] if str(g).strip())
    if data.get("studio") is not None:
        fields["studio"] = str(data.get("studio") or "").strip()
    if data.get("set") is not None:
        fields["collection"] = str(data.get("set") or "").strip()
    if isinstance(data.get("country"), list):
        fields["country"] = " / ".join(str(c).strip() for c in data["country"] if str(c).strip())
    if data.get("plot") is not None:
        fields["plot"] = str(data.get("plot") or "")
    rt = _hhmmss(data.get("runtime"))
    if rt:
        fields["runtime"] = rt
    try:
        if data.get("rating") not in (None, ""):
            fields["rating"] = float(data["rating"])
    except (TypeError, ValueError):
        pass
    try:
        if data.get("userrating") not in (None, ""):
            fields["user_rating"] = float(data["userrating"])
    except (TypeError, ValueError):
        pass
    try:
        if m.get("id") and fields:
            db.update_media_fields(int(m["id"]), **fields)
            res["db_ok"] = True
        res["db_fields"] = sorted(fields.keys())
    except Exception as e:
        res["err"] = (res["err"] or "") + f" 数据库同步失败：{type(e).__name__}: {e}"
    return res
