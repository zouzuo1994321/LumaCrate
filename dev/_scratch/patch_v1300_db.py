# -*- coding: utf-8 -*-
"""补丁：database.py 加「首字母」排序 + people 查询口径提取 + people_letter_index（v1.30.0）。"""
import io

P = r"Z:/【01】自研软件/【26-19】本地影视中心/src/database.py"
s = io.open(P, encoding="utf-8", newline="").read()


def patch(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, "命中 %d 次（期望 %d）：\n%s" % (n, count, old[:120])
    s = s.replace(old, new)
    print("  [ok] +%d" % count)


# ---- 1) ACTOR_SORTS 加「首字母」 ----
patch(
    '''ACTOR_SORTS = [
    ("works",     "作品数",   "works"),
    ("last_year", "最新作品", "last_year"),
    ("name",      "姓名",     "p.name COLLATE NOCASE"),
    ("birthday",  "生日",     "p.birthday"),''',
    '''# v1.30.0：A-Z 字母索引用的「首字母」排序键。
# 优先罗马音 `romaji`（真机库覆盖约 67%），没有就退回姓名首字符（欧美演员名本身
# 就是 ASCII）；中日文汉字/假名开头的会自成一组，按 Unicode 排在所有 A-Z 之后，
# 界面上显示为「#」。**排序与索引必须用同一个表达式**，否则字母跳转会错位。
_ACTOR_LETTER_EXPR = ("UPPER(SUBSTR(COALESCE(NULLIF(TRIM(p.romaji), ''), p.name), 1, 1))")

ACTOR_SORTS = [
    ("works",     "作品数",   "works"),
    ("last_year", "最新作品", "last_year"),
    ("name",      "姓名",     "p.name COLLATE NOCASE"),
    ("letter",    "首字母",   _ACTOR_LETTER_EXPR),
    ("birthday",  "生日",     "p.birthday"),''')

# ---- 2) 提取 people 的 WHERE/HAVING 构造（query_people / count_people / people_letter_index 共用） ----
patch(
    '''def query_people(role_type: str = "Actor", limit: int = 0, offset: int = 0,
                 sort: str = "works", asc: bool = False, favorite=None, pinned=None,
                 status=None, has_photo=None, min_works=None, cur_year=None):
    """演员库查询（筛选 + 排序 + 分页）。

    排序恒以「置顶」优先（与旧行为一致）；`sort` 只接受白名单键。
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
    expr = _ACTOR_SORT_EXPR.get(sort) or _ACTOR_SORT_EXPR["works"]''',
    '''def _people_clauses(role_type="Actor", favorite=None, pinned=None, status=None,
                    has_photo=None, min_works=None, cur_year=None):
    """演员/导演页的 WHERE + HAVING 构造（v1.30.0 提取）。

    `query_people` / `count_people` / `people_letter_index` **必须共用这一份** ——
    口径一旦分叉，就会出现「共 N 位」和实际列表对不上、字母跳转错位这类静默 bug。
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


def query_people(role_type: str = "Actor", limit: int = 0, offset: int = 0,
                 sort: str = "works", asc: bool = False, favorite=None, pinned=None,
                 status=None, has_photo=None, min_works=None, cur_year=None):
    """演员库查询（筛选 + 排序 + 分页）。

    排序恒以「置顶」优先（与旧行为一致）；`sort` 只接受白名单键。
    """
    clauses, params, having, hparams = _people_clauses(
        role_type, favorite, pinned, status, has_photo, min_works, cur_year)
    expr = _ACTOR_SORT_EXPR.get(sort) or _ACTOR_SORT_EXPR["works"]''')

# ---- 3) count_people 复用同一份口径 ----
patch(
    '''    """`query_people` 同口径的总人数（用于「共 N 位」）。"""
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
    sql = ("SELECT COUNT(*) c FROM (SELECT p.id AS pid, MAX(m.year) AS last_year, "''',
    '''    """`query_people` 同口径的总人数（用于「共 N 位」）。"""
    clauses, params, having, hparams = _people_clauses(
        role_type, favorite, pinned, status, has_photo, min_works, cur_year)
    sql = ("SELECT COUNT(*) c FROM (SELECT p.id AS pid, MAX(m.year) AS last_year, "''')

# ---- 4) 新增 people_letter_index（紧跟 count_people 之后） ----
patch(
    '''def all_people_ordered(role_type: str = "Actor"):''',
    '''def people_letter_index(role_type: str = "Actor", asc: bool = True, **filters):
    """A-Z 字母索引（v1.30.0）：字母 -> 该字母在「首字母」排序下的**第几个人**（0 基）。

    返回的键只含结果里实际出现过的字母；非 A-Z（中日文开头且无 romaji）统一记为 "#"。
    值是**人员序号**，界面再按「每行 N 个」换算成行号去滚动 —— 因为只有界面知道列数。

    口径与 `query_people(sort="letter", asc=asc, **filters)` 完全一致（共用
    `_people_clauses`，ORDER BY 也用同一个 `_ACTOR_LETTER_EXPR`），否则跳转会错位。
    """
    clauses, params, having, hparams = _people_clauses(role_type=role_type, **filters)
    expr = _ACTOR_LETTER_EXPR
    direction = "ASC" if asc else "DESC"
    sql = (f"SELECT {expr} AS k FROM people p WHERE " + " AND ".join(clauses)
           + " GROUP BY p.id")
    if having:
        sql += " HAVING " + " AND ".join(having)
    sql += f" ORDER BY p.pinned DESC, {expr} {direction}, p.name COLLATE NOCASE"
    with _LOCK:
        conn = get_conn()
        try:
            keys = [r[0] for r in conn.execute(sql, params + hparams).fetchall()]
        finally:
            conn.close()
    out = {}
    for i, k in enumerate(keys):
        kk = (k or "").strip().upper()
        key = kk if (len(kk) == 1 and "A" <= kk <= "Z") else "#"
        if key not in out:
            out[key] = i
    return out


def all_people_ordered(role_type: str = "Actor"):''')

io.open(P, "w", encoding="utf-8", newline="").write(s)
print("database.py patched,", len(s), "chars")
