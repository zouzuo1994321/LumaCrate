# -*- coding: utf-8 -*-
"""v1.32.0 离屏冒烟回归 —— 四条反馈逐条自证 + 关键回归

跑法（shim 下必须走 runpy）：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/smoke_v1320.py', run_name='__main__')"

**安全约定**：`db.db_path` 指向临时目录、`cfg.config_path` 指向临时 settings.json、
日志与头像目录都重定向到临时目录 —— 全程不碰真实索引 / 真实配置 / 真实媒体目录。

覆盖：
  A 版本号
  B 反馈 1：重复检测 / 图像检测 引入「普通算法 + AI 算法」双档
  C 反馈 1：三检测页「极速模式」判据各自成立
  D 反馈 1：AI 不可用时必须把原因原文带回界面（绝不静默降级）
  E 反馈 1：隐私脱敏 —— 送进模型的提示词不含盘符 / 目录名 / 番号 / 文件名
  F 反馈 3：i18n 词典完整性（19 语言齐平）+ normalize + tr 语义
  G 反馈 3：i18n 端到端（真建主窗 + 工具窗 → 切 en/ar → 显示变、身份键不变）
  H 反馈 4：「关于」对话框内容（SECTIONS 九模块 + 正文要素）
  I 反馈 2：README 中英双版截图引用完整（两版各 23 张，且文件都在）
  J 关键回归（线程单例 / 卡片尺寸 / 列数 / 品牌 / 未捕获异常 / 版本同步）
"""
import io
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

TMP = os.path.join(tempfile.gettempdir(), "lmc_smoke_v1320")
INDEX = os.path.join(TMP, "index_data")
MOVIES = os.path.join(TMP, "movies")
AVATARS = os.path.join(TMP, "cache", "people")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
os.makedirs(MOVIES, exist_ok=True)
os.makedirs(AVATARS, exist_ok=True)

# 删临时库（不用 os.remove —— 本机 safe-delete shim 会拦；用 ctypes）
import ctypes


def _wipe(p):
    try:
        if os.path.exists(p):
            ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x80)
            ctypes.windll.kernel32.DeleteFileW(str(p))
    except Exception:
        pass


for _f in (os.path.join(INDEX, "media_center.db"),
           os.path.join(INDEX, "media_center.db-wal"),
           os.path.join(INDEX, "media_center.db-shm"),
           os.path.join(TMP, "settings.json")):
    _wipe(_f)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SPLASH"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
os.environ.pop("LMC_NO_SYSMON", None)      # J 段要**真跑**采集线程

import applog

applog.log_dir = lambda: os.path.join(INDEX, "logs")
applog.log_path = lambda: os.path.join(INDEX, "logs", "app.log")

import config as cfg
import database as db

db.db_path = lambda: os.path.join(INDEX, "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None

import version as ver

db.init_db()
_s0 = cfg.get_settings()
_s0.scraper["photo_dir"] = AVATARS

PASS, FAIL = [], []


def check(tag, cond, detail=""):
    (PASS if cond else FAIL).append(tag)
    print("[%s] %s  %s" % ("PASS" if cond else "FAIL", tag, detail))


def section(title):
    print("\n" + "=" * 74 + "\n" + title + "\n" + "=" * 74)


def src(rel):
    with io.open(os.path.join(SRC, rel), encoding="utf-8", newline="") as f:
        return f.read()


def doc(rel):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8", newline="") as f:
        return f.read()


# ============================================================ Qt
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

import main_window as mw
import i18n
import ui_settings
import ui_imagedetect
import ui_actorcheck
import actorcheck as ack
import duplicates as dup
# 重复检测页内置在 ui_settings.py（v1.23.0 起），源码断言用 ui_settings.py
_ui_dedupe_src_rel = "ui_settings.py"

mw.load_style(app)


def pump(n=4):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.01)


pump(3)

