# -*- coding: utf-8 -*-
"""SQLite 数据库：媒体库 + 独立演员库(参考 emby 的 People 模式)。

v1.14.0 海量数据优化（目标 5 万+ 影片）
--------------------------------------
1. **连接复用**：原来每个函数都 `connect()`/`close()`。5 万条规模下，扫描一部片子要开关库
   好几次，开销远大于查询本身 → 改为**线程内复用**（`threading.local`），
   并用 `_PooledConn` 代理把既有的 `conn.close()` 变成 no-op（不用改几十处调用点）。
2. **WAL + 大缓存 + mmap**：读写不再互相阻塞；随机读走内存映射，快很多。
3. **补齐索引**：`library / favorite / year / added_time / collection / media_people.person_id`
   这些「筛选与排序」会用到的列原先都没有索引 → 每次都是全表扫描。
4. **查询分层**：`search_media()` 支持分页(offset/limit) + 排序白名单 + 多条件筛选；
   新增 `count_media()` 供「共 N 部」与进度显示使用。
5. **关联表按需查**：`cast_crew_map()` / `actors_map()` 支持只查指定若干 media_id，
   不再每次都把整张 `media_people`（5 万片 × 数人 = 数十万行）拉进内存。
"""
import json
import os
import random
import re
import sqlite3
import sys
import threading
from datetime import datetime
from typing import Optional

_LOCK = threading.RLock()
_LOCAL = threading.local()


def db_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)          # exe 同级目录，数据持久化
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "index_data", "media_center.db")


def _open(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    for pragma in (
        "PRAGMA foreign_keys = ON",
        "PRAGMA journal_mode = WAL",        # 读写并行，海量数据下不再互相卡
        "PRAGMA synchronous = NORMAL",
        "PRAGMA temp_store = MEMORY",
        "PRAGMA cache_size = -16000",       # ≈16MB 页缓存
        "PRAGMA mmap_size = 268435456",     # 256MB 内存映射，随机读加速
        "PRAGMA busy_timeout = 15000",
    ):
        try:
            conn.execute(pragma)
        except sqlite3.Error:
            pass
    return conn


class _PooledConn:
    """sqlite3.Connection 的薄代理：把 close() 变成 no-op，从而复用底层长连接。

    为什么要这样：既有代码几十处 `finally: conn.close()`，逐处改风险大；
    用代理把 close 屏蔽掉，即可在**不改调用点**的前提下拿到连接复用的收益。
    `execute/commit/executescript/row_factory` 等一律透传。
    """

    __slots__ = ("_c",)

    def __init__(self, conn: sqlite3.Connection):
        self._c = conn

    def __getattr__(self, name):
        return getattr(self._c, name)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):                     # 故意不关：连接由线程内复用
        pass

    def really_close(self):
        self._c.close()


def get_conn():
    """取当前线程的连接（不存在则建，之后复用）。"""
    path = db_path()
    conn = getattr(_LOCAL, "conn", None)
    if conn is not None and getattr(_LOCAL, "path", None) == path:
        return conn
    if conn is not None:
        try:
            conn.really_close()
        except Exception:
            pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = _PooledConn(_open(path))
    _LOCAL.conn = conn
    _LOCAL.path = path
    return conn


def close_conn() -> None:
    """关闭当前线程的连接。**导入备份覆盖 db 文件前必须调用**，否则旧句柄会写回旧文件。"""
    conn = getattr(_LOCAL, "conn", None)
    if conn is not None:
        try:
            conn.really_close()
        except Exception:
            pass
    _LOCAL.conn = None
    _LOCAL.path = None


def close_all() -> None:
    close_conn()


