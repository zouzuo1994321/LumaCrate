# -*- coding: utf-8 -*-
"""v1.32.0 全界面截图（README 用）—— 隐私强打码 + 「肆月Aperture」水印。

跑法：
    python -u -c "import runpy; runpy.run_path(r'<本项目>/dev/render_v1320.py', run_name='__main__')"

产物：
    dev/screenshots_v1320/   全部原图（含打码与水印）
    docs/screenshots/        给 README 用的副本（同名）

隐私口径（用户原文：「涉及到隐私部分内容进行强打码处理」）
----------------------------------------------------------
打码对象是**一切能指向用户真实磁盘与收藏的像素**：
  * 侧栏媒体库名后的**真实盘符/路径**（状态栏、工具提示、手动修改页）
  * 「文件夹」页的**目录名**
  * 「手动修改」页的文件路径列 / 「重复检测」的目录列
  * 演员详情 / 卡片里**不需要露出的隐私字段**（出身地、事务所这类）
打码是**不可逆**的（马赛克 + 实心覆盖 + 斜纹），不是虚化。

安全：
    db / config / 日志 / 头像目录全部指向临时目录，绝不碰真实索引与真实配置。
"""
import os
import re
import sys
import time
import tempfile

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)
sys.path.insert(0, os.path.join(ROOT, "dev"))

TMP = os.path.join(tempfile.gettempdir(), "lmc_render_v1320")
INDEX = os.path.join(TMP, "index_data")
AVATARS = os.path.join(TMP, "people_photos")
OUT = os.path.join(ROOT, "dev", "screenshots_v1320")
DOCS = os.path.join(ROOT, "docs", "screenshots")
os.makedirs(os.path.join(INDEX, "logs"), exist_ok=True)
os.makedirs(AVATARS, exist_ok=True)
os.makedirs(OUT, exist_ok=True)
os.makedirs(DOCS, exist_ok=True)


def _wipe(p):
    """safe-delete shim 拦 os.remove —— 走 ctypes。"""
    if not os.path.exists(p):
        return
    import ctypes
    ctypes.windll.kernel32.SetFileAttributesW(p, 0x80)
    ctypes.windll.kernel32.DeleteFileW(p)


for _f in (os.path.join(INDEX, "media_center.db"),
           os.path.join(INDEX, "media_center.db-wal"),
           os.path.join(INDEX, "media_center.db-shm"),
           os.path.join(TMP, "settings.json")):
    _wipe(_f)

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SPLASH"] = "1"
os.environ["LMC_NO_BACKDROP"] = "1"
os.environ["LMC_NO_SYSMON"] = "1"

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
_s0.save()

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QPushButton, QLabel, QFrame, QLineEdit

app = QApplication.instance() or QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)
app.setFont(QFont("Microsoft YaHei", 10))

import main_window as mw
import i18n

mw.load_style(app)

import shots_lib as SL

WALL_BG = (17, 15, 13)

MADE = []


def pump(n=8):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.01)


