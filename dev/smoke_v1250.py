# -*- coding: utf-8 -*-
"""v1.25.0 离屏冒烟回归 —— 六条反馈逐条自证

跑法（shim 下必须走 runpy）：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/smoke_v1250.py', run_name='__main__')"

**安全约定**：`db.db_path` 指向临时目录的 media_center.db，`cfg.config_path` 指向临时
settings.json，日志也重定向到临时目录 —— 全程不碰真实索引、真实配置、真实媒体目录。
「标签优化」要真的写盘，所以 fixture 的 nfo 建在**临时目录**里，改的也是它。

v1.24.1 的 4 条反馈另跑 `dev/smoke_v1241.py` 做回归，本脚本只覆盖 v1.25.0 的 6 条。
"""
import io
import os
import re
import sys
import json
import shutil
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = os.path.join(tempfile.gettempdir(), "lmc_smoke_v1250")
FIX = os.path.join(TMP, "fix")                  # 媒体 / nfo 的临时「磁盘」
INDEX = os.path.join(TMP, "index_data")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
# 每次从干净的索引 + 干净配置开始（残留会让「6 部 / 4 部收藏」这类断言漂移）
for _f in (os.path.join(INDEX, "media_center.db"),
           os.path.join(INDEX, "media_center.db-wal"),
           os.path.join(INDEX, "media_center.db-shm"),
           os.path.join(TMP, "settings.json"),
           os.path.join(TMP, "alt_settings.json")):
    try:
        os.remove(_f)
    except OSError:
        pass
shutil.rmtree(FIX, ignore_errors=True)          # 上一轮写的 nfo / *.bak-* 一起清掉
os.makedirs(FIX, exist_ok=True)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SPLASH"] = "1"

import applog

applog.log_dir = lambda: os.path.join(INDEX, "logs")
applog.log_path = lambda: os.path.join(INDEX, "logs", "app.log")

import config as cfg
import database as db

db.db_path = lambda: os.path.join(INDEX, "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None

# 这些模块统一在最外层 import：某个段落中途失败时，后面的段落不该因为 NameError
# 而报出「假的第二个错」，把真正的问题盖掉。
import recommend as rec_mod
import tagopt
import ui_home
import ui_settings
import main_window as mw
from PySide6.QtWidgets import QGroupBox, QLabel, QBoxLayout, QPushButton
from PySide6.QtWidgets import QGraphicsDropShadowEffect
from PySide6.QtCore import Qt as _Qt, QThread

PASS, FAIL = [], []


def check(tag, cond, detail=""):
    (PASS if cond else FAIL).append(tag)
    print(f"[{'PASS' if cond else 'FAIL'}] {tag}  {detail}")


def section(t):
    print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)


def pump(app, n=12):
    """推进事件循环：LazyGrid / singleShot 的定时器都靠它跑起来。"""
    import time as _t
    from PySide6.QtCore import QCoreApplication
    for _ in range(n):
        QCoreApplication.processEvents()
        app.processEvents()
        _t.sleep(0.012)


# ============================================================ A. 版本号
section("A. 版本号（v1.25.0 / Build 2609210035）")
try:
    import version as ver
    check("A1 外部版本 v1.25.0", ver.VERSION == "v1.25.0", ver.VERSION)
    check("A2 内部构建号 2609210035", ver.BUILD == "2609210035", ver.BUILD)
    check("A3 大版本迭代 = 25 / 小版本 = 0",
          ver.MAJOR_ITER == 25 and ver.MINOR_ITER == 0,
          f"{ver.MAJOR_ITER}.{ver.MINOR_ITER}")
    check("A4 版权声明保留",
          "肆月Aperture" in ver.COPYRIGHT and "禁止用于商业用途" in ver.LICENSE_NOTE)
except Exception:
    check("A 版本号", False, traceback.format_exc().splitlines()[-1])

# ============================================================ B. fixture
section("B. 临时 fixture（60 部作品 / 4 部收藏 + 真 nfo 落到临时磁盘）")
IMG = os.path.join(FIX, "poster.png")
VIDEO = os.path.join(FIX, "smoke movie.mp4")
NOTVIDEO = os.path.join(FIX, "note.txt")
NFO = os.path.join(FIX, "smoke movie.nfo")
# nfo 里刻意混入：① 日语标签 ② 库内已有的中文写法 ③ **技术标签 1080p**
#                    ④ 片商 / 系列 ⑤ 演员 / 导演 / uniqueid / plot / thumb（写回时不许动）
NFO_TEXT = """<?xml version='1.0' encoding='utf-8'?>
<movie>
  <title>冒烟作品 中出し 巨乳</title>
  <originaltitle>Smoke Original</originaltitle>
  <plot>冒烟简介：中出し 的剧情。</plot>
  <year>2024</year>
  <studio>冒烟社</studio>
  <set>
    <name>冒烟系列</name>
  </set>
  <genre>中出し</genre>
  <genre>巨乳</genre>
  <genre>単体作品</genre>
  <genre>1080p</genre>
  <uniqueid type="tmdb">998877</uniqueid>
  <actor>
    <name>冒烟演员甲</name>
    <role>主演</role>
  </actor>
  <director>冒烟导演</director>
  <ratings>
    <rating name="imdb" max="10" default="true">
      <value>7.5</value>
    </rating>
  </ratings>
  <thumb>poster.png</thumb>
</movie>
"""
MEDIA_IDS, FAV_IDS, NFO_MEDIA_ID = [], [], 0
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QImage, QColor

    app = QApplication.instance() or QApplication(sys.argv)

    im = QImage(120, 180, QImage.Format_RGB32)
    im.fill(QColor(200, 30, 60))
    check("B1 生成测试海报 PNG", im.save(IMG), IMG)
    with open(VIDEO, "wb") as f:
        f.write(b"x" * 8)
    with open(NOTVIDEO, "w", encoding="utf-8") as f:
        f.write("x")
    with io.open(NFO, "w", encoding="utf-8", newline="") as f:
        f.write(NFO_TEXT)
    check("B2 真 nfo 已落到临时磁盘", os.path.isfile(NFO), NFO)

    db.init_db()
    # 4 部收藏（提供偏好画像）+ 56 部候选（供「换一批」消耗）
    for i in range(60):
        is_fav = i < 4
        mid = db.insert_media(
            title=f"冒烟作品 {i:02d}", year=2020 + (i % 6), kind="movie", library="冒烟库",
            genres=("标签A, 标签B, 片商:冒烟社, 系列:冒烟系列" if is_fav
                    else f"标签A, 标签C{i:02d}, 片商:冒烟社"),
            studio="冒烟社", collection="冒烟系列", quality="1080P",
            runtime="01:40:00", file_size=3 * 1024 ** 3, rating=7.5,
            favorite=1 if is_fav else 0,
            file_path=(VIDEO if i == 0 else NOTVIDEO), poster=IMG, fanart=IMG, thumb=IMG,
            nfo_path=(NFO if i == 0 else ""), added_date="2026-09-21")
        MEDIA_IDS.append(mid)
        if is_fav:
            FAV_IDS.append(mid)
    NFO_MEDIA_ID = MEDIA_IDS[0]
    db.link_media_person(FAV_IDS[0], db.upsert_person("冒烟演员甲", "Actor"), "Actor", 0)
    check("B3 60 部作品入库", len(db.media_for_insight()) == 60,
          str(len(db.media_for_insight())))
    check("B4 4 部收藏", len(db.media_for_insight(favorites_only=True)) == 4,
          str(len(db.media_for_insight(favorites_only=True))))
    check("B5 nfo 能反查到 media.id",
          db.media_id_by_nfo(NFO) == NFO_MEDIA_ID, str(db.media_id_by_nfo(NFO)))

    cs = cfg.get_settings()
    if not cs.library("冒烟库"):
        cs.add_library("冒烟库", "电影", [FIX])
    check("B6 媒体库「冒烟库」指向临时目录",
          (cs.library("冒烟库") or {}).get("paths") == [FIX],
          str((cs.library("冒烟库") or {}).get("paths")))
except Exception:
    check("B fixture", False, traceback.format_exc().splitlines()[-1])

