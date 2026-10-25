# -*- coding: utf-8 -*-
"""v1.24.1 离屏冒烟回归（4 项反馈逐条自证 + v1.24.0 回归另跑一次）

跑法（shim 下必须走 runpy）：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/smoke_v1241.py', run_name='__main__')"

**安全约定**：本脚本把 `db.db_path` 指到**临时目录**的 media_center.db，全程不碰真实索引；
配置与日志同样重定向到临时目录。所以下面全部 fixture 都是自己造的，不依赖真机数据。
"""
import os
import re
import sys
import json
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = os.path.join(tempfile.gettempdir(), "lmc_smoke_v1241")
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)
# 每次从干净的索引开始：临时 DB 会跨次保留，残留行会让「6 部 / 4 部收藏」这类断言漂移
for _f in (os.path.join(TMP, "index_data", "media_center.db"),
           os.path.join(TMP, "index_data", "media_center.db-wal"),
           os.path.join(TMP, "index_data", "media_center.db-shm"),
           os.path.join(TMP, "index_data", "settings.json"),
           os.path.join(TMP, "settings.json"),          # cfg.config_path() 指向的就是这个
           os.path.join(TMP, "alt_settings.json")):
    try:
        os.remove(_f)
    except OSError:
        pass
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SPLASH"] = "1"

import applog
applog.log_dir = lambda: os.path.join(TMP, "index_data", "logs")
applog.log_path = lambda: os.path.join(TMP, "index_data", "logs", "app.log")

import config as cfg
import database as db

# 索引库也要隔离（真实索引只读都不读）
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")

_REAL_CONFIG_PATH = cfg.config_path      # 先留住真家伙，J 段要验它的 LMC_CONFIG 覆盖逻辑
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
# 注意：上面这行把模块属性换成了常量 lambda —— 后来在 J 段里直接调 cfg.config_path()
# 验环境变量，结果验的是这个 lambda，第一次写就栽在这上面。
cfg._SETTINGS = None

PASS, FAIL = [], []


def check(tag, cond, detail=""):
    (PASS if cond else FAIL).append(tag)
    print(f"[{'PASS' if cond else 'FAIL'}] {tag}  {detail}")


def section(t):
    print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)


def pump(app, n=12):
    """推进事件循环：LazyGrid 的 QTimer.singleShot(1) 与 QTimer.singleShot(0) 都靠它跑起来。"""
    import time as _t
    from PySide6.QtCore import QCoreApplication
    for _ in range(n):
        QCoreApplication.processEvents()
        app.processEvents()
        _t.sleep(0.012)          # singleShot(1) 需要真的过 1ms，光 processEvents 推不动


# ============================================================ 0. 版本号
section("A. 版本号（v1.24.1 / Build 2609210033）")
try:
    import version as ver
    check("A1 外部版本 v1.24.1", ver.VERSION == "v1.24.1", ver.VERSION)
    check("A2 内部构建号 2609210033", ver.BUILD == "2609210033", ver.BUILD)
    check("A3 版权声明保留",
          "肆月Aperture" in ver.COPYRIGHT and "禁止用于商业用途" in ver.LICENSE_NOTE)