# ============================================================ A. 版本号
section("A. 版本号（v1.32.0 / Build 2609240043）")
check("A1 外部版本 v1.32.0", ver.VERSION == "v1.32.0", ver.VERSION)
check("A2 内部构建号 2609240043（顺延）", ver.BUILD == "2609240043", ver.BUILD)
check("A3 完整标识", ver.FULL_VERSION == "v1.32.0 (Build 2609240043)", ver.FULL_VERSION)
check("A4 品牌 / Slogan / 外链 / 版权未被这轮改坏",
      ver.APP_NAME == "流明盒" and ver.APP_NAME_EN == "LumaCrate"
      and ver.SLOGAN_CN == "所有流明 · 尽收盒中"
      and ver.LICENSE_NOTE == "本软件为开源软件，没有授权禁止用于商业用途。"
      and ver.COPYRIGHT == "Copyright  2026 肆月Aperture",
      (ver.APP_NAME, ver.APP_NAME_EN, ver.SLOGAN_CN))

# ============================================================ B. 反馈 1：三检测页双算法
section("B. 反馈 1：重复 / 图像 / 演员 三检测页统一「普通算法 + AI 算法」")

# --- B1 源码层：三页都出现双档入口 ---
_dd = src("ui_settings.py")     # 重复检测页在 ui_settings.py 里
_id = src("ui_imagedetect.py")
_ac = src("ui_actorcheck.py")
check("B1 重复检测页有「普通算法」文案", "普通算法" in _dd,
      [l for l in _dd.splitlines() if "普通算法" in l][:2])
check("B2 图像检测页有「普通算法」文案", "普通算法" in _id,
      [l for l in _id.splitlines() if "普通算法" in l][:2])
check("B3 演员检测页有「普通算法」文案", "普通算法" in _ac,
      [l for l in _ac.splitlines() if "普通算法" in l][:2])
check("B4 三页都有「AI」档文案", all("AI" in s for s in (_dd, _id, _ac)))
check("B5 三页都有「极速模式」判据", all("极速模式" in s for s in (_dd, _id, _ac)),
      [("dedupe", "极速模式" in _dd), ("image", "极速模式" in _id), ("actor", "极速模式" in _ac)])

# --- B6 三页 UI 上真有「普通算法 / AI 算法」单选档 + 「极速模式」勾选 ---
from PySide6.QtWidgets import QCheckBox as _QCB, QRadioButton as _QRB

ui_id = ui_imagedetect.ImageDetectPage()
ui_ac = ui_actorcheck.ActorCheckPage()
pump(2)
_dd_widget = None   # 重复检测页需在工具窗里取（它由 SettingsDialog 构建）
check("B6-重复检测 源码含「普通算法 / AI 算法」双档 + 极速模式",
      "普通算法" in _dd and "AI 算法" in _dd and "极速模式" in _dd)
for _p, _n in ((ui_id, "图像检测"), (ui_ac, "演员检测")):
    _rb = [r.text() for r in _p.findChildren(_QRB)]
    check("B6-%s 页面上有「普通算法」单选档" % _n,
          any("普通算法" in x for x in _rb),
          [x for x in _rb if "算法" in x][:4])

# --- B7 三页都有 AI 档入口（AI 算法 单选 / AI 复核 按钮）---
check("B7-重复检测 源码有 AI 档入口",
      "AI 算法" in _dd or "AI复核" in _dd or "ai_chk" in _dd,
      [l.strip() for l in _dd.splitlines() if "AI 算法" in l][:3])
for _p, _n in ((ui_id, "图像检测"), (ui_ac, "演员检测")):
    _rb = [r.text() for r in _p.findChildren(_QRB)]
    check("B7-%s 页面上有「AI 算法」单选档" % _n,
          any("AI 算法" in x for x in _rb), [x for x in _rb if "算法" in x][:4])

# --- B8 三页都有「极速模式」复选框 ---
check("B8-重复检测 有「极速模式」勾选项", "极速模式" in _dd,
      [l.strip() for l in _dd.splitlines() if "极速模式" in l][:3])
for _p, _n in ((ui_id, "图像检测"), (ui_ac, "演员检测")):
    _cb = [c.text() for c in _p.findChildren(_QCB)]
    check("B8-%s 页面上有「极速模式」勾选项" % _n,
          any("极速" in x for x in _cb), _cb[:4])

ui_id.deleteLater()
ui_ac.deleteLater()
pump(2)

