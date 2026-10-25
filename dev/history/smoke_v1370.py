# -*- coding: utf-8 -*-
"""v1.37.0 离屏冒烟（构建期）。

五条反馈的回归与单元断言：
① 详情页「演职人员信息」：艺人/导演 收藏→金、置顶→粗、二者兼有→金粗（CastAvatar）。
② 影片卡片小字（演员/导演）同步上色；cast_crew_map_ex 携带 收藏/置顶 标记，
   cast_crew_map 仍返回纯文本且不重复查表。
③ 首页右侧详情顶部空白带：HeroView._build 仅当 on_back 不为 None 时建 topbar
   （on_back=None 时第一行应为横幅 HeroBanner，而非空 topbar）。
④ 首页右侧「影片详细信息」面板加高亮色边框：detail_host 开 WA_StyledBackground +
   style.qss 的 QWidget#DetailHost 规则（且经 render_style 后 __ACCENT_LIGHT__ 被解析）。
⑤ 启动动画配色跟随「外观 → 高亮色」：splash._derive_splash_theme 按 accent 派生，
   朱红→红调、靛蓝→蓝调；SplashScreen 可构建且绘制不报错。

使用临时数据库与临时配置，绝不读写真实索引 / 真实 settings.json。
"""
import os
import sys
import shutil
import tempfile
import faulthandler

faulthandler.enable()

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_SYSMON"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"

TMP = tempfile.mkdtemp(prefix="lmc_smoke_v1370_")
os.environ["LMC_CONFIG"] = os.path.join(TMP, "settings.json")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from PySide6.QtWidgets import QApplication, QLabel, QWidget, QPushButton
from PySide6.QtGui import QFontDatabase

app = QApplication(sys.argv)

import database as db
import config as cfg
import version as ver
import applog
import splash as splash_mod
from main_window import MainWindow, PosterCard, load_style
from ui_hero import CastAvatar, HeroView, HeroBanner

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")

for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

FAIL = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (("   -> " + str(extra)) if extra else ""))
    if not cond:
        FAIL.append(name)


# ================================================================ 样本库
root = os.path.join(TMP, "lib")
os.makedirs(root, exist_ok=True)
_meta = '<movie><title>样本影片</title><year>2020</year><runtime>120</runtime>' \
        '<country>日本</country><genre>輪姦</genre><plot>x</plot>' \
        '<actor><name>三上悠亜</name></actor></movie>'
d = os.path.join(root, "MV-001")
os.makedirs(d, exist_ok=True)
with open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8") as f:
    f.write('<?xml version="1.0"?>\n' + _meta)
with open(os.path.join(d, "MV-001.mp4"), "w") as f:
    f.write("x" * 1024)
with open(os.path.join(d, "poster.jpg"), "w") as f:
    f.write("x" * 256)
db.init_db()
import scanner as scanner_mod
scanner_mod.scan_library(root)
rows = db.movies()
check("样本库已建好", len(rows) >= 1, len(rows))

# ================================================================ ① 详情页演职人员上色
print("\n---- ① CastAvatar 收藏/置顶 上色 ----")
def _name_ss(fav, pin):
    c = CastAvatar({"name": "测试甲", "favorite": fav, "pinned": pin}, None)
    for lab in c.findChildren(QLabel):
        if lab.text() == "测试甲":
            return lab.styleSheet()
    return ""


_ss_fav = _name_ss(1, 0)
_ss_pin = _name_ss(0, 1)
_ss_both = _name_ss(1, 1)
_ss_none = _name_ss(0, 0)
check("收藏 → 名字金色(不含加粗)", "color:#d4af37" in _ss_fav and "font-weight:bold" not in _ss_fav, _ss_fav)
check("置顶 → 名字加粗(非金色)", "font-weight:bold" in _ss_pin and "color:#d4af37" not in _ss_pin, _ss_pin)
check("收藏+置顶 → 金色加粗", "color:#d4af37" in _ss_both and "font-weight:bold" in _ss_both, _ss_both)
check("普通 → 默认色不加粗", "color:#d4af37" not in _ss_none and "font-weight:bold" not in _ss_none, _ss_none)