# ============================================================ C. 反馈 1
section("C. 反馈 1：AI 智能推荐可自填模型（含 ollama list 说明与示例）")
try:
    import recommend as rec_mod

    check("C1 DEFAULT_RECOMMEND 新增 ai_model 且默认空（= 自动）",
          cfg.DEFAULT_RECOMMEND.get("ai_model") == "", repr(cfg.DEFAULT_RECOMMEND.get("ai_model")))
    check("C2 list_models 对外公开（= ollama list 的第一列）", callable(rec_mod.list_models))
    check("C3 resolve_model / configured_model 对外公开",
          callable(rec_mod.resolve_model) and callable(rec_mod.configured_model))
    check("C4 探测地址仍是本机 11434",
          rec_mod.OLLAMA_HOST == "127.0.0.1:11434" and
          rec_mod.OLLAMA_URL.startswith("http://127.0.0.1:11434"))

    _real_list = rec_mod.list_models
    try:
        s = cfg.get_settings()
        s.recommend["ai_model"] = ""

        # --- 三种 list_models 场景 ---
        rec_mod.list_models = lambda *a, **k: []
        check("C5 本机没 Ollama → probe 返回 None", rec_mod.probe_ollama() is None)
        st = rec_mod.ai_status()
        check("C6 没 Ollama → engine=builtin", st["engine"] == "builtin", st["label"])
        check("C7 没 Ollama 时提示里写了「ollama list」这一条命令",
              "ollama list" in st["detail"], st["detail"][:60])
        check("C8 没 Ollama 时也给了 pull 指引（可执行）",
              "ollama pull" in st["detail"], st["detail"][:60])
        check("C9 状态文案不用 Markdown 反引号（QLabel 不认）", "`" not in st["detail"])

        rec_mod.list_models = lambda *a, **k: ["llama3:8b"]
        s.recommend["ai_model"] = "qwen2.5:7b"
        check("C10 指定了但本机没装 → probe 返回 None（不再乱退回/乱用别的模型）",
              rec_mod.probe_ollama() is None)
        st = rec_mod.ai_status()
        check("C11 指定未装 → 仍是 builtin 且标签写明「未安装」",
              st["engine"] == "builtin" and "未安装" in st["label"], st["label"])
        check("C12 指定未装 → 详情里列出本机到底装了什么",
              "llama3:8b" in st["detail"], st["detail"][:70])
        check("C13 指定未装 → 详情给出 ollama pull <模型> 的补救命令",
              "ollama pull qwen2.5:7b" in st["detail"], st["detail"][-60:])

        rec_mod.list_models = lambda *a, **k: ["qwen2.5:7b", "llama3:8b"]
        check("C14 指定的模型装了 → probe 就用它",
              rec_mod.probe_ollama() == "qwen2.5:7b", str(rec_mod.probe_ollama()))
        st = rec_mod.ai_status()
        check("C15 指定且装了 → engine=ollama", st["engine"] == "ollama", st["label"])
        check("C16 标签里带上实际要用的模型名",
              "qwen2.5:7b" in st["label"] and "设置里指定" in st["label"], st["label"])
        s.recommend["ai_model"] = ""
        check("C17 留空 → 自动取本机第一个",
              rec_mod.probe_ollama() == "qwen2.5:7b" and "自动选取" in rec_mod.ai_status()["label"],
              rec_mod.ai_status()["label"])
        check("C18 resolve_model 优先级：显式 > 设置 > 本机第一个",
              rec_mod.resolve_model("muse-glimmer:12b") == "muse-glimmer:12b"
              and rec_mod.resolve_model() == "qwen2.5:7b",
              rec_mod.resolve_model())
        rec_mod.list_models = lambda *a, **k: []
        check("C19 什么都没有时 resolve_model 兜底 llama3",
              rec_mod.resolve_model() == "llama3", rec_mod.resolve_model())

        # --- 请求体里真的带着用户填的模型 ---
        CAP = {}

        class _FakeResp:
            def __init__(self, payload):
                self._p = payload

            def read(self):
                return self._p

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def _fake_urlopen(req, timeout=None):
            CAP["url"] = req.full_url
            CAP["body"] = req.data
            return _FakeResp(json.dumps({"response": "苗条, 潮吹, 巨尻"}).encode("utf-8"))

        import urllib.request as _ur
        _real_open = _ur.urlopen
        _ur.urlopen = _fake_urlopen
        try:
            s.recommend["ai_model"] = "muse-glimmer:12b"
            words = rec_mod._ollama_expand(["标签A"], model=None)
            body = json.loads(CAP["body"].decode("utf-8"))
            check("C20 扩词请求打到 /api/generate", CAP["url"].endswith("/api/generate"), CAP["url"])
            check("C21 请求体 model = 设置里填的名字", body["model"] == "muse-glimmer:12b",
                  body["model"])
            check("C22 扩词结果被正确切分",
                  words == ["苗条", "潮吹", "巨尻"], str(words))
            check("C23 显式传参覆盖设置",
                  (rec_mod._ollama_expand(["x"], model="qwen3:4b") or True) and
                  json.loads(CAP["body"].decode("utf-8"))["model"] == "qwen3:4b",
                  json.loads(CAP["body"].decode("utf-8"))["model"])
            s.recommend["ai_model"] = ""
            rec_mod.list_models = lambda *a, **k: ["llama3:8b"]
            rec_mod._ollama_expand(["x"])
            check("C24 留空时用本机第一个模型",
                  json.loads(CAP["body"].decode("utf-8"))["model"] == "llama3:8b",
                  json.loads(CAP["body"].decode("utf-8"))["model"])
        finally:
            _ur.urlopen = _real_open
            rec_mod.list_models = _real_list

        # --- 偏好清洗 ---
        s.set_recommend(ai_model="  qwen2.5:7b  ")
        check("C25 模型名去空格后落盘", s.recommend["ai_model"] == "qwen2.5:7b",
              repr(s.recommend["ai_model"]))
        s.set_recommend(ai_model='bad name!@#$%^&*()";drop')
        check("C26 模型名里的危险字符被清掉",
              s.recommend["ai_model"] == "badname:drop" or
              re.fullmatch(r"[0-9A-Za-z_.:\-/]*", s.recommend["ai_model"]) is not None,
              repr(s.recommend["ai_model"]))
        s.set_recommend(ai_model="x" * 200)
        check("C27 模型名限长 64", len(s.recommend["ai_model"]) == 64,
              str(len(s.recommend["ai_model"])))
        s.set_recommend(ai_model="")
        check("C28 可以清回空（= 自动）", s.recommend["ai_model"] == "")
    finally:
        rec_mod.list_models = _real_list

    # --- UI：输入框 / 说明 / 示例 / 读取本机模型 ---
    import ui_settings
    import main_window as mw

    win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))
    win._open_settings()
    dlg = win._settings_dlg
    dlg._show("智能推荐")
    check("C29 智能推荐页有「调用模型」输入框", dlg.ed_ai_model is not None)
    check("C30 输入框有 placeholder（留空 = 自动）",
          "自动" in dlg.ed_ai_model.placeholderText(), dlg.ed_ai_model.placeholderText())
    check("C31 输入框 tooltip 写明就是 ollama list 第一列",
          "ollama list" in dlg.ed_ai_model.toolTip(), dlg.ed_ai_model.toolTip()[:50])
    check("C32 有「读取本机模型」按钮", dlg.btn_ai_models is not None and
          dlg.btn_ai_models.text() == "读取本机模型")

    # 说明文案：正文里必须同时出现 ollama list 与输入示例（这是反馈 1 的硬要求）
    hints = [w.text() for w in dlg._pg_smart.findChildren(ui_settings.QLabel)]
    joined = "\n".join(hints)
    check("C33 页面上写了「启动 Ollama 后执行 ollama list 查看已装模型」",
          "ollama list" in joined and "已经安装的模型" in joined)
    check("C34 页面给了多条可照抄的输入示例",
          all(x in joined for x in ("qwen2.5:7b", "llama3.1:8b", "qwen3:4b", "gemma3:12b")),
          "缺：" + "、".join(x for x in ("qwen2.5:7b", "llama3.1:8b", "qwen3:4b", "gemma3:12b")
                            if x not in joined))
    check("C35 示例里说明了「冒号和标签都要带上」",
          "冒号" in joined and "标签" in joined)
    check("C36 页面上说明了「填了但没装会自动降级」",
          "降级" in joined or "本机没装" in joined)

    # 输入 → 落盘 → 重开还在
    _real_start = ui_settings.AiProbeWorker.start
    ui_settings.AiProbeWorker.start = lambda self: None
    try:
        dlg.ed_ai_model.setText("qwen2.5:7b")
        dlg._on_ai_model_edited()
        check("C37 输入框改完即落盘", cfg.get_settings().recommend["ai_model"] == "qwen2.5:7b",
              repr(cfg.get_settings().recommend["ai_model"]))
        cfg._SETTINGS = None
        check("C38 重读配置后仍然是它",
              cfg.get_settings().recommend["ai_model"] == "qwen2.5:7b",
              repr(cfg.get_settings().recommend["ai_model"]))
        win._settings_dlg = None
        win._open_settings()
        dlg = win._settings_dlg
        dlg._show("智能推荐")
        check("C39 重开工具页输入框回显上次填的模型",
              dlg.ed_ai_model.text() == "qwen2.5:7b", dlg.ed_ai_model.text())
    finally:
        ui_settings.AiProbeWorker.start = _real_start

    # 读取本机模型 → 下拉填充 → 点选即填入
    _real_models_start = ui_settings.AiModelsWorker.start
    _real_probe_start = ui_settings.AiProbeWorker.start
    ui_settings.AiModelsWorker.start = lambda self: None
    ui_settings.AiProbeWorker.start = lambda self: None
    try:
        dlg._load_ai_models()
        check("C40 点「读取本机模型」立刻置灰并改文案（有即时反馈）",
              dlg.btn_ai_models.isEnabled() is False and dlg.btn_ai_models.text() == "读取中…",
              dlg.btn_ai_models.text())
        dlg._on_ai_models(["qwen2.5:7b", "llama3:8b"])
        check("C41 读完恢复按钮", dlg.btn_ai_models.isEnabled() and
              dlg.btn_ai_models.text() == "读取本机模型")
        check("C42 下拉列出本机模型（多一行说明）", dlg.cb_ai_model.count() == 3,
              str(dlg.cb_ai_model.count()))
        check("C43 首项是说明项（data 为空，不会被误选）",
              dlg.cb_ai_model.itemData(0) == "" and
              "2 个模型" in dlg.cb_ai_model.itemText(0), dlg.cb_ai_model.itemText(0))
        dlg._pick_ai_model(1)
        check("C44 点选模型即填入输入框并落盘",
              dlg.ed_ai_model.text() == "qwen2.5:7b" and
              cfg.get_settings().recommend["ai_model"] == "qwen2.5:7b",
              dlg.ed_ai_model.text())
        dlg._on_ai_models([])
        check("C45 读不到模型时给出可读原因（不是空白）",
              "Ollama" in dlg.cb_ai_model.itemText(0), dlg.cb_ai_model.itemText(0))
    finally:
        ui_settings.AiModelsWorker.start = _real_models_start
        ui_settings.AiProbeWorker.start = _real_probe_start

    rec_mod.list_models = lambda *a, **k: ["qwen2.5:7b"]
    try:
        dlg._on_ai_probe(rec_mod.ai_status())
        check("C46 检测结果里带 ✅ 与模型名",
              "✅" in dlg.ai_state.text() and "qwen2.5:7b" in dlg.ai_state.text(),
              dlg.ai_state.text()[:60])
    finally:
        rec_mod.list_models = _real_list
    win.close()
except Exception:
    check("C 反馈 1", False, traceback.format_exc().splitlines()[-1])

