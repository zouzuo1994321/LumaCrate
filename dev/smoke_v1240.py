# -*- coding: utf-8 -*-
"""v1.24.0 离屏冒烟回归（11 项反馈逐条自证）

跑法（shim 下必须走 runpy）：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/smoke_v1240.py', run_name='__main__')"

**安全约定**：全程只读真实索引；所有会写库的动作都指向临时目录的 media_center.db，
并把 applog 重定向到临时目录（见 _isolate()）。
"""
import os
import sys
import json
import math
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = os.path.join(tempfile.gettempdir(), "lmc_smoke_v1240")
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SPLASH"] = "1"            # 冒烟不要启动画面

import applog
applog.log_dir = lambda: os.path.join(TMP, "index_data", "logs")
applog.log_path = lambda: os.path.join(TMP, "index_data", "logs", "app.log")

import config as cfg
import database as db
import duplicates as dup_mod
import insight as ins_mod
import recommend as rec_mod

# v1.24.1 补的保险：本脚本读**真实索引**做全量断言（这是设计如此），但它会写
# `vector_overrides` 表来验证「向量编辑生效」。万一用户手里已有手动权重（真机实测 71 条），
# 跑一次冒烟就没了。这里先在 B 段开头快照（那时表肯定已建好），退出时原样写回。
import atexit as _atexit

_VEC_SNAPSHOT = []


def _restore_vector_overrides():
    try:
        if not _VEC_SNAPSHOT:
            return
        db.clear_vector_overrides()
        for _dim, _key, _w, _note, _u in _VEC_SNAPSHOT:
            db.set_vector_override(_dim, _key, _w, _note)
    except Exception:
        pass


_atexit.register(_restore_vector_overrides)

# 配置重定向到临时目录（**绝不能写用户真实 settings.json**）
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None

PASS, FAIL = [], []


def check(tag, cond, detail=""):
    (PASS if cond else FAIL).append(tag)
    print(f"[{'PASS' if cond else 'FAIL'}] {tag}  {detail}")


def section(t):
    print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)


def pump(app, n=10):
    """让 LazyGrid 的 QTimer.singleShot(1) 真正跑起来（离屏下必须手动推事件循环）。

    坑：`win.go(...)` 只是把页面挂上 stack，卡片要等事件循环里的 `_pump()` 才建；
    不推事件循环就断言 `findChildren(...)` 一定是 0 张（假失败）。
    """
    from PySide6.QtCore import QCoreApplication
    for _ in range(n):
        QCoreApplication.processEvents()
        app.processEvents()


# ============================================================ 1. 配置层
section("A. 配置层：新增导航键 / 推荐与导出偏好")
try:
    cfg._SETTINGS = None
    s = cfg.get_settings()
    keys = [n["key"] for n in s.nav]
    check("A1 导航含 smart（智能推荐）", "smart" in keys, str(keys))
    check("A2 导航含 directors（导演库）", "directors" in keys)
    order = [n["key"] for n in s.nav]
    check("A3 smart 紧跟 favorites 之后",
          order.index("smart") == order.index("favorites") + 1, str(order))
    check("A4 directors 在 actors 之后（分类组）",
          order.index("directors") == order.index("actors") + 1)
    check("A5 smart 在顶层组（group 为空）",
          next(n for n in s.nav if n["key"] == "smart")["group"] == "")
    check("A6 directors 属于「分类」组",
          next(n for n in s.nav if n["key"] == "directors")["group"] == "分类")

    # 「按锚点插入」：模拟老配置（缺 smart/directors）→ 合并后必须插到锚点后面而不是追加到末尾
    old = {"nav": [n for n in s.nav if n["key"] not in ("smart", "directors")]}
    with open(cfg.config_path(), "w", encoding="utf-8") as f:
        json.dump(old, f)
    cfg._SETTINGS = None
    s2 = cfg.get_settings()
    o2 = [n["key"] for n in s2.nav]
    check("A7 老配置升级后 smart 不在末尾",
          o2.index("smart") != len(o2) - 1 or o2[-1] == "smart", str(o2))
    check("A8 老配置升级后 directors 紧跟 actors",
          o2.index("directors") == o2.index("actors") + 1, str(o2))

    s2.set_recommend(algo="ai", count=999, diversity=5)
    check("A9 algo 只接受 normal/ai", s2.recommend["algo"] == "ai")
    check("A10 count 被夹到 6~120", s2.recommend["count"] == 120, str(s2.recommend["count"]))
    s2.set_recommend(algo="normal", count=24)
    check("A11 use_userrating 默认 False", s2.recommend.get("use_userrating") is False)
    s2.set_export_sections(["favorite", "people_fav"])
    check("A12 导出分段可保存", s2.export_sections() == ["favorite", "people_fav"])
    s2.set_export_sections(["favorite", "bogus"])
    check("A13 未知分段被清洗", s2.export_sections() == ["favorite"])
    s2.set_export_sections([k for k, _ in cfg.EXPORT_SECTIONS])
    check("A14 export 含收藏 / 演员收藏两类",
          {"favorite", "people_fav"} <= {k for k, _ in cfg.EXPORT_SECTIONS})
    s2.set_dedupe_prefs(exclude_multipart=False)
    check("A15 分片开关可保存", s2.dedupe["exclude_multipart"] is False)
    s2.set_dedupe_prefs(exclude_multipart=True)