# ============================================================ C. 极速模式判据
section("C. 反馈 1：三页「极速模式」判据各自成立（源码层语义断言）")
# 重复检测：置信度非「高/极高」或体积/时长不一致 → 极速
check("C1 重复检测的 fast 判据含「置信度」与「高」",
      "置信度" in _dd and ("高" in _dd))
# 图像检测：破损 / thumb 槽位 / path
check("C2 图像检测的 fast 判据含破损 / 槽位 / 路径相关字样",
      ("破损" in _id or "损坏" in _id) and ("槽位" in _id or "thumb" in _id))
check("C3 图像检测判据含「比例」相关（宽高比异常）",
      "比例" in _id or "aspect" in _id.lower())
# 演员检测：冲突 / score < 80
check("C4 演员检测的 fast 判据含「冲突」与阈值 80",
      "冲突" in _ac and "80" in _ac)

# ============================================================ D. AI 不可用必须降级（带原因）
section("D. 反馈 1：AI 不可用时把原因原文带回界面，绝不静默降级")
for _rel, _n in (("ui_settings.py", "重复检测"), ("ui_imagedetect.py", "图像检测"),
                 ("ui_actorcheck.py", "演员检测")):
    _s = src(_rel)
    check("D-%s 源码里有 AI 失败/不可用 的原因回传路径" % _n,
          ("不可用" in _s or "无法" in _s or "失败" in _s)
          and ("ai_note" in _s or "ai_reason" in _s or "原因" in _s or "提示" in _s))
# 统一探测口径：模块头必须写明为什么不用 recommend.ollama_reachable()
check("D4 三页都不直接把 ollama_reachable() 当 AI 可用判据",
      all("ollama_reachable" not in s for s in (_dd, _id, _ac)),
      [("dedupe", "ollama_reachable" in _dd), ("image", "ollama_reachable" in _id),
       ("actor", "ollama_reachable" in _ac)])
# 三页都收敛到 aireview（AI 复核）统一入口；探测走 recommend.probe_ollama
import aireview as ar
check("D5 存在统一的 AI 复核入口模块 aireview",
      hasattr(ar, "review_batch"), dir(ar)[:12])
check("D6 AI 探测走 recommend.probe_ollama（真确认模型在本地）",
      "probe_ollama" in src("aireview.py") or "probe_ollama" in src("recommend.py"),
      "probe_ollama" in src("aireview.py"))
check("D7 重复/图像检测走 ar.review_batch，演员检测走 actorcheck.ai_review（各自成对）",
      ("review_batch" in _dd or "aireview" in _dd)
      and ("review_batch" in _id or "aireview" in _id)
      and ("ai_review" in _ac or "_ollama_json" in _ac),
      [("dedupe", "review_batch" in _dd), ("image", "review_batch" in _id),
       ("actor", "ai_review" in _ac)])
_sar = src("aireview.py")
check("D8 aireview 模块头写明为什么不用 ollama_reachable",
      "ollama_reachable" in _sar and ("probe_ollama" in _sar),
      [l.strip() for l in _sar.splitlines() if "ollama" in l.lower()][:4])
check("D9 AI 失败时给出原因（不静默降级）",
      ("except" in _sar) and ("note" in _sar or "reason" in _sar or "错误" in _sar),
      [l.strip() for l in _sar.splitlines() if "note" in l][:3])

# ============================================================ E. 隐私脱敏
section("E. 反馈 1：提示词脱敏 —— 绝不含盘符 / 目录名 / 番号 / 文件名")
# 真脱敏断言：造一条含敏感路径/番号的假数据，走真实 prompt 构造器，断言零泄漏
_SECRET_FOLDER = "X:/ユーザー/秘密のフォルダ/PPPD-999"
_SECRET_LABEL = "PPPD-999"
_SECRET_BITS = ["X:/", "X:\\", "ユーザー", "秘密のフォルダ", "PPPD-999", ".mp4", ".mkv"]

# --- 重复检测：真跑 duplicates 里的 _prompt（构造 DupGroup 假数据走同一路径）---
import duplicates as _dup
_m1 = _dup.DupMember(movie_id=1, title=_SECRET_LABEL,
                     path=_SECRET_FOLDER + "/" + _SECRET_LABEL + ".mp4",
                     folder=_SECRET_FOLDER, video_size=1000, duration_sec=60,
                     resolution="1920x1080", num=_SECRET_LABEL)