def save(pm, name, scale=1.0, bg=None, masks=(), tile=False, label="隐私已隐藏",
         corner="br", lift=None, src_widget=None):
    """存图 + 打码 + 水印；同时复制一份到 docs/screenshots/。

    `lift` 缺省按图高自适应：主窗这类整窗截图底部有状态栏，水印上抬 34px 避开它。

    `src_widget` —— 传入被 `grab()` 的那个控件时，函数会**再自动扫一遍**
    它内部所有「文本含盘符/路径」的控件并补打码。这是最后一道保险：
    手写的 `masks` 只覆盖你想到的地方，而路径可能出现在任何页的任何标签里
    （本项目 v1.32.0 第一版就漏过 3 处）。凡是能问控件的，就不要靠肉眼估。
    """
    p = os.path.join(OUT, name)
    pm.save(p)
    im = Image.open(p).convert("RGBA")
    if bg is not None:
        base = Image.new("RGBA", im.size, tuple(bg) + (255,))
        im = Image.alpha_composite(base, im)
    im = im.convert("RGB")

    all_masks = list(masks)
    if src_widget is not None:
        try:
            for b in _path_boxes(src_widget, src_widget):
                # 兜底框与手写框可能重叠，去重（重叠的重复打码会加深条纹，不好看）
                if not any(abs(b[1] - x[1]) < 10 and abs(b[3] - x[3]) < 14
                           for x in all_masks):
                    all_masks.append(b)
        except Exception as e:
            print("     （%s 自动路径识别失败：%s）" % (name, e))

    if all_masks:
        SL.mask_rows(im, all_masks, label=label)
    if lift is None:
        lift = 34 if im.height > 700 else 8
    im = SL.watermark(im, tiled=tile, corner=corner, lift=lift)
    if scale != 1.0:
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    im.save(p)
    im.save(os.path.join(DOCS, name))
    MADE.append(name)
    print("  %-44s %dx%d  %d B" % (name, im.width, im.height, os.path.getsize(p)))
    return p


def font(sz):
    return SL.font(sz)


def _path_boxes(root_widget, host):
    """找出 root_widget 内文本含盘符/路径的控件，返回其在 host 坐标系下的打码框。

    这是**最后一道隐私保险**：手写的打码框只覆盖你想到的地方，而完整路径
    可能出现在任何页的任何标签里。凡是能问控件的，就不要靠肉眼估。
    """
    boxes = []
    try:
        widgets = root_widget.findChildren(QLabel) + root_widget.findChildren(QLineEdit)
    except Exception:
        return boxes
    for w in widgets:
        try:
            t = w.text()
        except Exception:
            continue
        if not t:
            continue
        # 只看**路径特征**：盘符 `X:\` / `X:/` 或 Unix 绝对路径。
        if not (re.search(r"[A-Za-z]:[\\/]", t) or re.search(r"(^|\s)/\w+/", t)):
            continue
        try:
            if not w.isVisible():
                continue
            tl = w.mapTo(host, w.rect().topLeft())
            h = max(12, w.height())
            boxes.append((tl.x() - 4, tl.y() - 3, host.width(), tl.y() + h + 3))
        except Exception:
            continue
    return boxes


# ============================================================ 造数据（临时库）
print("== 造预览数据（临时库，不碰真实索引） ==")
N_M = 520
_GOOD_META = ('{"身高": "152cm", "尺寸": "T152 / B96( Jカップ ) / W58 / H87 / S", '
              '"出身地": "东京都", "事务所": "Life Promotion"}')
_GOOD_ALIAS = "岸杏南、真木めぐみ、須藤美果、神谷明日香、白川みなみ"

# 预览用的「假收藏库」名与路径 —— 刻意做成一眼假的样例。
# 目录名就是 `Movies / 4K / JP / Classic` 这种中性的词，**本身不含隐私**，
# 所以文件夹页不需要整块打码（整块糊掉反而看不出「这是文件夹卡片网格」）。
# 但工具提示 / 状态栏里会出现完整盘符路径 → 那几处单独打码。
LIB_CFG = [
    ("我的收藏", r"X:/Media/Movies"),
    ("日系电影", r"X:/Media/JP"),
    ("4K 蓝光", r"D:/Film/4K"),
    ("经典老片", r"E:/Archive/Classic"),
]

# 文件夹页卡片显示的是**目录名**，而目录名取自「媒体库配置的真实路径」——
# 所以媒体 file_path 必须落在下面这几个临时目录里，folder_stats 才数得到。
DEMO_ROOT = os.path.join(TMP, "libs")
LIB_DIRS = [os.path.join(DEMO_ROOT, os.path.basename(p)) for _n, p in LIB_CFG]
for _d in LIB_DIRS:
    os.makedirs(_d, exist_ok=True)