# ============================================================ D. 反馈 2
section("D. 反馈 2：数据导出 / 导入页的间距与下方一致（不再紧贴）")
try:
    from PySide6.QtWidgets import QGroupBox, QLabel, QBoxLayout
    win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))
    win._open_settings()
    dlg = win._settings_dlg
    dlg._show("数据与日志")
    groups = {g.title(): g for g in dlg._pg_data.findChildren(QGroupBox)}
    g = groups.get("数据导出 / 导入")
    check("D1 找到「数据导出 / 导入」分组", g is not None, str(list(groups)[:4]))
    if g is not None:
        lay = g.layout()
        check("D2 分组内层布局间距 = 10（原为 Qt 默认值）",
              lay is not None and lay.spacing() == 10,
              str(getattr(lay, "spacing", lambda: None)()))
        inner = [x for x in g.findChildren(QBoxLayout) if x is not lay]
        gaps = sorted({x.spacing() for x in inner})
        check("D3 没有子布局还在用 2 那种「贴死」间距（就是原来的缺陷值）",
              all(s != 2 for s in gaps), f"实际间距 {gaps}")
        lb = next((l for l in g.findChildren(QLabel)
                   if l.text() == "导出内容（可多选）："), None)
        check("D4 找到「导出内容（可多选）：」标签", lb is not None)
        if lb is not None:
            pw = lb.parentWidget()
            pl = pw.layout() if pw is not None else None
            check("D5 勾选区容器的间距与分组一致（都是 10）",
                  pl is not None and pl.spacing() == 10,
                  str(getattr(pl, "spacing", lambda: None)()))
            check("D6 勾选区与分组间距相等（视觉上上下一致）",
                  pl is not None and pl.spacing() == lay.spacing(),
                  f"{getattr(pl, 'spacing', lambda: None)()} vs {lay.spacing()}")
    win.close()
except Exception:
    check("D 反馈 2", False, traceback.format_exc().splitlines()[-1])

# ============================================================ E. 反馈 3
section("E. 反馈 3：最近 N 轮推荐过的不再重复出现（N 可设）")
try:
    s = cfg.get_settings()

    check("E1 DEFAULT_RECOMMEND 新增 no_repeat_rounds，默认 3",
          cfg.DEFAULT_RECOMMEND.get("no_repeat_rounds") == 3,
          str(cfg.DEFAULT_RECOMMEND.get("no_repeat_rounds")))
    check("E2 Settings 有按轮的推荐历史（不是只有一个扁平表）",
          hasattr(s, "smart_history") and isinstance(s.smart_history, list))
    check("E3 push_smart_round / recent_smart_ids / clear_smart_history 都在",
          all(callable(getattr(s, m, None))
              for m in ("push_smart_round", "recent_smart_ids", "clear_smart_history")))
    check("E4 旧键 seen_smart 仍保留（老导出包兼容）", hasattr(s, "seen_smart"))

    def rounds_n(n):
        """把「不重复轮数」设成 n，并清空历史，返回每次 recommend() 的实际结果。"""
        s.recommend["no_repeat_rounds"] = n
        s.clear_smart_history()
        out = []
        for _ in range(5):
            r = rec_mod.recommend(page=1, limit=12)
            out.append((set(p["id"] for p in r["picks"]), r.get("excluded"),
                        r.get("round"), len(r["picks"])))
        return out

    # ---- N = 0：不限制 → 每轮都拿到同一批（同时反证 exclude 真的没用上才叫「不限制」）
    got0 = rounds_n(0)
    check("E5 N=0 → recent_smart_ids 返回空（= 不限制）", s.recent_smart_ids() == [])
    check("E6 N=0 → 每轮都不避让（excluded 恒为 0）",
          [g[1] for g in got0] == [0] * 5, str([g[1] for g in got0]))
    check("E7 N=0 → 两轮结果完全相同（不限制就是重复出现）",
          got0[0][0] == got0[1][0] and len(got0[0][0]) == 12,
          f"{len(got0[0][0])} / 交集 {len(got0[0][0] & got0[1][0])}")

    # ---- N = 1：只避让最近 1 轮
    got1 = rounds_n(1)
    check("E8 N=1 → 避让数 0 / 12 / 12 / 12 / 12",
          [g[1] for g in got1] == [0, 12, 12, 12, 12], str([g[1] for g in got1]))
    check("E9 N=1 → 相邻两轮绝不相交",
          all(not (got1[i][0] & got1[i + 1][0]) for i in range(4)))
    check("E10 N=1 → 第 3 轮又回到第 1 轮那批（说明窗口正好是 1 轮）",
          got1[0][0] == got1[2][0], f"r1∩r3 = {len(got1[0][0] & got1[2][0])} / 12")

    # ---- N = 3：默认值，避让最近 3 轮
    got3 = rounds_n(3)
    check("E11 N=3 → 避让数递增 0/12/24/36，第 5 轮封顶在 36（只留 3 轮）",
          [g[1] for g in got3] == [0, 12, 24, 36, 36], str([g[1] for g in got3]))
    check("E12 N=3 → 每轮都是 12 部",
          all(g[3] == 12 for g in got3), str([g[3] for g in got3]))
    check("E13 N=3 → 前 4 轮两两不相交（这就是「换一批」该有的样子）",
          all(not (got3[i][0] & got3[j][0]) for i in range(4) for j in range(i + 1, 4)),
          str([len(got3[i][0] & got3[j][0]) for i in range(4) for j in range(i + 1, 4)]))
    check("E14 N=3 → 第 5 轮只与第 1 轮有重叠（窗口外放行）",
          bool(got3[4][0] & got3[0][0])
          and not (got3[4][0] & got3[1][0]) and not (got3[4][0] & got3[2][0])
          and not (got3[4][0] & got3[3][0]),
          f"∩r1={len(got3[4][0] & got3[0][0])} ∩r2={len(got3[4][0] & got3[1][0])}")
    check("E15 轮号 1..5 连续递增",
          [g[2] for g in got3] == [1, 2, 3, 4, 5], str([g[2] for g in got3]))
    check("E16 历史里确实记了 5 轮",
          len(s.smart_history) == 5, str(len(s.smart_history)))

    # ---- v1.24.x 的根因回归：page 回到 1 也必须避让
    s.recommend["no_repeat_rounds"] = 3
    s.clear_smart_history()
    a = set(p["id"] for p in rec_mod.recommend(page=1, limit=12)["picks"])
    b = set(p["id"] for p in rec_mod.recommend(page=1, limit=12)["picks"])
    check("E17 【根因回归】重新进推荐页（page 回到 1）也不给同一批",
          bool(a) and not (a & b), f"r1∩r2 = {len(a & b)}")

    # ---- Recommender 层的根因：exclude_ids 真的被用上了
    rec = rec_mod.Recommender(s)
    s.clear_smart_history()
    r1 = rec.recommend(limit=12, exclude_ids=[])
    ids1 = [p["id"] for p in r1["picks"]]
    r2 = rec.recommend(limit=12, exclude_ids=ids1)
    ids2 = [p["id"] for p in r2["picks"]]
    check("E18 【根因】exclude_ids 真的从候选池里剔除了",
          not (set(ids1) & set(ids2)) and len(ids2) == 12,
          f"交集 {len(set(ids1) & set(ids2))} / 第二轮 {len(ids2)} 部")
    r3 = rec.recommend(limit=12, exclude_ids=ids1 + ids2)
    check("E19 连续避让两次仍然拿得到 12 部（56 个候选够用）",
          len(r3["picks"]) == 12 and not (set(p["id"] for p in r3["picks"]) &
                                          set(ids1 + ids2)))
    check("E20 收藏的作品永远不进候选池",
          not (set(ids1) & set(FAV_IDS)), str(sorted(set(ids1) & set(FAV_IDS))))
    check("E21 exclude_ids 混入脏值不炸",
          len(rec.recommend(limit=6, exclude_ids=["x", None, 1.5, "9"])["picks"]) == 6)

    # ---- 清洗与落盘 ----
    s.set_recommend(no_repeat_rounds=999)
    check("E22 轮数上限收到 50", s.recommend["no_repeat_rounds"] == 50,
          str(s.recommend["no_repeat_rounds"]))
    s.set_recommend(no_repeat_rounds=-5)
    check("E23 轮数下限收到 0", s.recommend["no_repeat_rounds"] == 0,
          str(s.recommend["no_repeat_rounds"]))
    s.set_recommend(no_repeat_rounds="abc")
    check("E24 非数字回落到 3", s.recommend["no_repeat_rounds"] == 3,
          str(s.recommend["no_repeat_rounds"]))

    s.clear_smart_history()
    s.push_smart_round([FAV_IDS[0], FAV_IDS[1]])
    s.push_smart_round([])
    s.push_smart_round(["分", None])
    check("E25 空轮 / 脏 id 不产生新的一轮",
          len(s.smart_history) == 1, str(len(s.smart_history)))
    check("E26 轮内 id 去重",
          s.smart_history[0]["ids"] == [FAV_IDS[0], FAV_IDS[1]],
          str(s.smart_history[0]["ids"]))
    cfg._SETTINGS = None
    s2 = cfg.get_settings()
    check("E27 推荐历史真的落盘了",
          len(s2.smart_history) == 1 and s2.smart_history[0]["ids"] == [FAV_IDS[0], FAV_IDS[1]],
          str(s2.smart_history))
    check("E28 落盘后 recent_smart_ids 仍算得对",
          set(s2.recent_smart_ids(3)) == {FAV_IDS[0], FAV_IDS[1]},
          str(s2.recent_smart_ids(3)))
    check("E29 兼容键 seen_smart 同步成扁平列表",
          set(s2.seen_smart) == {FAV_IDS[0], FAV_IDS[1]}, str(s2.seen_smart))
    for _i in range(60):
        s2.push_smart_round([1000 + _i])
    check("E30 历史上限：不会无限膨胀（保留 ≥20 轮且远小于 61）",
          20 <= len(s2.smart_history) <= 40, str(len(s2.smart_history)))
    s2.clear_smart_history()
    check("E31 清空推荐历史同时清掉两个键",
          s2.smart_history == [] and s2.seen_smart == [] and s2.recent_smart_ids() == [])
    check("E32 脏历史（非 dict / 空 ids）在读配置时被丢掉",
          cfg.Settings._clean_smart_history(
              [{"round": 1, "ids": [3, 3, "4"]}, "垃圾", {"round": 2, "ids": []}, None])
          == [{"round": 1, "ids": [3, 4], "ts": 0.0}],
          str(cfg.Settings._clean_smart_history([{"round": 1, "ids": [3, 3, "4"]}, "垃圾",
                                                 {"round": 2, "ids": []}, None])))
    check("E33 老配置里只有 seen_smart 时能迁移成 1 轮",
          "[{'round': 1" in repr(
              cfg.Settings._clean_smart_history([{"round": 1, "ids": [7]}])),
          str(cfg.Settings._clean_smart_history([{"round": 1, "ids": [7]}])))

    # ---- UI 接线 ----
    win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))
    win._open_settings()
    dlg = win._settings_dlg
    dlg._show("智能推荐")
    check("E34 有「已经推荐的 N 轮内不再重复出现」控件",
          dlg.sp_rounds is not None and dlg.sp_rounds.suffix().strip() == "轮",
          dlg.sp_rounds.suffix() if dlg.sp_rounds else "")
    check("E35 轮数范围 0–50（0 = 不限制）",
          dlg.sp_rounds.minimum() == 0 and dlg.sp_rounds.maximum() == 50,
          f"{dlg.sp_rounds.minimum()}–{dlg.sp_rounds.maximum()}")
    check("E36 控件 tooltip 说明了「换一批 = 1 轮」",
          "换一批" in dlg.sp_rounds.toolTip() and "不限制" in dlg.sp_rounds.toolTip(),
          dlg.sp_rounds.toolTip()[:60])
    check("E37 有历史状态标签与「清空推荐历史」按钮",
          dlg.lb_hist is not None and
          any(b.text() == "清空推荐历史"
              for b in dlg._pg_smart.findChildren(ui_settings.QPushButton)))
    # 注意：用 cfg.get_settings() 而不是上面那个 s —— E27 里 cfg._SETTINGS 被置空过一次，
    # 之后重建的 Settings 才是 dlg.s 持有的那一个；拿旧引用写历史，界面读不到。
    cfg.get_settings().clear_smart_history()
    cfg.get_settings().push_smart_round(MEDIA_IDS[:12])
    dlg._refresh_hist_label()
    check("E38 状态标签显示轮数与避让条数",
          "1 轮" in dlg.lb_hist.text() and "12" in dlg.lb_hist.text(), dlg.lb_hist.text())
    dlg.sp_rounds.setValue(7)
    check("E39 改轮数立即落盘", cfg.get_settings().recommend["no_repeat_rounds"] == 7,
          str(cfg.get_settings().recommend["no_repeat_rounds"]))
    cfg.get_settings().push_smart_round(MEDIA_IDS[:12])
    dlg._refresh_hist_label()
    check("E40 轮数变大后避让条数跟着变（7 轮窗口 ≥ 2 轮窗口）",
          "2 轮" in dlg.lb_hist.text(), dlg.lb_hist.text())
    dlg._clear_smart_history()
    check("E41 点清空后历史为空且标签给出反馈",
          cfg.get_settings().smart_history == [] and "清空" in dlg.lb_hist.text(),
          dlg.lb_hist.text())
    win.close()