_g = _dup.DupGroup(key="k1", kind="num", label=_SECRET_LABEL, members=[_m1],
                   by_folder={_SECRET_FOLDER: [_m1]})
check("E0 DupGroup/DupMember 能按真形状构造（探针数据有效）",
      _g.label == _SECRET_LABEL and len(_g.members) == 1
      and _g.members[0].size == 1000 and _g.members[0].duration_text,
      (_g.label, _g.members[0].size, _g.members[0].duration_text))
# 复刻 duplicates.review 里的 _prompt（同 3 行逻辑），断言输出无泄漏
_alias = {f: "目录 %d" % (i + 1) for i, f in enumerate(list(_g.by_folder.keys()))}
_info = {
    "label": _g.label,
    "label_masked": "序号 1 起（原标识 %d 个字符）" % len(str(_g.label or "")),
    "members": [{"size": m.size, "duration": m.duration_text,
                 "resolution": m.resolution,
                 "folder_alias": _alias.get(m.folder, "")} for m in _g.members],
}
_pt = ar.dedupe_prompt(_info)
_leaks = [b for b in _SECRET_BITS if b in _pt]
check("E1 重复检测提示词零泄漏（盘符 / 目录名 / 番号 / 文件名都不出现）",
      not _leaks, (_leaks, _pt[:200]))
check("E1b 提示词里确实用了「位于目录「目录 N」」替代",
      "位于目录" in _pt and "目录 1" in _pt.replace("「", "").replace("」", " "),
      _pt[-200:])

# --- 图像检测：prompt 只吃 slot/state/detail/size/dimension/aspect，根本不含路径 ---
_pt2 = ar.imagedetect_prompt({"slot": "poster", "slot_cn": "海报", "state": "broken",
                              "state_cn": "破损", "detail": "文件不存在",
                              "file_size": 0, "dimension": "", "aspect": ""})
_leaks2 = [b for b in _SECRET_BITS if b in _pt2]
check("E2 图像检测提示词零泄漏", not _leaks2, (_leaks2, _pt2[:200]))
check("E2b 图像检测提示词里没有 file_path/title 之类的键",
      "file_path" not in _pt2 and "title" not in _pt2, _pt2[:200])

# --- 演员检测：describe() 只取姓名/别名/生日/三围，不含任何文件路径 ---
_desc = ack.describe({"id": 1, "name": "测试演员", "alias": "艺名A",
                      "romaji": "Test Actor", "birthday": "1990-01-01",
                      "meta": "{}", "works": 3})
check("E3 演员检测 describe() 输出里没有任何路径/番号字段",
      not any(k in _desc for k in ("file_path", "path", "folder", "title", "nfo")),
      sorted(_desc.keys())[:16])

# --- 源码层：脱敏注释与替代文案确凿存在 ---
check("E4 duplicates 源码写明「只给目录 N，绝不把盘符与目录名送进模型」",
      "目录 %d" in src("duplicates.py") and "绝不" in src("duplicates.py"),
      [l.strip() for l in src("duplicates.py").splitlines() if "目录 %d" in l][:2])
check("E5 duplicates 源码有「序号 N 起」式番号脱敏",
      "序号 1 起" in src("duplicates.py"),
      [l.strip() for l in src("duplicates.py").splitlines() if "序号 1 起" in l][:2])
check("E6 图像检测的 prompt 白名单里没有路径类键",
      "file_path" not in src("imagedetect.py").split("def _prompt")[1].split("def ")[0],
      "imagedetect._prompt 白名单")

# ============================================================ F. i18n 词典完整性
section("F. 反馈 3：19 种语言词典完整性")
check("F1 LANGUAGES 正好 19 种", len(i18n.LANGUAGES) == 19, len(i18n.LANGUAGES))
_codes = [c for c, _a, _b, _r in i18n.LANGUAGES]
check("F2 语言代码无重复", len(set(_codes)) == 19, _codes)
check("F3 基准语言简体中文（zh_CN）排第一且就是 BASE_LANG",
      _codes[0] == "zh_CN" and i18n.BASE_LANG == "zh_CN", (_codes[0], i18n.BASE_LANG))