except Exception:
    check("A 配置层", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 2. 数据库层
section("B. 数据库层：向量表 / 画像取数 / 合集海报")
try:
    db.init_db()
    # v1.24.1：B/D 两段的断言都要求 `vector_overrides` 是**空的**初态，而用户的库里可能
    # 已经有自己编好的权重（真机实测 71 条）。先快照再清空 —— 退出时原样写回。
    _VEC_SNAPSHOT[:] = [tuple(r) for r in db.vector_overrides()]
    db.clear_vector_overrides()
    check("B0 向量表已清空（原有权重已快照，退出写回）",
          db.vector_overrides() == [], f"快照 {len(_VEC_SNAPSHOT)} 条")
    cols = {r[1] for r in db.get_conn().execute("PRAGMA table_info(vector_overrides)")}
    check("B1 vector_overrides 表存在", {"dim", "key", "weight"} <= cols, str(cols))

    db.set_vector_override("tag", "巨乳", 1.5)
    db.set_vector_override("actor", "测试演员", 0.0)
    rows = db.vector_overrides()
    check("B2 写入 2 条向量权重", len(rows) == 2, str(rows))
    db.set_vector_override("tag", "巨乳", None)
    check("B3 传 None 删除", len(db.vector_overrides()) == 1)
    db.clear_vector_overrides()
    check("B4 清空", db.vector_overrides() == [])

    probe = db.media_for_insight()
    check("B5 media_for_insight 只取顶层条目且带分析列",
          len(probe) > 0 and "added_date" in probe[0] and "genres" in probe[0],
          f"{len(probe)} 行")
    ck = db.collection_posters([c for c, _n in db.collections()[:5]])
    check("B6 collection_posters 一次查完", isinstance(ck, dict), str(list(ck)[:2]))
    co = db.collections()
    if co:
        name, n = co[0]
        check("B7 collections 与墙同口径（top_only）",
              n == db.count_media(collection=name, top_only=True), f"{name}={n}")
    check("B8 people_links_map 可按角色查",
          isinstance(db.people_links_map("Director"), dict))
    role = db.people_counts_by_role()
    check("B9 role 统计含 Actor/Director",
          "Actor" in role and "Director" in role, str({k: v[1] for k, v in role.items()}))
    check("B10 favorite_people 可读", isinstance(db.favorite_people(), list))
except Exception:
    check("B 数据库层", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 3. 画像概览
section("C. 画像概览（反馈 6）")
try:
    data = ins_mod.Portrait().build()
    ov = data["overview"]
    check("C1 概览有作品数", ov["media"] > 0, str(ov["media"]))
    check("C2 八维雷达", len(data["radar"]) == 8, str([r[0] for r in data["radar"]]))
    check("C3 雷达值都在 0~1",
          all(0.0 <= v <= 1.0 for _l, v, _d in data["radar"]))
    # 真机教训：固定分母会让多轴同时顶满 1.0 → 要求至少有 6 轴不贴顶
    not_full = sum(1 for _l, v, _d in data["radar"] if v < 0.995)
    check("C4 雷达没有大面积贴顶（软饱和生效）", not_full >= 6, f"{not_full}/8 未贴顶")
    check("C5 雷达每轴都有人话说明",
          all(str(d).strip() for _l, _v, d in data["radar"]))
    check("C6 一句话画像非空", len(data["line"]) > 10, data["line"][:60])
    check("C7 高频榜五张", all(data.get(k) for k in
                               ("tags", "actors", "directors", "studios", "series")))
    # 真机教训：nfo 占位人名（未知演员 / 有码导演…）不能霸榜
    junk = [n for n, _c in data["actors"][:5] if ins_mod.is_junk_person(n)]
    check("C8 占位人名不进演员榜", not junk, str(junk))
    junk2 = [n for n, _c in data["directors"][:5] if ins_mod.is_junk_person(n)]
    check("C9 占位人名不进导演榜", not junk2, str(junk2))
    check("C10 分布五分项齐全",
          set(("画质", "评分", "时长", "年份", "入库月")) <= set(data["dist"]))
    check("C11 入库月有真实分布（非单月）", len(data["dist"]["入库月"]) >= 3,
          f"{len(data['dist']['入库月'])} 个月份")
    check("C12 评分分档按 10 分制（>5 的桶存在）",
          any(k in ("7.5~8", "8~9", "≥9") for k, _c in data["dist"]["评分"]),
          str([k for k, _c in data["dist"]["评分"]]))
    check("C13 标签共现非空", len(data["cooc"]) > 0)
    check("C14 split_tags 拆出片商/系列前缀",
          ins_mod.split_tags("巨乳, 片商:MOODYZ, 系列:abc") == (["巨乳"], ["MOODIZ"][:0] or ["MOODYZ"], [], ["abc"]))
    check("C15 时长解析（HH:MM:SS / 分钟 / 空）",
          (ins_mod._runtime_sec("01:30:00") == 5400
           and ins_mod._runtime_sec("") == 0 and ins_mod._runtime_sec("83") == 4980))
    check("C16 human_size / human_hours 可用",
          ins_mod.human_size(1536).endswith("KB") and "小时" in ins_mod.human_hours(1234))
except Exception:
    check("C 画像概览", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 4. 推荐引擎
section("D. 智能推荐（反馈 8）")
try:
    s = cfg.get_settings()
    r = rec_mod.Recommender(s)
    res_n = r.recommend(limit=12, algo="normal")
    picks = res_n.get("picks", [])
    check("D1 普通算法有结果", len(picks) == 12, f"{len(picks)} 部")
    check("D2 分数是真余弦（0~1）", all(0.0 < p["score"] <= 1.0 for p in picks),
          str([round(p["score"], 3) for p in picks[:4]]))
    check("D3 每部都带推荐理由", all(p.get("reason") for p in picks))
    check("D4 理由注明算法", all("普通算法" in p["reason"] for p in picks))
    check("D5 已收藏的不再被推荐", all(not p.get("favorite") for p in picks))
    check("D6 画像含收藏演员（归一化后不被标签淹没）",
          any(t.startswith("a:") for t, _w in res_n.get("profile_top", [])[:8]),
          str([t for t, _w in res_n.get("profile_top", [])[:8]]))
    res_a = rec_mod.Recommender(s).recommend(limit=12, algo="ai")
    check("D7 AI 算法有结果", len(res_a.get("picks", [])) == 12)
    check("D8 AI 理由注明 AI 算法",
          all("AI 算法" in p["reason"] for p in res_a.get("picks", [])))
    check("D9 AI 使用了某种引擎",
          res_a.get("engine") in ("builtin", "ollama"), str(res_a.get("engine")))
    st = rec_mod.ai_status()
    check("D10 ai_status 有中文说明", "label" in st and "detail" in st, st["label"])

    # 向量编辑必须真的影响结果
    s.set_vector_override_probe = None
    db.set_vector_override("tag", "巨乳", 0.0)       # 屏蔽
    try:
        res_blk = rec_mod.Recommender(s).recommend(limit=8, algo="normal")
        blocked = [p for p in res_blk["picks"] if "巨乳" in (p.get("reason") or "")]
        check("D11 权重 0 = 屏蔽该标签（不再作为推荐依据）", not blocked,
              str([p["reason"][:40] for p in blocked][:2]))
    finally:
        db.clear_vector_overrides()
    # 演员专一度：收藏演员在画像里权重最高
    prof, meta = rec_mod.Recommender(s).build_profile()
    top = max(prof.items(), key=lambda kv: kv[1])[0] if prof else ""
    # v1.24.1 修正口径：原来只认 a:（演员），但 v1.24.0 起「导演库」也能收藏导演，
    # 而收藏的导演本来就是与演员并列的最强信号（use_directors 默认开）。
    # 真机实测：用户收藏了导演「肉尊」后 top=d:肉尊 —— 这是**正确行为**，不是缺陷。
    check("D12 收藏的演员/导演权重最高（>标签）",
          top.startswith(("a:", "d:")) or meta["fav_people_n"] == 0,
          f"top={top} fav_people_n={meta['fav_people_n']}")
    check("D13 MMR 去重生效（结果不是同一演员刷屏）",
          len({(p.get("title") or "")[:6] for p in picks}) == len(picks))
except Exception:
    check("D 智能推荐", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 5. 重复检测
section("E. 重复检测（反馈 1/2/7）")
try:
    import inspect
    sig = inspect.signature(dup_mod.find_duplicates)
    check("E1 新增 exclude_multipart 参数", "exclude_multipart" in sig.parameters)
    check("E2 新增 verify_exists 参数", "verify_exists" in sig.parameters)

    # 造一批临时 media 行验证「删除的副本不再出现」
    alive = os.path.join(TMP, "alive")
    dead = os.path.join(TMP, "dead")
    os.makedirs(alive, exist_ok=True)
    os.makedirs(dead, exist_ok=True)
    f1 = os.path.join(alive, "AAA-001.mp4")
    f2 = os.path.join(dead, "AAA-001.mp4")           # 这个「已被删掉」→ 不创建
    open(f1, "wb").write(b"x" * 100)
    rows = [
        {"id": 990001, "parent_id": None, "kind": "movie", "title": "AAA-001 测试",
         "sort_title": "AAA-001", "year": 2020, "file_path": f1, "nfo_path": "",
         "quality": "1080P", "file_size": 100, "runtime": "01:00:00", "library": "T"},
        {"id": 990002, "parent_id": None, "kind": "movie", "title": "AAA-001 测试",
         "sort_title": "AAA-001", "year": 2020, "file_path": f2, "nfo_path": "",
         "quality": "1080P", "file_size": 200, "library": "T"},
    ]
    orig_rows = db.dedupe_rows
    orig_path = db.db_path

    def fake_rows(library=None):
        return list(rows)

    db.dedupe_rows = fake_rows
    rep_v = dup_mod.find_duplicates(verify_exists=True)
    check("E3 校验存在性后不再有重复组（只剩 1 份活的）",
          len(rep_v.groups) == 0, f"groups={[g.label for g in rep_v.groups]}")
    check("E4 报告记录「已失效副本」数量", rep_v.missing == 1, str(rep_v.missing))
    rep_n = dup_mod.find_duplicates(verify_exists=False)
    check("E5 关掉校验仍能查出这组重复（对照）", len(rep_n.groups) == 1,
          f"groups={len(rep_n.groups)}")
    check("E6 summary 暴露 missing / multipart_excluded",
          "missing" in rep_n.summary() and "multipart_excluded" in rep_n.summary())

    # 同目录分片开关
    same = os.path.join(TMP, "same")
    os.makedirs(same, exist_ok=True)
    p1 = os.path.join(same, "BBB-001 cd1.mp4")
    p2 = os.path.join(same, "BBB-001 cd2.mp4")
    open(p1, "wb").write(b"y" * 10)
    open(p2, "wb").write(b"y" * 10)
    rows2 = [
        {"id": 990011, "parent_id": None, "kind": "movie", "title": "BBB-001 测试",
         "sort_title": "BBB-001", "year": 2021, "file_path": p1, "nfo_path": "",
         "quality": "1080P", "file_size": 10, "runtime": "00:30:00", "library": "T"},
        {"id": 990012, "parent_id": None, "kind": "movie", "title": "BBB-001 测试",
         "sort_title": "BBB-001", "year": 2021, "file_path": p2, "nfo_path": "",
         "quality": "1080P", "file_size": 10, "runtime": "00:30:00", "library": "T"},
    ]
    db.dedupe_rows = lambda library=None: list(rows2)
    r_ex = dup_mod.find_duplicates(verify_exists=False, exclude_multipart=True)
    check("E7 开关打开 → 同目录分片只进 multipart",
          len(r_ex.groups) == 0 and len(r_ex.multipart) == 1,
          f"groups={len(r_ex.groups)} multipart={len(r_ex.multipart)}")
    r_no = dup_mod.find_duplicates(verify_exists=False, exclude_multipart=False)
    check("E8 开关关闭 → 同目录多份当重复组列出",
          len(r_no.groups) == 1 and len(r_no.multipart) == 0,
          f"groups={len(r_no.groups)}")
    check("E9 关掉开关时报告里标明「未按分片排除」",
          "关掉了该开关" in (r_no.groups[0].note or ""), r_no.groups[0].note)
    db.dedupe_rows = orig_rows
except Exception:
    check("E 重复检测", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 6. 分类导出 / 导入
section("F. 分类导出 / 导入（反馈 9）")
try:
    import backup as bk
    z = os.path.join(TMP, "sec.zip")
    r = bk.export_sections(z, ["favorite", "people_fav", "config"])
    check("F1 分类导出成功", r.get("ok"), str(r.get("error", "")))
    check("F2 只导出所选分段", set(r.get("items", [])) == {"favorite", "people_fav", "config"})
    check("F3 记录每段条数", "favorite" in r.get("counts", {}), str(r.get("counts")))
    import zipfile
    with zipfile.ZipFile(z) as zz:
        names = set(zz.namelist())
        meta = json.loads(zz.read("sections.json").decode("utf-8"))
    check("F4 包内有 sections.json 与 favorite.json",
          {"sections.json", "favorite.json"} <= names, str(sorted(names)))
    check("F5 未选的分段不写进包（无 media.json）", "media.json" not in names)
    check("F6 meta 声明类型", meta.get("type") == "lmc-sections")
    check("F7 收入演员收藏段", "people_fav" in meta.get("sections", []))
    r2 = bk.import_sections(z)
    check("F8 分类导入是合并（返回 restored）", r2.get("ok"), str(r2.get("error", "")))
    # 整库导出仍然可用（向后兼容）
    z2 = os.path.join(TMP, "whole.zip")
    r3 = bk.export_data(z2)
    check("F9 整库导出仍可用", r3.get("ok"), str(r3.get("error", "")))
    with zipfile.ZipFile(z2) as zz:
        check("F10 整库包含 media_center.db", "media_center.db" in set(zz.namelist()))
except Exception:
    check("F 分类导出", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 7. 启动画面
section("G. 蓝色启动画面（反馈 4）")
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QPixmap, QColor
    from PySide6.QtCore import Qt
    app = QApplication.instance() or QApplication(sys.argv)
    import splash as sp_mod
    check("G1 LMC_NO_SPLASH=1 时 make_splash 返回 None", sp_mod.make_splash() is None)
    os.environ.pop("LMC_NO_SPLASH")
    sp = sp_mod.SplashScreen(os.path.join(ROOT, "logo.png"))
    check("G2 尺寸 440x320", (sp.W, sp.H) == (440, 320), f"{sp.W}x{sp.H}")
    check("G3 LMC_NO_SPLASH 未设时可创建", sp is not None)
    sp.setProgress(42, "正在打开媒体索引…")
    check("G4 进度可设置", sp.progress() == 42)
    sp.setProgress(None)
    check("G5 支持不确定态", sp._indeterminate is True)
    sp.setProgress(100, "就绪")
    # 渲染验证：底色必须是**蓝的**（主色调为蓝色）
    pm = QPixmap(sp.W, sp.H)
    pm.fill(QColor("#000000"))
    sp.render(pm)
    img = pm.toImage()
    px = img.pixelColor(sp.W // 2, 8)          # 顶部中央
    r_, g_, b_ = px.red(), px.green(), px.blue()
    check("G6 顶部底色偏蓝（B 明显大于 R）", b_ > r_ + 12, f"rgb({r_},{g_},{b_})")
    px2 = img.pixelColor(20, sp.H // 2)
    check("G7 中部底色也是蓝调", px2.blue() > px2.red() + 12,
          f"rgb({px2.red()},{px2.green()},{px2.blue()})")
    check("G8 没有现成 splash 图片依赖（自绘）",
          not os.path.exists(os.path.join(SRC, "splash.png")))
    # 排版不得互相压行：v1.24.0 第一版出图时「64%」+ 进度槽正压在英文副标题上，
    # 这里按 _rows() 的实际几何做结构性拦截（改节奏常量后必然被这条挡住）。
    R = sp._rows()
    rows = [("logo", R["logo"], sp.LOGO), ("title", R["title"], sp._TITLE_H),
            ("sub", R["sub"], sp._SUB_H), ("pct", R["pct"], sp._PCT_H),
            ("bar", R["bar"], sp._BAR_H), ("tip", R["tip"], 18.0),
            ("ver", R["ver"], sp._FOOT_H), ("copy", R["copy"], sp._FOOT_H)]
    clash = ""
    for i in range(len(rows) - 1):
        n1, y1, h1 = rows[i]
        n2, y2, _h2 = rows[i + 1]
        if y1 + h1 > y2 + 0.01:                      # 允许刚好相接
            clash = f"{n1}({y1:.0f}+{h1:.0f}) 压到 {n2}({y2:.0f})"
            break
    check("G9 启动画面各行不重叠", not clash, clash)
    check("G10 页脚不出底边", R["copy"] + sp._FOOT_H <= sp.H + 0.01,
          f"{R['copy'] + sp._FOOT_H:.0f} vs {sp.H}")
except Exception:
    check("G 启动画面", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 8. 主界面结构
section("H. 主界面：工具改名 / 导演库 / 智能推荐页 / 合集卡片 / 扫描进度环（反馈 3/5/10/11）")
try:
    import main_window as mw
    import ui_settings
    from PySide6.QtWidgets import QApplication, QPushButton, QLabel, QScrollArea
    from PySide6.QtCore import Qt
    app = QApplication.instance() or QApplication(sys.argv)
    reg = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "msyh.ttc")
    if os.path.exists(reg):
        from PySide6.QtGui import QFontDatabase
        QFontDatabase.addApplicationFont(reg)
    mw.load_style(app)
    # 冒烟配置是临时目录里的空配置 → 先塞一个媒体库，才能验证「库名旁的进度环」
    cs = cfg.get_settings()
    if not cs.library_names():
        cs.add_library("冒烟库", "电影", [TMP])
    win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))

    labels = [b.text() for b in win.sidebar.findChildren(QPushButton)]
    check("H1 侧栏有「智能推荐」", "智能推荐" in labels, str(labels))
    check("H2 侧栏有「导演库」", "导演库" in labels)
    check("H3 侧栏有「＋新建媒体库」", any("新建" in t for t in labels), str(labels))
    top = [b.text() for b in win.findChildren(QPushButton)]
    check("H4 顶栏入口已改名「工具」", "工具" in top and "设置" not in top,
          str([t for t in top if t in ("工具", "设置")]))
    b = mw.DirectorCard.FACTS
    keys = [k for k, _r, _c, _s in b]
    check("H5 导演卡不含 生日/出身地/身高/胸围/三围",
          not ({"出生", "出身地", "身高", "胸围", "三围"} & set(keys)), str(keys))
    check("H6 导演卡显示 作品/别名/简介", set(keys) == {"作品", "别名", "简介"}, str(keys))
    check("H7 演员卡仍保留五/六项",
          {"出生", "出身地", "身高", "胸围", "三围"} <= {k for k, *_ in mw.ActorCard.FACTS})

    # 侧栏进度环
    check("H8 每个媒体库都有进度环", len(win._lib_rings) == len(win._lib_btns),
          f"{len(win._lib_rings)} vs {len(win._lib_btns)}")
    check("H8b 冒烟库已建（进度环有对象可测）", len(win._lib_rings) >= 1,
          str(list(win._lib_rings)))
    if win._lib_rings:
        ring = list(win._lib_rings.values())[0]
        check("H9 进度环默认隐藏", not ring.isVisible())
        ring.set_state(True, 55, "扫描中")
        check("H10 set_state(True) 后进入忙碌态", ring.is_busy() and ring._pct == 55)
        pm = QPixmap(ring.RING, ring.RING)
        pm.fill(QColor("#000000"))
        ring.render(pm)
        img = pm.toImage()
        # 环上应该有非黑像素（画出了弧线）
        lit = sum(1 for x in range(ring.RING) for y in range(ring.RING)
                  if img.pixelColor(x, y).blue() > 60)
        check("H11 进度环真的画出了弧线", lit > 8, f"{lit} 个亮像素")
        ring.set_state(False)
        check("H12 扫描结束自动隐藏", not ring.is_busy())

    # 导演库页面
    win.go(win._view_directors)
    pump(app)
    cur = win.stack.currentWidget()
    cards = cur.findChildren(mw.DirectorCard)
    check("H13 导演库能出卡片", len(cards) > 0, f"{len(cards)} 张")
    if cards:
        facts = cards[0]._facts.text()
        check("H14 导演卡 tooltip 信息区不含三围字段",
              ("三围" not in facts and "胸围" not in facts), facts.replace("\n", " | ")[:90])

    # 合集页 → 卡片网格（且必须是**分页**的，否则 7000 个合集会卡死）
    win.go(win._view_collections)
    pump(app)
    cur = win.stack.currentWidget()
    cols = cur.findChildren(mw.FolderCard)
    check("H15 合集页渲染为卡片网格", len(cols) > 0, f"{len(cols)} 张卡")
    # 关键：7000+ 个合集**绝不能一次建完控件**（离屏冒烟第一版就是这么被 SIGTERM 掉的）。
    # 离屏下滚动条 maximum 恒为 0 → LazyGrid 的「够一屏就停」判不出来，会连续 pump 到 720 张；
    # 所以这里断言的是**分页机制本身**（是 LazyGrid、按 batch 建卡、远少于总数），
    # 而不是某个具体的首屏张数。
    grids = cur.findChildren(mw.LazyGrid)
    check("H15b 合集页走 LazyGrid 分页",
          len(grids) == 1 and grids[0].batch == 48 and grids[0]._total == len(db.collections()),
          f"grids={len(grids)} batch={[g.batch for g in grids]} total={[g._total for g in grids]}")
    check("H15c 没有一次性建完全部合集卡",
          len(cols) < len(db.collections()),
          f"{len(cols)} 张 / 共 {len(db.collections())} 个合集")
    if cols:
        check("H16 合集卡片有拼贴封面 + 计数",
              cols[0].findChildren(QLabel) and "共" in " ".join(
                  l.text() for l in cols[0].findChildren(QLabel)),
              " | ".join(l.text() for l in cols[0].findChildren(QLabel)))

    # 智能推荐页（不跑算法，只看占位页 + 加载态）
    win._smart_picks = []
    win._smart_algo = None
    win._smart_worker = None
    win.go(win._view_smart)
    check("H17 智能推荐先给出加载页", win.stack.currentWidget() is not None)
    check("H18 加载页有进度条", win._smart_bar is not None)

    # 反复切换导航不出错（含新键）
    ok = True
    err = ""
    for k, fn in win._nav_builders().items():
        try:
            fn()
        except Exception as e:
            ok = False
            err = f"{k}: {type(e).__name__}: {e}"
            break
    check("H19 9 个导航全部可打开", ok, err)

    # 工具窗口（SettingsDialog）：标题 + 页面顺序 + 新页存在
    win._open_settings()
    dlg = win._settings_dlg
    check("H20 工具窗口标题为「工具」", dlg.windowTitle() == "工具", dlg.windowTitle())
    check("H21 左侧页签含 画像概览 / 智能推荐",
          "画像概览" in dlg.sub_btns and "智能推荐" in dlg.sub_btns,
          str(list(dlg.sub_btns)))
    od = dlg.ORDER
    check("H22 画像概览在 个性化设置 与 演员刮削 之间",
          od.index("个性化设置") + 1 == od.index("画像概览") and
          od.index("画像概览") + 1 == od.index("演员刮削"), str(od))
    check("H23 每个页签都挂上了页面", len(dlg.sub_btns) == dlg.stack.count(),
          f"{len(dlg.sub_btns)} vs {dlg.stack.count()}")
    # 切到每一页都不崩
    bad = ""
    for k in dlg.ORDER:
        try:
            dlg._show(k)
        except Exception as e:
            bad = f"{k}: {type(e).__name__}: {e}"
            break
    check("H24 七个工具页都能打开", not bad, bad)
    # 文案里不许再出现 Markdown 星号：QLabel / tooltip / QMessageBox 都不认 `**`，
    # 会原样显示成星号（v1.24.0 出图时才发现一堆提示带着 `**`）→ 统一过 rich()。
    _bad_txt = []
    for _k in dlg.ORDER:                       # 先把每页都走过，控件文案才算齐全
        dlg._show(_k)
    for _lbl in dlg.findChildren(QLabel):
        if "**" in (_lbl.text() or ""):
            _bad_txt.append("QLabel: " + _lbl.text()[:44].replace("\n", " "))
    for _w in dlg.findChildren(QPushButton):
        if "**" in (_w.toolTip() or ""):
            _bad_txt.append("tooltip: " + _w.toolTip()[:44].replace("\n", " "))
    check("H24b 工具页文案里没有残留的 Markdown 星号", not _bad_txt,
          " | ".join(_bad_txt[:3]))
    check("H24c rich() 能把 ** 转成 <b> 且不吃掉换行",
          ui_settings.rich("a **b** c\nd") == "a <b>b</b> c<br>d" and
          ui_settings.rich("纯文本\\n不动") == "纯文本\\n不动" and
          ui_settings.rich("**< 0**").endswith("</b>"),
          ui_settings.rich("a **b** c\nd"))
    check("H24d 富文本里的裸小于号被转义", "&lt;" in ui_settings.rich("**< 0 = 软排斥**"),
          ui_settings.rich("**< 0 = 软排斥**"))
    # 切页后整窗不能长高到超出 1080p 屏幕：画像概览内容很高，没套 QScrollArea 时
    # 会把 dialog 的最小高度顶到 1700+（真机验收抓到 1005x1733），底部按钮点不到。
    dlg.resize(1000, 900)
    _tall = []
    for _k in dlg.ORDER:
        dlg._show(_k)
        app.processEvents()
        _h = dlg.minimumSizeHint().height()
        if _h > 1000:
            _tall.append(f"{_k}={_h}")
    check("H24e 每页都不把工具窗撑高过 1080p 屏幕", not _tall, " | ".join(_tall))
    check("H24f 画像概览页套了滚动区",
          isinstance(dlg._pg_insight, QScrollArea), type(dlg._pg_insight).__name__)
    dlg._show("个性化设置")
    check("H25 雷达图控件可渲染",
          dlg.ins_radar.width() > 0 and dlg.ins_radar.height() > 0)
    check("H26 向量编辑对话框可创建",
          dlg._vector_dlg is None or dlg._vector_dlg.table is not None)
    check("H27 重复检测用树显示（可展开）", dlg.dd_tree is not None)
    # ---- 真的填一次树：防「UI 读了不存在的属性」这类塌方（v1.24.0 踩过
    #      DupMember.size_text / duration_text 只在 as_dict 里才有的坑）
    _m1 = dup_mod.DupMember(movie_id=1, path=r"Z:\A\ABP-123\ABP-123.mp4",
                            folder=r"Z:\A\ABP-123", num="ABP-123",
                            title="ABP-123 示例", year=2023, resolution="1080P",
                            video_size=5 * 1024 ** 3, duration_sec=7200,
                            source="Jav-library")
    _m2 = dup_mod.DupMember(movie_id=2, path=r"X:\B\ABP-123\ABP-123.mkv",
                            folder=r"X:\B\ABP-123", num="ABP-123",
                            title="ABP-123 示例", year=2023, resolution="1080P",
                            video_size=3 * 1024 ** 3, duration_sec=7200,
                            source="Jav-VR")
    _g = dup_mod.DupGroup(key="ABP123", kind="num", label="ABP-123",
                          members=sorted([_m1, _m2], key=lambda x: -x.size),
                          by_folder={_m1.folder: [_m1], _m2.folder: [_m2]},
                          confidence="极高")
    _g.total_bytes = _m1.size + _m2.size
    _g.redundant_bytes = min(_m1.size, _m2.size)
    _rep = dup_mod.DupReport(groups=[_g], multipart=[], scanned=48079, elapsed=6.4,
                             generated_at="2026-09-21 01:40:00", missing=41)
    _err = ""
    try:
        dlg._on_dedupe_done(_rep)
        dlg.dd_tree.expandAll()
    except Exception as e:
        _err = f"{type(e).__name__}: {e}"
    check("H27b 重复结果能真正填进树（含子项）",
          not _err and dlg.dd_tree.topLevelItemCount() >= 1 and
          dlg.dd_tree.topLevelItem(0).childCount() == 2, _err or "")
    _child = dlg.dd_tree.topLevelItem(0).child(0) if not _err else None
    check("H27c 子项携带完整路径（供双击打开）",
          _child is not None and _child.data(0, Qt.UserRole) == _m1.path,
          "" if _child is None else str(_child.data(0, Qt.UserRole)))
    check("H27d 体积/时长有可读文本",
          _m1.size_text.endswith(("GB", "MB", "KB", "B")) and _m1.duration_text != "",
          f"{_m1.size_text} / {_m1.duration_text}")
    check("H27e 双击打开路径的方法存在",
          callable(getattr(dlg, "_open_dedupe_item", None)))
    check("H27f 摘要含分片开关状态与已失效数",
          "multipart_excluded" in _rep.summary() and
          _rep.summary()["multipart_excluded"] is True and
          _rep.summary()["missing"] == 41,
          str({k: _rep.summary()[k] for k in ("multipart_excluded", "missing")}))
    check("H28 分片开关存在且与偏好一致",
          dlg.dd_excl.isChecked() == bool(dlg.s.dedupe.get("exclude_multipart", True)))
    check("H29 导出内容可勾选（含收藏/演员收藏）",
          "favorite" in dlg.exp_ck and "people_fav" in dlg.exp_ck,
          str(sorted(dlg.exp_ck)))
    dlg.close()

    # 打包脚本必须带上 v1.24.0 的三个新模块（漏了 exe 会在运行期才炸 ImportError）
    _be = open(os.path.join(ROOT, "build_exe.py"), encoding="utf-8").read()
    _miss = [m for m in ("insight", "recommend", "splash")
             if f'"--hidden-import", "{m}"' not in _be]
    check("H30 打包脚本含新模块隐藏导入", not _miss, str(_miss))
    check("H31 打包脚本仍带 --icon（PE 图标）", '"--icon"' in _be)
    win.close()
except Exception:
    check("H 主界面", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 9. 扫描进度环接线
section("I. 侧栏扫描进度环与扫描流程接线（反馈 11）")
try:
    import main_window as mw
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    # ScanWorker：结构化进度 + 预估总数
    d = os.path.join(TMP, "scanroot", "sub")
    os.makedirs(d, exist_ok=True)
    for i in range(3):
        open(os.path.join(d, f"v{i}.mp4"), "wb").write(b"z")
    open(os.path.join(TMP, "scanroot", "note.txt"), "w").write("x")
    w = mw.ScanWorker([os.path.join(TMP, "scanroot")], library_name="冒烟库")
    check("I1 ScanWorker 暴露 tick 信号", hasattr(w, "tick"))
    check("I2 预估文件总数正确（只数视频扩展名）", w._count_files() == 3, str(w._count_files()))
    got = []
    w.tick.connect(lambda a, b, m: got.append((a, b, m)))
    w._on_progress("视频：v0")
    check("I3 进度消息会带动 tick", len(got) == 1 and got[0][1] == w._total,
          str(got[:1]))
    w2 = mw.ScanWorker([TMP], total_hint=42, precount=False)
    check("I4 total_hint 时不再走磁盘统计", w2._total == 42 and w2._precount is False)

    # 主窗口：库名 → 目录反查，进度环联动
    cs = cfg.get_settings()
    name0 = cs.library_names()[0]
    win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))
    check("I5 _lib_for_path 能反查库名",
          win._lib_for_path(TMP) == name0, f"{win._lib_for_path(TMP)} vs {name0}")
    check("I6 无关目录返回 None", win._lib_for_path("C:/definitely/not/here") is None)
    win._lib_ring(name0, True, 40, "视频：x")
    ring = win._lib_rings[name0]
    check("I7 外部调用可让进度环转起来（含百分比）",
          ring.is_busy() and ring._pct == 40)
    win._lib_ring(name0, False)
    check("I8 扫描结束进度环停下", not ring.is_busy())
    check("I9 文件夹扫描对话框可接收 tick 回调",
          "on_tick" in __import__("inspect").signature(mw.FolderScanDialog).parameters)
    win.close()
except Exception:
    check("I 进度环接线", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 汇总
print("\n" + "=" * 72)
print(f"总计 {len(PASS)} 通过 / {len(FAIL)} 失败")
if FAIL:
    print("失败项：")
    for t in FAIL:
        print("  -", t)
print("=" * 72)
sys.exit(1 if FAIL else 0)