except Exception:
    check("A 版本号", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 1. 造 fixture
section("B. 临时索引 fixture（6 部作品 / 4 部收藏 / 真人海报 + 真视频文件）")
IMG = os.path.join(TMP, "poster.png")
VIDEO = os.path.join(TMP, "movie.mp4")
NOTVIDEO = os.path.join(TMP, "note.txt")
MEDIA_IDS, FAV_IDS, NONFAV_IDS = [], [], []
DIRECTOR_ID = ACTOR_FAV_ID = ACTOR_NONFAV_ID = 0
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QImage, QColor
    app = QApplication.instance() or QApplication(sys.argv)

    im = QImage(120, 180, QImage.Format_RGB32)
    im.fill(QColor(200, 30, 60))                 # 纯色，便于与占位图区分
    check("B1 生成测试海报 PNG", im.save(IMG), IMG)
    open(VIDEO, "wb").write(b"x" * 8)
    open(NOTVIDEO, "w").write("x")

    db.init_db()
    DIRECTOR_ID = db.upsert_person("冒烟导演", "Director")
    ACTOR_FAV_ID = db.upsert_person("冒烟演员甲", "Actor")
    ACTOR_NONFAV_ID = db.upsert_person("冒烟演员乙", "Actor")

    for i in range(6):
        is_fav = i < 4
        fp = VIDEO if i < 3 else NOTVIDEO       # 前 3 部是可播放的视频文件
        mid = db.insert_media(
            title=f"冒烟作品 {i}", year=2020 + i, kind="movie", library="冒烟库",
            genres="标签A, 标签B, 片商:冒烟社, 系列:冒烟系列",
            studio="冒烟社", collection="冒烟系列", quality="1080P",
            runtime="01:40:00", file_size=3 * 1024 ** 3, rating=7.5,
            favorite=1 if is_fav else 0, file_path=fp, poster=IMG,
            fanart=IMG, thumb=IMG, added_date="2026-09-21")
        MEDIA_IDS.append(mid)
        (FAV_IDS if is_fav else NONFAV_IDS).append(mid)
    db.link_media_person(FAV_IDS[0], ACTOR_FAV_ID, "Actor", 0)
    db.link_media_person(FAV_IDS[0], DIRECTOR_ID, "Director", 0)
    db.link_media_person(NONFAV_IDS[0], ACTOR_NONFAV_ID, "Actor", 0)
    check("B2 6 部作品入库", len(db.media_for_insight()) == 6,
          str(len(db.media_for_insight())))
    check("B3 4 部收藏", len(db.media_for_insight(favorites_only=True)) == 4,
          str(len(db.media_for_insight(favorites_only=True))))
except Exception:
    check("B fixture", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 2. 反馈 1 根因自证
section("C. 反馈 1：智能推荐墙海报不显示 —— 根因是取数投影缺列")
try:
    raw = db.media_for_insight()
    r0 = raw[0]
    check("C1 分析投影**确实没有** poster（这就是根因）", "poster" not in r0,
          str(sorted(r0)[:8]))
    check("C2 分析投影**也没有** file_path（播放按钮因此建不出来）",
          "file_path" not in r0)
    check("C3 分析投影仍然带 genres / favorite（分析用得到）",
          "genres" in r0 and "favorite" in r0)
    # 完整行回查
    full = db.media_by_ids([MEDIA_IDS[2], MEDIA_IDS[0], MEDIA_IDS[1]])
    check("C4 media_by_ids 只取存在的 id 且**保序**",
          [int(x["id"]) for x in full] == [MEDIA_IDS[2], MEDIA_IDS[0], MEDIA_IDS[1]],
          str([x["id"] for x in full]))
    check("C5 media_by_ids 返回完整行（有 poster / file_path）",
          all(x.get("poster") and x.get("file_path") for x in full))
    check("C6 不存在的 id 被跳过而不是报错",
          [int(x["id"]) for x in db.media_by_ids([999999, MEDIA_IDS[0]])] == [MEDIA_IDS[0]])
    check("C7 空输入返回空",
          db.media_by_ids([]) == [] and db.media_by_ids(None) == [])
    check("C8 重复 id 只回一条",
          len(db.media_by_ids([MEDIA_IDS[0], MEDIA_IDS[0]])) == 1)
except Exception:
    check("C 反馈 1 根因", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 3. 反馈 1 回填
section("D. 反馈 1：_hydrate_picks 用完整行回填推荐结果")
try:
    import main_window as mw

    picks_in = db.media_for_insight()
    picks_in[0]["score"] = 0.8123
    picks_in[0]["reason"] = "普通算法：标签「标签A」高度吻合"
    picks_in[1]["score"] = 0.7654
    picks_in[1]["reason"] = "普通算法：标签「标签B」高度吻合"
    out = mw.MainWindow._hydrate_picks(picks_in)

    check("D1 条目不丢", len(out) == len(picks_in), f"{len(out)}/{len(picks_in)}")
    check("D2 每一条都补上了 poster", all(x.get("poster") for x in out))
    check("D3 每一条都补上了 file_path", all(x.get("file_path") for x in out))
    check("D4 顺序与分数一致（id 序列不变）",
          [x["id"] for x in out] == [x["id"] for x in picks_in])
    check("D5 score 没被完整行覆盖", out[0]["score"] == 0.8123, str(out[0]["score"]))
    check("D6 reason 没被完整行覆盖",
          out[1]["reason"].startswith("普通算法"), out[1]["reason"][:24])
    check("D7 分析字段仍在（genres / rating）",
          out[0].get("genres") and out[0].get("rating") is not None)
    check("D8 空 / None 输入安全",
          mw.MainWindow._hydrate_picks([]) == [] and
          mw.MainWindow._hydrate_picks(None) == [])
    check("D9 拿不到完整行时原样保留条目（不丢）",
          [x["id"] for x in mw.MainWindow._hydrate_picks([{"id": 999999, "t": 1}])]
          == [999999])
    check("D10 没有 id 的行也原样保留",
          mw.MainWindow._hydrate_picks([{"score": 1}])[0]["score"] == 1)
except Exception:
    check("D 反馈 1 回填", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 4. 反馈 1 渲染
section("E. 反馈 1：推荐墙渲染成与「全部」同款卡片（含左下 ☆ / 右下 ▶）")
try:
    from PySide6.QtWidgets import QLabel
    cs = cfg.get_settings()
    if not cs.library_names():
        cs.add_library("冒烟库", "电影", [TMP])
    win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))

    win._smart_picks = out
    win._smart_algo = "normal"
    win._smart_res = {"algo": "normal", "engine": "builtin",
                      "meta": {"favorites": 4, "liked": 0, "fav_people_n": 0},
                      "pool": 2, "picks": out}

    page = win._view_smart()               # 有缓存且算法未变 → 直接复用，不再跑算法
    pump(app, 30)
    cards = page.findChildren(mw.PosterCard)
    check("E1 推荐墙渲染出了卡片", len(cards) == len(out), f"{len(cards)}/{len(out)}")

    grids = page.findChildren(mw.LazyGrid)
    check("E2 推荐墙走 LazyGrid（与「全部」同一套增量网格）",
          len(grids) == 1, f"{len(grids)} 个网格")
    g = grids[0] if grids else None
    check("E3 网格总数 = 推荐条数", g is not None and g._total == len(out),
          f"{getattr(g, '_total', None)}")
    check("E4 工具行已接管按钮（解锁 more_btn 显隐门闩）",
          g is not None and g._toolbar_ready and g.more_btn.parent() is not None)
    check("E5 外层滚动条已挂上（滚到底自动续载）",
          g is not None and g._scrollbar is not None)
    check("E6 页面容器登记了 lazy_grid（_page 才能挂滚动条）",
          g is not None and getattr(g.parent(), "lazy_grid", None) is g)

    # 左下角 ☆ 收藏 / 右下角 ▶ 播放 —— 反馈 1 明确要求「也保留」
    no_fav = [c for c in cards if c.fav_btn is None]
    check("E7 每张卡都有左下角收藏星标", not no_fav, f"{len(no_fav)} 张缺星标")
    playable = [c for c in cards if mw.playable_media(c.media)]
    with_play = [c for c in playable if c.play_btn is not None]
    check("E8 可播放的作品都有右下角播放按钮",
          len(with_play) == len(playable) and len(playable) == 3,
          f"{len(with_play)}/{len(playable)}")
    nonplay = [c for c in cards if not mw.playable_media(c.media)]
    check("E9 非视频文件不建播放按钮（不给假按钮）",
          all(c.play_btn is None for c in nonplay), f"{len(nonplay)} 张")

    # 海报真的画出来了 —— 与占位图逐像素比对（这是「照片没有显示」的直接判据）
    def _poster_label(card):
        for l in card.findChildren(QLabel):
            pm = l.pixmap()
            if pm is not None and not pm.isNull() and l.width() == mw.POSTER_W:
                return l
        return None

    ph = mw.placeholder_pixmap(mw.POSTER_W, mw.POSTER_H, text="占")
    ph_img = ph.toImage()
    bad = []
    for c in cards:
        l = _poster_label(c)
        if l is None:
            bad.append("无海报控件")
            continue
        if l.pixmap().toImage() == ph_img:
            bad.append(f"占位图:{(c.media.get('title') or '')[:8]}")
    check("E10 没有一张卡是占位图（海报真的加载了）", not bad, " | ".join(bad[:3]))

    # 点星标 → 真的切换收藏（不该跳页，因为回调只是切库 + 刷新，不换视图）
    first = cards[0]
    before = bool(first.media.get("favorite"))
    first.fav_btn.click()
    check("E11 卡片星标点击会切换收藏态",
          bool(first.media.get("favorite")) != before,
          f"{before} -> {first.media.get('favorite')}")
    check("E12 星标视觉与数据同步",
          first.fav_btn._on == bool(first.media.get("favorite")))
    first.fav_btn.click()                     # 再点一次还原，别影响后面按收藏数统计的断言
    check("E13 再点一次回到原状态（收藏数不受测试影响）",
          bool(first.media.get("favorite")) == before and
          len(db.media_for_insight(favorites_only=True)) == 4,
          f"收藏 {len(db.media_for_insight(favorites_only=True))} 部")

    # v1.24.1：换页后 LazyGrid 排队的定时器可能打到已释放的对象上 → _qt_alive 必须能识别
    import shiboken6
    from PySide6.QtWidgets import QWidget, QGridLayout
    _tmp = QWidget()
    _tmp_lay = QGridLayout(_tmp)
    check("E14 _qt_alive 对活着的对象返回 True", mw._qt_alive(_tmp, _tmp_lay) is True)
    check("E14b 传 None 不算死亡", mw._qt_alive(None, _tmp) is True)
    shiboken6.delete(_tmp)
    check("E15 对象被 C++ 释放后 _qt_alive 返回 False（_pump 会安静退出）",
          mw._qt_alive(_tmp) is False and mw._qt_alive(_tmp_lay) is False)

    # 真机 app.log 里抓到过 `main_window.py, in mouseDoubleClickEvent` →
    # `RuntimeError: libshiboken: Internal C++ object (PosterCard) already deleted`：
    # 换页后队列里残留的鼠标事件仍会派发给已析构的卡片 → 两个事件入口都要能安静退出。
    _victim = cards[-1]
    _fired = []
    _victim._on_open = lambda *a: _fired.append(a)
    _victim._on_select = lambda *a: _fired.append(a)
    shiboken6.delete(_victim)
    _ok, _err = True, ""
    try:
        _victim.mouseDoubleClickEvent(None)
        _victim.mousePressEvent(None)
    except Exception as _e:                       # noqa: BLE001 - 断言用
        _ok, _err = False, f"{type(_e).__name__}: {_e}"
    check("E16 已析构的海报卡收到鼠标事件不再抛 RuntimeError（守卫生效）", _ok, _err)
    check("E17 已析构的海报卡的打开/选中回调不会被误触发", not _fired, str(_fired[:2]))

    # 合集卡（FolderCard）同一类风险：鼠标 + 右键菜单
    _fc = mw.FolderCard("冒烟目录", "X:/smoke", 3, [], lambda *a: None)
    _fc.fired = []
    _fc._on_open = lambda *a: _fc.fired.append(a)
    _fc._on_menu = lambda *a: _fc.fired.append(a)
    shiboken6.delete(_fc)
    _ok2, _err2 = True, ""
    try:
        _fc.mousePressEvent(None)
        _fc.contextMenuEvent(None)
    except Exception as _e:                       # noqa: BLE001 - 断言用
        _ok2, _err2 = False, f"{type(_e).__name__}: {_e}"
    check("E18 已析构的合集卡鼠标/右键事件也安静退出", _ok2, _err2)
    check("E19 已析构的合集卡回调不被误触发", not _fc.fired, str(_fc.fired[:2]))
    win.close()
except Exception:
    check("E 反馈 1 渲染", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 5. 反馈 3
section("F. 反馈 3：导演库点收藏 / 置顶不再跳到演员库")
try:
    win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))
    calls = []
    win._replace_current = lambda b: calls.append(b)

    # 进过导演库后，_people_builder 必须被登记成导演库
    # （页面要留下引用：没有父控件的页面被 GC 掉后，LazyGrid 里排队的 QTimer 会打到已释放对象上）
    _pg_d = win._view_directors()
    check("F1 进导演库后登记当前人物页 = 导演库",
          win._people_builder == win._view_directors)
    _pg_a = win._view_actors()
    check("F2 进演员库后登记 = 演员库", win._people_builder == win._view_actors)
    check("F2b 两个人物页都能建出网格",
          _pg_d.findChildren(mw.LazyGrid) and _pg_a.findChildren(mw.LazyGrid))

    win._people_builder = win._view_directors
    calls.clear()
    win._toggle_person_fav({"id": DIRECTOR_ID})
    pump(app, 6)
    check("F3 导演库点收藏 → 原地重建导演库（不再跳演员库）",
          calls and calls[-1] == win._view_directors,
          str([c.__name__ for c in calls]))
    check("F4 收藏真的落库", db.get_person(DIRECTOR_ID)["favorite"] == 1)

    calls.clear()
    win._toggle_person_pin({"id": DIRECTOR_ID})
    pump(app, 6)
    check("F5 导演库点置顶 → 仍是导演库",
          calls and calls[-1] == win._view_directors,
          str([c.__name__ for c in calls]))
    check("F6 置顶真的落库", db.get_person(DIRECTOR_ID)["pinned"] == 1)

    calls.clear()
    win._people_builder = win._view_actors
    win._toggle_person_fav({"id": ACTOR_FAV_ID})
    pump(app, 6)
    check("F7 演员库点收藏 → 重建演员库（反向也对）",
          calls and calls[-1] == win._view_actors,
          str([c.__name__ for c in calls]))

    # 从未进过任何人物页时不炸（退回演员库）
    win._people_builder = None
    calls.clear()
    win._refresh_people()
    check("F8 未初始化时安全退回演员库",
          calls and calls[-1] == win._view_actors)

    # 兼容旧名字
    check("F9 _refresh_actors 仍可用（兼容旧调用点）",
          callable(getattr(win, "_refresh_actors", None)))
    win.close()
except Exception:
    check("F 反馈 3", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 6. 反馈 4
section("G. 反馈 4：画像概览统计范围加入「我的收藏」")
try:
    import insight as ins_mod

    all_d = ins_mod.Portrait().build()
    check("G1 默认范围 = 全部媒体库", all_d["overview"]["scope"] == "全部媒体库",
          all_d["overview"]["scope"])
    check("G2 全部范围统计 6 部", all_d["overview"]["media"] == 6,
          str(all_d["overview"]["media"]))

    fav_d = ins_mod.Portrait(favorites_only=True).build()
    fov = fav_d["overview"]
    check("G3 收藏范围 scope = 我的收藏", fov["scope"] == "我的收藏", fov["scope"])
    check("G4 收藏范围只统计 4 部", fov["media"] == 4, str(fov["media"]))
    check("G5 收藏范围里 favorite == media（全是收藏）",
          fov["favorite"] == fov["media"] == 4)
    check("G6 一句话画像不再写「索引里共…」", "收藏了 4 部作品" in fav_d["line"],
          fav_d["line"][:60])

    lib_d = ins_mod.Portrait("冒烟库", favorites_only=True).build()
    check("G7 库 + 收藏 组合范围标题", lib_d["overview"]["scope"] == "冒烟库 · 我的收藏",
          lib_d["overview"]["scope"])
    lib_all = ins_mod.Portrait("冒烟库").build()
    check("G8 只给库时标题就是库名", lib_all["overview"]["scope"] == "冒烟库",
          lib_all["overview"]["scope"])

    # 关联条数必须跟着范围走（原来取全库 media_people 行数 → 收藏范围会显示成天文数字）
    check("G9 全范围的演员关联 = 2 条", all_d["overview"]["actor_links"] == 2,
          str(all_d["overview"]["actor_links"]))
    check("G10 收藏范围的演员关联 = 1 条（按范围收窄）",
          fov["actor_links"] == 1, str(fov["actor_links"]))
    check("G11 导演关联也按范围收窄",
          all_d["overview"]["director_links"] == 1 and fov["director_links"] == 1,
          f'{all_d["overview"]["director_links"]} / {fov["director_links"]}')
    check("G12 收藏范围的雷达仍是 8 轴且值合法",
          len(fav_d["radar"]) == 8 and
          all(0.0 <= v <= 1.0 for _l, v, _d in fav_d["radar"]))
    check("G13 收藏范围的高频榜非空（标签能算出来）",
          bool(fav_d["tags"]) and bool(fav_d["studios"]))
    check("G14 收藏范围拿不到数据时也不炸（0 部）",
          ins_mod.Portrait("不存在的库",
                           favorites_only=True).build()["overview"]["media"] == 0)
except Exception:
    check("G 反馈 4", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 7. 反馈 2
section("H. 反馈 2：检测本地 AI 引擎点下去必须有反馈")
try:
    import ui_settings
    import recommend as rec_mod

    check("H1 探测地址对外公开（提示文案要用）",
          rec_mod.OLLAMA_HOST == "127.0.0.1:11434" and
          rec_mod.OLLAMA_URL.startswith("http://127.0.0.1:11434"))
    st = rec_mod.ai_status()
    check("H2 ai_status 返回中文标签与说明",
          st.get("label") and st.get("detail"), st.get("label"))
    check("H3 未检出时给了「怎么装」的可执行指引",
          st["engine"] != "builtin" or ("ollama pull" in st["detail"]), st["detail"][:40])
    check("H4 未检出时不再用 Markdown 反引号（QLabel 不认）",
          "`" not in st["detail"])

    win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))
    win._open_settings()
    dlg = win._settings_dlg
    dlg._show("智能推荐")
    check("H5 智能推荐页有 ai_state 标签与检测按钮",
          dlg.ai_state is not None and dlg.ai_test is not None)
    check("H6 检测按钮有 tooltip 写明探测目标",
          rec_mod.OLLAMA_HOST in dlg.ai_test.toolTip(), dlg.ai_test.toolTip())

    # 忙碌态：把线程 start 换成 no-op，避免真起线程
    _real_start = ui_settings.AiProbeWorker.start
    ui_settings.AiProbeWorker.start = lambda self: None
    try:
        # 防抖：正在探测时再点一次应当直接忽略（不能重复起线程）
        class _RunningProbe:
            def isRunning(self):
                return True

        dlg._ai_worker = _RunningProbe()
        dlg.ai_state.setText("哨兵")
        dlg._refresh_ai_state()
        check("H9 探测进行中重复点击被忽略（防抖）",
              dlg.ai_state.text() == "哨兵", dlg.ai_state.text())

        dlg._ai_worker = None
        dlg._refresh_ai_state()
        check("H7 点按钮立刻显示「正在检测」（有即时反馈）",
              "正在检测" in dlg.ai_state.text(), dlg.ai_state.text()[:40])
        check("H8 检测期间按钮置灰并改文案",
              dlg.ai_test.isEnabled() is False and dlg.ai_test.text() == "检测中…",
              dlg.ai_test.text())
        check("H8b 忙碌态写明探测目标与超时",
              rec_mod.OLLAMA_HOST in dlg.ai_state.text(), dlg.ai_state.text()[:60])
    finally:
        ui_settings.AiProbeWorker.start = _real_start

    # 结果态：三种结论都要看得见，并且带时间戳（结论相同也能看出「刚检测过」）
    dlg._on_ai_probe({"engine": "builtin", "label": "内置离线联想引擎",
                      "detail": "未检测到本地 Ollama，使用内置的标签共现联想。"})
    t1 = dlg.ai_state.text()
    check("H10 未检出时给出明确结论", "检测完成" in t1 and "未检测到" in t1, t1[:60])
    check("H11 结果带时间戳", bool(re.search(r"\d{2}:\d{2}:\d{2}", t1)), t1[:40])
    check("H12 按钮恢复可用", dlg.ai_test.isEnabled() and
          dlg.ai_test.text() == "检测本地 AI 引擎")

    dlg._on_ai_probe({"engine": "ollama", "label": "本地 Ollama（qwen2.5:7b）",
                      "detail": "离线扩词已启用。"})
    check("H13 检出时给出 ✅ 结论", "✅" in dlg.ai_state.text(),
          dlg.ai_state.text()[:50])
    dlg._on_ai_probe({"engine": "error", "label": "未知", "detail": "boom"})
    check("H14 异常时给出 ❌ 结论", "❌" in dlg.ai_state.text(),
          dlg.ai_state.text()[:50])
    dlg._on_ai_probe(None)
    check("H15 收到 None 也不炸", dlg.ai_state.text() != "")

    # 回归：rich 拆出 html_esc 后行为不变
    check("H16 rich() 行为未变",
          ui_settings.rich("a **b** c\nd") == "a <b>b</b> c<br>d" and
          ui_settings.rich("纯文本\n不动") == "纯文本\n不动")
    check("H17 html_esc 转义 & < >",
          ui_settings.html_esc("a&b<c>d") == "a&amp;b&lt;c&gt;d")
    check("H18 结果里的 detail 被转义（不进 HTML 标签）",
          "&lt;" in ui_settings.html_esc("<script>"))
    win.close()
except Exception:
    check("H 反馈 2", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 8. 统计范围下拉接线
section("I. 反馈 4 UI 接线：统计范围下拉 / 换范围自动重算")
try:
    win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))
    win._open_settings()
    dlg = win._settings_dlg
    dlg._show("画像概览")
    texts = [dlg.ins_lib.itemText(i) for i in range(dlg.ins_lib.count())]
    check("I1 统计范围含（全部媒体库）", any("全部媒体库" in t for t in texts), str(texts))
    check("I2 统计范围含「我的收藏」",
          any("我的收藏" in t for t in texts), str(texts))
    check("I3 「我的收藏」排在全部媒体库之后", "我的收藏" in texts[1], texts[1])
    check("I4 媒体库各自还在选项里",
          all(n in texts for n in cfg.get_settings().library_names()), str(texts))

    check("I5 默认范围 = (None, False)", dlg._insight_scope() == (None, False),
          str(dlg._insight_scope()))
    dlg.ins_lib.blockSignals(True)
    dlg.ins_lib.setCurrentIndex(1)
    dlg.ins_lib.blockSignals(False)
    check("I6 选中「我的收藏」→ (None, True)", dlg._insight_scope() == (None, True),
          str(dlg._insight_scope()))
    dlg.ins_lib.blockSignals(True)          # 还原成初始项，I7c 要验的就是初始态
    dlg.ins_lib.setCurrentIndex(0)
    dlg.ins_lib.blockSignals(False)
    check("I7 Worker 接受 favorites_only 参数",
          "favorites_only" in
          __import__("inspect").signature(ui_settings.PortraitWorker).parameters)

    # v1.24.1：统计范围会被记住（换过之后下次打开还是它）
    check("I7b 默认偏好 = (全部媒体库, 不看收藏)",
          cfg.DEFAULT_INSIGHT == {"scope": "", "favorites_only": False},
          str(cfg.DEFAULT_INSIGHT))
    check("I7c 默认时下拉停在「全部媒体库」", dlg.ins_lib.currentIndex() == 0,
          str(dlg.ins_lib.currentIndex()))

    # 换范围必须作废旧结果并重算（否则页面还挂着上一个范围的画像）
    calls = []
    _real_run = dlg._run_insight
    dlg._run_insight = lambda: calls.append(1)
    try:
        dlg._insight_data = {"stale": True}
        dlg._on_insight_scope()
        check("I8 换范围会作废旧结果", dlg._insight_data == {})
        check("I9 换范围会自动重算", len(calls) == 1)
        check("I10 换范围有文字提示", "重新分析" in dlg.ins_status.text(),
              dlg.ins_status.text())
    finally:
        dlg._run_insight = _real_run

    # 分析中换范围 → 跑完补算一次，而不是丢掉新范围
    dlg._insight_pending = True
    dlg._on_insight_done({"error": "stale"})         # 旧结果应当被丢弃，不写进界面
    check("I11 分析中换范围 → 旧结果作废且补算一次",
          dlg._insight_pending is False and "失败" not in dlg.ins_status.text(),
          dlg.ins_status.text())
    dlg._insight_pending = False

    # 真的把「我的收藏」选上 → 写进偏好 → 重建工具窗口后仍是它（在 connect 之前就设好索引）
    dlg.ins_lib.blockSignals(True)
    dlg.ins_lib.setCurrentIndex(1)
    dlg.ins_lib.blockSignals(False)
    dlg._saved_run = dlg._run_insight
    dlg._run_insight = lambda: None
    try:
        dlg._on_insight_scope()
    finally:
        dlg._run_insight = dlg._saved_run
    cfg._SETTINGS = None                    # 从磁盘重读，验证真的落盘了
    s2 = cfg.get_settings()
    check("I12 统计范围落盘为「我的收藏」",
          s2.insight == {"scope": "", "favorites_only": True}, str(s2.insight))
    win._settings_dlg = None
    win._open_settings()
    dlg2 = win._settings_dlg
    check("I13 重开工具后下拉仍停在「我的收藏」",
          dlg2._insight_scope() == (None, True) and dlg2.ins_lib.currentIndex() == 1,
          f"{dlg2._insight_scope()} #{dlg2.ins_lib.currentIndex()}")
    set_insight = getattr(s2, "set_insight_scope", None)
    check("I14 有 set_insight_scope 写入接口", callable(set_insight))
    s2.set_insight_scope("冒烟库", True)
    check("I15 可写「库 + 收藏」组合",
          s2.insight == {"scope": "冒烟库", "favorites_only": True}, str(s2.insight))
    dlg2.close()
    win.close()