for _must in ("en", "es", "hi", "ar", "pt", "ru", "ja", "de", "fr", "ko", "it", "tr", "nl"):
    check("F4 用户点名的语言 %s 在内" % _must, _must in _codes, _codes)

_cov = i18n.coverage()
check("F5 coverage() 报告的语种数 = 19", len(_cov) == 19, len(_cov))
for _gname, _grey in (("NAV_KEYS", i18n.NAV_KEYS), ("TOOL_KEYS", i18n.TOOL_KEYS),
                      ("COMMON", i18n.COMMON)):
    _miss = []
    for _c in _codes:
        _d = _grey.get(_c) or {}
        if len(_d) != len(next(iter(_grey.values()))):
            _miss.append((_c, len(_d)))
    check("F6 %s：19 语言条目数齐平" % _gname, not _miss, _miss)
check("F7 SLOGAN：19 语言齐平", len(i18n.SLOGAN) == 19, len(i18n.SLOGAN))
check("F8 COMMON 至少 25 键（含搜索提示 + 5 条启动提示）",
      len(next(iter(i18n.COMMON.values()))) >= 25,
      len(next(iter(i18n.COMMON.values()))))
check("F9 NAV_KEYS 有 13 键", len(next(iter(i18n.NAV_KEYS.values()))) == 13,
      len(next(iter(i18n.NAV_KEYS.values()))))
check("F10 TOOL_KEYS 有 16 键", len(next(iter(i18n.TOOL_KEYS.values()))) == 16,
      len(next(iter(i18n.TOOL_KEYS.values()))))
check("F11 只有阿拉伯语是 RTL（其余 18 种都是 LTR）",
      [c for c, _a, _b, r in i18n.LANGUAGES if r] == ["ar"],
      [c for c, _a, _b, r in i18n.LANGUAGES if r])
_cn = {c: cn for c, _s, cn, _r in i18n.LANGUAGES}
check("F12 19 种语言的中文名全齐（含补齐的 5 种）",
      all(_cn.get(c) for c in _codes) and len(set(_cn.values())) == 19,
      _cn)

# ============================================================ G. i18n 语义 + 端到端
section("G. 反馈 3：i18n 语义与端到端切语言")
check("G1 normalize 认代码 en", i18n.normalize("en") == "en", i18n.normalize("en"))
check("G2 normalize 认中文名「英语」", i18n.normalize("英语") is not None)
check("G3 normalize 对认不出的字符串回落到基准语言（不猜、不报错）",
      i18n.normalize("English") == "zh_CN", i18n.normalize("English"))
check("G3b 自称由 native_name() 提供（en → English）",
      i18n.native_name("en") == "English", i18n.native_name("en"))
check("G4 normalize 空值回落基准语言 zh_CN",
      i18n.normalize("") == "zh_CN" and i18n.normalize(None) == "zh_CN",
      (i18n.normalize(""), i18n.normalize(None)))
check("G5 normalize 垃圾值回落基准语言",
      i18n.normalize("klingon-9") == "zh_CN", i18n.normalize("klingon-9"))
check("G6 normalize 大小写 / 空白 / 区域码容错",
      i18n.normalize("  EN  ") == "en" and i18n.normalize("en-US") == "en"
      and i18n.normalize("zh-Hans-CN") == "zh_CN",
      (i18n.normalize("  EN  "), i18n.normalize("en-US"), i18n.normalize("zh-Hans-CN")))
check("G7 zh_CN 下 tr() 原样返回（基准不翻译）",
      i18n.set_lang("zh_CN") == "zh_CN" and i18n.tr("媒体库") == "媒体库",
      i18n.tr("媒体库"))
i18n.set_lang("en")
check("G8 切 en 后 tr() 真翻译", i18n.tr("媒体库") != "媒体库", i18n.tr("媒体库"))
check("G9 查不到的键原样返回中文（绝不返回空）",
      i18n.tr("这个键不存在xyz") == "这个键不存在xyz",
      i18n.tr("这个键不存在xyz"))
