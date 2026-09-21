# -*- coding: utf-8 -*-
"""v1.23.0 离屏冒烟：重复检测 / 演员详情页 ☆▲·状态按钮 / exe 图标 / 品牌平齐 / 版本号。

约定：先 patch db.db_path 到临时目录、重定向 applog，**绝不碰真实索引**。
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LMC_NO_BACKDROP"] = "1"

TMP = tempfile.mkdtemp(prefix="lmc_smoke1230_")
os.makedirs(os.path.join(TMP, "index_data"), exist_ok=True)

import database as db                      # noqa: E402
db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")

import applog                              # noqa: E402
applog.log_dir = lambda: os.path.join(TMP, "logs")

import version as ver                      # noqa: E402

FAIL = []


def check(name, cond, extra=""):
    tag = "PASS" if cond else "FAIL"
    print(f"{tag} {name}" + (f"   -> {extra}" if (extra and not cond) else ""))
    if not cond:
        FAIL.append(name)


# ---------------------------------------------------------------------------
# A. 版本号
# ---------------------------------------------------------------------------
check("A1 VERSION=v1.23.0", ver.VERSION == "v1.23.0", ver.VERSION)
check("A2 BUILD=2609200030", ver.BUILD == "2609200030", ver.BUILD)

db.init_db()

# ---------------------------------------------------------------------------
# B. duplicates 归一化辅助
# ---------------------------------------------------------------------------
import duplicates as dup                    # noqa: E402

check("B1 norm_num(MSVD-700)=msvd700", dup.norm_num("MSVD-700") == "msvd700", dup.norm_num("MSVD-700"))
check("B2 extract_num from filename", dup.extract_num(r"Y:\x\ABC-123.mp4") == "abc123",
      dup.extract_num(r"Y:\x\ABC-123.mp4"))
check("B3 纯中文标题不误判番号", dup.extract_num("无番号片.mp4") == "", dup.extract_num("无番号片.mp4"))
check("B4 title_key 去番号+年份", dup.title_key("MSVD-700 标题", "", 2020).endswith("::2020")
      and "msvd" not in dup.title_key("MSVD-700 标题", "", 2020),
      dup.title_key("MSVD-700 标题", "", 2020))
check("B5 human_size(1GiB)=1.00 GB", dup.human_size(1073741824) == "1.00 GB", dup.human_size(1073741824))
check("B6 _runtime_sec(02:07:55)=7675", dup._runtime_sec("02:07:55") == 7675, dup._runtime_sec("02:07:55"))
check("B7 human_duration(7675)=2小时7分", dup.human_duration(7675) == "2小时7分", dup.human_duration(7675))

# ---------------------------------------------------------------------------
# C. find_duplicates 端到端
# ---------------------------------------------------------------------------
MB = 1048576


def add(lib, path, size, **kw):
    f = {"kind": "movie", "title": os.path.splitext(os.path.basename(path))[0],
         "sort_title": os.path.splitext(os.path.basename(path))[0],
         "file_path": path, "file_size": size, "library": lib, "runtime": "01:00:00"}
    f.update(kw)
    return db.insert_media(**f)


# g1：ABC-123 在 2 个目录（体积不同 → 高，冗余 = 总 - 最大份）
add("L", r"L:\A\ABC-123\ABC-123.mp4", 1000 * MB, year=2020)
add("L", r"L:\B\ABC-123\ABC-123.mp4", 500 * MB, year=2020)
# g2：XYZ-777 同一目录两份（分片，应排除）
add("L", r"L:\C\XYZ-777\XYZ-777-CD1.mp4", 300 * MB, year=2019)
add("L", r"L:\C\XYZ-777\XYZ-777-CD2.mp4", 300 * MB, year=2019)
# g3：无番号 → 标题+年份 → 中
add("L", r"L:\D\无番号片\无番号片.mp4", 200 * MB, year=2021)
add("L", r"L:\E\无番号片\无番号片.mp4", 250 * MB, year=2021)
# g4：DUP-001 跨 3 个目录、体积完全一致 → 极高，copies=3
add("L", r"L:\F\DUP-001\DUP-001.mp4", 700 * MB, year=2018)
add("L", r"L:\G\DUP-001\DUP-001.mp4", 700 * MB, year=2018)
add("L", r"L:\H\DUP-001\DUP-001.mp4", 700 * MB, year=2018)

rep = dup.find_duplicates()
s = rep.summary()
bykey = {g.key: g for g in rep.groups}

check("C1 重复组=3（g1/g3/g4；g2 是分片被排除）", len(rep.groups) == 3, [g.key for g in rep.groups])
check("C2 同目录分片=1（XYZ-777）", len(rep.multipart) == 1 and rep.multipart[0].key == "xyz777",
      [g.key for g in rep.multipart])
g1 = bykey.get("abc123")
check("C3 g1 份数=2/冗余=1", g1 and g1.copies == 2 and g1.redundant_copies == 1,
      g1 and (g1.copies, g1.redundant_copies))
check("C4 g1 可回收=500MB（总1500-最大1000）", g1 and g1.redundant_bytes == 500 * MB,
      g1 and g1.redundant_bytes)
check("C5 g1 置信度=高（番号一致、体积不同）", g1 and g1.confidence == "高", g1 and g1.confidence)
g4 = bykey.get("dup001")
check("C6 g4 跨 3 目录份数=3/冗余=2", g4 and g4.copies == 3 and g4.redundant_copies == 2,
      g4 and (g4.copies, g4.redundant_copies))
check("C7 g4 体积全一致 → 极高", g4 and g4.confidence == "极高", g4 and g4.confidence)
# 冗余份数 = 各组(份数-1)之和 = g1(1) + g3(1) + g4(2) = 4；分片组不计入冗余
check("C8 summary: 重复3组/冗余4份/分片1组", s["dup_groups"] == 3 and s["redundant_copies"] == 4
      and s["multipart_groups"] == 1 and s["dup_movies"] == 7, s)
g3 = [g for g in rep.groups if g.kind == "title"]
check("C9 标题+年份组 kind=title 置信度=中", len(g3) == 1 and g3[0].confidence == "中",
      [(g.kind, g.confidence) for g in rep.groups])

# 置信度过滤：只看 高 及以上 → 排除 中 的 g3
rep2 = dup.find_duplicates(min_confidence="高")
check("C10 min_confidence=高 过滤掉 中", all(g.confidence in ("高", "极高") for g in rep2.groups)
      and len(rep2.groups) == 2, [g.confidence for g in rep2.groups])

# 库过滤：换一个空库名 → 0 组
rep3 = dup.find_duplicates(library="__nope__")
check("C11 library 过滤生效", len(rep3.groups) == 0 and rep3.scanned == 0, rep3.summary())

# 导出
csv_p = os.path.join(TMP, "dup.csv")
json_p = os.path.join(TMP, "dup.json")
dup.export_csv(rep, csv_p)
dup.export_json(rep, json_p)
check("C12 export_csv 落盘且含表头", os.path.exists(csv_p)
      and "重复组汇总" in open(csv_p, encoding="utf-8-sig").read(), csv_p)
check("C13 export_json 落盘且可解析", os.path.exists(json_p)
      and '"duplicate"' not in open(json_p, encoding="utf-8").read()
      and '"groups"' in open(json_p, encoding="utf-8").read(), json_p)

# ---------------------------------------------------------------------------
# D. UI：演员详情页 ☆/▲ + 状态按钮 + 设置页
# ---------------------------------------------------------------------------
from PySide6.QtWidgets import QApplication, QPushButton   # noqa: E402
from PySide6.QtGui import QFontDatabase                    # noqa: E402

app = QApplication.instance() or QApplication([])
for _f in (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import main_window as mw                                   # noqa: E402
mw.load_style(app)
from ui_hero import compact_button                        # noqa: E402

# D1 方法存在
check("D1 MainWindow._toggle_actor_fav/_toggle_actor_pin 存在",
      hasattr(mw.MainWindow, "_toggle_actor_fav") and hasattr(mw.MainWindow, "_toggle_actor_pin"))

# D2 compact_button 带上 compact 属性（状态按钮裁切修复的前提）
cb = compact_button("现役", 60, 26, ghost=False)
check("D2 compact_button: compact=1 / 60x26",
      cb.property("compact") == "1" and cb.width() == 60 and cb.height() == 26,
      (cb.property("compact"), cb.size().toTuple()))

# D3 构造主窗口 → 演员详情页：状态按钮 + ☆/▲ 齐全且状态按钮带 compact
pid = db.upsert_person("测试演员")
db.update_person(pid, only_missing=False, status="退役")
try:
    win = mw.MainWindow(logo_path=os.path.join(ROOT, "logo.png"))
    # 注意：_view_actor_detail 是「构建器」，返回的页面是 detached（parent=None），
    # 必须经 self.go() 挂进 stack 成为窗口子孙，否则 win.findChildren 永远搜不到（同 _wall_page 坑）。
    win.go(lambda _p=pid: win._view_actor_detail(_p))
    page = win.stack.currentWidget()
    btns = [b for b in win.findChildren(QPushButton)]
    texts = [b.text() for b in btns]
    status_btns = [b for b in btns if b.text() in ("现役", "退役", "未知")]
    check("D3a 详情页含 现役/退役/未知 三按钮", len(status_btns) == 3, texts[-12:])
    check("D3b 状态按钮带 compact 且高 26（不被 padding 裁）",
          bool(status_btns) and all(b.property("compact") == "1" and b.height() == 26
                                    for b in status_btns),
          [(b.text(), b.property("compact"), b.height()) for b in status_btns])
    # 名字旁的收藏/置顶：按「精确文案」判定，避免被侧栏「我的收藏」误命中
    fav_hit = [t for t in texts if t in ("☆ 收藏", "★ 已收藏")]
    pin_hit = [t for t in texts if t in ("△ 置顶", "▲ 已置顶")]
    check("D4 详情页名字旁有 ☆收藏 / △置顶", len(fav_hit) == 1 and len(pin_hit) == 1,
          (fav_hit, pin_hit, [t for t in texts if "收藏" in t or "置顶" in t]))
    # 与 people 数据同步：切换收藏
    before = bool(db.get_person(pid).get("favorite"))
    win._toggle_actor_fav(pid)
    after = bool(db.get_person(pid).get("favorite"))
    check("D5 _toggle_actor_fav 翻转 people.favorite", before != after, (before, after))
    win._toggle_actor_pin(pid)
    check("D6 _toggle_actor_pin 翻转 people.pinned", bool(db.get_person(pid).get("pinned")) is True,
          db.get_person(pid).get("pinned"))
except Exception as e:
    check(f"D3~D6 主窗口/详情页构造（异常：{type(e).__name__}: {e}）", False)

# D7 设置页：重复检测页存在且在 服务管理 之后、数据与日志 之前
try:
    import ui_settings as us
    keys = ["个性化设置", "演员刮削", "服务管理", "重复检测", "数据与日志"]
    check("D7a SettingsDialog 有 _build_dedupe/_run_dedupe/_on_dedupe_done/_export_dedupe",
          all(hasattr(us.SettingsDialog, m) for m in
              ("_build_dedupe", "_run_dedupe", "_on_dedupe_done", "_export_dedupe")))
    check("D7b 重复检测 排在 服务管理 与 数据与日志 之间",
          keys.index("服务管理") < keys.index("重复检测") < keys.index("数据与日志"))
except Exception as e:
    check(f"D7 设置页（异常：{type(e).__name__}: {e}）", False)

# ---------------------------------------------------------------------------
# E. 打包脚本：--icon 与 duplicates 隐藏导入
# ---------------------------------------------------------------------------
be = open(os.path.join(ROOT, "build_exe.py"), encoding="utf-8").read()
check("E1 build_exe.py 含 --icon", '"--icon"' in be)
check("E2 build_exe.py 含 --hidden-import duplicates", '"duplicates"' in be)
check("E3 logo.ico 存在且是多档 ico", os.path.exists(os.path.join(ROOT, "logo.ico")))

# ---------------------------------------------------------------------------
print("\n==== v1.23.0 冒烟结果：%s ====" % ("ALL PASS" if not FAIL else f"{len(FAIL)} FAIL"))
if FAIL:
    for f in FAIL:
        print("  FAIL:", f)
sys.exit(0 if not FAIL else 1)