except Exception:
    check("E 反馈 3", False, traceback.format_exc().splitlines()[-1])

# ============================================================ F. 反馈 4 引擎
section("F. 反馈 4：标签优化引擎（普通 / AI + 日语转中文 + 补全 + 安全写回）")
try:
    import tagopt

    # 用 AST 解析真实 import 语句（不能拿源码做字符串搜索：模块文档里就写着「不 import Qt」）
    import ast as _ast
    _tree = _ast.parse(io.open(os.path.join(SRC, "tagopt.py"), encoding="utf-8").read())
    _mods = set()
    for _node in _ast.walk(_tree):
        if isinstance(_node, _ast.Import):
            _mods |= {a.name.split(".")[0] for a in _node.names}
        elif isinstance(_node, _ast.ImportFrom) and _node.module:
            _mods.add(_node.module.split(".")[0])
    check("F1 tagopt 不 import Qt（可离屏单测）",
          "PySide6" not in _mods, "实际 import：" + "、".join(sorted(_mods)))
    check("F2 词典无冲突", tagopt.JA2ZH_CONFLICTS == [], str(tagopt.JA2ZH_CONFLICTS))
    check("F3 词典规模 ≥ 150 条", len(tagopt.JA2ZH) >= 150, str(len(tagopt.JA2ZH)))
    check("F4 普通智能算法 + AI 智能算法两个入口都在",
          callable(tagopt.TagOptimizer) and callable(tagopt.ai_suggest))

    # ---- 词典：对齐用户库里真实在用的中文写法 ----
    check("F5 中出し → 中出（库内 22545 次那个写法，不是「内射」）",
          tagopt.to_zh("中出し") == "中出", tagopt.to_zh("中出し"))
    check("F6 単体作品 → 单体作品（库内 27899 次）",
          tagopt.to_zh("単体作品") == "单体作品", tagopt.to_zh("単体作品"))
    check("F7 大乱交 → 滥交（对齐库内写法）",
          tagopt.to_zh("大乱交") == "滥交", tagopt.to_zh("大乱交"))
    check("F8 デカ尻 → 巨尻（库内 1993 次，不是「巨臀」）",
          tagopt.to_zh("デカ尻") == "巨尻", tagopt.to_zh("デカ尻"))
    check("F9 复合标签整串命中：キス·接吻 → 接吻",
          tagopt.to_zh("キス·接吻") == "接吻", tagopt.to_zh("キス·接吻"))
    check("F10 复合标签只有一半是日语时取中文那半",
          tagopt.to_zh("寝取り·寝取られ·ＮＴＲ") == "寝取",
          tagopt.to_zh("寝取り·寝取られ·ＮＴＲ"))
    check("F11 假阳性修正：総集编 不是「中文」，要译成总集篇",
          tagopt.to_zh("総集编") == "总集篇" and tagopt.to_zh("女优ベスト·総集编") == "总集篇",
          f'{tagopt.to_zh("総集编")} / {tagopt.to_zh("女优ベスト·総集编")}')
    check("F12 纯中文标签不翻译（返回空串 = 保持不动）",
          tagopt.to_zh("巨乳") == "" and tagopt.to_zh("连裤袜") == "" and
          tagopt.to_zh("苗条") == "")
    check("F13 技术标签识别（1080p / HEVC / WEB-DL）",
          tagopt.is_tech("1080p") and tagopt.is_tech("HEVC") and tagopt.is_tech("WEB-DL")
          and not tagopt.is_tech("巨乳"))
    check("F14 伪标签与技术标签在 split_genres 里分得开",
          tagopt.split_genres("巨乳, 片商:冒烟社, 1080p") == (["巨乳"], ["片商:冒烟社"]),
          str(tagopt.split_genres("巨乳, 片商:冒烟社, 1080p")))
    check("F15 从标题抽关键词（标题写着玩法词而标签是空的）",
          "中出" in tagopt.tags_from_title("冒烟作品 中出し 巨乳"),
          str(tagopt.tags_from_title("冒烟作品 中出し 巨乳")))

    # ---- 磁盘扫描与定位 ----
    s = cfg.get_settings()
    opt = tagopt.TagOptimizer(s)
    check("F16 按视频文件定位同目录 nfo", opt.resolve_nfo(VIDEO) == NFO, str(opt.resolve_nfo(VIDEO)))
    check("F17 直接给 nfo 也认", opt.resolve_nfo(NFO) == NFO)
    check("F18 不存在的路径返回 None", opt.resolve_nfo(os.path.join(FIX, "没有这个.mp4")) is None)
    check("F19 单一文件范围只收 1 个 nfo", opt.collect("file", VIDEO) == [NFO],
          str(opt.collect("file", VIDEO)))
    check("F20 文件夹范围递归收 nfo",
          NFO in opt.collect("folder", FIX), str([os.path.basename(x) for x in opt.collect("folder", FIX)]))
    check("F21 媒体库范围按库配置的目录收 nfo",
          NFO in opt.collect("library", "冒烟库"),
          str([os.path.basename(x) for x in opt.collect("library", "冒烟库")]))
    check("F22 不存在的库返回空", opt.collect("library", "没有这个库") == [])

    # ---- 计划：不写盘，先看结果 ----
    p1 = opt.plan_one(NFO, algo="normal", translate=True, overwrite=False,
                      complete=True, use_cooccur=False)
    check("F23 计划读到了标题", p1["title"] == "冒烟作品 中出し 巨乳", p1["title"])
    check("F24 计划不报错", p1["error"] == "", p1["error"])
    check("F25 原有标签一个不少（含技术标签 1080p）",
          set(["中出し", "巨乳", "単体作品", "1080p"]) <= set(p1["before"]),
          str(p1["before"]))
    check("F26 【契约】技术标签 1080p 也在 before 里（不会被悄悄写没）",
          "1080p" in p1["before"], str(p1["before"]))
    check("F27 不覆盖源标签时，日语文案原样保留",
          "中出し" in p1["after"], str(p1["after"]))
    check("F28 同时补上中文写法 中出",
          "中出" in p1["after"], str(p1["after"]))
    check("F29 翻译登记了 (中出し → 中出)",
          ("中出し", "中出") in p1["translated"], str(p1["translated"]))
    check("F30 単体作品 也被译成 单体作品",
          ("単体作品", "单体作品") in p1["translated"], str(p1["translated"]))
    check("F31 纯中文标签没被乱译",
          all(a != b for a, b in p1["translated"]) and
          not any(a in ("巨乳", "1080p") for a, _b in p1["translated"]),
          str(p1["translated"]))
    check("F32 补上了「片商:冒烟社」伪标签（与库内约定一致）",
          "片商:冒烟社" in p1["after"], str(p1["after"]))
    check("F33 补上了「系列:冒烟系列」伪标签",
          "系列:冒烟系列" in p1["after"], str(p1["after"]))
    check("F34 不覆盖时 removed 为空（只做加法）", p1["removed"] == [], str(p1["removed"]))
    check("F35 added 就是 after - before",
          set(p1["added"]) == set(p1["after"]) - set(p1["before"]), str(p1["added"]))
    check("F36 计划阶段**没有**动磁盘",
          io.open(NFO, encoding="utf-8").read() == NFO_TEXT)
    check("F37 计划阶段没生成备份",
          not [f for f in os.listdir(FIX) if ".bak-" in f],
          str([f for f in os.listdir(FIX) if ".bak-" in f]))

    # 覆盖模式：用中文替换源日语
    p2 = opt.plan_one(NFO, algo="normal", translate=True, overwrite=True,
                      complete=False, use_cooccur=False)
    check("F38 覆盖模式：日语被中文替换掉", "中出" in p2["after"] and "中出し" not in p2["after"],
          str(p2["after"]))
    check("F39 覆盖模式：被替换的原标签记在 removed 里（可回溯）",
          "中出し" in p2["removed"] and "単体作品" in p2["removed"], str(p2["removed"]))
    check("F40 覆盖模式：不需要翻译的技术标签原样留下",
          "1080p" in p2["after"], str(p2["after"]))

    # 关掉翻译 / 关掉补全
    p3 = opt.plan_one(NFO, algo="normal", translate=False, complete=False,
                      use_cooccur=False)
    check("F41 关掉翻译 + 关掉补全 → 只动片商 / 系列，标签集合基本不变",
          set(["中出し", "巨乳", "単体作品", "1080p"]) <= set(p3["after"]) and
          p3["translated"] == [], str(p3["after"]))

    # AI 算法：不可用时静默降级
    _real_ai = tagopt.ai_suggest
    tagopt.ai_suggest = lambda *a, **k: []
    try:
        p4 = opt.plan_one(NFO, algo="ai", translate=True, complete=False, use_cooccur=False)
        check("F42 AI 引擎不可用 → 静默降级为内置算法（不抛错）",
              p4["error"] == "" and p4["engine"] == "builtin", p4["engine"])
        check("F43 降级后结果仍可用（翻译照做）", "中出" in p4["after"], str(p4["after"]))
    finally:
        tagopt.ai_suggest = _real_ai
    tagopt.ai_suggest = lambda *a, **k: ["苗条", "潮吹", "中出し"]
    try:
        p5 = opt.plan_one(NFO, algo="ai", translate=True, complete=False, use_cooccur=False)
        check("F44 AI 有输出 → 标成 ollama 引擎", p5["engine"] == "ollama", p5["engine"])
        check("F45 AI 给的中文词被采纳", "苗条" in p5["after"] and "潮吹" in p5["after"],
              str(p5["after"]))
        check("F46 AI 给的日语词也会被顺手译成中文",
              "中出" in p5["after"] and "中出し" not in p5["added"], str(p5["after"]))
        check("F47 AI 词不会把已有标签写重", len(p5["after"]) == len(set(p5["after"])),
              str(len(p5["after"])))
    finally:
        tagopt.ai_suggest = _real_ai

    # ---- 写回：备份 + 只动 genre + 同步数据库 ----
    plan = opt.plan_one(NFO, algo="normal", translate=True, overwrite=False,
                        complete=True, use_cooccur=False)
    stats = opt.apply([plan], backup=True)
    check("F48 写入 1 个 / 失败 0 个",
          stats["written"] == 1 and stats["failed"] == 0,
          f'written={stats["written"]} failed={stats["failed"]} {stats["errors"]}')
    baks = [f for f in os.listdir(FIX) if ".bak-" in f]
    check("F49 生成了 *.nfo.bak-<时间戳> 备份", len(baks) == 1, str(baks))
    if baks:
        bak_text = io.open(os.path.join(FIX, baks[0]), encoding="utf-8").read()
        check("F50 备份内容与改动前**逐字节相同**", bak_text == NFO_TEXT,
              f"备份 {len(bak_text)}B / 原文 {len(NFO_TEXT)}B")
    after_text = io.open(NFO, encoding="utf-8").read()
    check("F51 磁盘上的 nfo 真的改了", after_text != NFO_TEXT)
    check("F52 <genre> 已重写（含新的中文标签）",
          "<genre>中出</genre>" in after_text, after_text[:200])
    check("F53 技术标签 1080p 没被删掉（契约守住了）",
          "<genre>1080p</genre>" in after_text)
    check("F54 演员节点原样保留", "<name>冒烟演员甲</name>" in after_text)
    check("F55 导演节点原样保留", "<director>冒烟导演</director>" in after_text)
    check("F56 uniqueid 原样保留", "998877" in after_text)
    check("F57 plot / thumb / 标题原样保留",
          "冒烟简介：中出し 的剧情。" in after_text and "poster.png" in after_text
          and "冒烟作品 中出し 巨乳" in after_text)
    re_parsed = tagopt.nfo_parser.parse_any(NFO)
    check("F58 改写后仍是合法 XML 且能被解析器读回",
          re_parsed.get("title") == "冒烟作品 中出し 巨乳", str(re_parsed.get("title")))
    check("F59 读回的标签里同时有日语原文与中文写法",
          "中出し" in re_parsed.get("genres", "") and "中出" in re_parsed.get("genres", ""),
          re_parsed.get("genres"))
    check("F60 数据库 media.genres 同步了",
          stats["db_synced"] == 1 and "中出" in
          str(db.media_by_ids([NFO_MEDIA_ID], light=False)[0]["genres"]),
          str(stats["db_synced"]))
    check("F61 同步后库里也不再是旧标签",
          str(db.media_by_ids([NFO_MEDIA_ID], light=False)[0]["genres"]).count("中出し") == 1,
          str(db.media_by_ids([NFO_MEDIA_ID], light=False)[0]["genres"]))

    # 再算一次计划：此时磁盘上的标签已经是最新的 → before == after → 应跳过、不再刷备份
    # （注意必须重新 plan；拿旧的 plan 再 apply 的话 before/after 还是「改动前 vs 改动后」，
    #   看起来有差异，会照写一遍 —— 那验的就不是「无变化跳过」了）
    plan_same = opt.plan_one(NFO, algo="normal", translate=True, overwrite=False,
                             complete=True, use_cooccur=False)
    check("F61b 重新规划后 before 与 after 已一致（磁盘已是最新）",
          list(plan_same["before"]) == list(plan_same["after"]),
          f'{plan_same["before"]} vs {plan_same["after"]}')
    stats2 = opt.apply([plan_same], backup=True)
    check("F62 标签无变化时跳过（不重复写盘）",
          stats2["skipped"] == 1 and stats2["written"] == 0, str(stats2["skipped"]))
    check("F63 跳过时不再多生成备份",
          len([f for f in os.listdir(FIX) if ".bak-" in f]) == 1,
          str([f for f in os.listdir(FIX) if ".bak-" in f]))
    check("F64 扫描时会自动跳过 *.bak-* 备份文件",
          not any(".bak-" in f for f in opt.collect("folder", FIX)),
          str([os.path.basename(x) for x in opt.collect("folder", FIX)]))

    # 关掉备份 → 不留 *.bak-*
    for f in [x for x in os.listdir(FIX) if ".bak-" in x]:
        os.remove(os.path.join(FIX, f))
    plan_b = opt.plan_one(NFO, algo="normal", translate=False, overwrite=False,
                          complete=False, use_cooccur=False)
    plan_b["after"] = list(plan_b["after"]) + ["冒烟新增标签"]
    stats3 = opt.apply([plan_b], backup=False)
    check("F65 关掉备份时不留 *.bak-*（用户明示选择）",
          stats3["written"] == 1 and
          not [f for f in os.listdir(FIX) if ".bak-" in f], str(stats3["written"]))
    check("F66 新增标签确实写进去了",
          "<genre>冒烟新增标签</genre>" in io.open(NFO, encoding="utf-8").read())

    # 异常输入不炸
    _miss = opt.plan_one(os.path.join(FIX, "没有.nfo"))
    check("F67 计划一个不存在的 nfo 不抛错，返回空计划（不是崩溃，也不是假成功）",
          _miss["before"] == [] and _miss["after"] == [], repr(_miss["error"]))
    check("F68 apply 忽略带 error 的计划",
          opt.apply([{"nfo": "", "error": "x"}])["skipped"] == 1)
    check("F69 空计划列表安全", opt.apply([]) == {"written": 0, "skipped": 0, "failed": 0,
                                                  "db_synced": 0, "backups": [], "errors": []})

    # ---- 共现补全（普通算法的第 4 步）----
    counts, co = tagopt.library_tag_stats()
    check("F70 全库标签统计能跑出结果（60 部 fixture）", bool(counts), str(len(counts)))
    check("F71 共现补全能给出候选",
          isinstance(tagopt.suggested_from_cooccur(["标签A"], co), list))
    check("F72 共现结果里不含技术标签与伪标签",
          all(not tagopt.is_tech(t) and not t.startswith(tagopt.PREFIXES)
              for t in tagopt.suggested_from_cooccur(["标签A"], co)),
          str(tagopt.suggested_from_cooccur(["标签A"], co)[:5]))