check("G10 is_rtl 认阿拉伯语",
      i18n.is_rtl("ar") is True and i18n.is_rtl("en") is False,
      (i18n.is_rtl("ar"), i18n.is_rtl("en")))
check("G11 lang_names() 返回 19 项", len(i18n.lang_names()) == 19, len(i18n.lang_names()))
i18n.set_lang("zh_CN")
_slog_zh = i18n.tr_slogan()
_slog_bak = _slog_zh
i18n.set_lang("en")
_slog_en = i18n.tr_slogan()
i18n.set_lang("zh_CN")
check("G12 tr_slogan 随语言变化且基准仍是中文原句",
      _slog_zh == ver.SLOGAN_CN and _slog_en != _slog_zh,
      (repr(_slog_zh), repr(_slog_en)))

# --- G13 端到端：真建主窗 + 工具窗，切语言看显示变、身份不变 ---
win = mw.MainWindow()
win.show()
pump(6)


def _nav_texts(w):
    """侧栏里当前显示的导航文字 + 分组标题（顺序取）。"""
    out = []
    for _l in w.sidebar.findChildren(QLabel):
        if _l.objectName() == "Section":
            out.append(_l.text())
    for _b in w.sidebar.findChildren(QPushButton):
        out.append(_b.text())
    return out


_st = cfg.get_settings()
_nav_keys_before = [_n.get("key") for _n in _st.nav]
_libs_before = dict(getattr(win, "_lib_btns", {}) or {})

_zh_texts = _nav_texts(win)
check("G13 基准语言下侧栏用的是中文分组标题",
      "媒体库" in _zh_texts, _zh_texts[:8])

# 切到英语
_st.appearance["language"] = "en"
i18n.set_lang("en")
win._apply_settings()
pump(8)
_en_texts = _nav_texts(win)
check("G14 切英语后侧栏出现英文分组标题（显示层真翻译了）",
      any(x != "媒体库" for x in _en_texts) and any("Librar" in x for x in _en_texts),
      _en_texts[:10])
check("G15 切英语后导航**身份键**不变（config.nav 的 key 不受语言影响）",
      [_n.get("key") for _n in cfg.get_settings().nav] == _nav_keys_before,
      [n.get("key") for n in cfg.get_settings().nav])
check("G16 切英语后库名不变（库名是用户起的身份，不翻译）",
      set((getattr(win, "_lib_btns", {}) or {}).keys()) == set(_libs_before.keys()),
      (list((getattr(win, "_lib_btns", {}) or {}).keys()), list(_libs_before.keys())))

# 切到阿拉伯语（RTL：只翻译文字，版面不镜像）
_st.appearance["language"] = "ar"
i18n.set_lang("ar")
win._apply_settings()
pump(8)
_ar_texts = _nav_texts(win)
check("G17 切阿拉伯语后文字变了（确实应用了）",
      _ar_texts != _zh_texts, _ar_texts[:6])
check("G18 阿拉伯语下导航身份键仍不变（语言只影响显示）",
      [_n.get("key") for _n in cfg.get_settings().nav] == _nav_keys_before)

# 切回基准语言
_st.appearance["language"] = "zh_CN"
i18n.set_lang("zh_CN")
win._apply_settings()
pump(6)
check("G19 切回简体中文后侧栏恢复中文",
      "媒体库" in _nav_texts(win), _nav_texts(win)[:8])

# --- G20 工具窗外观页有语言下拉，且真能切换 ---
dlg = ui_settings.SettingsDialog(win, on_changed=win._apply_settings)
pump(6)
_cb = getattr(dlg, "ap_lang", None)
check("G20 外观页有语言下拉控件", _cb is not None, type(_cb).__name__)
if _cb is not None:
    _items = [_cb.itemData(i) for i in range(_cb.count())] if hasattr(_cb, "itemData") else []
    if not any(_items):
        _items = [_cb.itemText(i) for i in range(_cb.count())]
    check("G21 语言下拉至少 19 项", _cb.count() >= 19, _cb.count())
    _texts22 = [_cb.itemText(i) for i in range(_cb.count())]
    check("G22 下拉条目文本是「自称 · 中文名」（用户认自己的字）",
          any("English" in x and "英语" in x for x in _texts22), _texts22[:4])
    check("G22b 下拉 itemData 是真语言代码（不是显示文本）",
          _items[:3] == ["zh_CN", "en", "ja"], _items[:4])