except Exception:
    check("I 反馈 4 UI 接线", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 9. 真机验收用的配置覆盖
section("J. LMC_CONFIG：让打包后的 exe 读临时配置（真机验收不碰用户 settings.json）")
try:
    alt = os.path.join(TMP, "alt_settings.json")
    before = _REAL_CONFIG_PATH()
    os.environ["LMC_CONFIG"] = alt
    check("J1 环境变量能覆盖配置路径",
          _REAL_CONFIG_PATH() == alt, _REAL_CONFIG_PATH())
    os.environ.pop("LMC_CONFIG", None)
    check("J2 不设环境变量时回到 exe 同级 / 项目根",
          _REAL_CONFIG_PATH() == before, _REAL_CONFIG_PATH())
    with open(alt, "w", encoding="utf-8") as f:
        json.dump({"insight": {"scope": "", "favorites_only": True}}, f)
    os.environ["LMC_CONFIG"] = alt
    _saved_patch = cfg.config_path
    cfg.config_path = _REAL_CONFIG_PATH                  # 临时恢复到真实实现来验读取
    cfg._SETTINGS = None
    check("J3 临时配置里的统计范围被读到",
          cfg.get_settings().insight == {"scope": "", "favorites_only": True},
          str(cfg.get_settings().insight))
    os.environ.pop("LMC_CONFIG", None)
    cfg.config_path = _saved_patch
    cfg._SETTINGS = None
except Exception:
    check("J LMC_CONFIG", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 汇总
print("\n" + "=" * 72)
print(f"总计 {len(PASS)} 通过 / {len(FAIL)} 失败")
if FAIL:
    print("失败项：")
    for t in FAIL:
        print("  -", t)
print("=" * 72)
sys.exit(1 if FAIL else 0)