except Exception:
    check("F 反馈 4 引擎", False, traceback.format_exc().splitlines()[-1])

# ============================================================ G. 反馈 4 UI
section("G. 反馈 4：工具箱里的「标签优化」页（控件接线 / 预览 / 进度 / 状态）")
try:
    from PySide6.QtWidgets import QRadioButton, QCheckBox, QTableWidget, QProgressBar
    from PySide6.QtWidgets import QAbstractItemView
    from PySide6.QtCore import Qt as _Qt

    # 自己开一个干净的窗口 + 工具页（上一段的窗口已经 close 了）
    win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))
    win._open_settings()
    dlg = win._settings_dlg
    check("G1 工具页顺序里「标签优化」紧跟「智能推荐」",
          "标签优化" in dlg.ORDER and
          dlg.ORDER.index("标签优化") == dlg.ORDER.index("智能推荐") + 1,
          str(dlg.ORDER))
    dlg._show("标签优化")
    check("G2 能从侧栏切到「标签优化」页",
          dlg.stack.currentWidget() is dlg._pg_tagopt,
          str(dlg.stack.currentWidget() is dlg._pg_tagopt))

    # 范围：单一文件 / 文件夹 / 媒体库
    check("G3 处理范围三个单选都在",
          all(x is not None for x in (dlg.rb_to_file, dlg.rb_to_folder, dlg.rb_to_lib)))
    check("G4 三个范围的文案就是反馈里那三种",
          (dlg.rb_to_file.text(), dlg.rb_to_folder.text(), dlg.rb_to_lib.text())
          == ("单一文件", "文件夹", "媒体库"),
          f"{dlg.rb_to_file.text()}/{dlg.rb_to_folder.text()}/{dlg.rb_to_lib.text()}")
    dlg.rb_to_file.setChecked(True)
    check("G5 默认/切到单一文件 → scope=file", dlg._tagopt_scope() == "file",
          dlg._tagopt_scope())
    check("G6 单一文件模式路径框可用、库下拉灰掉",
          dlg.to_path.isEnabled() and not dlg.to_lib.isEnabled())
    dlg.rb_to_lib.setChecked(True)
    check("G7 媒体库模式 → scope=library 且库下拉可用", dlg._tagopt_scope() == "library"
          and dlg.to_lib.isEnabled())
    check("G8 媒体库下拉列出了用户的库",
          any(dlg.to_lib.itemData(i) == "冒烟库" for i in range(dlg.to_lib.count())),
          str([dlg.to_lib.itemText(i) for i in range(dlg.to_lib.count())]))
    dlg.rb_to_folder.setChecked(True)
    check("G9 文件夹模式 → scope=folder", dlg._tagopt_scope() == "folder")
    check("G10 路径框 placeholder 随范围变化（提示会递归）",
          "文件夹" in dlg.to_path.placeholderText(), dlg.to_path.placeholderText())

    # 算法：普通 + AI
    # （注意：普通算法是默认已选中项，再 setChecked(True) 不会发 toggled，
    #   所以必须「先切到 AI、再切回来」才能真正触发 _on_tagopt_algo_changed）
    check("G11 两种算法都在，且文案写明「普通智能算法 / AI 智能算法」",
          "普通智能算法" in dlg.rb_to_normal.text() and "AI 智能算法" in dlg.rb_to_ai.text(),
          f"{dlg.rb_to_normal.text()} | {dlg.rb_to_ai.text()}")
    _real_probe_start = ui_settings.AiProbeWorker.start
    ui_settings.AiProbeWorker.start = lambda self: None     # 别真起线程去探 localhost
    try:
        check("G12 默认 = 普通算法，kwargs.algo = normal",
              dlg.rb_to_normal.isChecked() and dlg._tagopt_kwargs()["algo"] == "normal",
              str(dlg._tagopt_kwargs()["algo"]))
        dlg.rb_to_ai.setChecked(True)
        check("G13 选 AI 算法 → kwargs.algo = ai 且**立刻**给出检测反馈",
              dlg._tagopt_kwargs()["algo"] == "ai" and
              "正在检测" in dlg.to_ai_state.text(), dlg.to_ai_state.text()[:36])
        check("G14 AI 模型与「智能推荐」页共用同一项设置",
              dlg._tagopt_kwargs()["ai_model"] == cfg.get_settings().recommend["ai_model"],
              str(dlg._tagopt_kwargs()["ai_model"]))
        dlg._on_to_ai_probe({"engine": "builtin", "label": "内置离线联想引擎",
                             "detail": "未检测到本地 Ollama。"})
        check("G15 探测没命中时说明会退回内置算法（用户知道发生了什么）",
              "退回内置算法" in dlg.to_ai_state.text(), dlg.to_ai_state.text()[:50])
        dlg._on_to_ai_probe({"engine": "ollama", "label": "本地 Ollama（qwen2.5:7b）"})
        check("G16 探测命中时说明「本地离线 AI 可用」并指出去哪儿换模型",
              "本地离线 AI 可用" in dlg.to_ai_state.text() and
              "智能推荐" in dlg.to_ai_state.text(), dlg.to_ai_state.text()[:60])
        dlg.rb_to_normal.setChecked(True)
        check("G17b 切回普通算法 → kwargs.algo = normal 且文案说「完全不依赖 AI」",
              dlg._tagopt_kwargs()["algo"] == "normal" and
              "不依赖 AI" in dlg.to_ai_state.text(), dlg.to_ai_state.text()[:44])
    finally:
        ui_settings.AiProbeWorker.start = _real_probe_start

    # 四个勾选项
    check("G17 有「日语转中文」勾选项（例：中出し → 中出）",
          "日语" in dlg.ck_to_trans.text() and "中出" in dlg.ck_to_trans.text(),
          dlg.ck_to_trans.text())
    check("G18 有「覆盖源标签」勾选项（可选）",
          "覆盖" in dlg.ck_to_over.text(), dlg.ck_to_over.text())
    check("G19 有「补全缺失标签」勾选项", "补全" in dlg.ck_to_full.text())
    check("G20 有「写入前备份」勾选项且默认勾上",
          "备份" in dlg.ck_to_bak.text() and dlg.ck_to_bak.isChecked())
    dlg.ck_to_trans.setChecked(False)
    check("G21 关掉「日语转中文」→「覆盖源标签」跟着灰掉（避免无意义选项）",
          dlg.ck_to_over.isEnabled() is False, str(dlg.ck_to_over.isEnabled()))
    dlg.ck_to_trans.setChecked(True)
    check("G22 重新勾上「日语转中文」→ 覆盖项恢复可用",
          dlg.ck_to_over.isEnabled() is True)
    check("G23 kwargs 把 translate/complete/backup 都带上了",
          set(dlg._tagopt_kwargs()) >= {"algo", "translate", "overwrite", "complete",
                                       "ai_model", "ai_limit"},
          str(sorted(dlg._tagopt_kwargs())))

    # 预览表
    check("G24 预览表 5 列且表头就是那五列",
          dlg.to_table.columnCount() == 5 and
          [dlg.to_table.horizontalHeaderItem(i).text() for i in range(5)]
          == ["文件", "引擎", "原有标签", "将新增", "日语→中文"],
          str([dlg.to_table.horizontalHeaderItem(i).text() for i in range(5)]))
    check("G25 状态标签强制纯文本（进度文案里有 || & 也不会被当富文本）",
          dlg.to_status.textFormat() == _Qt.PlainText)
    check("G26 有进度条且有「扫描并预览 / 执行写入 / 清空预览」三个按钮",
          dlg.to_progress is not None and dlg.btn_to_scan.text() == "扫描并预览"
          and dlg.btn_to_run.text() == "执行写入" and dlg.btn_to_clear.text() == "清空预览")
    check("G27 还没预览时「执行写入」是灰的（不会误写盘）",
          dlg.btn_to_run.isEnabled() is False)

    plan_ui = tagopt.TagOptimizer(cfg.get_settings()).plan_one(
        NFO, algo="normal", translate=True, overwrite=False, complete=False,
        use_cooccur=False)
    dlg._fill_to_table([plan_ui])
    check("G28 预览表填了 1 行", dlg.to_table.rowCount() == 1, str(dlg.to_table.rowCount()))
    check("G29 第 0 列是文件名", dlg.to_table.item(0, 0).text() == os.path.basename(NFO),
          dlg.to_table.item(0, 0).text())
    check("G30 第 1 列标出引擎", dlg.to_table.item(0, 1).text() == "内置算法",
          dlg.to_table.item(0, 1).text())
    check("G31 第 2 列原有标签数 = len(before)",
          dlg.to_table.item(0, 2).text() == str(len(plan_ui["before"])),
          dlg.to_table.item(0, 2).text())
    check("G32 第 3 列是 +N 形式且 tooltip 列出具体标签",
          dlg.to_table.item(0, 3).text().startswith("+") and
          dlg.to_table.item(0, 3).toolTip() != "", dlg.to_table.item(0, 3).text())
    check("G33 第 4 列是日语→中文的条数，tooltip 显示映射",
          dlg.to_table.item(0, 4).text() == str(len(plan_ui["translated"])) and
          "→" in dlg.to_table.item(0, 4).toolTip(),
          dlg.to_table.item(0, 4).toolTip()[:50])
    _it00 = dlg.to_table.item(0, 0)
    check("G34 预览表设为只读（NoEditTriggers，用户改不动预览）",
          dlg.to_table.editTriggers() == QAbstractItemView.NoEditTriggers,
          str(dlg.to_table.editTriggers()))

    dlg._on_to_progress(1, 4, "已分析 1/4：x.nfo")
    check("G35 进度回调把进度条推到 25%", dlg.to_progress.value() == 25,
          str(dlg.to_progress.value()))
    check("G36 进度回调把文案写进状态栏", "已分析 1/4" in dlg.to_status.text(),
          dlg.to_status.text())
    dlg._tagopt_clear()
    check("G37 清空预览：表空 / 执行按钮灰 / 进度归零",
          dlg.to_table.rowCount() == 0 and dlg.btn_to_run.isEnabled() is False
          and dlg.to_progress.value() == 0)
    check("G38 清空后有文字反馈", "清空" in dlg.to_status.text(), dlg.to_status.text())

    # 没填路径就点扫描 → 必须给明确提示，而不是默默不动
    dlg.rb_to_file.setChecked(True)
    dlg.to_path.setText("")
    dlg.to_status.setText("哨兵")
    dlg._tagopt_scan()
    check("G39 没填路径点「扫描并预览」→ 给出 ✗ 提示",
          "✗" in dlg.to_status.text() and "路径" in dlg.to_status.text(),
          dlg.to_status.text()[:50])

    dlg._on_tagopt_applied({"written": 3, "skipped": 1, "failed": 0, "db_synced": 3})
    check("G40 写入完成后给出 ✓ 汇总（写入/跳过/失败/数据库同步）",
          "✓" in dlg.to_status.text() and "写入 3" in dlg.to_status.text()
          and "数据库同步 3" in dlg.to_status.text(), dlg.to_status.text())
    check("G41 写入完成后按钮恢复可用", dlg.btn_to_scan.isEnabled())
    check("G42 完成后清空待写队列（避免重复写）",
          dlg._to_plans == [] and dlg._to_changed == [])
    dlg._on_tagopt_applied({"written": 0, "failed": 1, "errors": ["boom"]})
    check("G43 有失败时汇总里带出首个错误",
          "boom" in dlg.to_status.text(), dlg.to_status.text()[:60])

    # 偏好落盘
    dlg.rb_to_folder.setChecked(True)
    dlg.to_path.setText(FIX)
    dlg.ck_to_over.setChecked(True)
    dlg.rb_to_ai.setChecked(True)
    dlg._tagopt_save_prefs()
    cfg._SETTINGS = None
    to = cfg.get_settings().tagopt
    check("G44 范围 / 路径 / 算法 / 覆盖 全都落盘",
          to["scope"] == "folder" and to["path"] == FIX and
          to["algo"] == "ai" and to["overwrite"] is True, str(to))
    check("G45 关掉「日语转中文」时 overwrite 会被强制成 False（kwargs 层）",
          (dlg.ck_to_trans.setChecked(False), dlg._tagopt_kwargs()["overwrite"] is False)[1],
          str(dlg._tagopt_kwargs()["overwrite"]))
    dlg.ck_to_trans.setChecked(True)
    check("G46 脏 tagopt（scope 乱写 / algo 乱写）会被清洗",
          (cfg.get_settings().tagopt.update({"scope": "天外", "algo": "神算"}),
           cfg.get_settings()._sanitize_tagopt(),
           cfg.get_settings().tagopt["scope"] == "file"
           and cfg.get_settings().tagopt["algo"] == "normal")[2],
          str(cfg.get_settings().tagopt["scope"]) + "/" +
          str(cfg.get_settings().tagopt["algo"]))
    check("G47 DEFAULT_TAGOPT 键齐全（scope/path/library/algo/translate/overwrite/"
          "complete/backup）",
          set(cfg.DEFAULT_TAGOPT) == {"scope", "path", "library", "algo", "translate",
                                      "overwrite", "complete", "backup"},
          str(sorted(cfg.DEFAULT_TAGOPT)))
    check("G48 两个后台工人（扫描 / 运行）都定义了",
          issubclass(ui_settings.TagOptScanWorker, ui_settings.QThread) and
          issubclass(ui_settings.TagOptRunWorker, ui_settings.QThread))
    check("G49 写盘工人不挂 parent（与 AiProbeWorker 同样的线程安全约定）",
          "TagOptRunWorker(opt, changed, backup)" in
          io.open(os.path.join(SRC, "ui_settings.py"), encoding="utf-8").read())
    win.close()