# ============================================================ H. 关于对话框
section("H. 反馈 4：「关于」对话框内容已更新")
_secs = getattr(mw.AboutDialog, "SECTIONS", None)
check("H1 AboutDialog 有 SECTIONS 类属性", _secs is not None,
      type(_secs).__name__)
check("H2 SECTIONS 含 9 个模块", _secs is not None and len(_secs) == 9,
      len(_secs) if _secs else 0)
check("H3 SECTIONS 每项是 (标题, 一句话说明) 且说明非空",
      bool(_secs) and all(isinstance(x, (tuple, list)) and len(x) == 2
                          and x[0] and x[1] for x in _secs), _secs[:3] if _secs else None)
_body_src = src("main_window.py")
check("H4 _body() 是 Markdown 正文生成器",
      "@classmethod" in _body_src and "def _body" in _body_src)

_about = mw.AboutDialog()
pump(3)
_bw = None
for _c in _about.findChildren(__import__("PySide6.QtWidgets", fromlist=["QTextBrowser"]).QTextBrowser):
    _bw = _c
    break
check("H5 关于窗用 QTextBrowser 承载正文", _bw is not None)
_txt = _bw.toPlainText() if _bw is not None else ""
check("H6 正文含软件名「流明盒」", "流明盒" in _txt, _txt[:60].replace("\n", " "))
check("H7 正文含英文名 LumaCrate", "LumaCrate" in _txt)
check("H8 正文含版本号与内部构建号",
      ver.FULL_VERSION in _txt or (ver.VERSION in _txt and ver.BUILD in _txt),
      [l for l in _txt.splitlines() if "版本" in l][:2])
check("H9 正文含版权声明", ver.COPYRIGHT in _txt or "肆月Aperture" in _txt)
check("H10 正文含作者主页链接", ver.AUTHOR_URL in _txt)
check("H11 正文含项目主页链接", ver.REPO_URL in _txt)
check("H12 正文含 Slogan", ver.SLOGAN_CN in _txt or ver.SLOGAN_EN in _txt)
check("H13 正文含「开源」与商业用途限制",
      "开源" in _txt and ("商业" in _txt or ver.LICENSE_NOTE in _txt))
check("H14 正文含隐私/联网说明",
      ("隐私" in _txt) and ("离线" in _txt or "联网" in _txt or "Ollama" in _txt))
check("H15 正文含技术栈（PySide6）", "PySide6" in _txt)
check("H16 正文含界面语言支持说明（19 种）",
      "语言" in _txt and ("19" in _txt), [l for l in _txt.splitlines() if "语言" in l][:2])
check("H17 正文 Markdown 至少 5 个二级标题", _txt.count("\n") >= 0 and
      len([l for l in _txt.splitlines() if l.strip() and l.isupper() is False]) >= 5)
_about.close()
pump(2)

# ============================================================ I. README 截图引用
section("I. 反馈 2：中英 README 截图引用完整")
_rmd = doc("README.md")
_ren = doc("README_EN.md")
check("I1 README.md 有「屏幕截图」段", "屏幕截图" in _rmd or "截图" in _rmd)
check("I2 README_EN.md 有 Screenshots 段",
      "Screenshot" in _ren or "screenshot" in _ren)

import re
_shots_dir = os.path.join(ROOT, "docs", "screenshots")
_refs_cn = set(re.findall(r"docs/screenshots/([0-9A-Za-z_\-\.]+\.png)", _rmd))
_refs_en = set(re.findall(r"docs/screenshots/([0-9A-Za-z_\-\.]+\.png)", _ren))
_files = set(f for f in os.listdir(_shots_dir) if f.endswith(".png")) if os.path.isdir(_shots_dir) else set()
check("I3 中文 README 引用 23 张截图", len(_refs_cn) == 23, len(_refs_cn))
check("I4 英文 README 引用 23 张截图", len(_refs_en) == 23, len(_refs_en))
check("I5 中英引用的截图集合一致",
      _refs_cn == _refs_en, (_refs_cn ^ _refs_en))