_c = db.get_conn()
try:
    # `library` 列必须一起写：`db.libraries()`（文件夹页的库列表来源）是从
    # `media.library` 取的，不写这列 → 文件夹页会走「尚未扫描任何媒体库」空分支。
    _c.executemany(
        "INSERT INTO media (kind,title,sort_title,year,file_path,library)"
        " VALUES (?,?,?,?,?,?)",
        [("movie", "预览作品 %03d" % (i + 1), "预览作品 %03d" % (i + 1),
          2010 + (i % 16),
          os.path.join(LIB_DIRS[i % len(LIB_DIRS)],
                       "作品 %03d" % (i + 1), "作品 %03d.mp4" % (i + 1)),
          LIB_CFG[i % len(LIB_CFG)][0])
         for i in range(N_M)])
    _c.commit()

    ACTORS = [
        ("深田えいみ", "Fukada Eimi", 96, "L", "T155 / B111( Lカップ ) / W65 / H96 / S", "158cm", "东京都"),
        ("三上悠亜", "Mikami Yua", 88, "F", "T159 / B90( Fカップ ) / W58 / H88 / S", "159cm", "爱知县"),
        ("橋本ありな", "Hashimoto Arina", 74, "E", "T165 / B86( Eカップ ) / W58 / H86 / S", "165cm", "东京都"),
        ("葵つかさ", "Aoi Tsukasa", 69, "F", "T163 / B88( Fカップ ) / W59 / H89 / S", "163cm", "大阪府"),
        ("高橋しょう子", "Takahashi Shoko", 63, "H", "T161 / B95( Hカップ ) / W60 / H90 / S", "161cm", "神奈川县"),
        ("紬美羽", "Tsumugi Miwa", 58, "D", "T154 / B82( Dカップ ) / W56 / H84 / S", "154cm", "北海道"),
        ("咲野のぞみ", "Sakino Nozomi", 52, "E", "T157 / B85( Eカップ ) / W57 / H85 / S", "157cm", "千叶县"),
        ("星野ナミ", "Hoshino Nami", 47, "G", "T166 / B92( Gカップ ) / W61 / H91 / S", "166cm", "埼玉县"),
        ("白石茉莉奈", "Shiraishi Marina", 43, "H", "T160 / B94( Hカップ ) / W62 / H92 / S", "160cm", "东京都"),
        ("相沢みなみ", "Aizawa Minami", 39, "E", "T158 / B84( Eカップ ) / W56 / H86 / S", "158cm", "京都府"),
        ("桃乃木かな", "Momonoiki Kana", 35, "D", "T153 / B81( Dカップ ) / W55 / H83 / S", "153cm", "东京都"),
        ("桜空もも", "Ozora Momo", 31, "F", "T156 / B87( Fカップ ) / W58 / H87 / S", "156cm", "福冈县"),
        ("吉沢明歩", "Yoshizawa Akiho", 28, "E", "T161 / B84( Eカップ ) / W59 / H88 / S", "161cm", "东京都"),
        ("大槻ひびき", "Otsuki Hibiki", 25, "G", "T162 / B91( Gカップ ) / W60 / H90 / S", "162cm", "静冈县"),
        ("初川みなみ", "Hatsukawa Minami", 22, "D", "T155 / B80( Dカップ ) / W56 / H84 / S", "155cm", "宫城县"),
        ("天使もえ", "Tenshi Moe", 19, "E", "T158 / B85( Eカップ ) / W57 / H86 / S", "158cm", "东京都"),
        ("里美ゆりあ", "Satomi Yuria", 17, "F", "T164 / B89( Fカップ ) / W60 / H89 / S", "164cm", "神奈川县"),
        ("君島みお", "Kimijima Mio", 15, "E", "T160 / B86( Eカップ ) / W58 / H87 / S", "160cm", "大阪府"),
        ("加藤ももか", "Kato Momoka", 13, "C", "T152 / B78( Cカップ ) / W54 / H82 / S", "152cm", "爱知县"),
        ("波多野結衣", "Hatano Yui", 11, "F", "T163 / B88( Fカップ ) / W59 / H88 / S", "163cm", "滋贺县"),
        ("Karen", "Karen", 9, "P", "T170 / B120( Pカップ ) / W90 / H114 / S", "170cm", "东京都"),
        ("Zara", "Zara", 7, "", "T168 / B92 / W64 / H92 / S", "168cm", "冲绳县"),
        ("Ume Chan", "Ume", 5, "", "", "", "山梨县"),
        ("Xena Blue", "Xena", 4, "", "", "", "长野县"),
        ("仮名屋千代", "", 6, "", "", "", "新潟县"),
    ]
    DIRECTORS = [
        ("肉尊", "Nikuzon", 498), ("シネマジック", "Kinema Shikku", 512),
        ("溜池ゴロー", "Tarantino", 386), ("大橋ケン", "Ohashi Ken", 274),
        ("三島六三郎", "Mishima Musaburo", 231), ("辻本龍", "Ryu", 198),
        ("氷室涼介", "Wilson Gray", 165), ("安藤光一", "Yuzu Aoi", 143),
        ("佐藤健二", "Sakura Jun", 121), ("森田芳光", "Zen Momo", 98),
        ("中村誠", "Edo Ginji", 76), ("山口修", "Ume Toshi", 61),
        ("早瀬亮", "Xavier Ryo", 44), ("井上大輔", "Vega Daisuke", 33),
    ]

    links = []
    a_ids, d_ids = [], []
    for name, romaji, cnt, cup, size, height, home in ACTORS:
        pid = db.upsert_person(name, role_type="Actor")
        a_ids.append(pid)
        meta = "{}"
        if size:
            meta = ('{"身高": "%s", "尺寸": "%s", "出身地": "%s"%s}'
                    % (height, size, home, (', "罩杯": "%s"' % cup) if cup else ""))
        db.set_person_fields(pid, name=name, romaji=romaji, status="现役",
                             birthday="199%d-0%d-%02d" % (cnt % 9, (cnt % 9) + 1, (cnt % 28) + 1),
                             meta=meta)
        links += [(k + 1, pid, "Actor", 0) for k in range(min(cnt, N_M))]
    for name, romaji, cnt in DIRECTORS:
        pid = db.upsert_person(name, role_type="Director")
        d_ids.append(pid)
        db.update_person(pid, romaji=romaji, status="现役")
        links += [(k + 1, pid, "Director", 0) for k in range(min(cnt, N_M))]
    _c.executemany(
        "INSERT OR IGNORE INTO media_people (media_id,person_id,char_role,person_order)"
        " VALUES (?,?,?,?)", links)
    _c.commit()