def init_db() -> None:
    with _LOCK:
        conn = get_conn()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS media (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind        TEXT NOT NULL,            -- movie / tvshow / episode
                    title       TEXT NOT NULL,
                    sort_title  TEXT,
                    year        INTEGER,
                    plot        TEXT,
                    rating      REAL,
                    poster      TEXT,
                    fanart      TEXT,
                    thumb       TEXT,
                    file_path   TEXT,                    -- 视频文件路径
                    nfo_path    TEXT,
                    library     TEXT,                    -- 所属媒体库根目录
                    genres      TEXT,                    -- 逗号分隔
                    season      INTEGER,
                    episode     INTEGER,
                    parent_id   INTEGER,                 -- 剧集 -> tvshow
                    runtime     TEXT,                    -- 时长 02:07:55
                    country     TEXT,                    -- 国家/地区
                    studio      TEXT,                    -- 制片/发行
                    file_size   INTEGER,                 -- 字节
                    quality     TEXT,                    -- 画质徽章: 4K,HDR10,Atmos
                    tmdb_id     TEXT,
                    certification TEXT,                  -- 分级
                    collection  TEXT,                    -- 合集名(<set>)
                    added_date  TEXT,                    -- 入库日期 YYYY-MM-DD
                    premiere    TEXT,                    -- 上映日期 YYYY-MM-DD
                    user_rating REAL,                    -- 用户评分
                    file_mtime  REAL,                    -- 视频文件修改时间(检测变更)
                    favorite    INTEGER DEFAULT 0,
                    play_count  INTEGER DEFAULT 0,
                    last_played REAL,
                    added_time  REAL DEFAULT (strftime('%s','now'))
                );

                CREATE TABLE IF NOT EXISTS people (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT NOT NULL UNIQUE,
                    role_type   TEXT DEFAULT 'Actor',     -- Actor / Director / Writer
                    thumb       TEXT,
                    bio         TEXT,
                    photo_path  TEXT,
                    alias       TEXT,                     -- 别名 / 爱称（刮削）
                    birthday    TEXT,                     -- 生日 YYYY-MM-DD（刮削）
                    romaji      TEXT,                     -- 罗马音（用于跨站二次检索）
                    source      TEXT,                     -- 最近一次刮削来源
                    source_url  TEXT,
                    scraped_at  TEXT,
                    meta        TEXT                      -- 其它刮削字段(JSON: 身高/尺寸/出身地/事务所…)
                );

                CREATE TABLE IF NOT EXISTS media_people (
                    media_id    INTEGER NOT NULL,
                    person_id   INTEGER NOT NULL,
                    char_role   TEXT,                     -- 饰演角色
                    person_order INTEGER DEFAULT 0,
                    PRIMARY KEY (media_id, person_id)
                );

                -- v1.24.0「智能推荐 → 向量编辑」：手动加权的偏好向量持久化在库里
                -- （settings.json 里也存一份快照，便于随配置一起导出/导入）。
                -- weight>0 加强 / weight<0 软排斥 / weight=0 屏蔽
                CREATE TABLE IF NOT EXISTS vector_overrides (
                    dim     TEXT NOT NULL,                -- tag / actor / director / studio / series
                    key     TEXT NOT NULL,
                    weight  REAL NOT NULL,
                    note    TEXT,
                    updated REAL,
                    PRIMARY KEY (dim, key)
                );

                CREATE INDEX IF NOT EXISTS idx_media_title ON media(title);
                CREATE INDEX IF NOT EXISTS idx_media_kind ON media(kind);
                CREATE INDEX IF NOT EXISTS idx_people_name ON people(name);
                """
            )
            _migrate(conn)
            _ensure_indexes(conn)
            conn.commit()
        finally:
            conn.close()


# 筛选 / 排序 / 关联查询会用到的列。**老库也要补**（CREATE INDEX IF NOT EXISTS 幂等），
# 否则 5 万条规模下每次筛选排序都是全表扫描 —— 这正是「一操作就卡」的主因之一。
_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_media_library    ON media(library)",
    "CREATE INDEX IF NOT EXISTS idx_media_favorite   ON media(favorite)",
    "CREATE INDEX IF NOT EXISTS idx_media_year       ON media(year)",
    "CREATE INDEX IF NOT EXISTS idx_media_added_time ON media(added_time)",
    "CREATE INDEX IF NOT EXISTS idx_media_added_date ON media(added_date)",
    "CREATE INDEX IF NOT EXISTS idx_media_premiere   ON media(premiere)",
    "CREATE INDEX IF NOT EXISTS idx_media_rating     ON media(rating)",
    "CREATE INDEX IF NOT EXISTS idx_media_userrating ON media(user_rating)",
    "CREATE INDEX IF NOT EXISTS idx_media_sort_title ON media(sort_title)",
    # v1.26.0（性能基准测试查出来的）：上面这些单列索引**影片墙一条也用不上** ——
    # `search_media` 的排序键永远带附加项（`ORDER BY <expr> <方向>, m.year DESC, m.id ASC`），
    # 而 `sort_title` 索引是 BINARY collation、查询却写 `COLLATE NOCASE`。
    # 结果：每次翻页都 `SCAN m` + `USE TEMP B-TREE FOR ORDER BY`（全表扫 + 全表排序）。
    # 补两条**与 ORDER BY 逐列对齐**的复合索引后，本机实测（4.8 万条）：
    #   名称升序 深翻页 223.5ms → 7.9ms；最近添加 倒序 95.3ms → 0.0ms。
    "CREATE INDEX IF NOT EXISTS idx_wall_title ON media(sort_title COLLATE NOCASE, year DESC, id ASC)",
    "CREATE INDEX IF NOT EXISTS idx_wall_time  ON media(added_time DESC, year DESC, id ASC)",
    "CREATE INDEX IF NOT EXISTS idx_media_path       ON media(file_path)",
    "CREATE INDEX IF NOT EXISTS idx_media_collection ON media(collection)",
    "CREATE INDEX IF NOT EXISTS idx_media_lib_kind   ON media(library, kind)",
    # v1.15.0：分片（选集）子记录按 parent_id 回查；影片墙又靠 parent_id IS NULL 过滤
    "CREATE INDEX IF NOT EXISTS idx_media_parent     ON media(parent_id)",
    "CREATE INDEX IF NOT EXISTS idx_mp_media         ON media_people(media_id)",
    "CREATE INDEX IF NOT EXISTS idx_mp_person        ON media_people(person_id)",
    "CREATE INDEX IF NOT EXISTS idx_people_role      ON people(role_type)",
)


def _ensure_indexes(conn) -> None:
    for sql in _INDEXES:
        try:
            conn.execute(sql)
        except sqlite3.Error:
            pass


# 老库补列：列名 -> 列定义
_MEDIA_NEW_COLS = {
    "runtime": "TEXT", "country": "TEXT", "studio": "TEXT",
    "file_size": "INTEGER", "quality": "TEXT", "tmdb_id": "TEXT",
    "certification": "TEXT", "added_date": "TEXT", "collection": "TEXT",
    "favorite": "INTEGER DEFAULT 0", "play_count": "INTEGER DEFAULT 0",
    "last_played": "REAL",
    "premiere": "TEXT", "user_rating": "REAL", "file_mtime": "REAL",
}

# 老库 people 表补列
_PEOPLE_NEW_COLS = {
    "alias": "TEXT", "birthday": "TEXT", "romaji": "TEXT",
    "source": "TEXT", "source_url": "TEXT", "scraped_at": "TEXT", "meta": "TEXT",
    # v1.10.0：演员库卡片化所需的「状态 / 收藏 / 置顶」
    "status": "TEXT", "favorite": "INTEGER DEFAULT 0", "pinned": "INTEGER DEFAULT 0",
}


def _migrate(conn: sqlite3.Connection) -> None:
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(media)").fetchall()}
    for col, decl in _MEDIA_NEW_COLS.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE media ADD COLUMN {col} {decl}")
    ppl = {r["name"] for r in conn.execute("PRAGMA table_info(people)").fetchall()}
    for col, decl in _PEOPLE_NEW_COLS.items():
        if col not in ppl:
            conn.execute(f"ALTER TABLE people ADD COLUMN {col} {decl}")


def upsert_person(name: str, role_type: str = "Actor", thumb: Optional[str] = None) -> int:
    with _LOCK:
        conn = get_conn()
        try:
            row = conn.execute("SELECT id FROM people WHERE name=?", (name,)).fetchone()
            if row:
                pid = row["id"]
                if thumb and not row.get("thumb"):
                    conn.execute("UPDATE people SET thumb=? WHERE id=?", (thumb, pid))
                conn.commit()
                return pid
            cur = conn.execute(
                "INSERT INTO people(name, role_type, thumb) VALUES(?,?,?)",
                (name, role_type, thumb),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


def link_media_person(media_id: int, person_id: int, char_role: str, order: int) -> None:
    with _LOCK:
        conn = get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO media_people(media_id, person_id, char_role, person_order) "
                "VALUES(?,?,?,?)",
                (media_id, person_id, char_role, order),
            )
            conn.commit()
        finally:
            conn.close()


def insert_media(**fields) -> int:
    with _LOCK:
        conn = get_conn()
        try:
            cols = list(fields.keys())
            ph = ",".join("?" for _ in cols)
            sql = f"INSERT INTO media({','.join(cols)}) VALUES({ph})"
            cur = conn.execute(sql, [fields[c] for c in cols])
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


def clear_media() -> None:
    with _LOCK:
        conn = get_conn()
        try:
            conn.execute("DELETE FROM media")
            conn.execute("DELETE FROM media_people")
            conn.commit()
        finally:
            conn.close()


# ---------- 影片墙 / 列表的筛选与排序（v1.14.0） ----------
# 排序字段白名单：**只允许这些键**，绝不把用户输入拼进 SQL。
# 参考 Emby 的排序菜单：名称 / 类型 / 添加时间 / 上映日期 / 评分（+ 升降序）。
_RUNTIME_MIN = ("CAST(substr(IFNULL(m.runtime,''),1,2) AS INTEGER)*60"
                " + CAST(substr(IFNULL(m.runtime,''),4,2) AS INTEGER)")
_RUNTIME_SEC = ("CAST(substr(IFNULL(m.runtime,''),1,2) AS INTEGER)*3600"
                " + CAST(substr(IFNULL(m.runtime,''),4,2) AS INTEGER)*60"
                " + CAST(substr(IFNULL(m.runtime,''),7,2) AS INTEGER)")

MEDIA_SORTS = [
    ("sort_title",  "名称",     "m.sort_title COLLATE NOCASE"),
    ("kind",        "类型",     "m.kind"),
    ("added_time",  "添加时间", "m.added_time"),
    ("premiere",    "上映日期", "m.premiere"),
    ("year",        "年份",     "m.year"),
    ("rating",      "评分",     "m.rating"),
    ("user_rating", "用户评分", "m.user_rating"),
    ("favorite",    "收藏",     "m.favorite"),
    ("runtime",     "时长",     _RUNTIME_SEC),
    ("file_size",   "文件大小", "m.file_size"),
    ("play_count",  "观看次数", "m.play_count"),
    ("last_played", "最近播放", "m.last_played"),
    ("random",      "随机",     "RANDOM()"),   # v1.16.0：真实 ORDER BY 由 search_media 特殊处理
]
_SORT_EXPR = {k: e for k, _l, e in MEDIA_SORTS}

# 画质筛选：按 quality 字段里的徽章子串匹配
QUALITY_FILTERS = [("4K", "4K"), ("1080P", "1080P"), ("720P", "720P"),
                   ("HDR10", "HDR10"), ("杜比视界", "杜比视界"), ("Atmos", "Atmos")]

# 多维筛选面板（v1.16.0）用的固定选项：风格 / 地区。
# 「其他」＝排除以上全部已知值后剩下的（genres/country 里都不含任何一个）。
GENRE_FACETS = ["剧情", "喜剧", "动作", "爱情", "犯罪", "悬疑", "战争", "科幻", "动画",
                "恐怖", "家庭", "冒险", "奇幻", "历史", "纪录", "音乐", "西部"]
COUNTRY_FACETS = ["中国大陆", "中国香港", "中国台湾", "美国", "英国", "法国", "德国",
                  "意大利", "西班牙", "葡萄牙", "韩国", "日本", "印度", "泰国"]

# v1.16.0「随机」排序 —— 关键点：**不能用 `ORDER BY RANDOM()` 直接分页**。
# 那样每翻一页都会重新随机，页面之间会重复/漏项（LazyGrid 是按 offset/limit 增量取的）。
# 这里改用一个「会话种子」做伪随机置换：((id * 大质数 + 种子) % 质数)，
# 同一会话内排序稳定（分页正确），点「刷新一下」换种子即重新洗牌。
_RANDOM_SEED = random.randint(1, 2147483646)
_RANDOM_MUL = 2654435761
_RANDOM_MOD = 2147483647


def reshuffle() -> int:
    """换一个随机种子 → 同一筛选条件下重新洗牌（不改数据、不改排序键）。"""
    global _RANDOM_SEED
    _RANDOM_SEED = random.randint(1, _RANDOM_MOD - 1)
    return _RANDOM_SEED


def _like_escape(s: str) -> str:
    """把用户目录路径转成安全的 LIKE 前缀（转义 % _ \\ 并追加 %）。"""
    s = (s or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return s + "%"


def _media_where(keyword: str = "", kind: Optional[str] = None, genre: Optional[str] = None,
                 person: Optional[str] = None, country: Optional[str] = None,
                 certification: Optional[str] = None, collection: Optional[str] = None,
                 library: Optional[str] = None, favorite=None,
                 min_user_rating=None, has_user_rating=None,
                 year_from=None, year_to=None, quality=None, library_in=None,
                 top_only=None, ident=None, progress=None,
                 genre_other=None, country_other=None, has_collection=None,
                 path_prefix=None):
    """把筛选条件翻译成 (WHERE 片段, 参数表)。search_media / count_media 共用，保证口径一致。"""
    clauses, params = [], []
    if kind:
        clauses.append("m.kind=?")
        params.append(kind)
    # v1.15.0：`top_only=True` 只取「顶层条目」，把分片子记录（cd1/cd2… 与剧集分集）挡在影片墙外。
    # 子记录只能从所属影片的「选集」里进入，不再各自占一张海报位。
    if top_only:
        clauses.append("m.parent_id IS NULL")
    # v1.16.0：多维筛选面板新增的维度
    if ident == "nfo":
        clauses.append("IFNULL(m.nfo_path,'')<>''")
    elif ident == "tmdb":
        clauses.append("IFNULL(m.tmdb_id,'')<>''")
    elif ident == "smart":      # 无 nfo，但靠文件名/本地图片识别出了年份或画质
        clauses.append("IFNULL(m.nfo_path,'')='' AND (IFNULL(m.year,'')<>'' "
                       "OR IFNULL(m.quality,'')<>'')")
    elif ident == "none":       # 既无 nfo，也没识别出年份/画质 → 基本空壳
        clauses.append("IFNULL(m.nfo_path,'')='' AND IFNULL(m.year,'')='' "
                       "AND IFNULL(m.quality,'')=''")
    if progress == "unwatched":
        clauses.append("IFNULL(m.play_count,0)=0")
    elif progress == "watched":
        clauses.append("IFNULL(m.play_count,0)>0")
    if has_collection is True:
        clauses.append("IFNULL(m.collection,'')<>''")
    elif has_collection is False:
        clauses.append("IFNULL(m.collection,'')=''")
    if genre:
        clauses.append("m.genres LIKE ?")
        params.append(f"%{genre}%")
    elif genre_other:      # 「其他」＝不含任一已知风格
        if GENRE_FACETS:
            clauses.append("(" + " AND ".join("IFNULL(m.genres,'') NOT LIKE ?"
                                              for _ in GENRE_FACETS) + ")")
            params.extend(f"%{g}%" for g in GENRE_FACETS)
    if country:
        clauses.append("m.country LIKE ?")
        params.append(f"%{country}%")
    elif country_other:    # 「其他」＝不含任一已知地区
        if COUNTRY_FACETS:
            clauses.append("(" + " AND ".join("IFNULL(m.country,'') NOT LIKE ?"
                                              for _ in COUNTRY_FACETS) + ")")
            params.extend(f"%{c}%" for c in COUNTRY_FACETS)
    if certification:
        clauses.append("m.certification LIKE ?")
        params.append(f"%{certification}%")
    if collection:
        clauses.append("m.collection=?")
        params.append(collection)
    if library:
        clauses.append("m.library=?")
        params.append(library)
    if library_in:
        names = [x for x in library_in if x]
        if names:
            clauses.append("m.library IN (%s)" % ",".join("?" * len(names)))
            params.extend(names)
    # v1.17.0：按「目录前缀」筛选（文件夹页点目录卡片进入该目录的影片墙）。
    # 坑：设置里的路径用正斜杠（X:/【01】Jav精选），而索引里的 file_path 用反斜杠
    # （Y:\【02】Jav严选\...）。所以两种分隔符各给一条 LIKE（都是「列 LIKE 常量前缀」，
    # 走得到 file_path 索引；不要用 REPLACE(列,…) 那样会造成全表扫描）。
    if path_prefix:
        base = str(path_prefix).rstrip("/\\")
        variants = [_like_escape(base.replace("/", sep).replace("\\", sep)) for sep in ("\\", "/")]
        clauses.append("(" + " OR ".join("m.file_path LIKE ? ESCAPE '\\'" for _ in variants) + ")")
        params.extend(variants)
    if favorite is True:
        clauses.append("IFNULL(m.favorite,0)=1")
    elif favorite is False:
        clauses.append("IFNULL(m.favorite,0)=0")
    if has_user_rating is True:
        clauses.append("m.user_rating IS NOT NULL")
    elif has_user_rating is False:
        clauses.append("m.user_rating IS NULL")
    if min_user_rating is not None:
        clauses.append("m.user_rating IS NOT NULL AND m.user_rating>=?")
        params.append(float(min_user_rating))
    if year_from is not None:
        clauses.append("m.year IS NOT NULL AND m.year>=?")
        params.append(int(year_from))
    if year_to is not None:
        clauses.append("m.year IS NOT NULL AND m.year<=?")
        params.append(int(year_to))
    if quality:
        clauses.append("m.quality LIKE ?")
        params.append(f"%{quality}%")
    if person:
        clauses.append(
            "m.id IN (SELECT mp.media_id FROM media_people mp "
            "JOIN people p ON p.id=mp.person_id WHERE p.name LIKE ?)"
        )
        params.append(f"%{person}%")
    if keyword:
        clauses.append("(m.title LIKE ? OR m.plot LIKE ?)")
        params.append(f"%{keyword}%")
        params.append(f"%{keyword}%")
    return ((" WHERE " + " AND ".join(clauses)) if clauses else ""), params


_MEDIA_COLS = None


def _select_cols(light: bool = False) -> str:
    """列投影。`light=True` 时不取 plot（列表用不到的大文本字段）。

    v1.14.0：列表页 5 万条时，plot 是最大的文本列，一次全读进来要多占几百 MB 内存，
    而列表根本不显示它 —— 详情面板需要时按 id 单行取回即可。
    """
    global _MEDIA_COLS
    if _MEDIA_COLS is None:
        with _LOCK:
            conn = get_conn()
            try:
                _MEDIA_COLS = [r["name"] for r in
                               conn.execute("PRAGMA table_info(media)").fetchall()]
            except sqlite3.Error:
                _MEDIA_COLS = []
            finally:
                conn.close()
    cols = list(_MEDIA_COLS or [])
    if not cols:
        return "m.*"
    if light:
        cols = [c for c in cols if c != "plot"]
    return ", ".join("m." + c for c in cols)


def search_media(keyword: str = "", kind: Optional[str] = None, genre: Optional[str] = None,
                 person: Optional[str] = None, country: Optional[str] = None,
                 certification: Optional[str] = None, collection: Optional[str] = None,
                 library: Optional[str] = None, limit: int = 500, offset: int = 0,
                 sort: str = "sort_title", asc: bool = True, light: bool = False, **filters):
    """查询影片。

    v1.14.0：新增 `offset`（分页）/ `sort`+`asc`（排序）/ `light`（不取 plot 大字段）/
    更多筛选（见 `_media_where`）。排序只接受白名单键，未知名回落到名称升序 ——
    既防 SQL 注入，也避免拼字符串出错。
    """
    where, params = _media_where(keyword, kind, genre, person, country, certification,
                                 collection, library, **filters)
    if sort == "random":
        # 用会话种子做伪随机置换：分页稳定（同一批内不重复），reshuffle() 换种子即洗牌。
        expr = f"((m.id * {_RANDOM_MUL} + {_RANDOM_SEED}) % {_RANDOM_MOD})"
        direction = "ASC"
    else:
        expr = _SORT_EXPR.get(sort) or _SORT_EXPR["sort_title"]
        direction = "ASC" if asc else "DESC"
    sql = ("SELECT " + _select_cols(light) + " FROM media m" + where +
           f" ORDER BY {expr} {direction}, m.year DESC, m.id ASC LIMIT ? OFFSET ?")
    params = params + [int(limit), int(offset)]
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()


def count_media(keyword: str = "", kind: Optional[str] = None, genre: Optional[str] = None,
                person: Optional[str] = None, country: Optional[str] = None,
                certification: Optional[str] = None, collection: Optional[str] = None,
                library: Optional[str] = None, **filters) -> int:
    """同筛选口径下的总数（用于「共 N 部」与加载进度）。"""
    where, params = _media_where(keyword, kind, genre, person, country, certification,
                                 collection, library, **filters)
    with _LOCK:
        conn = get_conn()
        try:
            r = conn.execute("SELECT COUNT(*) c FROM media m" + where, params).fetchone()
            return r["c"] if r else 0
        finally:
            conn.close()


def library_counts() -> dict:
    """一次取出「每个媒体库有多少影片」—— 侧边栏与页面标题要显示总数，不能逐个 COUNT。

    v1.15.0：只数**顶层条目**（`parent_id IS NULL`）。否则侧边栏写着 1410，影片墙按
    顶层过滤只显示 312，两边数字对不上（用户一眼就能看出来）。
    """
    with _LOCK:
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT library, COUNT(*) c FROM media "
                "WHERE library IS NOT NULL AND library<>'' AND parent_id IS NULL "
                "GROUP BY library"
            ).fetchall()
            return {r["library"]: r["c"] for r in rows}
        finally:
            conn.close()


def libraries():
    with _LOCK:
        conn = get_conn()
        try:
            return [r["library"] for r in conn.execute(
                "SELECT DISTINCT library FROM media WHERE library IS NOT NULL ORDER BY library"
            ).fetchall()]
        finally:
            conn.close()


def folder_stats(paths, sample: int = 2) -> dict:
    """文件夹页用（v1.17.0）：每个配置目录的影片数 + 代表海报。

    返回 {目录路径: {"count": n, "posters": [海报/缩略图路径, ...]}}。
    只数**顶层条目**（与影片墙口径一致），并按 sort_title 取前 sample 张海报做拼贴封面。
    """
    out = {}
    with _LOCK:
        conn = get_conn()
        try:
            for p in (paths or []):
                where, params = _media_where(top_only=True, path_prefix=p)
                r = conn.execute("SELECT COUNT(*) c FROM media m" + where, params).fetchone()
                n = int(r["c"]) if r else 0
                posters = []
                if n:
                    rows = conn.execute(
                        "SELECT m.poster, m.thumb FROM media m" + where +
                        " ORDER BY m.sort_title COLLATE NOCASE, m.id LIMIT ?",
                        params + [int(sample)]).fetchall()
                    for rr in rows:
                        pm = rr["poster"] or rr["thumb"]
                        if pm:
                            posters.append(pm)
                out[p] = {"count": n, "posters": posters}
        finally:
            conn.close()
    return out


def rename_library(old: str, new: str) -> int:
    """媒体库改名后同步已有媒体的 library 字段。返回受影响行数。"""
    with _LOCK:
        conn = get_conn()
        try:
            cur = conn.execute("UPDATE media SET library=? WHERE library=?", (new, old))
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()


def count_library(name: str) -> int:
    """统计某媒体库下的条目数与磁盘占用。"""
    with _LOCK:
        conn = get_conn()
        try:
            r = conn.execute(
                "SELECT COUNT(*) c, COALESCE(SUM(file_size),0) s FROM media WHERE library=?",
                (name,)).fetchone()
            return {"count": r["c"], "size": r["s"]}
        finally:
            conn.close()


def delete_library(name: str) -> int:
    """删除媒体库下的索引记录（含演员关联）。**不删除磁盘文件**。返回删除条数。"""
    with _LOCK:
        conn = get_conn()
        try:
            ids = [r["id"] for r in conn.execute(
                "SELECT id FROM media WHERE library=?", (name,)).fetchall()]
            for i in ids:
                conn.execute("DELETE FROM media_people WHERE media_id=?", (i,))
            conn.execute("DELETE FROM media WHERE library=?", (name,))
            conn.commit()
            return len(ids)
        finally:
            conn.close()


def collections():
    """[（合集名, 顶层条目数）, ...]

    v1.24.0（反馈 3）：加上 `parent_id IS NULL` —— 合集页现在与影片墙一样按**顶层条目**计数，
    否则卡片上写「共 12 部」、点进去的墙却是「8 部」（差的是 CD 分片），看着像 bug。
    """
    with _LOCK:
        conn = get_conn()
        try:
            return [(r["collection"], r["c"]) for r in conn.execute(
                "SELECT collection, COUNT(*) c FROM media "
                "WHERE collection IS NOT NULL AND collection<>'' "
                "AND parent_id IS NULL "
                "GROUP BY collection ORDER BY collection"
            ).fetchall()]
        finally:
            conn.close()


def collection_posters(names, sample: int = 2) -> dict:
    """合集卡片封面（v1.24.0 反馈 3）：{合集名: [海报, ...]}，每个合集取前 sample 张。

    **一次查询搞定**：真机有 7 千多个合集，逐名 `LIMIT 2` 要发 7 千条 SQL（实测 7 秒以上，
    页面会明显卡住）。改成按 collection 排序**一遍扫过全部顶层条目**（4.8 万行、只取 3 列），
    在 Python 里边走边收每个合集的头两张 —— 实测 ~0.3 秒。
    """
    out = {}
    names = set(names or [])
    if not names:
        return out
    with _LOCK:
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT collection c, poster, thumb FROM media "
                "WHERE parent_id IS NULL AND collection IS NOT NULL AND collection<>'' "
                "ORDER BY collection, sort_title COLLATE NOCASE, id").fetchall()
        finally:
            conn.close()
    for r in rows:
        name = r["c"]
        if name not in names:
            continue
        bucket = out.setdefault(name, [])
        if len(bucket) >= int(sample):
            continue
        pm = r["poster"] or r["thumb"]
        if pm:
            bucket.append(pm)
    return out


def movies(limit: int = 500):
    return search_media("", kind="movie")


def tvshows(limit: int = 500):
    return search_media("", kind="tvshow")


def get_media(id_: int):
    with _LOCK:
        conn = get_conn()
        try:
            return dict(conn.execute("SELECT * FROM media WHERE id=?", (id_,)).fetchone())
        finally:
            conn.close()


def get_cast(media_id: int):
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT p.*, mp.char_role, mp.person_order FROM media_people mp "
                "JOIN people p ON p.id=mp.person_id WHERE mp.media_id=? "
                "ORDER BY mp.person_order", (media_id,)
            ).fetchall()]
        finally:
            conn.close()


def get_person(pid: int):
    """取单个演员。附带 works / last_year —— 详情页的「状态」推断也需要它们
    （v1.11.0：原先只有 all_people_ordered 带这两个字段，详情页永远判成「未知」）。"""
    with _LOCK:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT p.*, "
                "(SELECT COUNT(*) FROM media_people mp WHERE mp.person_id=p.id) AS works, "
                "(SELECT MAX(m.year) FROM media_people mp JOIN media m ON m.id=mp.media_id "
                " WHERE mp.person_id=p.id) AS last_year "
                "FROM people p WHERE p.id=?", (pid,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


def dedupe_rows(library=None):
    """重复检测取数（v1.23.0）：列出所有带 ``file_path`` 的条目（跨目录去重需要文件路径）。

    只取轻量列，避免把 ``plot`` 等大字段拉进内存（5 万片规模下差异明显）。
    """
    with _LOCK:
        conn = get_conn()
        try:
            sql = ("SELECT id, kind, title, sort_title, year, file_path, nfo_path, "
                   "file_size, runtime, library, quality FROM media "
                   "WHERE IFNULL(file_path,'')<>''")
            params = []
            if library:
                sql += " AND library=?"
                params.append(library)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()


def _chunks(seq, n=900):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def actors_map(limit_names: int = 0, ids=None):
    """取出 media_id -> "演员1 / 演员2" 的映射（首页演员列 / 排序用，避免逐条查询）。

    v1.14.0：支持 `ids` —— 只查当前真正要显示的那批影片。
    传 None 时才是全量（全量在 5 万片规模下会把整张关联表拉进内存，慎用）。
    """
    rows = []
    with _LOCK:
        conn = get_conn()
        try:
            if ids is None:
                rows = conn.execute(
                    "SELECT mp.media_id AS mid, p.name AS name FROM media_people mp "
                    "JOIN people p ON p.id=mp.person_id "
                    "ORDER BY mp.media_id, mp.person_order"
                ).fetchall()
            else:
                ids = [int(i) for i in ids]
                for part in _chunks(ids):
                    ph = ",".join("?" * len(part))
                    rows.extend(conn.execute(
                        "SELECT mp.media_id AS mid, p.name AS name FROM media_people mp "
                        "JOIN people p ON p.id=mp.person_id "
                        f"WHERE mp.media_id IN ({ph}) "
                        "ORDER BY mp.media_id, mp.person_order", part).fetchall())
        finally:
            conn.close()
    agg = {}
    for r in rows:
        nm = (r["name"] or "").strip()
        if not nm:
            continue
        agg.setdefault(r["mid"], []).append(nm)
    out = {}
    for mid, names in agg.items():
        seen, keep = set(), []
        for n in names:
            if n not in seen:
                seen.add(n)
                keep.append(n)
        if limit_names and len(keep) > limit_names:
            keep = keep[:limit_names]
        out[mid] = " / ".join(keep)
    return out


def person_works(pid: int):
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT m.*, mp.char_role FROM media_people mp "
                "JOIN media m ON m.id=mp.media_id WHERE mp.person_id=? "
                "ORDER BY m.year DESC", (pid,)
            ).fetchall()]
        finally:
            conn.close()


def all_people(role_type: str = "Actor"):
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT p.*, (SELECT COUNT(*) FROM media_people mp WHERE mp.person_id=p.id) AS works "
                "FROM people p WHERE p.role_type=? ORDER BY works DESC, p.name", (role_type,)
            ).fetchall()]
        finally:
            conn.close()


# ---------- 演员库的筛选与排序（v1.14.0） ----------
# 「首字母」：优先罗马音 romaji（真机 4766 / 7127 有值），退化到姓名首字符。
# 用它排序时中/日文名会挤到后面，所以 A-Z 索引把非 A-Z 的一律归到 "#"（见
# `people_letter_index`），不做分散处理。
_ACTOR_LETTER_EXPR = "UPPER(SUBSTR(COALESCE(NULLIF(TRIM(p.romaji), ''), p.name), 1, 1))"

ACTOR_SORTS = [
    ("works",     "作品数",   "works"),
    ("last_year", "最新作品", "last_year"),
    ("name",      "姓名",     "p.name COLLATE NOCASE"),
    ("letter",    "首字母",   _ACTOR_LETTER_EXPR),
    ("birthday",  "生日",     "p.birthday"),
    ("favorite",  "收藏",     "p.favorite"),
    ("pinned",    "置顶",     "p.pinned"),
    ("added",     "加入顺序", "p.id"),
]
_ACTOR_SORT_EXPR = {k: e for k, _l, e in ACTOR_SORTS}

ACTOR_STATUSES = ["现役", "退役", "未知"]

# works / last_year 用 JOIN+GROUP BY 一次算完（原来是对每一行跑 2 个相关子查询，
# 演员上千人时开销可观）。
_PEOPLE_SELECT = ("p.*, COUNT(mp.media_id) AS works, MAX(m.year) AS last_year "
                  "FROM people p "
                  "LEFT JOIN media_people mp ON mp.person_id = p.id "
                  "LEFT JOIN media m ON m.id = mp.media_id")


def _people_having(status=None, min_works=None, cur_year=None):
    """状态筛选依赖聚合出来的 last_year → 只能放 HAVING。"""
    having, params = [], []
    if status:
        y = int(cur_year or datetime.now().year)
        live = ("(p.status='现役' OR (IFNULL(p.status,'')='' AND last_year IS NOT NULL "
                "AND last_year>=?))")
        retired = ("(p.status='退役' OR (IFNULL(p.status,'')='' AND last_year IS NOT NULL "
                   "AND last_year<?))")
        unknown = "(IFNULL(p.status,'')='' AND last_year IS NULL)"
        expr = {"现役": live, "退役": retired, "未知": unknown}.get(status)
        if expr == live:
            having.append(expr)
            params.append(y - 1)
        elif expr == retired:
            having.append(expr)
            params.append(y - 1)
        elif expr == unknown:
            having.append(expr)
    if min_works is not None:
        having.append("works>=?")
        params.append(int(min_works))
    return having, params


def _people_clauses(role_type="Actor", favorite=None, pinned=None, status=None,
                    has_photo=None, min_works=None, cur_year=None):
    """WHERE / HAVING / 参数 **三处共用**（v1.30.0）。

    原来 `query_people` 与 `count_people` 各写一份构造逻辑 —— 两处一旦不同步
    （比如漏一个 `has_photo`），表现是「总数是 5909，实际翻几页就没了」这种
    极难复盘的错。现在只有这一份，`people_letter_index` 也复用它，三边口径天然一致。
    """
    clauses = ["p.role_type=?"]
    params = [role_type]
    if favorite is True:
        clauses.append("IFNULL(p.favorite,0)=1")
    elif favorite is False:
        clauses.append("IFNULL(p.favorite,0)=0")
    if pinned is True:
        clauses.append("IFNULL(p.pinned,0)=1")
    elif pinned is False:
        clauses.append("IFNULL(p.pinned,0)=0")
    if has_photo is True:
        clauses.append("p.photo_path IS NOT NULL AND p.photo_path<>''")
    elif has_photo is False:
        clauses.append("(p.photo_path IS NULL OR p.photo_path='')")
    having, hparams = _people_having(status, min_works, cur_year)
    return clauses, params, having, hparams


def _people_order(sort: str, asc: bool) -> str:
    """ORDER BY 子句（含 tie-breaker），查询与字母索引共用同一份口径。"""
    expr = _ACTOR_SORT_EXPR.get(sort) or _ACTOR_SORT_EXPR["works"]
    return f" ORDER BY p.pinned DESC, {expr} {'ASC' if asc else 'DESC'}, p.name COLLATE NOCASE"


def query_people(role_type: str = "Actor", limit: int = 0, offset: int = 0,
                 sort: str = "works", asc: bool = False, favorite=None, pinned=None,
                 status=None, has_photo=None, min_works=None, cur_year=None):
    """演员库查询（筛选 + 排序 + 分页）。

    排序恒以「置顶」优先（与旧行为一致）；`sort` 只接受白名单键。
    """
    clauses, params, having, hparams = _people_clauses(
        role_type, favorite, pinned, status, has_photo, min_works, cur_year)
    sql = ("SELECT " + _PEOPLE_SELECT + " WHERE " + " AND ".join(clauses) + " GROUP BY p.id")
    if having:
        sql += " HAVING " + " AND ".join(having)
    sql += _people_order(sort, asc)
    if limit and int(limit) > 0:
        sql += " LIMIT ? OFFSET ?"
        params = params + hparams + [int(limit), int(offset)]
    else:
        params = params + hparams
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()


def count_people(role_type: str = "Actor", favorite=None, pinned=None, status=None,
                 has_photo=None, min_works=None, cur_year=None) -> int:
    """`query_people` 同口径的总人数（用于「共 N 位」）。"""
    clauses, params, having, hparams = _people_clauses(
        role_type, favorite, pinned, status, has_photo, min_works, cur_year)
    sql = ("SELECT COUNT(*) c FROM (SELECT p.id AS pid, MAX(m.year) AS last_year, "
           "COUNT(mp.media_id) AS works FROM people p "
           "LEFT JOIN media_people mp ON mp.person_id = p.id "
           "LEFT JOIN media m ON m.id = mp.media_id"
           " WHERE " + " AND ".join(clauses) + " GROUP BY p.id")
    if having:
        sql += " HAVING " + " AND ".join(having)
    sql += ")"
    with _LOCK:
        conn = get_conn()
        try:
            r = conn.execute(sql, params + hparams).fetchone()
            return r["c"] if r else 0
        finally:
            conn.close()


def people_letter_index(role_type: str = "Actor", asc: bool = True, favorite=None,
                        pinned=None, status=None, has_photo=None, min_works=None,
                        cur_year=None) -> dict:
    """A-Z 导航条用的「字母 -> 该字母第一个人在列表中的下标（0 基）」映射。

    必须与 `query_people(sort="letter", asc=asc)` 的 ORDER BY **逐项一致**
    （`_people_order` 共用 + 这里内联同一个首字母表达式），否则点字母会跳错人。
    `p.pinned DESC` 那段意味着置顶的人排在最前 —— 若某个字母的第一人恰好是置顶者，
    映射里该字母的下标就是 0，跳转仍然正确（扫的是同一条顺序）。

    非 A-Z 开头的一律归到 "#"（真机 actors 里姓名以 ASCII 开头的只有 101 位，
    绝大多数要靠 romaji 兜），其余字母不出现在返回的 dict 里 → 界面画成暗色不可点。
    """
    clauses, params, having, hparams = _people_clauses(
        role_type, favorite, pinned, status, has_photo, min_works, cur_year)
    letter = _ACTOR_LETTER_EXPR
    sql = ("SELECT p.id AS id, " + letter + " AS lt FROM people p "
           "LEFT JOIN media_people mp ON mp.person_id = p.id "
           "LEFT JOIN media m ON m.id = mp.media_id"
           " WHERE " + " AND ".join(clauses) + " GROUP BY p.id")
    if having:
        sql += " HAVING " + " AND ".join(having)
    # 注意：这里**不能**用 _people_order(sort="letter")，因为它第三 tie-breaker 是
    # p.name —— 两边一致即可（查询侧也是同样的三元组），所以直接内联同一串。
    sql += f" ORDER BY p.pinned DESC, {letter} {'ASC' if asc else 'DESC'}, p.name COLLATE NOCASE"
    with _LOCK:
        conn = get_conn()
        try:
            rows = conn.execute(sql, params + hparams).fetchall()
        finally:
            conn.close()
    out = {}
    for i, r in enumerate(rows):
        ch = (r["lt"] or "").strip().upper()
        key = ch if ("A" <= ch <= "Z") else "#"
        # 只记第一次出现的位置：置顶块里可能已经出现过该字母，后面正文里那次不必覆盖
        if key not in out:
            out[key] = i
    return out


def all_people_ordered(role_type: str = "Actor"):
    """演员库卡片化：排序 = 置顶 > 收藏 > 作品数 > 姓名（保留旧入口，内部走 query_people）。

    额外带出 works（作品数）与 last_year（其作品的最新年份）；
    last_year 供「状态」启发式推断使用（v1.11.0：无刮削数据时按作品年份判现役/退役）。
    """
    return query_people(role_type=role_type, limit=0, sort="works", asc=False)


def media_with_nfo(limit: int = 1500):
    """有 nfo_path 的媒体（供演职员关联回填用）。"""
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT id, nfo_path FROM media "
                "WHERE IFNULL(nfo_path,'')<>'' ORDER BY id LIMIT ?", (int(limit),)
            ).fetchall()]
        finally:
            conn.close()


def media_id_by_nfo(nfo_path: str):
    """按 nfo_path 反查 media.id（v1.25.0：标签优化写回 nfo 后要同步库里的 genres）。

    Windows 路径大小写不敏感，用 COLLATE NOCASE 匹配；查不到返回 None。
    """
    if not nfo_path:
        return None
    with _LOCK:
        conn = get_conn()
        try:
            r = conn.execute(
                "SELECT id FROM media WHERE nfo_path = ? COLLATE NOCASE LIMIT 1",
                (str(nfo_path),)).fetchone()
            return int(r["id"]) if r else None
        finally:
            conn.close()


def media_people_roles(media_id: int):
    """返回某媒体现有的 [(姓名, role_type)]（按 order），用于判断关联是否需要回填。"""
    with _LOCK:
        conn = get_conn()
        try:
            return [(r["name"] or "", r["role_type"] or "Actor") for r in conn.execute(
                "SELECT p.name AS name, p.role_type AS role_type "
                "FROM media_people mp JOIN people p ON p.id=mp.person_id "
                "WHERE mp.media_id=? ORDER BY mp.person_order", (media_id,)
            ).fetchall()]
        finally:
            conn.close()


def count_people_links(role_type: Optional[str] = None) -> int:
    """media_people 关联数；给定 role_type 时只数该类型（如 'Director'）。"""
    with _LOCK:
        conn = get_conn()
        try:
            if role_type:
                r = conn.execute(
                    "SELECT COUNT(*) c FROM media_people mp JOIN people p ON p.id=mp.person_id "
                    "WHERE p.role_type=?", (role_type,)).fetchone()
            else:
                r = conn.execute("SELECT COUNT(*) c FROM media_people").fetchone()
            return r["c"] if r else 0
        finally:
            conn.close()


def toggle_person_favorite(person_id: int) -> int:
    """切换演员收藏状态，返回新值（1=已收藏）。"""
    with _LOCK:
        conn = get_conn()
        try:
            row = conn.execute("SELECT favorite FROM people WHERE id=?", (person_id,)).fetchone()
            new = 0 if (row and row["favorite"]) else 1
            conn.execute("UPDATE people SET favorite=? WHERE id=?", (new, person_id))
            conn.commit()
            return new
        finally:
            conn.close()


def toggle_person_pinned(person_id: int) -> int:
    """切换演员置顶状态，返回新值（1=已置顶）。"""
    with _LOCK:
        conn = get_conn()
        try:
            row = conn.execute("SELECT pinned FROM people WHERE id=?", (person_id,)).fetchone()
            new = 0 if (row and row["pinned"]) else 1
            conn.execute("UPDATE people SET pinned=? WHERE id=?", (new, person_id))
            conn.commit()
            return new
        finally:
            conn.close()


def cast_crew_map(ids=None):
    """取出 media_id -> {'actors': '演员1 / 演员2', 'directors': '导演1'}。

    用于影片卡片小字（演员 + 导演）。导演以 media_people.role_type='Director' 区分。

    v1.14.0：`ids` 限定只查这批影片 —— 影片墙改成按页加载后，每页只需几十条关联，
    不必再把几十万行关联整表拉进内存（这是「一进媒体库就卡死」的第一元凶）。
    """
    rows = []
    with _LOCK:
        conn = get_conn()
        try:
            if ids is None:
                rows = conn.execute(
                    "SELECT mp.media_id AS mid, p.name AS name, p.role_type AS rtype "
                    "FROM media_people mp JOIN people p ON p.id=mp.person_id "
                    "ORDER BY mp.media_id, mp.person_order"
                ).fetchall()
            else:
                ids = [int(i) for i in ids]
                for part in _chunks(ids):
                    ph = ",".join("?" * len(part))
                    rows.extend(conn.execute(
                        "SELECT mp.media_id AS mid, p.name AS name, p.role_type AS rtype "
                        "FROM media_people mp JOIN people p ON p.id=mp.person_id "
                        f"WHERE mp.media_id IN ({ph}) "
                        "ORDER BY mp.media_id, mp.person_order", part).fetchall())
        finally:
            conn.close()
    actors, directors = {}, {}
    for r in rows:
        nm = (r["name"] or "").strip()
        if not nm:
            continue
        mid = r["mid"]
        (directors if r["rtype"] == "Director" else actors).setdefault(mid, []).append(nm)
    out = {}
    for mid in set(actors) | set(directors):
        out[mid] = {
            "actors": " / ".join(dict.fromkeys(actors.get(mid, []))),
            "directors": " / ".join(dict.fromkeys(directors.get(mid, []))),
        }
    return out


def stats():
    """左下角统计。v1.14.0：改成 2 条查询（原来 4 条各自全表 COUNT）。

    v1.15.0：电影 / 剧集只数顶层条目（分片子记录归入「选集」，不重复计数）；
    「分片」单列一项，让用户知道库里有多少条子记录（cd1… / 剧集分集）。
    """
    with _LOCK:
        conn = get_conn()
        try:
            kinds = {r["kind"]: r["c"] for r in conn.execute(
                "SELECT kind, COUNT(*) c FROM media WHERE parent_id IS NULL "
                "GROUP BY kind").fetchall()}
            parts = conn.execute(
                "SELECT COUNT(*) c FROM media WHERE parent_id IS NOT NULL").fetchone()["c"]
            p = conn.execute("SELECT COUNT(*) c FROM people").fetchone()["c"]
            return {"movies": kinds.get("movie", 0), "tvshows": kinds.get("tvshow", 0),
                    "episodes": kinds.get("episode", 0), "parts": parts, "people": p}
        finally:
            conn.close()


def runtime_status() -> dict:
    """v1.18.0（反馈 98）：设置→数据与日志 的「实时运行状态」面板数据源。

    尽可能全面地汇总当前运行态：索引/连接/磁盘信息（与版本无关），供用户一眼掌握软件状态。
    """
    with _LOCK:
        conn = get_conn()
        try:
            s = stats()
            libs = library_counts()
            top = conn.execute(
                "SELECT COUNT(*) c FROM media WHERE parent_id IS NULL").fetchone()["c"]
            pragmas = {}
            for name in ("journal_mode", "synchronous", "cache_size", "mmap_size",
                         "page_size", "page_count", "freelist_count"):
                try:
                    row = conn.execute(f"PRAGMA {name}").fetchone()
                    pragmas[name] = row[0] if row else None
                except sqlite3.Error:
                    pragmas[name] = None
            return {"stats": s, "library_counts": libs, "top_total": top,
                    "pragmas": pragmas, "db_path": db_path()}
        finally:
            conn.close()


def toggle_favorite(media_id: int) -> int:
    with _LOCK:
        conn = get_conn()
        try:
            row = conn.execute("SELECT favorite FROM media WHERE id=?", (media_id,)).fetchone()
            new = 0 if (row and row["favorite"]) else 1
            conn.execute("UPDATE media SET favorite=? WHERE id=?", (new, media_id))
            conn.commit()
            return new
        finally:
            conn.close()


def set_user_rating(media_id: int, value) -> None:
    """写入用户评分（保留 1 位小数）；value 为 None 表示清除。"""
    with _LOCK:
        conn = get_conn()
        try:
            conn.execute("UPDATE media SET user_rating=? WHERE id=?", (value, media_id))
            conn.commit()
        finally:
            conn.close()


def favorites(kind: Optional[str] = None):
    with _LOCK:
        conn = get_conn()
        try:
            # v1.15.0：只取顶层条目，分片子记录不单独出现在收藏页
            sql = "SELECT * FROM media WHERE favorite=1 AND parent_id IS NULL"
            params = []
            if kind:
                sql += " AND kind=?"
                params.append(kind)
            sql += " ORDER BY added_time DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()


def recent(limit: int = 60):
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM media WHERE kind IN ('movie','tvshow') "
                "AND parent_id IS NULL "
                "ORDER BY COALESCE(last_played, added_time) DESC LIMIT ?", (limit,)
            ).fetchall()]
        finally:
            conn.close()


def mark_played(media_id: int) -> None:
    with _LOCK:
        conn = get_conn()
        try:
            conn.execute(
                "UPDATE media SET play_count=COALESCE(play_count,0)+1, "
                "last_played=strftime('%s','now') WHERE id=?", (media_id,)
            )
            conn.commit()
        finally:
            conn.close()


def all_genres():
    with _LOCK:
        conn = get_conn()
        try:
            rows = conn.execute("SELECT genres FROM media WHERE genres IS NOT NULL AND genres<>''").fetchall()
            seen = {}
            for r in rows:
                for g in (r["genres"] or "").split(","):
                    g = g.strip()
                    if g:
                        seen[g] = seen.get(g, 0) + 1
            return sorted(seen.items(), key=lambda kv: -kv[1])
        finally:
            conn.close()


def set_person_photo(person_id: int, photo_path: str) -> None:
    with _LOCK:
        conn = get_conn()
        try:
            conn.execute("UPDATE people SET photo_path=? WHERE id=?", (photo_path, person_id))
            conn.commit()
        finally:
            conn.close()


#: 「演员检测 → 手动编辑」允许直接改的列（白名单，防止 UI 误传字段写坏库）
_PERSON_EDITABLE = ("name", "alias", "romaji", "birthday", "status", "bio",
                    "thumb", "photo_path", "meta", "source", "source_url")


def set_person_fields(person_id: int, **fields) -> int:
    """**手动编辑专用**：原样写入，含空串 —— 也就是「能把字段清空」。

    为什么不复用 `update_person`：那个函数是给刮削用的，刻意跳过空值（不能拿空值覆盖
    已刮好的数据）。但手动编辑里用户把别名删掉就该真的删掉，所以另开这一条通道。
    `name` 有 UNIQUE 约束，撞名会抛 `sqlite3.IntegrityError`，由调用方提示。
    """
    sets, vals = [], []
    for k, v in fields.items():
        if k not in _PERSON_EDITABLE:
            continue
        sets.append(f"{k}=?")
        vals.append("" if v is None else str(v))
    if not sets:
        return 0
    with _LOCK:
        conn = get_conn()
        try:
            conn.execute(f"UPDATE people SET {', '.join(sets)} WHERE id=?",
                         vals + [int(person_id)])
            conn.commit()
            return len(sets)
        finally:
            conn.close()


# ---------- 演员刮削 ----------
_PERSON_FIELDS = ("name", "thumb", "bio", "photo_path", "alias", "birthday",
                  "romaji", "source", "source_url", "scraped_at", "meta", "status")


def update_person(person_id: int, only_missing: bool = False, **fields) -> int:
    """写入刮削结果。only_missing=True 时只填空缺字段（不覆盖已有）。返回更新字段数。"""
    sets, vals = [], []
    with _LOCK:
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM people WHERE id=?", (person_id,)).fetchone()
            if row is None:
                return 0
            cur = dict(row)
            for k, v in fields.items():
                if k not in _PERSON_FIELDS or v in (None, ""):
                    continue
                if only_missing and (cur.get(k) not in (None, "")):
                    continue
                sets.append(f"{k}=?")
                vals.append(v)
            # v1.21.1（反馈 2）：覆盖模式（即「修复历史资料」重刮）下，若这次没取回
            # meta/bio 的干净值，而本地仍是 v1.10.0 写坏的站内样板/HTML 残片垃圾，
            # 必须**显式清空**——否则「重新刮削」跑完，修复数量永不下降。
            # 注意 update_person 默认跳过空值（上面 v in (None,"") 分支），所以垃圾清不掉，
            # 这里单独把判定为 junk 的 meta/bio 置空。只在覆盖模式做，普通填空缺不会误清。
            if not only_missing:
                for k in ("meta", "bio"):
                    if k in fields:          # 已带干净值，不需清空
                        continue
                    old = cur.get(k) or ""
                    if old and _is_junk(old):
                        sets.append(f"{k}=?")
                        vals.append("")
            if not sets:
                return 0
            vals.append(person_id)
            conn.execute(f"UPDATE people SET {', '.join(sets)} WHERE id=?", vals)
            conn.commit()
            return len(sets)
        finally:
            conn.close()


def _is_junk(text: str) -> bool:
    """判断一段文本是否命中 v1.10.0 残留的站内样板/HTML 残片特征（与 _JUNK_LIKES 对应）。"""
    t = text or ""
    if not t:
        return False
    for pat in _JUNK_LIKES:
        tok = pat.strip("%")
        if tok and tok in t:
            return True
    return False


def people_for_scrape(only_no_photo: bool = True, limit: int = 0,
                      role_type: str = "Actor"):
    """待刮削演员清单：缺头像者优先，其余按缺信息程度排序。"""
    sql = ["SELECT p.*, (SELECT COUNT(*) FROM media_people mp WHERE mp.person_id=p.id) AS works",
           "FROM people p WHERE p.role_type=?"]
    args = [role_type]
    if only_no_photo:
        sql.append("AND (p.photo_path IS NULL OR p.photo_path='')")
    sql.append("ORDER BY (p.photo_path IS NULL OR p.photo_path='') DESC, works DESC, p.id")
    if limit and limit > 0:
        sql.append("LIMIT ?")
        args.append(int(limit))
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(" ".join(sql), args).fetchall()]
        finally:
            conn.close()


# 站内样板文案 / HTML 残片特征词（与 scraper._JUNK_TOKENS、main_window._META_JUNK 一致）
_JUNK_LIKES = ("%掲載%", "%情報交換%", "%無料動画%", "%アダルトビデオ%",
               "%og:%", "%property=%", "%content=%")


def _repair_where(role_type="Actor"):
    """「需要修复」的 WHERE 片段：仅命中 v1.10.0 误写入的站内样板/HTML 残片。

    修复集 = meta/bio 命中 _JUNK_LIKES 的演员。**不再**用「生日为空」判定——
    很多数据源（如 minnano）本就不提供生日，重刮也补不回来；把生日空当「待修复」
    会让计数永远降不下来（v1.21.2 修：用户报「修复完成还是 14」即此因）。
    真·损坏是样板文案垃圾，清掉即出列。
    """
    junk = " OR ".join(["p.meta LIKE ?"] * len(_JUNK_LIKES)
                       + ["p.bio LIKE ?"] * len(_JUNK_LIKES))
    sql = ("WHERE p.role_type=? "
           "AND (COALESCE(p.source_url,'')<>'' OR COALESCE(p.scraped_at,'')<>'') "
           "AND ( %s )" % junk)
    return sql, [role_type] + list(_JUNK_LIKES) * 2


def people_needing_repair(limit: int = 0, role_type: str = "Actor"):
    """需要**重新刮削修复**的演员清单（= 资料里残留 v1.10.0 样板/HTML 残片的演员）。

    背景（v1.11.1）：v1.10.0 的解析器把 `<head>` 里 og:description 的站内样板文案
    写进了 meta/bio（真机库 72/108 条）。解析器修好后，这批历史记录只能重刮清掉。
    注意：本函数**只认样板垃圾**，不再用「生日为空」判定——不少数据源（minnano）
    本就不提供生日，缺生日属正常缺失，不算损坏（v1.21.2 修正，见 _repair_where）。
    """
    where, args = _repair_where(role_type)
    sql = ("SELECT p.*, (SELECT COUNT(*) FROM media_people mp WHERE mp.person_id=p.id) AS works "
           "FROM people p " + where + " ORDER BY works DESC, p.id")
    if limit and limit > 0:
        sql += " LIMIT ?"
        args = list(args) + [int(limit)]
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
        finally:
            conn.close()


def count_needing_repair(role_type: str = "Actor") -> int:
    where, args = _repair_where(role_type)
    with _LOCK:
        conn = get_conn()
        try:
            return conn.execute("SELECT COUNT(*) c FROM people p " + where, args).fetchone()["c"]
        finally:
            conn.close()


# v1.22.0：「补齐信息」判定 —— 资料不全（缺头像 / 别名 / 简介）的演员。
# 注意：**不把「缺生日」算进来** —— 多数数据源（minnano）本就不提供生日，把它算作待补齐
# 会让这个集合永远清不空（与 _repair_where 同一教训，见 v1.21.2）。
_FILL_MISSING = ("COALESCE(p.photo_path,'')='' OR COALESCE(p.alias,'')='' "
                 "OR COALESCE(p.bio,'')=''")


def people_needing_fill(limit: int = 0, role_type: str = "Actor"):
    """「补齐信息」待办清单：缺头像 / 别名 / 简介的演员（按缺得多的排前面）。"""
    sql = ("SELECT p.*, (SELECT COUNT(*) FROM media_people mp WHERE mp.person_id=p.id) AS works "
           "FROM people p WHERE p.role_type=? AND (" + _FILL_MISSING + ") "
           "ORDER BY (COALESCE(p.photo_path,'')='') DESC, works DESC, p.id")
    args = [role_type]
    if limit and limit > 0:
        sql += " LIMIT ?"
        args.append(int(limit))
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
        finally:
            conn.close()


def count_needing_fill(role_type: str = "Actor") -> int:
    with _LOCK:
        conn = get_conn()
        try:
            return conn.execute(
                "SELECT COUNT(*) c FROM people p WHERE p.role_type=? AND (" + _FILL_MISSING + ")",
                (role_type,)).fetchone()["c"]
        finally:
            conn.close()


def scraper_stats():
    with _LOCK:
        conn = get_conn()
        try:
            total = conn.execute("SELECT COUNT(*) c FROM people").fetchone()["c"]
            photo = conn.execute(
                "SELECT COUNT(*) c FROM people WHERE photo_path IS NOT NULL AND photo_path<>''"
            ).fetchone()["c"]
            bday = conn.execute(
                "SELECT COUNT(*) c FROM people WHERE birthday IS NOT NULL AND birthday<>''"
            ).fetchone()["c"]
            alias = conn.execute(
                "SELECT COUNT(*) c FROM people WHERE alias IS NOT NULL AND alias<>''"
            ).fetchone()["c"]
            scraped = conn.execute(
                "SELECT COUNT(*) c FROM people WHERE scraped_at IS NOT NULL AND scraped_at<>''"
            ).fetchone()["c"]
            where, args = _repair_where()
            repair = conn.execute("SELECT COUNT(*) c FROM people p " + where, args).fetchone()["c"]
            fill = conn.execute(
                "SELECT COUNT(*) c FROM people p WHERE p.role_type='Actor' AND ("
                + _FILL_MISSING + ")").fetchone()["c"]
            return {"total": total, "photo": photo, "birthday": bday,
                    "alias": alias, "scraped": scraped, "repair": repair, "fill": fill}
        finally:
            conn.close()


def people_by_role(role_type: str = "Actor", limit: int = 500):
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM people WHERE role_type=? ORDER BY name LIMIT ?",
                (role_type, limit)
            ).fetchall()]
        finally:
            conn.close()


# ---------- 演员检测（v1.31.0，反馈 3） ----------
def people_for_match(role_type: str = "Actor"):
    """演员检测的输入：一次取回比对所需的**轻量画像**。

    刻意不取 `bio`（每条几百字，5909 条纯属浪费）—— 比对只用得上
    `name / alias / romaji / birthday / meta / 头像 / 作品数`。
    """
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT p.id, p.name, p.alias, p.romaji, p.birthday, p.thumb,"
                " p.photo_path, p.status, p.meta, p.source,"
                " (SELECT COUNT(*) FROM media_people mp WHERE mp.person_id=p.id) AS works"
                " FROM people p WHERE p.role_type=? ORDER BY p.id", (role_type,)
            ).fetchall()]
        finally:
            conn.close()


def merge_people(keep_id: int, drop_id: int) -> dict:
    """把 `drop` 并进 `keep`（「演员检测」页确认关联时调用的唯一写入口）。

    做四件事：
      1. `media_people` 链接搬运 —— 主键是 (media_id, person_id)，所以用
         `INSERT OR IGNORE ... SELECT` 天然去重（两人都演过的片子不会插重）；
      2. 补齐 `keep` 的空字段（生日 / 罗马音 / 头像 / 简介 / 来源…），
         已有值**一律不覆盖** —— 合并是「补全」而不是「覆盖」；
      3. `alias` 追加 `drop` 的主名与旧别名（去重、滤垃圾），
         `meta` 按键补齐缺失项；
      4. 删掉 `drop` 行（`people.name` 是 UNIQUE，所以名字只能落进 alias）。

    返回统计字典；失败时 `ok=False` 且不改动任何东西。
    """
    keep_id, drop_id = int(keep_id), int(drop_id)
    if keep_id == drop_id:
        return {"ok": False, "err": "保留者与被合并者是同一个人"}
    with _LOCK:
        conn = get_conn()
        try:
            k = conn.execute("SELECT * FROM people WHERE id=?", (keep_id,)).fetchone()
            d = conn.execute("SELECT * FROM people WHERE id=?", (drop_id,)).fetchone()
            if k is None or d is None:
                return {"ok": False, "err": "记录不存在（可能已被合并过）"}
            kd, dd = dict(k), dict(d)

            before = conn.total_changes
            conn.execute(
                "INSERT OR IGNORE INTO media_people(media_id, person_id, char_role, person_order)"
                " SELECT media_id, ?, char_role, person_order FROM media_people WHERE person_id=?",
                (keep_id, drop_id))
            moved = conn.total_changes - before
            conn.execute("DELETE FROM media_people WHERE person_id=?", (drop_id,))

            sets, vals = [], []
            for f in ("birthday", "romaji", "thumb", "photo_path", "bio",
                      "source", "source_url", "status"):
                if not str(kd.get(f) or "").strip() and str(dd.get(f) or "").strip():
                    sets.append(f"{f}=?")
                    vals.append(dd[f])

            alias = _merge_alias_text(kd.get("alias"), kd.get("name"),
                                      dd.get("name"), dd.get("alias"))
            if alias != (kd.get("alias") or ""):
                sets.append("alias=?")
                vals.append(alias)

            meta = _merge_meta_text(kd.get("meta"), dd.get("meta"))
            if meta != (kd.get("meta") or ""):
                sets.append("meta=?")
                vals.append(meta)

            if sets:
                conn.execute(f"UPDATE people SET {', '.join(sets)} WHERE id=?",
                             vals + [keep_id])
            conn.execute("DELETE FROM people WHERE id=?", (drop_id,))
            conn.commit()
            return {"ok": True, "keep_id": keep_id, "drop_id": drop_id, "moved": moved,
                    "fields": len(sets), "alias": alias}
        finally:
            conn.close()


#: 别名拆分类（与 actorcheck._ALIAS_SEP 同口径，但这边不能反向 import 检测层）
_ALIAS_SPLIT = re.compile(r"[、，,／/|｜;；・･]+")


def _merge_alias_text(keep_alias, keep_name, drop_name, drop_alias) -> str:
    out, seen = [], set()
    for src in (keep_alias, drop_name, drop_alias):
        for t in _ALIAS_SPLIT.split(str(src or "")):
            t = t.strip()
            if not t or len(t) < 2 or any(x in t for x in ("編集", "データ")):
                continue
            key = t.casefold()
            if key == str(keep_name or "").strip().casefold() or key in seen:
                continue
            seen.add(key)
            out.append(t)
    return "、".join(out[:40])


def _merge_meta_text(keep_meta, drop_meta) -> str:
    """meta 按键补齐（keep 已有的键不动），非法 JSON 时退化为「keep 原样」。"""
    try:
        km = json.loads(keep_meta) if keep_meta else {}
        dm = json.loads(drop_meta) if drop_meta else {}
    except Exception:
        return keep_meta or ""
    if not isinstance(km, dict) or not isinstance(dm, dict):
        return keep_meta or ""
    changed = False
    for key, val in dm.items():
        if val in (None, "") or km.get(key):
            continue
        km[key] = val
        changed = True
    if not changed:
        return keep_meta or ""
    try:
        return json.dumps(km, ensure_ascii=False)
    except Exception:
        return keep_meta or ""


# v1.15.0：决定「一条记录是独立影片、还是某部影片的分片/分集」的结构字段。
# 这四个字段与 mode 无关，永远比对写入（见 upsert_media_by_path）。
_STRUCT_COLS = ("kind", "parent_id", "season", "episode")


def media_id_by_path(fp: str):
    with _LOCK:
        conn = get_conn()
        try:
            r = conn.execute("SELECT id FROM media WHERE file_path=?", (fp,)).fetchone()
            return r["id"] if r else None
        finally:
            conn.close()


def upsert_media_by_path(mode: str = "overwrite", **fields) -> int:
    """按 file_path 去重写入，返回 media.id。

    mode:
      - "overwrite": 全量覆盖（默认，兼容旧行为）。
      - "new":        仅当文件为新增、或 file_mtime 变化(被修改)时才更新。
      - "fill":       仅补充缺失(空)字段，不覆盖已有非空值。

    v1.15.0：`_STRUCT_COLS`（kind / parent_id / season / episode）**忽略 mode 一律比对写入**。
    否则用户把 cd1…cd5 归组后，只有「扫描全部并覆盖」能生效，`new`（mtime 没变）与 `fill`
    （字段非空就不写）都会让老记录一直停在「各自当成一部电影」的状态。
    """
    with _LOCK:
        conn = get_conn()
        try:
            fp = fields.get("file_path")
            _r = conn.execute("SELECT * FROM media WHERE file_path=?", (fp,)).fetchone() if fp else None
            row = dict(_r) if _r is not None else None
            mid = row["id"] if row else None
            if mid:
                # 结构字段：值确实变了才写
                struct = {c: fields[c] for c in _STRUCT_COLS
                          if c in fields and row.get(c) != fields[c]}
                if mode == "new":
                    cur_m = fields.get("file_mtime")
                    old_m = row.get("file_mtime")
                    if cur_m is not None and old_m is not None and abs(float(cur_m) - float(old_m)) < 1:
                        if struct:
                            sets = ",".join(f"{c}=?" for c in struct)
                            conn.execute(f"UPDATE media SET {sets} WHERE id=?",
                                         list(struct.values()) + [mid])
                            conn.commit()
                        return mid  # 未变更，跳过
                if mode == "fill":
                    cols, vals = list(struct), list(struct.values())
                    for c, v in fields.items():
                        if c == "id" or c in struct or v in (None, ""):
                            continue
                        old = row.get(c)
                        if old in (None, "", 0):
                            cols.append(c)
                            vals.append(v)
                    if cols:
                        sets = ",".join(f"{c}=?" for c in cols)
                        conn.execute(f"UPDATE media SET {sets} WHERE id=?", vals + [mid])
                else:
                    cols = [c for c in fields if c != "id"]
                    sets = ",".join(f"{c}=?" for c in cols)
                    conn.execute(
                        f"UPDATE media SET {sets} WHERE id=?",
                        [fields[c] for c in cols] + [mid],
                    )
            else:
                cols = list(fields.keys())
                ph = ",".join("?" for _ in cols)
                cur = conn.execute(
                    f"INSERT INTO media({','.join(cols)}) VALUES({ph})",
                    [fields[c] for c in cols],
                )
                mid = cur.lastrowid
            conn.commit()
            return mid
        finally:
            conn.close()


def clear_media_people(media_id: int) -> None:
    with _LOCK:
        conn = get_conn()
        try:
            conn.execute("DELETE FROM media_people WHERE media_id=?", (media_id,))
            conn.commit()
        finally:
            conn.close()


# ---------------- v1.15.0：选集（分片）与索引清理 ----------------

def children_of(parent_id: int):
    """取某部影片的分片/分集，按序号升序 —— 详情页「选集」用。"""
    if not parent_id:
        return []
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM media WHERE parent_id=? "
                "ORDER BY IFNULL(season,1), IFNULL(episode,9999), id",
                (int(parent_id),)).fetchall()]
        finally:
            conn.close()


def parts_counts(ids):
    """批量取「这批判片各自有几个分片」→ {media_id: n}。一次 GROUP BY，不是逐个查。"""
    ids = [i for i in (ids or []) if i]
    if not ids:
        return {}
    out = {}
    with _LOCK:
        conn = get_conn()
        try:
            for chunk in _chunks(ids):
                ph = ",".join("?" * len(chunk))
                for r in conn.execute(
                        f"SELECT parent_id, COUNT(*) c FROM media "
                        f"WHERE parent_id IN ({ph}) GROUP BY parent_id", chunk).fetchall():
                    out[r["parent_id"]] = r["c"]
        finally:
            conn.close()
    return out


def delete_media(media_id: int) -> int:
    """删除一条媒体记录（含其关联演员）。**不动磁盘文件。** 返回删掉的关联行数。"""
    with _LOCK:
        conn = get_conn()
        try:
            n = conn.execute("SELECT COUNT(*) c FROM media_people WHERE media_id=?",
                             (media_id,)).fetchone()["c"]
            conn.execute("DELETE FROM media_people WHERE media_id=?", (media_id,))
            conn.execute("DELETE FROM media WHERE id=?", (media_id,))
            conn.commit()
            return n
        finally:
            conn.close()


def update_media_fields(media_id: int, **fields) -> None:
    """更新媒体记录的部分字段（v1.15.0 分组 / 失效清理用）。

    只写入给出的键，空值（None/""）也会覆盖成空 —— 分组时要把旧 parent_id 清回 NULL，
    必须能显式置空，不能用 upsert 的「非空才写」语义。
    """
    fields = {k: v for k, v in fields.items() if k not in ("id",)}
    if not fields:
        return
    with _LOCK:
        conn = get_conn()
        try:
            sets = ",".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE media SET {sets} WHERE id=?",
                         list(fields.values()) + [int(media_id)])
            conn.commit()
        finally:
            conn.close()


def media_for_prune(library: Optional[str] = None, root: Optional[str] = None):
    """取用于「校验文件是否还存在」的最小字段集（id/parent_id/kind/file_path）。

    只挑需要的列，5 万条也不会把 plot 之类的大字段读进内存。
    """
    where, params = [], []
    if library:
        where.append("library=?")
        params.append(library)
    if root:
        where.append("(file_path LIKE ? OR nfo_path LIKE ?)")
        params.extend([root.rstrip("\\/") + "%", root.rstrip("\\/") + "%"])
    sql = ("SELECT id, parent_id, kind, file_path, nfo_path, title, poster FROM media"
           + ((" WHERE " + " AND ".join(where)) if where else ""))
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()


def media_for_imagescan(library: Optional[str] = None):
    """图像检测（v1.30.0）用：只取判定需要的最小列。

    刻意**不带 plot**：5 万片时那列能占几百 MB，而检测只需要路径。

    `poster/thumb/fanart` 三列来自上一次刮削，是「图上哪儿去了」的第一线索；
    真正判定时 `imagedetect.resolve()` 还会拿它们当候选之一。
    """
    if library:
        sql = ("SELECT id, title, library, file_path, nfo_path, poster, thumb, fanart "
               "FROM media WHERE library=? ORDER BY sort_title")
        params = (library,)
    else:
        sql = ("SELECT id, title, library, file_path, nfo_path, poster, thumb, fanart "
               "FROM media")
        params = ()
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()


def count_for_prune(library: Optional[str] = None, root: Optional[str] = None) -> int:
    rows = media_for_prune(library, root)
    return len(rows)


# ---------------- 智能推荐：向量编辑 / 画像概览（v1.24.0） ----------------
def vector_overrides():
    """读出手动加权的偏好向量：[(dim, key, weight, note, updated), ...]。

    `dim` ∈ tag / actor / director / studio / series；weight>0 加强、<0 软排斥、=0 屏蔽。
    这是向量编辑页的**权威来源**（settings.json 里另存一份快照，随配置一起导入导出）。
    """
    with _LOCK:
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT dim, key, weight, note, updated FROM vector_overrides "
                "ORDER BY dim, key").fetchall()
            return [tuple(r) for r in rows]
        except sqlite3.Error:
            return []
        finally:
            conn.close()


def set_vector_override(dim: str, key: str, weight, note: str = None):
    """写一条向量权重；weight 传 None → 删除该条。"""
    dim, key = str(dim), str(key)
    with _LOCK:
        conn = get_conn()
        try:
            if weight is None:
                conn.execute("DELETE FROM vector_overrides WHERE dim=? AND key=?",
                             (dim, key))
            else:
                conn.execute(
                    "INSERT INTO vector_overrides (dim, key, weight, note, updated) "
                    "VALUES (?,?,?,?,?) ON CONFLICT(dim, key) DO UPDATE SET "
                    "weight=excluded.weight, note=excluded.note, updated=excluded.updated",
                    (dim, key, float(weight), note, datetime.now().timestamp()))
            conn.commit()
        finally:
            conn.close()


def clear_vector_overrides(dim: str = None):
    """清空向量权重（传 dim 只清某一维度）。"""
    with _LOCK:
        conn = get_conn()
        try:
            if dim:
                conn.execute("DELETE FROM vector_overrides WHERE dim=?", (str(dim),))
            else:
                conn.execute("DELETE FROM vector_overrides")
            conn.commit()
        finally:
            conn.close()


def media_for_insight(library: Optional[str] = None, favorites_only: bool = False):
    """画像概览 / 智能推荐用的**一次全量取数**（只挑分析要的列，5 万条约 1~2 秒）。

    刻意不走 `search_media`：那张表投影 + 分页是为「墙」服务的，分析要的是全量行。

    v1.24.1（反馈 4）：`favorites_only` 支持把统计范围收窄到「我的收藏」。
    **注意这里的列是分析专用投影，没有 poster / file_path** —— 拿这些行直接去画卡片
    会全是占位图（v1.24.0 智能推荐墙的根因），要画卡片请用 `media_by_ids()` 回填。
    """
    cols = ("id, title, year, genres, studio, collection, quality, runtime, file_size, "
            "rating, user_rating, favorite, play_count, added_time, added_date, "
            "kind, library")
    where, params = ["parent_id IS NULL"], []
    if library:
        where.append("library=?")
        params.append(library)
    if favorites_only:
        where.append("favorite=1")
    sql = f"SELECT {cols} FROM media WHERE {' AND '.join(where)}"
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()


def media_by_ids(ids, light: bool = True):
    """按 id 批量取**完整** media 行，返回顺序与传入 ids 一致（不存在的跳过）。

    v1.24.1（反馈 1）：智能推荐拿到的行来自 `media_for_insight`，只有分析列，
    没有 poster / fanart / file_path / thumb —— 卡片于是全成占位图、播放按钮也不建。
    推荐结果出炉后用这个函数把 id 换成完整行即可。
    """
    out, seen = [], []
    for i in ids or ():
        try:
            n = int(i)
        except (TypeError, ValueError):
            continue
        if n not in seen:
            seen.append(n)
    if not seen:
        return out
    by_id = {}
    with _LOCK:
        conn = get_conn()
        try:
            for chunk in _chunks(seen, 900):
                marks = ",".join("?" * len(chunk))
                sql = (f"SELECT {_select_cols(light)} FROM media m WHERE m.id IN ({marks})")
                for r in conn.execute(sql, [int(x) for x in chunk]).fetchall():
                    by_id[int(r["id"])] = dict(r)
        finally:
            conn.close()
    for n in seen:
        r = by_id.get(n)
        if r is not None:
            out.append(r)
    return out


def people_links_map(role_type: str = None, media_ids=None):
    """{media_id: [人名, ...]}。用于推荐打分与画像统计（57k 链接一次读完）。"""
    where, params = [], []
    if role_type:
        where.append("p.role_type=?")
        params.append(role_type)
    if media_ids:
        ids = list(media_ids)
        out = {}
        with _LOCK:
            conn = get_conn()
            try:
                for chunk in _chunks(ids, 900):
                    qs = ",".join("?" * len(chunk))
                    sql = ("SELECT mp.media_id, p.name FROM media_people mp "
                           "JOIN people p ON p.id=mp.person_id "
                           f"WHERE mp.media_id IN ({qs})"
                           + ((" AND " + " AND ".join(where)) if where else ""))
                    for mid, name in conn.execute(sql, list(chunk) + params):
                        out.setdefault(mid, []).append(name)
                return out
            finally:
                conn.close()
    sql = ("SELECT mp.media_id, p.name FROM media_people mp "
           "JOIN people p ON p.id=mp.person_id"
           + ((" WHERE " + " AND ".join(where)) if where else ""))
    out = {}
    with _LOCK:
        conn = get_conn()
        try:
            for mid, name in conn.execute(sql, params):
                out.setdefault(mid, []).append(name)
            return out
        finally:
            conn.close()


def people_counts_by_role() -> dict:
    """{'Actor': (人数, 链接数), 'Director': (...)} —— 画像概览头部用。"""
    out = {}
    with _LOCK:
        conn = get_conn()
        try:
            for role, n in conn.execute(
                    "SELECT role_type, COUNT(*) FROM people GROUP BY role_type"):
                out[role or "Other"] = [int(n), 0]
            for role, n in conn.execute(
                    "SELECT p.role_type, COUNT(*) FROM media_people mp "
                    "JOIN people p ON p.id=mp.person_id GROUP BY p.role_type"):
                out.setdefault(role or "Other", [0, 0])[1] = int(n)
        finally:
            conn.close()
    return out


def favorite_people(role_type: str = None):
    """收藏的人（演员/导演）→ 推荐画像的种子。"""
    sql = "SELECT id, name, role_type FROM people WHERE COALESCE(favorite,0)=1"
    params = []
    if role_type:
        sql += " AND role_type=?"
        params.append(role_type)
    with _LOCK:
        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()


def person_work_counts() -> dict:
    """{人名: 作品数} —— 全库每位演员/导演关联的**去重作品数**。

    v1.33.2（反馈）：智能推荐里「收藏的艺人」需要按**稀有度**给权重，否则
    作品数最多的那几位（如 350 部的头部艺人）会垄断推荐结果。这里一次性
    聚合出全库计数（约 7000 人，毫秒级），供 recommend.py 做稀有度折减。
    同名不同人（重名）会合并计数 —— 对「稀有度」这个用途足够了。
    """
    out = {}
    with _LOCK:
        conn = get_conn()
        try:
            for name, n in conn.execute(
                    "SELECT p.name, COUNT(DISTINCT mp.media_id) "
                    "FROM people p JOIN media_people mp ON mp.person_id=p.id "
                    "GROUP BY p.name"):
                out[str(name or "")] = int(n)
        finally:
            conn.close()
    return out