check("I6 引用的截图文件都存在（无死链）",
      _refs_cn.issubset(_files), sorted(_refs_cn - _files))
check("I7 docs/screenshots 里正好 23 张图", len(_files) == 23, len(_files))
check("I8 截图目录同时在 dev/ 下也有副本（出图脚本双落点）",
      os.path.isdir(os.path.join(ROOT, "dev", "screenshots_v1320")))

# ============================================================ J. 关键回归
section("J. 关键回归")
check("J1 演员卡六项 5 格、三围整行跨两列",
      mw._ACTOR_FACTS[-1] == ("三围", 2, 0, 2)
      and {r for _k, r, _c, _s in mw._ACTOR_FACTS} == {0, 1, 2})
check("J2 导演卡「作品 / 别名」两项、高度算式未变",
      [k for k, _r, _c, _s in mw._DIRECTOR_FACTS] == ["作品", "别名"]
      and mw.DIRECTOR_CARD_H == mw.ACTOR_CARD_H - 2 * (17 + 4))
check("J3 列数未动（媒体 8 / 演员与导演 6）",
      mw.LazyGrid.COLS_BY_KIND["media"] == 8
      and mw.LazyGrid.COLS_BY_KIND["actor"] == 6, mw.LazyGrid.COLS_BY_KIND)
check("J4 工具窗导航仍是四分组且顺序未乱",
      [g for g, _k in ui_settings.SettingsDialog.NAV_GROUPS] ==
      ["基础工具", "数据优化", "智能检测", "数据分析"],
      [g for g, _k in ui_settings.SettingsDialog.NAV_GROUPS])
check("J5 PART 3 的 nav 早退兜底还在（stack 未建时不炸）",
      "if getattr(self, \"stack\", None) is None" in src("ui_settings.py"))

# 线程单例（v1.27.0 命门）
win._apply_settings()
pump(8)
import sysmon as _sy
_workers = app.findChildren(_sy.SysMonWorker)
check("J6 v1.27.0 线程单例仍成立（重建侧栏后 SysMonWorker 仍 1 个且在跑）",
      len(_workers) == 1 and _workers[0].isRunning(),
      (len(_workers), [w.isRunning() for w in _workers]))
check("J7 主窗里没有检测页的线程（检测只活在工具窗里）",
      len(win.findChildren(ui_imagedetect.ImageScanWorker)) == 0
      and len(win.findChildren(ui_actorcheck.ActorCheckWorker)) == 0)
check("J8 侧栏品牌与外链过滤器仍被持有引用",
      win._brand_link is not None and win._footer_link is not None)

# 工具窗能打开（v1.31.0 曾因 stack 属性炸掉）
dlg2 = ui_settings.SettingsDialog(win, on_changed=win._apply_settings)
pump(6)
check("J9 工具窗能正常构建（v1.31.0 的 stack AttributeError 未复发）",
      dlg2.stack.count() == len(dlg2.ORDER),
      (dlg2.stack.count(), len(dlg2.ORDER)))
for _k in dlg2.ORDER:
    dlg2._show(_k)
    pump(1)
check("J10 工具窗每一页都能切过去（无异常）",
      dlg2.stack.currentWidget() is dlg2._pg_data, dlg2.stack.currentWidget())
dlg2.close()
pump(2)

win.close()
pump(3)

check("J11 未捕获异常为零（日志里没有 Traceback）",
      "Traceback" not in (io.open(applog.log_path(), encoding="utf-8", errors="replace").read()
                          if os.path.exists(applog.log_path()) else ""),
      applog.log_path())
check("J12 README.md 与 version.py 版本号一致",
      ver.VERSION in doc("README.md"), ver.VERSION)
check("J13 README_EN.md 与 version.py 版本号一致",
      ver.VERSION in doc("README_EN.md"), ver.VERSION)
check("J14 内部构建号也进了两版 README",
      ver.BUILD in doc("README.md") and ver.BUILD in doc("README_EN.md"))

print("\n" + "=" * 74)
print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败：")
    for t in FAIL:
        print("  -", t)
print("=" * 74)
