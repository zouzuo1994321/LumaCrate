"""诊断：真实库里「需要修复」的演员到底被什么条件命中（只读，不写库）。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/src")
import database as db

print("db_path =", db.db_path())

with db._LOCK:
    conn = db.get_conn()
    try:
        # 当前 _repair_where 命中的全部人
        where, args = db._repair_where("Actor")
        rows = conn.execute(
            "SELECT p.id, p.name, p.role_type, p.source, "
            "substr(p.meta,1,40) AS meta_head, "
            "substr(p.bio,1,40) AS bio_head, "
            "COALESCE(p.birthday,'') AS birthday, "
            "COALESCE(p.source_url,'')<>'' AS has_url, "
            "COALESCE(p.scraped_at,'')<>'' AS has_scraped "
            "FROM people p " + where + " ORDER BY p.id", args).fetchall()
    finally:
        conn.close()

print(f"需要修复人数 = {len(rows)}")
junk_n, bday_n, both_n = 0, 0, 0
src_counter = {}
for r in rows:
    r = dict(r)
    meta, bio, bday = r["meta_head"] or "", r["bio_head"] or "", r["birthday"]
    is_junk = db._is_junk(meta) or db._is_junk(bio)
    is_bday = (bday == "")
    if is_junk: junk_n += 1
    if is_bday: bday_n += 1
    if is_junk and is_bday: both_n += 1
    src_counter[r["source"]] = src_counter.get(r["source"], 0) + 1
    print(f"  #{r['id']} {r['name']!r} src={r['source']!r} junk={is_junk} bday_empty={is_bday} "
          f"meta={meta!r} bio={bio!r}")

print(f"\n仅 junk 命中: {junk_n}  仅 birthday 命中: {bday_n}  两者都命中: {both_n}")
print(f"source 分布: {src_counter}")