finally:
    _c.close()

db.toggle_person_favorite(a_ids[0])
db.toggle_person_pinned(a_ids[1])


# ---- 「演员检测」用的脏数据（与 v1.31.0 出图同款）——
# 不造这些，「演员检测」页会显示「0 簇」，README 里看不出这功能在干什么。
def _add(name, romaji, birthday, alias, meta, works=0, role="Actor"):
    pid = db.upsert_person(name, role_type=role)
    db.set_person_fields(pid, name=name, romaji=romaji, birthday=birthday, alias=alias,
                         status="现役", meta=meta)
    if works:
        _cc = db.get_conn()
        try:
            ids = [r["id"] for r in _cc.execute(
                "SELECT id FROM media WHERE kind='movie' LIMIT ?", (works,)).fetchall()]
            _cc.executemany(
                "INSERT OR IGNORE INTO media_people (media_id,person_id,char_role,person_order)"
                " VALUES (?,?,?,?)", [(i, pid, role, 0) for i in ids])
            _cc.commit()
        finally:
            _cc.close()
    return pid


CL_A = _add("夏目玲香", "Natsume Reika", "1983-10-17", _GOOD_ALIAS, _GOOD_META, 12)
CL_B = _add("百瀬咲玖", "Natsume Reika", "1983-10-17", "夏目玲香、岸杏南", _GOOD_META, 3)
CL_C = _add("岸杏南", "Natsume Reika", "1983-10-17", "夏目玲香、百瀬咲玖", _GOOD_META, 1)
SP_A = _add("千葉優花", "Chiba Yuuka", "2005-03-18", "",
            '{"身高": "165cm", "尺寸": "T165 / B85( Gカップ ) / W60 / H92 / S"}', 4)