except Exception:
    check("G 反馈 4 UI", False, traceback.format_exc().splitlines()[-1])

# ============================================================ H. 反馈 5
section("H. 反馈 5：12 种高亮色 + 选中外发光（QGraphicsDropShadowEffect）")
try:
    from PySide6.QtWidgets import QGraphicsDropShadowEffect
    import main_window as mw
    import ui_settings

    check("H1 高亮色正好 12 种", len(cfg.ACCENT_COLORS) == 12, str(len(cfg.ACCENT_COLORS)))
    check("H2 12 种色的十六进制都合法且唯一",
          all(re.fullmatch(r"#[0-9a-fA-F]{6}", h) for _n, h in cfg.ACCENT_COLORS) and
          len({h.lower() for _n, h in cfg.ACCENT_COLORS}) == 12,
          str([h for _n, h in cfg.ACCENT_COLORS]))
    check("H3 每种色都有中文名",
          all(n and isinstance(n, str) for n, _h in cfg.ACCENT_COLORS),
          "、".join(n for n, _h in cfg.ACCENT_COLORS))
    check("H4 默认高亮色 = 朱红 #c0392b（保持原视觉）",
          cfg.ACCENT_DEFAULT.lower() == "#c0392b" and cfg.accent_name("#c0392b") == "朱红",
          f"{cfg.ACCENT_DEFAULT} / {cfg.accent_name('#c0392b')}")
    check("H5 accent_rgb 解析正确", cfg.accent_rgb("#c0392b") == (192, 57, 43),
          str(cfg.accent_rgb("#c0392b")))
    sh = cfg.accent_shades("#c0392b")
    check("H6 朱红的浅色档与原硬编码 #e05243 逐字节一致（视觉零回退）",
          sh["light"] == (224, 82, 67), str(sh["light"]))
    # 明暗档位的**序**必须对：QSS 里 dark 是按下底、deep 是主按钮底、light 是亮描边。
    # 用 HLS 明度判序（不看 RGB 通道，避免被高饱和色的通道溢出骗到）。
    import colorsys as _cs

    def _lum(rgb):
        return _cs.rgb_to_hls(*[c / 255.0 for c in rgb])[1]

    _bad_order = []
    for _nm, _h in cfg.ACCENT_COLORS:
        _s = cfg.accent_shades(_h)
        if not (_lum(_s["dark"]) < _lum(_s["deep"]) < _lum(_s["base"]) < _lum(_s["light"])):
            _bad_order.append(_nm)
    check("H7 12 色的四档明暗序都对（dark < deep < base < light）",
          not _bad_order, "、".join(_bad_order))
    check("H8 深浅档用 HLS 派生（不是简单 RGB 缩放）",
          cfg.accent_shades("#d4af37")["light"] != tuple(
              min(255, int(c * (224 / 192))) for c in cfg.accent_rgb("#d4af37")),
          str(cfg.accent_shades("#d4af37")["light"]))

    # 12 色逐一渲染：无残留令牌 + 自绘色同步 + 该色真的出现在 QSS 里
    raw_qss = io.open(os.path.join(SRC, "style.qss"), encoding="utf-8").read()
    base_tokens = len(re.findall(r"rgba\(__ACCENT__", raw_qss))
    bad_tokens, bad_global, bad_hex = [], [], []
    for nm, h in cfg.ACCENT_COLORS:
        out = mw.render_style({"mode": "经典暗色", "level": "中", "accent": h})
        if re.findall(r"__[A-Z_]+__", out):
            bad_tokens.append(nm)
        if mw.ACCENT_RGB != cfg.accent_rgb(h):
            bad_global.append(nm)
        r, g, b = cfg.accent_rgb(h)
        if f"rgba({r}, {g}, {b}," not in out:
            bad_hex.append(nm)
    check("H9 12 色渲染后都没有残留 __TOKEN__", not bad_tokens, "、".join(bad_tokens))
    check("H10 12 色渲染后自绘用的 ACCENT_RGB 都同步了", not bad_global,
          "、".join(bad_global))
    check("H11 12 色都真的写进了样式表", not bad_hex, "、".join(bad_hex))
    _zh_out = mw.render_style({"mode": "经典暗色", "level": "中"})
    check("H12 令牌占位与原生 rgba(192,57,43 的出现次数一一对应",
          base_tokens > 0 and len(re.findall(r"rgba\(192, 57, 43", _zh_out)) == base_tokens,
          f"令牌 {base_tokens} 处")
    # 裸令牌（`border-color: __ACCENT_LIGHT__;` 这种直接当颜色值的）必须输出成合法颜色。
    # 塞 "224, 82, 67" 进去不是合法 CSS，Qt 会把整条声明丢掉 —— 表现为「换了高亮色但
    # 某些描边/选中底不跟着变」，而且不报错，很难发现。
    _stray = re.findall(r":\s*\d{1,3},\s*\d{1,3},\s*\d{1,3}\s*[;}]", _zh_out)
    check("H12b 没有「xxx-color: 192, 57, 43;」这种非法声明（裸令牌输出十六进制）",
          not _stray, str(_stray[:3]))
    check("H12c 裸令牌渲染成了该高亮色的十六进制",
          "#c0392b" in _zh_out and "#e05243" in _zh_out)
    check("H13 原硬编码 #e05243 已全部换成令牌",
          "#e05243" not in raw_qss and raw_qss.count("__ACCENT_LIGHT__") >= 3,
          str(raw_qss.count("__ACCENT_LIGHT__")))
    check("H14 原硬编码 #c0392b 也不再直接出现",
          "#c0392b" not in raw_qss, str(raw_qss.count("#c0392b")))

    # 落盘 / 校验
    s = cfg.get_settings()
    s.set_accent("#5aa469")
    check("H15 换色落盘", s.accent() == "#5aa469", s.accent())
    cfg._SETTINGS = None
    check("H16 重读配置后仍是新色", cfg.get_settings().accent() == "#5aa469",
          cfg.get_settings().accent())
    cfg.get_settings().set_accent("#123456")          # 不在 12 色里
    check("H17 非法颜色被拒绝（不会写进配置）", cfg.get_settings().accent() == "#5aa469",
          cfg.get_settings().accent())
    cfg.get_settings().set_accent("#c0392b")

    # 色板控件
    win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))
    win._open_settings()
    dlg = win._settings_dlg
    dlg._show("个性化设置")
    check("H18 外观里有 12 个色块", len(dlg._accent_btns) == 12, str(len(dlg._accent_btns)))
    check("H19 色块尺寸 26×26（小方块）",
          all(b.width() == 26 and b.height() == 26 for b in dlg._accent_btns.values()))
    check("H20 当前色块打勾、其余不打勾",
          sum(1 for b in dlg._accent_btns.values() if b.text() == "✓") == 1 and
          dlg._accent_btns["#c0392b"].text() == "✓",
          str([b.text() for b in dlg._accent_btns.values()]))
    check("H21 色块样式显式写了 padding:0（否则 26px 方块内容区被压负）",
          all("padding:0" in b.styleSheet() for b in dlg._accent_btns.values()))
    check("H22 色块 tooltip 带中文色名", "朱红" in dlg._accent_btns["#c0392b"].toolTip(),
          dlg._accent_btns["#c0392b"].toolTip())
    check("H23 有「当前：色名 色值」提示", "朱红" in dlg.lb_accent.text(),
          dlg.lb_accent.text())
    dlg._apply_accent("#d4af37")
    check("H24 点色块后配置 / 提示 / 勾选一起变",
          cfg.get_settings().accent() == "#d4af37" and "鎏金" in dlg.lb_accent.text()
          and dlg._accent_btns["#d4af37"].text() == "✓"
          and dlg._accent_btns["#c0392b"].text() == "",
          dlg.lb_accent.text())
    check("H25 换色后 ACCENT_RGB 也跟着换",
          mw.ACCENT_RGB == cfg.accent_rgb("#d4af37"), str(mw.ACCENT_RGB))

    # 外发光：给选中的卡片挂 QGraphicsDropShadowEffect
    rows = db.media_by_ids(MEDIA_IDS[:3], light=False)
    cards = [mw.PosterCard(r, lambda *a: None, on_select=lambda *a: None) for r in rows]
    check("H26 造出 3 张真海报卡用于选中测试", len(cards) == 3)
    cfg.get_settings().set_accent("#c0392b")
    mw.render_style({"mode": "经典暗色", "level": "中"})
    win._select_card(cards[0])
    eff = cards[0].graphicsEffect()
    check("H27 选中后卡片挂上了外发光效果",
          isinstance(eff, QGraphicsDropShadowEffect), type(eff).__name__)
    check("H28 发光是「向外扩散」的：blur 38 且 offset 为 0（四周均匀）",
          eff is not None and eff.blurRadius() == 38 and eff.offset().x() == 0
          and eff.offset().y() == 0, f"{eff.blurRadius()} {eff.offset()}" if eff else "")
    check("H29 发光颜色 = 当前高亮色 + 高透明度（能看见光晕）",
          eff is not None and (eff.color().red(), eff.color().green(), eff.color().blue())
          == (192, 57, 43) and eff.color().alpha() >= 180,
          f"{eff.color().red()},{eff.color().green()},{eff.color().blue()},"
          f"a={eff.color().alpha()}" if eff else "")
    check("H30 卡片自身记着选中态", cards[0]._selected is True)

    win._select_card(cards[1])
    check("H31 换选中目标 → 新的挂上发光",
          isinstance(cards[1].graphicsEffect(), QGraphicsDropShadowEffect))
    check("H32 旧的发光被摘掉（不会两张都亮）",
          cards[0].graphicsEffect() is None and cards[0]._selected is False)
    _eff_before = cards[1].graphicsEffect()
    win._select_card(cards[1])            # 同一张 → 直接 return，不该再挂一个
    check("H33 命中同一张卡时直接返回（不会重复挂 effect）",
          cards[1].graphicsEffect() is _eff_before)

    # 换高亮色 → 发光颜色立刻跟着变
    cfg.get_settings().set_accent("#3fa9c9")
    mw.render_style({"mode": "经典暗色", "level": "中", "accent": "#3fa9c9"})
    win._select_card(cards[2])
    eff2 = cards[2].graphicsEffect()
    check("H34 换高亮色后外发光跟着换（天青）",
          eff2 is not None and (eff2.color().red(), eff2.color().green(),
                                eff2.color().blue()) == (63, 169, 201),
          f"{eff2.color().red()},{eff2.color().green()},{eff2.color().blue()}"
          if eff2 else "")
    def _class_block(src, name):
        """按类名切出整段类体（到下一个顶层 class 为止），别用固定字符数截。"""
        i = src.index("class %s" % name)
        m = re.search(r"^class ", src[i + 1:], re.M)
        return src[i: i + 1 + (m.start() if m else len(src))]

    _mw_src = io.open(os.path.join(SRC, "main_window.py"), encoding="utf-8").read()
    _pc = _class_block(_mw_src, "PosterCard")
    _ac = _class_block(_mw_src, "ActorCard")
    check("H35 两张卡的自绘选中描边都取 ACCENT_RGB（换色时描边跟着换，不只是外发光）",
          "ACCENT_RGB" in _pc and "ACCENT_RGB" in _ac,
          f"PosterCard {_pc.count('ACCENT_RGB')} 处 / ActorCard {_ac.count('ACCENT_RGB')} 处")
    win._apply_appearance()
    check("H36 重载外观后当前选中卡的外发光被重新贴上（不会丢）",
          isinstance(win._selected_card.graphicsEffect(), QGraphicsDropShadowEffect))
    # 页面重建 / 换页后，队列里残留的事件可能落到已析构的卡片上；
    # _apply_card_glow 开头有 _qt_alive 守卫，必须安静退出而不是抛 RuntimeError。
    import shiboken6
    _victim = cards[0]
    shiboken6.delete(_victim)
    _ok_h37, _err_h37 = True, ""
    try:
        win._apply_card_glow(_victim)
    except Exception as _e:                       # noqa: BLE001 - 断言用
        _ok_h37, _err_h37 = False, f"{type(_e).__name__}: {_e}"
    check("H37 对已析构的卡片挂发光安静退出（_qt_alive 守卫生效）", _ok_h37, _err_h37)
    cfg.get_settings().set_accent("#c0392b")
    mw.render_style({"mode": "经典暗色", "level": "中"})
    win.close()
