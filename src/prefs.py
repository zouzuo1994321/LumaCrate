# -*- coding: utf-8 -*-
"""偏好管理（v1.43.0）
=====================
把「**个人偏好**」从索引里单独拎出来备份 / 恢复 —— 它们与文件路径无关，
换目录、换电脑、重新刮削覆盖了 nfo，都应该能一键找回。

备份内容（单个 JSON，跨版本可读）：
  · media[]  —— 每部片一条，键是**番号**（`mide823` 这种归一化形式）：
                favorite（收藏）/ play_count（观看次数）/ last_played（最近播放）/
                user_rating（用户评分）
  · people[] —— 演员库 / 导演库里 favorite（收藏）或 pinned（置顶）的人，
                键是 name + role_type
  · meta     —— 版本 / 导出时间 / 条数

恢复时：
  · 影片按**番号**匹配（番号从 file_path / title 提取，与「重复检测」同一套
    归一化规则），同一番号的多个副本（CD 分片）一起更新；
  · 用户评分**同时写回 nfo** 的 `<userrating>`（nfo 被重新刮削覆盖后也能恢复）；
  · 人物按 name（+ role_type）匹配。

设计取舍：只导出「非默认值」，文件很小（几千部片也就几百 KB）；
导入是**逐条 UPDATE**，不删任何数据、不覆盖资料字段，可反复执行。
"""
import json
import os
from datetime import datetime

import database as db
import duplicates
import nfo_parser as nfo_mod
import version as ver


def prefs_export_name() -> str:
    return f"{ver.APP_NAME}-偏好-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"


# ---------- v1.46.12：进度回调 ----------
# 为什么要有：导入/导出原来**同步跑在 GUI 线程**，实测一次导入 7.09s
# （其中 415 个 nfo 回写占 4.24s、结尾整页刷新占 1.4s），期间事件循环
# 一次都不跳 → Windows 5 秒就判「未响应」，用户还以为卡死了。
# 现在这两件事都能给一个 `progress(done, total, label)` 回调，由界面
# 搬到后台线程并画进度条；回调**返回 True** 表示「用户要求停止」。

def _tick(progress, done, total, label) -> bool:
    """统一出口：没有回调就什么都不做；回调抛异常只当「不停止」。

    返回 True = 调用方要求中止。
    """
    if progress is None:
        return False
    try:
        return bool(progress(int(done), int(total), str(label)))
    except Exception:
        return False


#: 导出范围（v1.44.2，保留兼容）
SCOPES = (("all", "全部偏好（收藏 + 观看 + 评分）"),
          ("favorite", "仅收藏"),
          ("rating", "仅用户评分"))

#: v1.45.5（反馈 4）：**可勾选**的导出项（导出什么由用户决定）
INCLUDE_ITEMS = (("favorite", "收藏状态"),
                 ("play", "观看次数 / 最近播放"),
                 ("rating", "用户评分（同时写回 nfo）"),
                 ("people", "演员 / 导演的收藏与置顶"),
                 ("gender", "演员性别"))


def _media_rows(scope="all"):
    conn = db.get_conn()
    base = ("SELECT id, title, file_path, nfo_path, favorite, play_count, "
            "last_played, user_rating FROM media WHERE ")
    if scope == "favorite":
        sql = base + "COALESCE(favorite,0)=1 ORDER BY id"
    elif scope == "rating":
        sql = base + "COALESCE(user_rating,0)>0 ORDER BY id"
    else:
        sql = (base + "COALESCE(favorite,0)=1 OR COALESCE(play_count,0)>0 "
               "OR (last_played IS NOT NULL AND last_played>0) "
               "OR COALESCE(user_rating,0)>0 ORDER BY id")
    return [dict(r) for r in conn.execute(sql).fetchall()]


def _people_rows():
    conn = db.get_conn()
    sql = ("SELECT name, role_type, favorite, pinned, gender FROM people "
           "WHERE COALESCE(favorite,0)=1 OR COALESCE(pinned,0)=1 "
           "ORDER BY role_type, name")
    return [dict(r) for r in conn.execute(sql).fetchall()]