# ================================================================ ② 卡片小字上色 + 数据层
print("\n---- ② PosterCard 小字上色 + cast_crew_map_ex ----")
MEDIA = {"id": 1, "title": "样本影片", "year": 2020, "poster": None, "file_path": None,
         "favorite": 0}
card = PosterCard(MEDIA, on_open=None, actor_crew=[("测试甲", 1, 0), ("测试乙", 0, 1)],
                  director_crew=[("导演丙", 1, 1)])
crew_lab = None
for lab in card.findChildren(QLabel):
    if lab.objectName() == "CardCrew":
        crew_lab = lab
        break
check("卡片存在 CardCrew 标签", crew_lab is not None)
_ct = crew_lab.text() if crew_lab else ""
check("卡片小字含金色 span（收藏）", "color:#d4af37" in _ct, _ct)
check("卡片小字含加粗 span（置顶）", "font-weight:bold" in _ct, _ct)
check("卡片小字含前缀「演员：」+ 名字「测试甲」",
      "演员：" in _ct and "测试甲" in _ct, _ct)
check("卡片小字含前缀「导演：」+ 名字「导演丙」",
      "导演：" in _ct and "导演丙" in _ct, _ct)

# 纯文本兜底路径（冒烟旧调用）：给 actor_text 不给 actor_crew
card2 = PosterCard(MEDIA, on_open=None, actor_text="名前A")
lab2 = None
for lab in card2.findChildren(QLabel):
    if lab.objectName() == "CardCrew":
        lab2 = lab
        break
check("纯文本兜底：含名前A 且无 span", lab2 is not None and "名前A" in lab2.text()
      and "color:#d4af37" not in lab2.text(), lab2.text() if lab2 else "")

# 数据层：cast_crew_map_ex 携带标记；cast_crew_map 仍纯文本
# 把样本艺人置为「收藏」，再查该片的 cast_crew_map_ex
_cast = db.get_cast(rows[0]["id"]) if rows else []
_pid = _cast[0]["id"] if _cast else None
if _pid is not None:
    db.toggle_person_favorite(_pid)
ex = db.cast_crew_map_ex([rows[0]["id"]])
ex_actors = ex.get(rows[0]["id"], {}).get("actors", [])
check("cast_crew_map_ex 返回 (name, fav, pin) 三元组",
      ex_actors and isinstance(ex_actors[0], tuple) and len(ex_actors[0]) == 3, ex_actors)
check("cast_crew_map_ex 携带 favorite 标记(已置收藏→1)",
      ex_actors and ex_actors[0][1] == 1, ex_actors)
plain = db.cast_crew_map([rows[0]["id"]])
check("cast_crew_map 仍返回纯文本名字串",
      isinstance(plain.get(rows[0]["id"], {}).get("actors", ""), str), plain)

# ================================================================ ③ HeroView topbar 条件
print("\n---- ③ HeroView 顶部空白带修复 ----")
MEDIA_D = {"id": None, "title": "测试片", "year": 2020, "genres": "测试",
           "rating": None, "poster": None, "fanart": None}
hv_none = HeroView(MEDIA_D, on_back=None)
hv_back = HeroView(MEDIA_D, on_back=lambda: None)
_content_none = hv_none.widget()
_content_back = hv_back.widget()
_first_none = _content_none.layout().itemAt(0).widget()
_first_back = _content_back.layout().itemAt(0).widget()
check("on_back=None 时首行是横幅 HeroBanner（无空 topbar）",
      isinstance(_first_none, HeroBanner), type(_first_none).__name__)
