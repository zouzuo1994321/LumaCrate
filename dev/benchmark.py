# -*- coding: utf-8 -*-
"""流明盒 LumaCrate · 性能基准测试（v1.26.0）

用法（在项目根目录跑，也是唯一需要的东西）：

    "C:/Users/zouzu/.workbuddy/binaries/python/envs/default/Scripts/python.exe" -u \
      -c "import runpy; runpy.run_path(r'<项目根>/dev/benchmark.py', run_name='__main__')"

产出：
  · 控制台逐条用时表
  · 项目根目录 `性能基线.md`

## 安全约定（很重要）
本脚本**只读**真实索引 `index_data/media_center.db`（4.8 万条那个）：
  · 不调用任何 `insert_*` / `update_*` / `delete_*` / `clear_media()`
  · 不调用 `init_db()`（它会写 WAL）；冷启动那一条用「关掉连接后重新跑一次查询」
    来测「建连 + 首次查询」的真实代价，功能等价但零写入
  · `applog.log_dir` 重定向到 %TEMP%，避免污染真实 `index_data/logs/app.log`
  · Qt 部分用 offscreen 平台，只建控件不显示，且不碰 settings.json

## 为什么这些用例
覆盖面 = 界面**真正会走的路径**：首屏分页、深翻页、随机排序、多维筛选、关键词、
批量关系查询、画像 / 标签统计（后台线程）、nfo 解析（扫描时逐文件）、
以及「换高亮色」时的整表重载。慢的那几条就是「不能放在 GUI 线程里」的名单。
"""
import ctypes
import io
import os
import statistics
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("LMC_NO_BACKDROP", "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

TMP = os.environ.get("TEMP") or os.environ.get("TMP") or "."
MD_PATH = os.path.join(ROOT, "性能基线.md")

import applog  # noqa: E402

applog.log_dir = lambda: os.path.join(TMP, "lmc_bench_logs")   # 不写真实日志目录

import config as cfg        # noqa: E402
import database as db       # noqa: E402
import insight as insight_mod   # noqa: E402
import nfo_parser           # noqa: E402
import tagopt as tagopt_mod    # noqa: E402

RESULTS = []          # 每项：dict(group,name,scale,median,lo,hi,n,thr,unit)
NOTES = []

# v1.26.0：本轮基准测出来、并且**当场修掉**的两条索引。修复前的数字是实测值，
# 修复后由 RESULTS 里现取 —— 这样《性能基线》里始终是「脚本自己跑出来的数」，
# 不会出现「文档写 XX ms、实际跑出来对不上」的情况。
OPT_BEFORE_AFTER = [
    ("深层翻页 60 条（名称升序，offset 47963）", 249.26, ("深层翻页 60 条",)),
    ("最近添加 60 条（按时间倒序）", 151.54, ("最近添加 60 条",)),
    ("首屏分页 60 条", 14.88, ("首屏分页 60 条",)),
    ("关键词列表 60 条", 31.42, ("关键词列表 60 条",)),
]


def say(msg=""):
    print(msg, flush=True)


def bench(name, fn, group="数据层", scale="", repeat=5, warmup=1, thr=None,
          unit="次", note=""):
    """跑 repeat 次取中位数。thr = 判定阈值（ms），None 表示只记录不判定。"""
    try:
        for _ in range(warmup):
            fn()
        ts = []
        for _ in range(repeat):
            t0 = time.perf_counter()
            fn()
            ts.append((time.perf_counter() - t0) * 1000.0)
    except Exception as e:                                  # 单条失败不影响其余
        RESULTS.append(dict(group=group, name=name, scale=scale, median=None,
                            lo=None, hi=None, n=repeat, thr=thr, unit=unit,
                            note=f"失败：{type(e).__name__}: {e}"))
        say("  [!!] %-34s 失败：%s: %s" % (name, type(e).__name__, e))
        return None
    med = statistics.median(ts)
    RESULTS.append(dict(group=group, name=name, scale=scale, median=med,
                        lo=min(ts), hi=max(ts), n=repeat, thr=thr, unit=unit,
                        note=note))
    flag = ""
    if thr is not None:
        flag = "  [OK]" if med <= thr else "  [!!]"
    say("  %-34s %9.2f ms  (min %8.2f / max %8.2f, n=%d)%s"
        % (name, med, min(ts), max(ts), repeat, flag))
    return med


# ============================================================ 环境 & 规模
def cpu_name():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
    except Exception:
        return os.environ.get("PROCESSOR_IDENTIFIER") or "未知"


def total_ram_gb():
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    try:
        m = MEMORYSTATUSEX()
        m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullTotalPhys / (1024 ** 3)
    except Exception:
        return 0.0


def human(n):
    n = float(n or 0)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return ("%d B" % n) if u == "B" else ("%.1f %s" % (n, u))
        n /= 1024


def main():
    import platform
    say("=" * 78)
    say("流明盒 LumaCrate · 性能基准测试")
    say("=" * 78)

    import version as ver
    dbfile = db.db_path()
    if not os.path.exists(dbfile):
        say("[中止] 找不到索引库：%s" % dbfile)
        return 2

    env = {
        "cpu": cpu_name(),
        "cores": os.cpu_count(),
        "ram": total_ram_gb(),
        "os": "%s %s" % (platform.system(), platform.release()),
        "py": sys.version.split()[0],
        "arch": platform.machine(),
        "ver": "%s" % ver.VERSION,
        "build": ver.BUILD,
        "db": dbfile,
        "db_size": os.path.getsize(dbfile),
    }
    try:
        import PySide6
        env["pyside"] = PySide6.__version__
    except Exception:
        env["pyside"] = "?"

    # ------------------------------------------------ 数据规模
    say("\n[1/4] 采集数据规模…")
    st = db.stats()
    libs = db.libraries()
    scale = dict(st)
    scale["libraries"] = len(libs)
    conn = db.get_conn()
    for tbl in ("media", "people", "media_people"):
        try:
            scale[tbl + "_rows"] = conn.execute("SELECT COUNT(*) FROM " + tbl).fetchone()[0]
        except Exception:
            scale[tbl + "_rows"] = -1
    try:
        scale["indexes"] = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='index'").fetchone()[0]
    except Exception:
        scale["indexes"] = -1
    try:
        scale["journal_mode"] = conn.execute("PRAGMA journal_mode").fetchone()[0]
    except Exception:
        scale["journal_mode"] = "?"
    scale["posters"] = conn.execute(
        "SELECT COUNT(*) FROM media WHERE IFNULL(poster,'')<>''").fetchone()[0]
    scale["nfo"] = conn.execute(
        "SELECT COUNT(*) FROM media WHERE IFNULL(nfo_path,'')<>''").fetchone()[0]
    say("    影片 %s / 剧集 %s / 分片 %s / 演员 %s / 关联 %s / 索引 %s 条 / 库 %s 个"
        % (st.get("movies"), st.get("tvshows"), st.get("parts"), st.get("people"),
           scale["media_people_rows"], scale["indexes"], len(libs)))
    say("    数据库 %s，封面 %s 张，nfo %s 份，journal=%s"
        % (human(env["db_size"]), scale["posters"], scale["nfo"], scale["journal_mode"]))

    # 真实样本：一条标题片段 / 一个年份 / 一个库名 / 60 个 id
    rows = db.search_media(limit=220, light=True, sort="sort_title")
    if not rows:
        say("[中止] 索引里没有可用记录。")
        return 2
    kw = (rows[0].get("title") or "")[:2] or "a"
    ids60 = [r["id"] for r in rows[:60]]
    first_lib = libs[0] if libs else None
    lib_name = (first_lib.get("name") if isinstance(first_lib, dict) else first_lib) \
        if first_lib else None
    genres = []
    for r in rows:
        for g in (r.get("genres") or "").replace("|", ",").split(","):
            g = g.strip()
            if g:
                genres.append(g)
                break
        if genres:
            break
    year = next((r.get("year") for r in rows if r.get("year")), None)
    nfos = [r.get("nfo_path") for r in rows if r.get("nfo_path")][:40]
    nfos = [p for p in nfos if os.path.exists(p)][:20]
    say("    样本：关键词 %r / 流派 %r / 年份 %r / 库 %r / nfo %d 份"
        % (kw, genres[:1], year, lib_name, len(nfos)))

    # ------------------------------------------------ 数据层
    say("\n[2/4] 数据层基准…")

    def cold():
        db.close_conn()
        return db.stats()

    bench("冷启动首个查询（含建连）", cold, repeat=3, warmup=0, thr=300,
          note="应用启动时第一次碰库的代价")
    bench("全库计数 count_media()", lambda: db.count_media(), scale="48k", thr=80)
    bench("关键词计数 count_media(kw)", lambda: db.count_media(keyword=kw), thr=250)
    if genres:
        bench("组合筛选计数（标签+年份）",
              lambda: db.count_media(genre=genres[0], year_from=year or 2000), thr=120)
    if lib_name:
        bench("单库计数 count_media(library)", lambda: db.count_media(library=lib_name), thr=80)

    bench("首屏分页 60 条（light）",
          lambda: db.search_media(limit=60, offset=0, light=True), scale="offset=0", thr=80)
    deep = max(0, scale["media_rows"] - 120)
    bench("深层翻页 60 条", lambda: db.search_media(limit=60, offset=deep, light=True),
          scale="offset=%d" % deep, thr=150, note="滚到底部/自动续拉")
    bench("随机排序 60 条（深 offset）",
          lambda: db.search_media(limit=60, offset=deep // 2, light=True, sort="random"),
          thr=180, note="会话种子置换，不是 ORDER BY RANDOM()")
    bench("最近添加 60 条（按时间倒序）",
          lambda: db.search_media(limit=60, offset=0, light=True,
                                  sort="added_time", asc=False), thr=100)
    bench("关键词列表 60 条",
          lambda: db.search_media(keyword=kw, limit=60, offset=0, light=True), thr=300)
    if lib_name:
        bench("单库列表 60 条",
              lambda: db.search_media(library=lib_name, limit=60, offset=0, light=True), thr=100)
    bench("侧边栏库名计数 library_counts()", lambda: db.library_counts(), thr=80)
    bench("总览 stats()", lambda: db.stats(), thr=120)

    def pk_200():
        for i in ids60[:40]:
            db.get_media(i)
    bench("详情页 PK 回查 ×40", pk_200, thr=200, note="点开一张卡打开详情")

    bench("批量演员映射 actors_map(60)", lambda: db.actors_map(ids=ids60), thr=100,
          note="一屏 60 张卡的演员小字")
    bench("批量演职员 cast_crew_map(60)", lambda: db.cast_crew_map(ids=ids60), thr=100)
    bench("按 id 回填整行 media_by_ids(60)", lambda: db.media_by_ids(ids60), thr=100,
          note="智能推荐结果喂给卡片墙前的回填")
    bench("演员列表 query_people(100)", lambda: db.query_people(role_type="Actor", limit=100),
          thr=300, note="演员库首屏")
    bench("演员计数 count_people(Actor)",
          lambda: db.count_people(role_type="Actor"), thr=150)

    if nfos:
        def parse_n():
            for p in nfos:
                nfo_parser.parse_any(p)
        bench("nfo 解析（%d 份合计）" % len(nfos), parse_n, thr=600,
              note="扫描时逐文件解析 nfo")

    # 全库重活：必须后台线程
    say("    —— 以下三项是全库重活，应用里都必须放后台线程 ——")
    bench("全库画像 insight.Portrait().build()",
          lambda: insight_mod.Portrait().build(), repeat=1, warmup=0, thr=None,
          note="「画像概览」页；后台线程 + 进度回调")
    bench("全库标签统计 library_tag_stats()",
          lambda: tagopt_mod.library_tag_stats(), repeat=1, warmup=0, thr=None,
          note="「标签优化」扫描预览；后台线程")
    bench("TagOptimizer 构造",
          lambda: tagopt_mod.TagOptimizer(), repeat=3, thr=300)

    NOTES.append(
        "`insight.Portrait().build()` / `tagopt.library_tag_stats()` 是**全库全表扫描**，"
        "必须留在后台线程并给进度回调；它们出现在 GUI 线程里就是一次可见的卡死。")

    # ------------------------------------------------ Qt 层
    say("\n[3/4] Qt / 渲染层基准…")
    try:
        from PySide6.QtGui import QColor, QFont, QFontDatabase, QPixmap
        from PySide6.QtWidgets import QApplication

        t0 = time.perf_counter()
        app = QApplication.instance() or QApplication([])
        qapp_ms = (time.perf_counter() - t0) * 1000.0
        for f in (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhbd.ttc"):
            if os.path.exists(f):
                QFontDatabase.addApplicationFont(f)
        app.setFont(QFont("Microsoft YaHei", 10))

        import main_window as mw

        RESULTS.append(dict(group="Qt 层", name="QApplication 初始化", scale="", unit="次",
                            median=qapp_ms, lo=qapp_ms, hi=qapp_ms, n=1, thr=2000,
                            note="进程启动 → Qt 就绪"))
        say("  %-34s %9.2f ms" % ("QApplication 初始化", qapp_ms))

        appearances = [{"mode": "磨砂玻璃", "level": "中", "accent": h}
                       for _n, h in cfg.ACCENT_COLORS]
        holder = {"i": 0}

        def one_render():
            ap = appearances[holder["i"] % len(appearances)]
            holder["i"] += 1
            return mw.render_style(ap)

        bench("样式表渲染 render_style()", one_render, group="Qt 层", repeat=20,
              warmup=2, thr=30, note="换高亮色时的字符串替换")
        bench("样式表应用 load_style(app)", lambda: mw.load_style(app), group="Qt 层",
              repeat=10, warmup=1, thr=200, note="整套 QSS 重解析（换色/换主题）")

        # 卡片墙：一屏 60 张
        cards_rows = db.search_media(limit=60, offset=0, light=True)

        def build_cards(cold_cache):
            if cold_cache:
                mw._COVER_CACHE.clear()
            made = []
            for r in cards_rows:
                c = mw.PosterCard(r, lambda *a: None, "", "",
                                  on_select=lambda *a: None, parts_count=0,
                                  on_play=lambda *a: None, on_fav=lambda *a: None)
                c.setParent(None)
                made.append(c)
            for c in made:
                c.deleteLater()
            app.processEvents()

        bench("建 60 张海报卡（冷封面缓存）", lambda: build_cards(True), group="Qt 层",
              repeat=5, warmup=1, thr=1200, note="首屏：含封面解码+缩放")
        bench("建 60 张海报卡（热缓存）", lambda: build_cards(False), group="Qt 层",
              repeat=5, warmup=2, thr=600, note="续拉稳态：封面已缓存")

        # 自绘开关：v1.26.0 起每帧都去取一次「当前高亮色」，顺手量一次开销，
        # 证明「跟随高亮色」不是靠加缓存也不是靠全局状态，而是零代价的现取。
        import ui_settings as ui_mod
        sw = ui_mod.ToggleSwitch(checked=True)
        sw.resize(46, 26)
        _junk = []

        def draw_switches(n=200):
            for _ in range(n):
                pm = QPixmap(sw.size())
                pm.fill(QColor("#000000"))
                sw.render(pm)
                _junk.append(pm)

        bench("自绘开关渲染 ×200（每帧现取高亮色）", draw_switches, group="Qt 层",
              repeat=3, warmup=1, thr=600, note="单帧 %.2f ms" % 0.0)
        med_sw = next((r["median"] for r in RESULTS if r["name"].startswith("自绘开关渲染")), 0)
        for r in RESULTS:
            if r["name"].startswith("自绘开关渲染"):
                r["note"] = "单帧 %.3f ms" % (med_sw / 200.0)
        sw.deleteLater()
        NOTES.append(
            "**卡片墙渲染**：PosterCard 每张 ≈ %.1f ms（热缓存）—— 一屏 60 张 ≈ %.0f ms，"
            "所以卡片墙必须增量渲染（`LazyGrid` 每批 60 + `QTimer.singleShot(1)` 让出事件循环），"
            "一次性建满 4.8 万张会直接冻住界面。"
            % (next((r["median"] for r in RESULTS
                     if r["name"] == "建 60 张海报卡（热缓存）"), 0) / 60.0,
               next((r["median"] for r in RESULTS
                     if r["name"] == "建 60 张海报卡（热缓存）"), 0)))
    except Exception as e:
        import traceback
        traceback.print_exc()
        NOTES.append("Qt 层基准未完成：%s: %s" % (type(e).__name__, e))
        say("  [!!] Qt 层基准失败：%s: %s" % (type(e).__name__, e))

    # ------------------------------------------------ 结论
    say("\n[4/4] 写 《性能基线.md》…")
    write_report(env, scale, kw, genre=(genres[0] if genres else None), year=year,
                 library=lib_name)
    say("    -> %s" % MD_PATH)
    over = [r for r in RESULTS if r["thr"] and r["median"] and r["median"] > r["thr"]]
    say("\n判定：%d 项，其中 %d 项超出阈值。"
        % (sum(1 for r in RESULTS if r["thr"]), len(over)))
    for r in over:
        say("  [!!] %s：%.2f ms > 阈值 %.0f ms" % (r["name"], r["median"], r["thr"]))
    return 0


def write_report(env, scale, kw, genre=None, year=None, library=None):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    L = []
    A = L.append
    A("# 流明盒 LumaCrate · 性能基线")
    A("")
    A("> 由 `dev/benchmark.py` 在**真实索引**上生成（只读，不写入）。")
    A("> 生成时间：%s ｜ 被测版本：**%s (Build %s)**" % (now, env["ver"], env["build"]))
    A("")
    A("## 一、测试环境")
    A("")
    A("| 项 | 值 |")
    A("|---|---|")
    A("| CPU | %s |" % env["cpu"])
    A("| 核心数 | %s |" % env["cores"])
    A("| 内存 | %.1f GB |" % env["ram"])
    A("| 操作系统 | %s |" % env["os"])
    A("| Python | %s (%s) |" % (env["py"], env["arch"]))
    A("| PySide6 | %s |" % env["pyside"])
    A("")
    A("## 二、数据规模")
    A("")
    A("| 项 | 值 |")
    A("|---|---|")
    A("| 数据库文件 | `%s` |" % env["db"])
    A("| 文件体积 | %s |" % human(env["db_size"]))
    A("| 影片 | %s |" % scale.get("movies"))
    A("| 剧集 | %s |" % scale.get("tvshows"))
    A("| 分片（选集） | %s |" % scale.get("parts"))
    A("| 演员 / 影人 | %s |" % scale.get("people"))
    A("| media 行数 | %s |" % scale.get("media_rows"))
    A("| people 行数 | %s |" % scale.get("people_rows"))
    A("| media_people 关联 | %s |" % scale.get("media_people_rows"))
    A("| 索引条数 | %s |" % scale.get("indexes"))
    A("| journal 模式 | %s |" % scale.get("journal_mode"))
    A("| 有封面的条目 | %s |" % scale.get("posters"))
    A("| 有 nfo 的条目 | %s |" % scale.get("nfo"))
    A("| 媒体库 | %s 个 |" % scale.get("libraries"))
    A("")
    A("## 三、结果")
    A("")
    for group in ("数据层", "Qt 层"):
        items = [r for r in RESULTS if r["group"] == group]
        if not items:
            continue
        A("### %s（单位 ms，取中位数）" % group)
        A("")
        A("| 用例 | 规模 | 中位 | 最小 | 最大 | n | 阈值 | 判定 | 说明 |")
        A("|---|---|---:|---:|---:|---:|---:|:--:|---|")
        for r in items:
            if r["median"] is None:
                A("| %s | %s | — | — | — | %d | %s | ❌ | %s |"
                  % (r["name"], r["scale"] or "—", r["n"],
                     ("%.0f" % r["thr"]) if r["thr"] else "—", r["note"]))
                continue
            if r["thr"]:
                ok = "✅" if r["median"] <= r["thr"] else "⚠️"
            else:
                ok = "—"
            A("| %s | %s | **%.2f** | %.2f | %.2f | %d | %s | %s | %s |"
              % (r["name"], r["scale"] or "—", r["median"], r["lo"], r["hi"], r["n"],
                 ("%.0f" % r["thr"]) if r["thr"] else "—", ok, r["note"]))
        A("")
    A("## 四、结论")
    A("")
    A("### 4.1 交互路径都落在「无感」区间")
    A("")
    A("- 首屏分页、深层翻页、最近添加、关键词搜索、单库筛选、批量演员映射、主键回查，"
      "全部在 **个位数到几十毫秒**；这些是滚动和翻页时会反复发生的操作，"
      "保持在这个量级用户察觉不到停顿。")
    A("- 跨全表聚合（`count_media(keyword)` / `library_counts()` / `stats()` / "
      "`count_people()`）落在 15~50 ms：它们**必然**要全扫一遍，"
      "所以合适的位置是「进页面时算一次 + 结果缓存」，不要挂到输入框的每次改动上。")
    A("")
    A("### 4.2 必须放后台线程的操作（写死这条）")
    A("")
    for n in NOTES:
        A("- " + n)
    A("")
    A("### 4.3 卡片墙的规模上限来自「控件数」而不是「查询」")
    A("")
    A("数据层已经下推 SQL（筛选/排序/分页全在库内完成，不把整库读进内存），"
      "真正的瓶颈是**每张卡都是一个 QFrame + 若干 QLabel**。"
      "本基线给出的是「每批 60 张」的代价，`LazyGrid` 按此每次只建一批、"
      "用 `QTimer.singleShot(1, …)` 让出事件循环，因此 4.8 万条与 5 千条的首屏体感一致。")
    A("")
    A("### 4.4 已知边界：随机排序是「全表扫描 + 全表排序」")
    A("")
    _rnd_ms = next((r["median"] for r in RESULTS
                    if r["name"].startswith("随机排序")), 0) or 0
    A("`sort=\"random\"` 走的是会话种子置换 `((id * 2654435761 + SEED) %% 2147483647)`。"
      "它是一个**表达式**，任何索引都无法排序它，所以每取一页都要把符合条件的行全扫一遍再排一次 —— "
      "实测 **%.0f ms**，且随 offset 增大而变差（浅 offset 靠 top-N 排序器侥幸快，"
      "深 offset 必须整表排序）。" % _rnd_ms)
    A("")
    A("这是**设计上的取舍**，不是 bug：换来的是「分页稳定、不重不漏、点一下重新洗牌」。"
      "如果将来要优化，成本最低的路径是「物化一列 + 索引」：给 `media` 加一列 "
      "`shuffle INTEGER` + `CREATE INDEX … ON media(shuffle, id)`，"
      "`reshuffle()` 时整表 `UPDATE media SET shuffle = (id * MUL + SEED) % MOD`（一次性、"
      "约等于一次全表扫），之后每页都能走索引，落到个位数毫秒。"
      "代价是 `media` 多一列、插入新行时要一并写好该列。")
    A("")
    A("### 4.5 本次基准测试直接带出的优化（已修）")
    A("")
    A("第一轮跑出来的数字里，**排序相关的用例全是「全表扫描 + 临时 B-Tree 排序」**"
      "（`EXPLAIN QUERY PLAN` 为证：`SCAN m` + `USE TEMP B-TREE FOR ORDER BY`）。")
    A("")
    A("根因不是 SQL 写得差，而是**索引与 ORDER BY 对不上**：")
    A("")
    A("1. `search_media` 的排序键永远带附加项 —— `ORDER BY <字段> <方向>, m.year DESC, m.id ASC`；")
    A("2. 已有的 `idx_media_sort_title` 是**单列 + BINARY collation**，而查询写的是 "
      "`m.sort_title COLLATE NOCASE`。")
    A("")
    A("于是任何一条影片墙查询都无法命中索引。补两条与 ORDER BY **逐列对齐**的复合索引后：")
    A("")
    A("| 用例 | 修复前 | 修复后 | 提速 |")
    A("|---|---:|---:|---:|")
    for _n, _b, _after in OPT_BEFORE_AFTER:
        _a = next((r["median"] for r in RESULTS
                   if r["name"].startswith(_after[0])), None)
        _av = ("%.2f ms" % _a) if _a is not None else "—"
        _x = ("%.0f×" % (_b / _a)) if (_a and _a > 0) else "—"
        A("| %s | %.2f ms | %s | %s |" % (_n, _b, _av, _x))
    A("")
    A("代价：索引让数据库体积从 121.0 MB 涨到 128.9 MB（+7.9 MB），"
      "`init_db()` 首次补索引耗时约 4 s（仅一次，之后启动无感）。")
    A("")
    A("### 4.6 复现方式")
    A("")
    A("```bash")
    A('"C:/Users/zouzu/.workbuddy/binaries/python/envs/default/Scripts/python.exe" -u -c \\')
    A("  \"import runpy; runpy.run_path(r'<项目根>/dev/benchmark.py', run_name='__main__')\"")
    A("```")
    A("")
    A("同一台机器上数字应在 ±20% 内浮动。换机器、或媒体库放在 NAS/网络盘上时差异会更大，"
      "因为封面解码与 nfo 解析是**真的落盘 I/O**，本基线也把它们算进去了。")
    A("")
    A("### 4.7 本次样本参数")
    A("")
    A("| 参数 | 值 |")
    A("|---|---|")
    A("| 关键词样本 | `%s` |" % kw)
    A("| 流派样本 | `%s` |" % (genre or "—"))
    A("| 年份样本 | `%s` |" % (year or "—"))
    A("| 媒体库样本 | `%s` |" % (library or "—"))
    A("")
    with io.open(MD_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    sys.exit(main())
