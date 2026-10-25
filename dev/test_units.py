# -*- coding: utf-8 -*-
"""v1.45.0：纯函数单元自检（不启动 GUI、不联网、不碰真实库）。

覆盖「最容易悄悄退化、又不需要真机」的几块：
  · duplicates 番号/标题归一化（偏好管理的匹配键）
  · scraper 假名转写 + 维基 wikitext 解析（两个实测坑的回归）
  · nfo_parser 用户评分写入 / 删除
  · prefs 导出→预览→导入（临时库，含 0 分语义）
  · i18n 工具页键完整性
  · style.qss 令牌替换与关键规则

跑法：python dev/test_units.py     全过退出 0，打印 PASS n/n
"""
import io
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

TMP = tempfile.mkdtemp(prefix="lmc_units_")
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)

import config as cfg
import database as db

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
db.init_db()

PASS = [0]
FAIL = []


def ck(label, cond, detail=""):
    PASS[0] += 1
    if cond:
        print("  [OK] " + label)
    else:
        print("  [!!] " + label + ("  (%s)" % detail if detail else ""))
        FAIL.append(label)


print("== duplicates 归一化 ==")
import duplicates as dup
ck("MIDE-823 テスト.mp4 → mide823",
   dup.extract_num("MIDE-823 テスト.mp4") == "mide823", dup.extract_num("MIDE-823 テスト.mp4"))
ck("无番号标题 → 空串", dup.extract_num("无番号的纪录片") == "")
ck("番号大小写/分隔符归一", dup.extract_num("ssis-001.mkv") == "ssis001")
ck("norm_title 去标点", dup.norm_title("ABP-123 テスト！") == "テスト",
   dup.norm_title("ABP-123 テスト！"))

print("== scraper 假名转写 / 维基解析 ==")
import scraper as sc
ck("みかみ ゆあ → mikami yua", sc.kana_to_romaji("みかみ ゆあ") == "mikami yua")
ck("片假名同等", sc.kana_to_romaji("ミカミ ユア") == "mikami yua")
ck("拗音 きょうこ → kyouko", sc.kana_to_romaji("きょうこ") == "kyouko")
WIKI = """{{Infobox YouTube personality
| years_active = [[2016年]] -
}}
{{Infobox 芸能人
| 身長 = 159
| 出身地 = [[愛知県]][[名古屋市]]
}}
'''三上悠亜'''（みかみ ゆあ、本名：'''鬼頭 桃菜'''〈きとう ももな〉<ref>2023-08-16</ref>'''、
[[1993年]]〈[[平成5年]]〉[[8月16日]]{{R|livedoor}} - ）は、日本のタレント。
身長159cm。<ref>2019年1月14日</ref>
"""
wi = sc._wiki_parse("三上悠亜", WIKI, "https://img/x.jpg", "https://ja.wikipedia.org/wiki/x")
ck("维基生日不被 ref 污染", wi["birthday"] == "1993-08-16", wi["birthday"])
ck("维基读音", wi["romaji"] == "みかみ ゆあ", wi["romaji"])
ck("维基身高", wi["meta"].get("身高") == "159cm", wi["meta"])
ck("维基头图", wi["photo_url"] == "https://img/x.jpg")

print("== nfo 用户评分 ==")
import nfo_parser as nfo
p = os.path.join(TMP, "a.nfo")
with open(p, "w", encoding="utf-8") as f:
    f.write('<?xml version="1.0"?><movie><title>A</title></movie>')
ck("写入 8.5", nfo.write_user_rating(p, 8.5) and "<userrating>8.5</userrating>"
   in io.open(p, encoding="utf-8").read())
ck("传 None 删除节点", nfo.write_user_rating(p, None)
   and "<userrating>" not in io.open(p, encoding="utf-8").read())

print("== prefs 往返（临时库） ==")
import prefs
np = os.path.join(TMP, "MIDE-823.nfo")
with open(np, "w", encoding="utf-8") as f:
    f.write('<?xml version="1.0"?><movie><title>MIDE-823</title></movie>')
conn = db.get_conn()
conn.execute("INSERT INTO media (kind,title,file_path,nfo_path,favorite,play_count,user_rating)"
             " VALUES ('movie','MIDE-823 x',?,?,1,3,9.0)", (os.path.join(TMP, "MIDE-823.mp4"), np))
conn.commit()
fp = os.path.join(TMP, "prefs.json")
r = prefs.export_prefs(fp)
ck("导出 1 部片", r.get("ok") and r.get("media") == 1, r)
conn.execute("UPDATE media SET favorite=0, user_rating=0")
conn.commit()
dry = prefs.import_prefs(fp, dry_run=True)
ck("预览不改库（favorite 仍 0）",
   dry.get("dry_run") and conn.execute("SELECT favorite FROM media").fetchone()[0] == 0)
prefs.import_prefs(fp)
row = conn.execute("SELECT favorite, play_count, user_rating FROM media").fetchone()
ck("导入恢复 收藏/观看/评分", tuple(row) == (1, 3, 9.0), tuple(row))
ck("评分写回 nfo", "<userrating>9.0</userrating>" in io.open(np, encoding="utf-8").read())

print("== i18n / QSS ==")
import i18n
ck("19 语言都有 数据管理/日志中心",
   all("数据管理" in v and "日志中心" in v for v in i18n.TOOL_KEYS.values()),
   [k for k, v in i18n.TOOL_KEYS.items() if "数据管理" not in v])
import main_window as mw
qss = mw.render_style(cfg.get_settings().appearance)
ck("无未替换令牌", not any(t in qss for t in ("__ACCENT__", "__PANEL__", "__SURF__",
                                             "__DLG__", "__VEIL__")))
ck("状态栏面板色", "background: #1c1815" in qss)
ck("版权左下/临时消息样式", "QLabel#FooterNote" in qss and "QLabel#ToastNote" in qss)
# v1.46.5（反馈 1）：状态栏进度条 —— 空闲**空槽**（轨道有边框、填充透明），
# 只有 [busy="true"] 才是高亮朱红。这条防的是「又被改回整条灰」。
ck("进度条空闲为空槽", "QProgressBar#BusyBar::chunk" in qss
   and "QProgressBar#BusyBar[busy=\"true\"]::chunk" in qss)
_seg = qss.split("QProgressBar#BusyBar::chunk")[1].split("}")[0] if \
    "QProgressBar#BusyBar::chunk" in qss else ""
ck("空槽填充为透明", "transparent" in _seg)
ck("busy 时用高亮色", "background: #" in
   qss.split('QProgressBar#BusyBar[busy="true"]::chunk')[1].split("}")[0])

# ---------------------------------------------------------------- 自定义网址规整
import scraper as _sc
ck("补 scheme", _sc.normalize_base_url("a.com") == "https://a.com")
ck("根路径不留尾巴", _sc.normalize_base_url("https://a.com/") == "https://a.com")
ck("保留路径与查询", _sc.normalize_base_url("http://a.com/b?c=1") == "http://a.com/b?c=1")
ck("无效网址判空", all(_sc.normalize_base_url(x) == ""
                     for x in ("", "  ", "localhost", "ftp://a.com", "a b")))

print()
print("PASS %d/%d" % (PASS[0] - len(FAIL), PASS[0]))
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("UNIT_ALL_OK")