check("on_back 存在时首行是带返回按钮的 topbar",
      isinstance(_first_back, QWidget) and _first_back.findChild(QPushButton) is not None
      and _first_back.findChild(QPushButton).text() == "← 返回",
      type(_first_back).__name__)

# ================================================================ ④ 详情面板边框
print("\n---- ④ 影片详细信息 面板边框 ----")
qss = open(os.path.join(SRC, "style.qss"), encoding="utf-8").read()
check("style.qss 含 QWidget#DetailHost 规则",
      "QWidget#DetailHost" in qss and "border: 1px solid rgba(__ACCENT_LIGHT__, 0.55)" in qss)
ui_home_src = open(os.path.join(SRC, "ui_home.py"), encoding="utf-8").read()
check("ui_home 给 detail_host 设对象名 + WA_StyledBackground",
      'setObjectName("DetailHost")' in ui_home_src and "WA_StyledBackground" in ui_home_src)
load_style(app)
ss = app.styleSheet()
check("render_style 后 __ACCENT_LIGHT__ 已在 #DetailHost 解析为 rgba(r,g,b,...)",
      "QWidget#DetailHost" in ss and "border: 1px solid rgba(" in ss,
      ("#DetailHost" in ss))

# ================================================================ ⑤ 启动画面随高亮色
print("\n---- ⑤ 启动画面配色跟随高亮色 ----")
t_red = splash_mod._derive_splash_theme("#c0392b")
t_blue = splash_mod._derive_splash_theme("#3b6fd4")
check("朱红高亮 → 底色红通道占优（红调）",
      t_red["bg_top"].red() > t_red["bg_top"].blue()
      and t_red["bg_top"].red() >= t_red["bg_top"].green(),
      (t_red["bg_top"].red(), t_red["bg_top"].green(), t_red["bg_top"].blue()))
check("朱红高亮 → 进度条亮端=高亮色原色(192,57,43)",
      (t_red["accent_a"].red(), t_red["accent_a"].green(), t_red["accent_a"].blue())
      == (192, 57, 43))
check("靛蓝高亮 → 底色蓝通道占优（蓝调）",
      t_blue["bg_top"].blue() > t_blue["bg_top"].red(),
      (t_blue["bg_top"].red(), t_blue["bg_top"].green(), t_blue["bg_top"].blue()))
check("靛蓝高亮 → 进度条亮端=高亮色原色(59,111,212)",
      (t_blue["accent_a"].red(), t_blue["accent_a"].green(), t_blue["accent_a"].blue())
      == (59, 111, 212))
# 跟随配置读取的默认高亮色
acc = splash_mod._accent_hex()
check("默认高亮色可被读取（非空）", bool(acc), acc)

# SplashScreen 可构建且绘制不报错
_err = None
try:
    sp = splash_mod.SplashScreen(logo_path=None, title="流明盒",
                                 version_text=ver.FULL_VERSION, copyright_text=ver.COPYRIGHT)
    sp.setProgress(40, "正在自检…")
    sp.repaint()
    app.processEvents()
    check("SplashScreen 构建 + 绘制无异常", sp._t is not None and isinstance(sp._t, dict))
except Exception as e:  # noqa: BLE001
    _err = f"{type(e).__name__}: {e}"
    check("SplashScreen 构建 + 绘制无异常", False, _err)

# ================================================================ ⑥ 版本号
print("\n---- ⑥ 版本号 ----")
check("外部版本号 = v1.37.0", ver.VERSION == "v1.37.0", ver.VERSION)
check("内部构建号 = 2610070055", ver.BUILD == "2610070055", ver.BUILD)

print("")
print(f"==== v1.37.0 冒烟结果：{'PASS' if not FAIL else 'FAIL'}  (失败 {len(FAIL)} 项) ====")
for n in FAIL:
    print("  FAIL:", n)

try:
    shutil.rmtree(TMP, ignore_errors=True)
except Exception:
    pass
sys.exit(1 if FAIL else 0)