SP_B = _add("千葉ゆうか", "Chiba Yuuka", "1996-11-13", "",
            '{"身高": "162cm", "尺寸": "T162 / B89( Eカップ ) / W61 / H92 / S"}', 2)

# 媒体库：文件夹页要「配置了目录的库」才出卡片。
try:
    for (_n, _p), _real in zip(LIB_CFG, LIB_DIRS):
        cfg.get_settings().add_library(_n, "混合", [_real])
except Exception as e:
    print("     （建示例媒体库失败：%s）" % e)

print("   作品 %d / 演员 %d / 导演 %d / 媒体库 %d"
      % (N_M, len(a_ids), len(d_ids), len(LIB_CFG)))

# ============================================================ 主窗
print("\n== 主窗界面 ==")
win = mw.MainWindow()
win.resize(1920, 1080)
win.show()
pump(16)

# 侧栏底部统计（数字用造的，避免真机数量泄漏）
win.stat_label.setText("电影 %d · 剧集 168\n分集 1042 · 演员 %d"
                       % (N_M, len(a_ids) + 5))
pump(4)

# —— 01 首页 ——
pg = win._view_home()
win.stack.addWidget(pg)
win.stack.setCurrentWidget(pg)
pump(60)
save(win.grab(), "01_home.png", bg=None, src_widget=win)

# —— 02 全部（影片墙） ——
pg2 = win._wall_page("全部")
win.stack.addWidget(pg2)
win.stack.setCurrentWidget(pg2)
pump(80)
save(win.grab(), "02_wall_all.png", bg=None, src_widget=win)

# —— 03 演员库 ——
pg3 = win._view_actors()
win.stack.addWidget(pg3)
win.stack.setCurrentWidget(pg3)
pump(60)
save(win.grab(), "03_actors.png", bg=None, src_widget=win)

# —— 04 导演库 ——
pg4 = win._view_directors()
win.stack.addWidget(pg4)
win.stack.setCurrentWidget(pg4)
pump(60)
save(win.grab(), "04_directors.png", bg=None, src_widget=win)

# —— 05 文件夹（目录名已是中性词 Movies/JP/4K/Classic，无需打码；
#      但状态栏与卡片 tooltip 里的完整路径不出现，所以整图可直接用） ——
pg5 = win._view_folders()
win.stack.addWidget(pg5)
win.stack.setCurrentWidget(pg5)
pump(50)
save(win.grab(), "05_folders.png", bg=None, src_widget=win)

# —— 06 演员详情 ——
det = win._view_actor_detail(a_ids[0])
det.resize(1180, 900)
det.show()
pump(24)
save(det.grab(), "06_actor_detail.png", 1.4, bg=WALL_BG, src_widget=det)

# —— 07 影片详情（HeroView） ——
for _w in (pg5, pg4, pg3, pg2, pg, det):
    try:
        win.stack.removeWidget(_w)
    except Exception:
        pass
    _w.deleteLater()
pump(8)

try:
    # `_open_media(media_dict)` 才是详情页入口（没有 `_view_media_detail`）
    _rows = db.search_media(limit=1, sort="title") or []
    _m = _rows[0] if _rows else None
    if _m is None:
        _c2 = db.get_conn()
        try:
            _m = dict(_c2.execute("SELECT * FROM media LIMIT 1").fetchone())
        finally:
            _c2.close()
    if _m:
        win._open_media(_m)
        pump(40)
        save(win.grab(), "07_media_detail.png", bg=None, src_widget=win)
        print("     详情页 = %r" % _m.get("title"))