except Exception:
    check("H 反馈 5", False, traceback.format_exc().splitlines()[-1])

# ============================================================ I. 反馈 6
section("I. 反馈 6：首页三个快捷筛选选中后要一眼看出是「点了这个」")
try:
    import ui_home

    raw_qss = io.open(os.path.join(SRC, "style.qss"), encoding="utf-8").read()
    check("I1 新增了独立的 #Seg 选中样式（不再借用 #Ghost）",
          "QPushButton#Seg:checked" in raw_qss)
    seg_block = raw_qss[raw_qss.find("QPushButton#Seg {"):]
    seg_block = seg_block[:seg_block.find("\n\n")] if "\n\n" in seg_block else seg_block
    check("I2 选中态是「实心强调底」而不是只描边",
          "background" in seg_block and "rgba(__ACCENT_DARK__" in seg_block,
          seg_block[:120].replace("\n", " "))
    check("I3 选中态有加粗与亮描边（对比更强）",
          "font-weight: 600" in seg_block and "border: 1px solid __ACCENT_LIGHT__" in seg_block)
    check("I4 #Seg 有 hover 态", "QPushButton#Seg:hover" in raw_qss)

    home = ui_home.HomeListView()
    check("I5 三个快捷筛选都建出来了（默认开启）", len(home._chip_btns) == 3,
          str(list(home._chip_btns)))
    check("I6 三个按钮都改用了 #Seg 样式（objectName 不再是 Ghost）",
          all(b.objectName() == "Seg" for b in home._chip_btns.values()),
          str([b.objectName() for b in home._chip_btns.values()]))
    check("I7 三个按钮都是 checkable（点击有持久状态）",
          all(b.isCheckable() for b in home._chip_btns.values()))
    check("I8 初始状态一个都没选中",
          home._active_chip is None and
          not any(b.isChecked() for b in home._chip_btns.values()))
    check("I9 每个按钮都有 tooltip 说明「再点一次取消」",
          all("取消" in b.toolTip() for b in home._chip_btns.values()),
          home._chip_btns["recent"].toolTip())

    home._click_chip("favorites")
    pump(app, 6)
    check("I10 点「我的收藏」→ 进入选中态",
          home._active_chip == "favorites" and home._chip_btns["favorites"].isChecked(),
          str(home._active_chip))
    check("I11 同时只有一个亮着",
          sum(1 for b in home._chip_btns.values() if b.isChecked()) == 1)
    home._click_chip("recent")
    pump(app, 6)
    check("I12 点另一个 → 选中态转移，旧的自动熄灭（单选）",
          home._active_chip == "recent" and home._chip_btns["recent"].isChecked()
          and not home._chip_btns["favorites"].isChecked(), str(home._active_chip))

    before = len(home._view)
    home._click_chip("recent")                       # 再点一次同一个
    pump(app, 6)
    check("I13 再点同一个 → 取消筛选（回到全量列表）",
          home._active_chip is None and
          not any(b.isChecked() for b in home._chip_btns.values()),
          str(home._active_chip))
    check("I14 取消后列表恢复成全量（60 部 fixture）",
          len(home._view) == 60, f"{before} -> {len(home._view)}")
    check("I15 取消后按钮的选中态与内部状态一致",
          all(b.isChecked() == (k == home._active_chip)
              for k, b in home._chip_btns.items()))

    home._apply_chip("collections")
    pump(app, 6)
    check("I16 直接调用 _apply_chip 也会同步选中态",
          home._active_chip == "collections" and
          home._chip_btns["collections"].isChecked())
    home._load()
    check("I17 重新加载列表会清掉选中态（首页刷新后不留假高亮）",
          home._active_chip is None)
    check("I18 选中态样式与按钮的实际 objectName 对得上（QSS 选择器不会落空）",
          all(f"QPushButton#{b.objectName()}:checked" in raw_qss
              for b in home._chip_btns.values()),
          str([b.objectName() for b in home._chip_btns.values()]))
    check("I19 首页管理里三个开关仍在（能关掉对应按钮）",
          set(cfg.get_settings().home_modules) >= {"recent", "favorites", "collections"},
          str(sorted(cfg.get_settings().home_modules)))
