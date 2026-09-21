# -*- coding: utf-8 -*-
"""数据导出 / 导入（v1.13.0 新增）
=================================
把「处理与扫描过的信息」导出成一个 zip 备份，日后可导入用于**恢复数据库**。

备份包内容：
  · media_center.db   —— SQLite 快照（media / people / media_people 三表，用 sqlite3 的
                        backup API 生成一致性快照，避免直接拷文件时写坏）
  · settings.json     —— 媒体库配置 / 外观 / 刮削设置等（若有）
  · backup_info.txt   —— 版本号与导出时间，便于识别

导入时会先把现有文件另存为 `.bak-<时间戳>`，再覆盖，避免误操作不可逆。
"""
import os
import sys
import json
import shutil
import sqlite3
import zipfile
import tempfile
from datetime import datetime

import config as cfg
import database as db
import version as ver


def _default_name(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"


def data_export_name() -> str:
    return _default_name(f"{ver.APP_NAME}-数据备份")


def log_export_name() -> str:
    return _default_name(f"{ver.APP_NAME}-日志")


def _snapshot_db(tmp_db: str) -> bool:
    """用 sqlite backup API 生成一致性快照。"""
    src = db.db_path()
    if not os.path.exists(src):
        return False
    s = sqlite3.connect(src)
    try:
        d = sqlite3.connect(tmp_db)
        try:
            s.backup(d)
        finally:
            d.close()
    finally:
        s.close()
    return True


# ---------------------------------------------------------------------------
# v1.24.0（反馈 9）：**分类导出 / 导入**
# ---------------------------------------------------------------------------
# 需求：数据导出不该只有「整个数据库一把梭」，用户要能只导出「影片收藏」「演员收藏」
# 这类轻量信息（换机器时只想搬收藏，不想搬 15 万条索引）。
# 于是新增「分段导出」：每段一个 json，导入时按段**合并**（不是覆盖整库）。
_SECTION_QUERIES = {
    # 段名: (SQL, 主键列)
    "media": ("SELECT * FROM media ORDER BY id", "id"),
    "people": ("SELECT * FROM people ORDER BY id", None),
    "links": ("SELECT media_id, person_id, char_role, person_order FROM media_people", None),
    "favorite": ("SELECT id, title, file_path, favorite FROM media WHERE COALESCE(favorite,0)=1 "
                 "ORDER BY id", "id"),
    "play": ("SELECT id, title, play_count, last_played FROM media "
             "WHERE COALESCE(play_count,0)>0 OR (last_played IS NOT NULL AND last_played<>'') "
             "ORDER BY id", "id"),
    "userrating": ("SELECT id, title, user_rating FROM media "
                   "WHERE user_rating IS NOT NULL AND user_rating>0 ORDER BY id", "id"),
    "people_fav": ("SELECT id, name, role_type, favorite, pinned FROM people "
                   "WHERE COALESCE(favorite,0)=1 OR COALESCE(pinned,0)=1 ORDER BY id", "id"),
}
_SECTION_CN = {
    "media": "媒体索引", "people": "演员与导演资料", "links": "作品与人的关联",
    "favorite": "影片收藏", "play": "观看次数 / 最近播放", "userrating": "用户评分",
    "people_fav": "演员 / 导演 的收藏与置顶", "config": "媒体库与界面设置",
}


def _query_json(conn, sql):
    cur = conn.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def export_sections(dest_zip: str, sections) -> dict:
    """按段导出（v1.24.0 反馈 9）。返回 {'ok','path','items','counts'}。"""
    try:
        sections = [s for s in (sections or []) if s in _SECTION_QUERIES or s == "config"]
        if not sections:
            return {"ok": False, "error": "没有选择任何导出内容"}
        tmp_db = None
        counts = {}
        with tempfile.TemporaryDirectory(prefix="lmc_sec_") as td:
            tmp_db = os.path.join(td, "media_center.db")
            has_db = _snapshot_db(tmp_db)
            if not has_db:
                tmp_db = None
            info = (f"{ver.APP_NAME} 分类导出\n"
                    f"版本：{ver.FULL_VERSION}\n"
                    f"导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"包含分段：{'、'.join(_SECTION_CN.get(s, s) for s in sections)}\n")
            meta = {"type": "lmc-sections", "version": ver.FULL_VERSION,
                    "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "sections": sections, "counts": {}}
            with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as z:
                if tmp_db is not None:
                    conn = sqlite3.connect(tmp_db)
                    try:
                        for s in sections:
                            if s == "config":
                                continue
                            sql, _pk = _SECTION_QUERIES[s]
                            rows = _query_json(conn, sql)
                            counts[s] = len(rows)
                            z.writestr(f"{s}.json",
                                       json.dumps(rows, ensure_ascii=False))
                    finally:
                        conn.close()
                else:
                    # 没有索引文件就退化为「直接从连接读」
                    for s in sections:
                        if s == "config":
                            continue
                        sql, _pk = _SECTION_QUERIES[s]
                        counts[s] = 0
                        z.writestr(f"{s}.json", "[]")
                if "config" in sections:
                    sp = cfg.config_path()
                    if os.path.exists(sp):
                        tmp_set = os.path.join(td, "settings.json")
                        shutil.copy(sp, tmp_set)
                        z.write(tmp_set, arcname="settings.json")
                        counts["config"] = 1
                meta["counts"] = counts
                z.writestr("sections.json", json.dumps(meta, ensure_ascii=False, indent=2))
                z.writestr("backup_info.txt", info)
        return {"ok": True, "path": dest_zip, "items": sections, "counts": counts}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def import_sections(src_zip: str) -> dict:
    """导入「分类导出」的包：按段**合并**进现有数据（不替换整库）。"""
    stats = {}
    try:
        with zipfile.ZipFile(src_zip) as z:
            names = set(z.namelist())
            if "sections.json" not in names:
                return {"ok": False, "error": "不是分类导出包（缺少 sections.json）"}
            meta = json.loads(z.read("sections.json").decode("utf-8", "replace"))
            db.close_all()                     # 覆盖文件前先放掉连接（与整库导入一致）
            dst = db.db_path()
            ts = _stamp()
            if os.path.exists(dst):
                shutil.copy(dst, dst + f".bak-{ts}")
            conn = sqlite3.connect(dst)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                for s in meta.get("sections", []):
                    if s == "config" or s not in _SECTION_QUERIES:
                        continue
                    key = f"{s}.json"
                    if key not in names:
                        continue
                    rows = json.loads(z.read(key).decode("utf-8", "replace"))
                    stats[s] = _merge_rows(conn, s, rows)
                conn.commit()
            finally:
                conn.close()
            if "settings.json" in names:
                sp = cfg.config_path()
                os.makedirs(os.path.dirname(sp) or ".", exist_ok=True)
                if os.path.exists(sp):
                    shutil.copy(sp, sp + f".bak-{ts}")
                with z.open("settings.json") as fsrc, open(sp, "wb") as fdst:
                    shutil.copyfileobj(fsrc, fdst)
                stats["config"] = 1
        return {"ok": True, "restored": [f"{_SECTION_CN.get(k, k)}（{v} 条）"
                                         for k, v in stats.items()], "stats": stats}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _merge_rows(conn, section: str, rows) -> int:
    """把一段 json 合并进库。返回写入条数。"""
    if not rows:
        return 0
    n = 0
    if section == "media":
        cols = _table_cols(conn, "media")
        use = [c for c in rows[0].keys() if c in cols]
        sql = (f"INSERT OR REPLACE INTO media ({','.join(use)}) "
               f"VALUES ({','.join('?' * len(use))})")
        for r in rows:
            conn.execute(sql, [r.get(c) for c in use])
            n += 1
    elif section == "people":
        cols = _table_cols(conn, "people")
        use = [c for c in rows[0].keys() if c in cols and c != "id"]
        sets = ",".join(f"{c}=excluded.{c}" for c in use if c != "name")
        sql = (f"INSERT INTO people ({','.join(use)}) VALUES ({','.join('?' * len(use))}) "
               f"ON CONFLICT(name) DO UPDATE SET {sets}")
        for r in rows:
            conn.execute(sql, [r.get(c) for c in use])
            n += 1
    elif section == "links":
        for r in rows:
            conn.execute("INSERT OR REPLACE INTO media_people "
                         "(media_id, person_id, char_role, person_order) VALUES (?,?,?,?)",
                         (r.get("media_id"), r.get("person_id"),
                          r.get("char_role"), r.get("person_order") or 0))
            n += 1
    elif section == "favorite":
        for r in rows:
            conn.execute("UPDATE media SET favorite=? WHERE id=?",
                         (r.get("favorite") or 0, r.get("id")))
            n += 1
    elif section == "play":
        for r in rows:
            conn.execute("UPDATE media SET play_count=?, last_played=? WHERE id=?",
                         (r.get("play_count") or 0, r.get("last_played") or "",
                          r.get("id")))
            n += 1
    elif section == "userrating":
        for r in rows:
            conn.execute("UPDATE media SET user_rating=? WHERE id=?",
                         (r.get("user_rating") or 0, r.get("id")))
            n += 1
    elif section == "people_fav":
        for r in rows:
            conn.execute("UPDATE people SET favorite=?, pinned=? WHERE name=?",
                         (r.get("favorite") or 0, r.get("pinned") or 0, r.get("name")))
            n += 1
    return n


def _table_cols(conn, table: str) -> set:
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error:
        return set()


def export_data(dest_zip: str) -> dict:
    """整库导出（旧行为，保留向后兼容）。返回 {'ok', 'path', 'items'/'error'}。"""
    try:
        with tempfile.TemporaryDirectory(prefix="lmc_bk_") as td:
            items = []
            tmp_db = os.path.join(td, "media_center.db")
            has_db = _snapshot_db(tmp_db)
            if not has_db:
                tmp_db = None

            sp = cfg.config_path()
            has_settings = os.path.exists(sp)

            info = (f"{ver.APP_NAME} 数据备份\n"
                    f"版本：{ver.FULL_VERSION}\n"
                    f"导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"含数据库：{'是' if has_db else '否'}\n"
                    f"含设置：{'是' if has_settings else '否'}\n")

            with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as z:
                if has_db:
                    z.write(tmp_db, arcname="media_center.db")
                    items.append("media_center.db")
                if has_settings:
                    # 复制一份再写，避免直接读被写入的 settings.json
                    tmp_set = os.path.join(td, "settings.json")
                    shutil.copy(sp, tmp_set)
                    z.write(tmp_set, arcname="settings.json")
                    items.append("settings.json")
                z.writestr("backup_info.txt", info)
                items.append("backup_info.txt")
        return {"ok": True, "path": dest_zip, "items": items}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def import_data(src_zip: str) -> dict:
    """从 zip 恢复数据。现有文件先另存为 .bak-<时间戳>。返回 {'ok','restored'/'error'}。"""
    try:
        if not os.path.exists(src_zip):
            return {"ok": False, "error": "备份文件不存在"}
        with zipfile.ZipFile(src_zip) as z:
            names = set(z.namelist())
            if "media_center.db" not in names and "settings.json" not in names:
                return {"ok": False, "error": "不是有效的备份包（缺少 media_center.db / settings.json）"}

            restored = []
            ts = _stamp()

            if "media_center.db" in names:
                dst = db.db_path()
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                # v1.14.0：db 连接改为线程内复用，覆盖文件前**必须**先把句柄关掉，
                # 否则旧连接继续写在已被替换的文件上（Windows 上还会直接占用导致复制失败）。
                db.close_all()
                if os.path.exists(dst):
                    shutil.copy(dst, dst + f".bak-{ts}")
                with z.open("media_center.db") as fsrc, open(dst, "wb") as fdst:
                    shutil.copyfileobj(fsrc, fdst)
                # WAL/SHM 属于旧库，一并清掉，避免新库读到旧日志
                for suffix in ("-wal", "-shm"):
                    side = dst + suffix
                    if os.path.exists(side):
                        try:
                            os.remove(side)
                        except OSError:
                            pass
                restored.append("media_center.db")

            if "settings.json" in names:
                dst = cfg.config_path()
                os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
                if os.path.exists(dst):
                    shutil.copy(dst, dst + f".bak-{ts}")
                with z.open("settings.json") as fsrc, open(dst, "wb") as fdst:
                    shutil.copyfileobj(fsrc, fdst)
                restored.append("settings.json")
        return {"ok": True, "restored": restored}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def reload_settings() -> bool:
    """从磁盘重读设置（导入后立即可用；仍建议重启）。"""
    try:
        cfg._SETTINGS = None
        cfg.get_settings()
        return True
    except Exception:
        return False