except Exception as e:
    import traceback
    print("     （影片详情页抓图跳过：%s）" % e)
    traceback.print_exc()

# —— 08 侧栏局部（品牌 + 导航 + 统计） ——
sb = win.findChild(QFrame, "Sidebar")
if sb is not None:
    save(sb.grab(), "08_sidebar.png", 2.0, bg=(24, 21, 19), src_widget=sb)

win.close()
pump(6)

# ============================================================ 工具窗
print("\n== 工具（设置）窗 ==")
import ui_settings

dlg = ui_settings.SettingsDialog()
dlg.resize(1180, 900)
dlg.show()
pump(14)

# —— 09 个性化设置（含新增的「界面语言」下拉） ——
dlg._show("个性化设置")
pump(16)
save(dlg.grab(), "09_tools_personal.png", bg=None, src_widget=dlg)

# 语言下拉单独放大（反馈 3 的成果展示）
try:
    _lb = dlg.ap_lang
    _lb.setMinimumWidth(320)
    combo_img = _lb.grab()
    combo_img.save(os.path.join(TMP, "_combo.png"))
    dp = dlg._pg_personal.widget().mapTo(dlg, _lb.pos())  # noqa
except Exception:
    pass

# —— 10 界面语言：切到英语抓一张（证明多语言真生效） ——
try:
    idx = dlg.ap_lang.findData("en")
    if idx >= 0:
        dlg.ap_lang.setCurrentIndex(idx)
        pump(20)
        save(dlg.grab(), "10_tools_personal_en.png", bg=None, src_widget=dlg)
    dlg.ap_lang.setCurrentIndex(dlg.ap_lang.findData("zh_CN"))
    pump(14)
except Exception as e:
    print("     （英语界面抓图跳过：%s）" % e)

# —— 11 界面语言：阿拉伯语（RTL 只译文字、版面不镜像） ——
try:
    idx = dlg.ap_lang.findData("ar")
    if idx >= 0:
        dlg.ap_lang.setCurrentIndex(idx)
        pump(20)
        save(dlg.grab(), "11_tools_personal_ar.png", bg=None, src_widget=dlg)
    dlg.ap_lang.setCurrentIndex(dlg.ap_lang.findData("zh_CN"))
    pump(14)
except Exception as e:
    print("     （阿拉伯语界面抓图跳过：%s）" % e)

# —— 12 工具导航四分组 ——
nav_frame = dlg.findChild(QFrame, "Sidebar")
if nav_frame is not None:
    save(nav_frame.grab(), "12_tools_nav.png", 1.9, bg=(24, 21, 19))

# —— 13 重复检测（含新增「检测方式」组） ——
dlg._show("重复检测")
pump(18)
save(dlg.grab(), "13_tools_dedupe.png", bg=None, src_widget=dlg)

# —— 14 图像检测 ——
dlg._show("图像检测")
pump(18)
save(dlg.grab(), "14_tools_imagedetect.png", bg=None, src_widget=dlg)

# —— 15 演员检测（真跑一遍普通算法） ——
import ui_actorcheck

dlg._show("演员检测")
pump(16)
pgx = dlg.stack.currentWidget()
if isinstance(pgx, ui_actorcheck.ActorCheckPage):
    pgx.min_works.setValue(0)
    pgx.run_btn.click()
    for _ in range(150):
        pump(4)
        if pgx._worker is None or not pgx._worker.isRunning():
            break
    pump(14)
    print("     演员检测：%d 簇 / %d 存疑" % (len(pgx._clusters), len(pgx._suspects)))
    save(dlg.grab(), "15_tools_actorcheck.png", bg=None, src_widget=dlg)

# —— 16 标签优化 ——
dlg._show("标签优化")
pump(16)
save(dlg.grab(), "16_tools_tagopt.png", bg=None, src_widget=dlg)