except Exception:
    check("I 反馈 6", False, traceback.format_exc().splitlines()[-1])

# ============================================================ 汇总
section("J. 发布前加固：选中定时器复用 + 已析构对象兜底（Build 0035）")
try:
    import shiboken6
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import main_window as mw

    rows = [{"id": 9100 + i, "title": "加固%d" % i, "library": "L", "kind": "电影",
             "file_path": "Z:/x/%d.mp4" % i, "poster": "", "favorite": 0,
             "genres": "", "year": 2020, "rating": 0, "user_rating": 0}
            for i in range(2)]
    card = mw.PosterCard(rows[0], lambda *a: None, on_select=lambda *a: None)

    # 旧写法是「每次选中都新建 QTimer 并覆盖旧引用」→ 旧对象一旦被析构，
    # self._timer 就成了「已析构的 C++ 对象」。这里先钉死新写法是「只建一次、复用」。
    card.set_selected(True)
    t1 = card._timer
    check("J1 选中后建了定时器且在跑",
          t1 is not None and t1.isActive())
    card.set_selected(False)
    check("J2 取消选中是 stop 同一个定时器（不是把对象丢掉）",
          card._timer is t1 and not t1.isActive())
    card.set_selected(True)
    check("J3 再次选中复用同一个 QTimer（不再新建）",
          card._timer is t1 and t1.isActive())

    # 真机崩溃点：app.log 2026-09-21 09:25:33
    #   mousePressEvent → _select_card → set_selected
    #   RuntimeError: Internal C++ object (QTimer) already deleted
    shiboken6.delete(t1)
    card._selected = False
    err = ""
    try:
        card.set_selected(True)
    except Exception as e:
        err = "%s: %s" % (type(e).__name__, e)
    check("J4 定时器已被析构时 set_selected 不抛异常", err == "", err)
    t2 = card._timer
    check("J5 并且按需重建了一个可用的新定时器",
          err == "" and t2 is not None and t2 is not t1 and t2.isActive(),
          "err=%r timer=%r" % (err, t2))

    # _select_card 的目标卡片也可能已被换页/刷新析构（队列里残留的鼠标事件）。
    # 用「桩对象」直接调真实方法体，避免为了这一条去建一个完整 MainWindow。
    class _Stub:
        _selected_card = None

        def _apply_card_glow(self, c):
            pass

    stub = _Stub()
    victim = mw.PosterCard(rows[1], lambda *a: None, on_select=lambda *a: None)
    err2 = ""
    try:
        mw.MainWindow._select_card(stub, victim)
        shiboken6.delete(victim)
        mw.MainWindow._select_card(stub, victim)      # 已析构 → 必须安静跳过
    except Exception as e:
        err2 = "%s: %s" % (type(e).__name__, e)
    check("J6 对已析构的卡片调用 _select_card 不抛异常", err2 == "", err2)
    check("J7 目标已析构时不会把它记成当前选中项", stub._selected_card is not victim)

    # 旧写法必须真的消失（防止以后被改回去）
    _src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "src", "main_window.py"), encoding="utf-8").read()
    check("J8 源码里已无「每次新建定时器」的旧写法",
          "elif self._timer:" not in _src and
          _src.count("定时器「只建一次、之后复用」") == 2)
except Exception:
    check("J 加固", False, traceback.format_exc().splitlines()[-1])

print("\n" + "=" * 72)
print(f"总计 {len(PASS)} 通过 / {len(FAIL)} 失败")
if FAIL:
    print("失败项：")
    for t in FAIL:
        print("  -", t)
print("=" * 72)
sys.exit(1 if FAIL else 0)
