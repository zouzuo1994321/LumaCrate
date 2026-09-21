# -*- coding: utf-8 -*-
"""v1.19.0 逻辑验证：反馈 99 / 100 / 101
- 99：多 CD 选集用「选集基名」nfo（SAVR-1144-8K.nfo），扫描应能匹配并回填年份/时长/片商/演员
- 100：RateDialog 点「确定」必须把 spinbox 当前值回写 self.value
- 101：设置窗口「运行日志（实时）」实时读取 app.log 尾部内容
"""
import os
import sys
import tempfile
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC = r"Z:\【01】自研软件\【26-19】本地影视中心\src"
sys.path.insert(0, SRC)

TMP = tempfile.mkdtemp(prefix="lmc_v119_")
DBP = os.path.join(TMP, "index_data", "media_center.db")

import database as db
db.db_path = lambda: DBP
db.init_db()

import scanner as scanner_mod

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  -> {detail}" if detail else ""))


# ---------------- 反馈 99：选集基名 nfo 匹配 ----------------
vr = os.path.join(TMP, "VR", "SAVR-1144-8K【弥生みづき】")
os.makedirs(vr)
nfo_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  <title>SAVR-1144-8K 测试选集</title>
  <year>2026</year>
  <runtime>78</runtime>
  <studio>KMPVR-彩-</studio>
  <genre>VR</genre>
  <genre>自定义</genre>
  <premiered>2026-09-05</premiered>
  <actor>
    <name>弥生みづき</name>
    <role>主演</role>
  </actor>
</movie>
"""
with open(os.path.join(vr, "SAVR-1144-8K.nfo"), "w", encoding="utf-8") as f:
    f.write(nfo_xml)
for cd in (1, 2):
    open(os.path.join(vr, f"SAVR-1144-8K-cd{cd}.mp4"), "wb").close()
open(os.path.join(vr, "SAVR-1144-8K-cd1-poster.jpg"), "wb").close()
open(os.path.join(vr, "SAVR-1144-8K-cd1-fanart.jpg"), "wb").close()

counts = scanner_mod.scan_library(vr, None, library_name="VR测试")
scanner_mod.group_cd_sets(vr)

tops = db.search_media(top_only=True, limit=50)
rep = next((m for m in tops if "SAVR-1144" in (m.get("title") or "")), None)
check("99.扫描产出顶层记录", rep is not None, f"title={rep['title'] if rep else None}")
if rep:
    check("99.年份已回填", rep.get("year") == 2026, f"year={rep.get('year')}")
    check("99.时长已回填", bool(rep.get("runtime")), f"runtime={rep.get('runtime')}")
    check("99.片商已回填", rep.get("studio") == "KMPVR-彩-", f"studio={rep.get('studio')}")
    cast = db.get_cast(rep["id"])
    check("99.演员已回填", len(cast) >= 1, f"actors={[c['name'] for c in cast]}")
    # 子片应挂在代表下
    parts = db.search_media(top_only=False, limit=50)
    children = [m for m in parts if m.get("parent_id") == rep["id"]]
    check("99.子片归组到代表", len(children) >= 1, f"children={len(children)}")


# ---------------- 反馈 100：RateDialog 回写 ----------------
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from ui_hero import RateDialog
dlg = RateDialog(None, None)
dlg.spin.setValue(8.5)
dlg._ok()
check("100.确定写入分值", dlg.value == 8.5, f"value={dlg.value}")
dlg2 = RateDialog(None, 5.0)
dlg2._clear()
check("100.清除写入 None", dlg2.value is None, f"value={dlg2.value}")


# ---------------- 反馈 101：运行日志实时显示 ----------------
import applog
TEST_LOG = os.path.join(TMP, "index_data", "logs", "app.log")
os.makedirs(os.path.dirname(TEST_LOG), exist_ok=True)
with open(TEST_LOG, "w", encoding="utf-8") as f:
    f.write("2026-09-19 12:00:00 [INFO] 软件启动\n")
    f.write("2026-09-19 12:00:01 [INFO] 扫描进行中：已处理 12345/50000 部 (24%)\n")
    f.write("2026-09-19 12:00:02 [INFO] 正在关联演员\n")
# 大日志尾部截断：写入 300KB 历史 + 最新一行，验证只取尾部
with open(TEST_LOG, "a", encoding="utf-8") as f:
    for i in range(4000):
        f.write(f"2026-09-19 12:00:0{i % 10} [DEBUG] 历史日志填充行 {i}\n")
    f.write("2026-09-19 12:05:00 [INFO] 最新进度：已处理 49999/50000 部 (99%)\n")

applog.log_path = lambda: TEST_LOG   # 重定向到测试日志
from ui_settings import SettingsDialog
sd = SettingsDialog(None)
sd._refresh_log()
txt = sd._log_view.toPlainText()
check("101.日志框非空", len(txt.strip()) > 0, f"len={len(txt)}")
check("101.显示最新进度", "已处理 49999/50000" in txt, "")
check("101.截断历史行", "历史日志填充行 0" not in txt, "早期历史应被截断")

# 资源清理
try:
    sd.deleteLater()
except Exception:
    pass

failed = [n for n, ok, _ in results if not ok]
print("\n==== 结果 ====")
print("ALL PASS" if not failed else f"FAILED: {failed}")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if not failed else 1)