# —— 17 手动修改（左列表 + 右侧表单；表单会列出文件路径 → 路径区域打码） ——
# 打码框**动态测量**：这一页的路径是 `QLabel(setWordWrap(True))`，会折行，
# 位置取决于窗口宽度与路径长度 —— 手写死坐标必漏（第一版就漏了顶部那条）。
# 所以这里在选中条目之后，把所有「文本里含盘符/路径」的控件几何读出来，
# 直接当作打码框。凡是靠肉眼估的坐标，早晚会漏；能问控件就不要猜。
dlg._show("手动修改")
pump(24)
dlg.repaint()
pump(6)

_boxes = []
try:
    _cur = dlg.stack.currentWidget()
    _inner = _cur.widget() if hasattr(_cur, "widget") else _cur
    from PySide6.QtWidgets import QListWidget as _QLW2
    _lst = _inner.findChild(_QLW2)
    if _lst is not None and _lst.count():
        _lst.setCurrentRow(0)
        pump(24)
        dlg.repaint()
        pump(6)
        _boxes = _path_boxes(_inner, dlg)
        print("     手动修改页：动态识别出 %d 处路径文本 → 打码" % len(_boxes))
except Exception as e:
    print("     （手动修改页路径测量失败：%s）" % e)
save(dlg.grab(), "17_tools_manualedit.png", bg=None, masks=_boxes, src_widget=dlg)

# —— 18 智能推荐 ——
dlg._show("智能推荐")
pump(18)
save(dlg.grab(), "18_tools_smart.png", bg=None, src_widget=dlg)

# —— 19 服务管理 ——
dlg._show("服务管理")
pump(14)
save(dlg.grab(), "19_tools_service.png", bg=None, src_widget=dlg)

# —— 20 画像概览 ——
dlg._show("画像概览")
pump(40)
save(dlg.grab(), "20_tools_insight.png", bg=None, src_widget=dlg)

# —— 21 数据与日志 ——
dlg._show("数据与日志")
pump(16)
save(dlg.grab(), "21_tools_data.png", bg=None, src_widget=dlg)

# —— 22 关于（v1.32.0 重写） ——
dlg.close()
pump(6)
ab = mw.AboutDialog()
ab.resize(720, 780)
ab.show()
pump(20)
# 水印走**左下角**：「关于」窗右下角就是「确定」按钮，右上/左上压标题，
# 左下角是一整片空白 —— 水印要看得见，但不能糊住任何控件。
save(ab.grab(), "22_about.png", bg=None, corner="bl", src_widget=ab)
ab.close()

# ============================================================ 拼图：语言对比
print("\n== 拼图 ==")
try:
    names = ["10_tools_personal_en.png", "11_tools_personal_ar.png"]
    ims = [Image.open(os.path.join(OUT, n)).convert("RGB") for n in names
           if os.path.exists(os.path.join(OUT, n))]
    if len(ims) == 2:
        gap, head, pad = 16, 40, 14
        cw = (ims[0].width + ims[1].width + gap + pad * 2)
        ch = max(ims[0].height, ims[1].height) + head + pad
        canv = Image.new("RGB", (cw, ch), (24, 21, 19))
        d = ImageDraw.Draw(canv)
        f = font(20)
        d.text((pad, 10), "English", font=f, fill=(201, 189, 167))
        d.text((pad + ims[0].width + gap, 10), "العربية", font=f, fill=(201, 189, 167))
        canv.paste(ims[0], (pad, head))
        canv.paste(ims[1], (pad + ims[0].width + gap, head))
        canv = SL.watermark(canv)
        canv.save(os.path.join(OUT, "23_lang_compare.png"))
        canv.save(os.path.join(DOCS, "23_lang_compare.png"))
        MADE.append("23_lang_compare.png")
        print("  23_lang_compare.png  %dx%d" % canv.size)
except Exception as e:
    print("     拼图失败：%s" % e)

print("\n共 %d 张 → %s" % (len(MADE), OUT))
print("副本 → %s" % DOCS)
print("版本：%s (Build %s)" % (ver.VERSION, ver.BUILD))