def export_prefs(dest_json: str, scope: str = "all", include=None,
                 progress=None) -> dict:
    """导出偏好到 JSON。返回 {'ok','path','media','people','no_code','include'}。

    `include`（v1.45.5）：勾选项集合 —— "favorite" / "play" / "rating" / "people" / "gender"。
    只写勾选的字段；导入侧本来就是「键存在才写」，所以空字段不会误清对方的值。

    `progress`（v1.46.12）：`progress(done, total, label)`，返回 True 表示中止
    （中止时**不写文件**，返回 {'ok': False, 'cancelled': True}）。
    """
    inc = set(include) if include else {"favorite", "play", "rating", "people", "gender"}
    if not inc:
        inc = {"favorite", "play", "rating", "people", "gender"}
    try:
        _tick(progress, 0, 0, "正在读取偏好记录…")
        rows = _media_rows(scope)
        media, seen, no_code = [], {}, 0
        n_all = len(rows)
        _tick(progress, 0, n_all, f"整理影片偏好 0/{n_all}")
        for i, r in enumerate(rows, 1):
            if i % 100 == 0 and _tick(progress, i, n_all,
                                      f"整理影片偏好 {i}/{n_all}"):
                return {"ok": False, "cancelled": True}
            code = duplicates.extract_num(r.get("file_path"), r.get("title"))
            if not code:
                # 没有番号的片子（剧集 / 纪录片）用标题兜底，仍可恢复
                key = "t:" + (r.get("title") or "").strip().lower()
                if not key.strip():
                    no_code += 1
                    continue
            else:
                key = "n:" + code
            item = seen.get(key)
            if item is None:
                item = {"num": code, "title": r.get("title") or ""}
                if "favorite" in inc:
                    item["favorite"] = 0
                if "play" in inc:
                    item["play_count"] = 0
                    item["last_played"] = None
                if "rating" in inc:
                    item["user_rating"] = None
                seen[key] = item
                media.append(item)
            # 同番号的多个副本（CD 分片）合并：取最大值，评分取最后非空
            if "favorite" in inc:
                item["favorite"] = max(int(item["favorite"] or 0),
                                       int(r.get("favorite") or 0))
            if "play" in inc:
                item["play_count"] = max(int(item["play_count"] or 0),
                                         int(r.get("play_count") or 0))
                lp = r.get("last_played")
                if lp:
                    item["last_played"] = max(float(item["last_played"] or 0), float(lp))
            if "rating" in inc:
                ur = r.get("user_rating")
                if ur is not None and float(ur or 0) > 0:
                    item["user_rating"] = float(ur)

        people = []
        if "people" in inc or "gender" in inc:
            _tick(progress, n_all, n_all, "正在整理人物收藏 / 置顶…")
            for p in _people_rows():
                if not p.get("name"):
                    continue
                it = {"name": p.get("name"),
                      "role_type": p.get("role_type") or "Actor"}
                if "people" in inc:
                    it["favorite"] = int(p.get("favorite") or 0)
                    it["pinned"] = int(p.get("pinned") or 0)
                if "gender" in inc:
                    it["gender"] = (p.get("gender") or "")
                people.append(it)

        if _tick(progress, n_all, n_all,
                 f"正在写入文件（影片 {len(media)} 条 · 人物 {len(people)} 位）…"):
            return {"ok": False, "cancelled": True}       # 写盘前还有机会停
        payload = {
            "type": "lmc-prefs",
            "app": ver.APP_NAME,
            "version": ver.FULL_VERSION,
            "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "counts": {"media": len(media), "people": len(people),
                       "no_code": no_code},
            "scope": scope,
            "include": sorted(inc),
            "media": media,
            "people": people,
        }
        d = os.path.dirname(dest_json)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(dest_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        return {"ok": True, "path": dest_json, "media": len(media),
                "people": len(people), "no_code": no_code}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _num_index(conn, progress=None):
    """番号 / 标题兜底键 → [media 行]（一次性建索引，避免逐条全表扫）。"""
    total = 0
    try:
        total = int(conn.execute("SELECT COUNT(*) FROM media").fetchone()[0])
    except Exception:
        pass
    _tick(progress, 0, total, f"正在建立番号索引 0/{total}")
    idx = {}
    for i, r in enumerate(conn.execute(
            "SELECT id, title, file_path, nfo_path FROM media"), 1):
        code = duplicates.extract_num(r["file_path"], r["title"])
        key = ("n:" + code) if code else ("t:" + (r["title"] or "").strip().lower())
        idx.setdefault(key, []).append(dict(r))
        if i % 2000 == 0:
            _tick(progress, i, total, f"正在建立番号索引 {i}/{total}")
    _tick(progress, total, total, f"番号索引就绪（{len(idx)} 个键），开始合并…")
    return idx


def import_prefs(src_json: str, dry_run: bool = False, progress=None) -> dict:
    """从 JSON 恢复偏好（合并式；不删数据）。返回统计。

    `progress`（v1.46.12）：`progress(done, total, label)`，返回 True 表示中止。
    中止时**已处理的部分照常提交**（合并式操作可反复执行，不会写坏数据），
    返回值里带 `cancelled: True`。
    """
    try:
        _tick(progress, 0, 0, "正在读取备份文件…")
        with open(src_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("type") != "lmc-prefs":
            return {"ok": False, "error": "不是偏好备份文件（缺少 type=lmc-prefs）"}
        conn = db.get_conn()
        idx = _num_index(conn, progress)

        items = data.get("media") or []
        n_items = len(items)
        _tick(progress, 0, n_items, f"正在合并影片偏好 0/{n_items}")
        m_ok = m_miss = nfo_ok = 0
        cancelled = False
        for i, it in enumerate(items, 1):
            if i % 25 == 0 and _tick(
                    progress, i, n_items,
                    f"正在合并影片偏好 {i}/{n_items}（已写回 nfo {nfo_ok}）"):
                cancelled = True
                break
            code = (it.get("num") or "").strip().lower()
            key = ("n:" + code) if code else \
                  ("t:" + (it.get("title") or "").strip().lower())
            rows = idx.get(key) or []
            if not rows:
                m_miss += 1
                continue
            sets, vals = [], []
            if "favorite" in it:
                sets.append("favorite=?")
                vals.append(int(it.get("favorite") or 0))
            if "play_count" in it:
                sets.append("play_count=?")
                vals.append(int(it.get("play_count") or 0))
            if it.get("last_played"):
                sets.append("last_played=?")
                vals.append(float(it["last_played"]))
            # v1.44.2：0 分也要能恢复/清空 —— 只有「键不存在 / None」才跳过
            if it.get("user_rating") is not None:
                sets.append("user_rating=?")
                vals.append(float(it.get("user_rating") or 0))
            if not sets:
                m_miss += 1
                continue
            if not dry_run:
                for r in rows:
                    conn.execute(f"UPDATE media SET {','.join(sets)} WHERE id=?",
                                 vals + [r["id"]])
            m_ok += 1
            # 评分回写 nfo（这一条是本功能的核心：nfo 被覆盖也能恢复评分）
            # v1.44.2：0 分也要处理 —— 传 None 给 write_user_rating 会**删掉**
            # `<userrating>` 节点，等价于「把评分清空」。
            if it.get("user_rating") is not None and not dry_run:
                for r in rows:
                    if r.get("nfo_path") and \
                            nfo_mod.write_user_rating(r["nfo_path"],
                                                      it.get("user_rating") or None):
                        nfo_ok += 1
                        break

        p_ok = p_miss = 0
        ppl = data.get("people") or []
        n_ppl = len(ppl)
        if cancelled:
            _tick(progress, n_items, n_items,
                  f"已停止合并影片（影片 {m_ok} 条 · nfo {nfo_ok} 个）")
        elif _tick(progress, n_items, n_items,
                   f"影片合并完成 {m_ok} 条，正在合并人物偏好 0/{n_ppl}"):
            cancelled = True              # 人物阶段前停下也算「停止」
        for j, p in enumerate(([] if cancelled else ppl), 1):
            if j % 50 == 0:
                _tick(progress, n_items, n_items,
                      f"正在合并人物偏好 {j}/{n_ppl}")
            name = (p.get("name") or "").strip()
            if not name:
                p_miss += 1
                continue
            role = (p.get("role_type") or "").strip()
            _has_fav = ("favorite" in p) or ("pinned" in p)
            _has_g = "gender" in p
            if dry_run:
                cur = conn.execute(
                    "SELECT 1 FROM people WHERE name=?" + (" AND role_type=?" if role else ""),
                    (name, role) if role else (name,))
                hit = cur.fetchone() is not None
            else:
                _sets, _vals = [], []
                if _has_fav:
                    _sets += ["favorite=?", "pinned=?"]
                    _vals += [int(p.get("favorite") or 0), int(p.get("pinned") or 0)]
                if _has_g:
                    _sets.append("gender=?")
                    _vals.append(str(p.get("gender") or ""))
                if not _sets:
                    hit = False
                else:
                    _where = "name=?" + (" AND role_type=?" if role else "")
                    _params = (_vals + [name, role]) if role else (_vals + [name])
                    cur = conn.execute("UPDATE people SET " + ", ".join(_sets)
                                       + " WHERE " + _where, _params)
                hit = bool(cur.rowcount)
            if hit:
                p_ok += 1
            else:
                p_miss += 1
        if not dry_run:
            _tick(progress, n_items, n_items, "正在提交改动…")
            conn.commit()
        return {"ok": True, "dry_run": bool(dry_run), "cancelled": bool(cancelled),
                "media_ok": m_ok, "media_miss": m_miss,
                "people_ok": p_ok, "people_miss": p_miss, "nfo_written": nfo_ok,
                "stamp": data.get("exported_at") or ""}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
