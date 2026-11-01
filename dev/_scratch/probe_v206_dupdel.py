# -*- coding: utf-8 -*-
"""v2.0.6 探针 ②：重复检测结果的「打开 / 定位 / 删除（含确认是否删源文件）」。

临时库 + 临时目录，删的也只是探针自己造的文件（走回收站）。
"""
import os
import shutil
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["LMC_NO_SYSMON"] = "1"
ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

TMP = tempfile.mkdtemp(prefix="lmc_probe_v206dup_")
os.makedirs(os.path.join(TMP, "index_data", "logs"), exist_ok=True)

from PySide6.QtWidgets import QApplication, QDialog   # noqa: E402
from PySide6.QtGui import QFontDatabase               # noqa: E402
from PySide6.QtCore import Qt                         # noqa: E402

app = QApplication(sys.argv)
for _f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc"):
    if os.path.exists(_f):
        QFontDatabase.addApplicationFont(_f)

import database as db          # noqa: E402
import config as cfg           # noqa: E402
import applog                  # noqa: E402

db.db_path = lambda: os.path.join(TMP, "index_data", "media_center.db")
cfg.config_path = lambda: os.path.join(TMP, "settings.json")
cfg._SETTINGS = None
applog.base_dir = lambda: TMP
db.init_db()

import duplicates as dup       # noqa: E402
import main_window as mw       # noqa: E402
import ui_settings as uis      # noqa: E402

mw.load_style(app)

FAIL = []


def ck(cond, label, extra=""):
    print(("PASS  " if cond else "FAIL  ") + label + (("   " + str(extra)) if extra else ""))
    if not cond:
        FAIL.append(label)


# ---------- 造两条「不同目录、同一部片」 ----------
LIB = os.path.join(TMP, "lib")
A = os.path.join(LIB, "A", "ID-063")
B = os.path.join(LIB, "B", "ID-063")
C = os.path.join(LIB, "C", "OTHER-001")
for d in (A, B, C):
    os.makedirs(d, exist_ok=True)


def mkvideo(d, name, size=2048):
    p = os.path.join(d, name)
    with open(p, "wb") as fh:
        fh.write(b"\0" * size)
    return p


VA = mkvideo(A, "ID-063.mp4")
VB = mkvideo(B, "ID-063.mp4")
VC = mkvideo(C, "OTHER-001.mp4")


def add(path, title):
    return db.insert_media(title=title, kind="movie", year=2016, rating=7.0,
                           file_path=path, library="探针库", sort_title=title)


mA = add(VA, "ID-063 测试片")
mB = add(VB, "ID-063 测试片")
mC = add(VC, "OTHER-001 别的片")

rep = dup.find_duplicates(verify_exists=True, exclude_multipart=True)
ck(len(rep.groups) == 1, "检出 1 个重复组", len(rep.groups))
ck(rep.groups and len(rep.groups[0].members) == 2, "组里 2 份副本",
   len(rep.groups[0].members) if rep.groups else 0)

# ---------- 建真实的工具窗（离屏），把结果填进树 ----------
dlg = uis.SettingsDialog(None)
dlg._dd_report = rep
dlg._dd_removed = set()
dlg._fill_dedupe_tree(rep)

ck(dlg.dd_tree.topLevelItemCount() == 1, "树里 1 个分组行", dlg.dd_tree.topLevelItemCount())
top = dlg.dd_tree.topLevelItem(0)
ck(top.childCount() == 2, "分组行下 2 个成员行", top.childCount())
ck(top.data(0, Qt.UserRole) == (rep.groups[0].members[0].path),
   "分组行也带路径（= 体积最大的那一份）")

# ---------- 四个操作按钮：没选中时全灰 ----------
ck(all(not b.isEnabled() for b in (dlg.dd_play, dlg.dd_reveal, dlg.dd_open_dir, dlg.dd_del)),
   "初始四枚按钮都不可点")
dlg.dd_tree.setCurrentItem(top.child(1))
app.processEvents()
ck(all(b.isEnabled() for b in (dlg.dd_play, dlg.dd_reveal, dlg.dd_open_dir, dlg.dd_del)),
   "选中一行后四枚按钮都可点")
ck(dlg._dd_current_path() == rep.groups[0].members[1].path, "能取到选中行的路径",
   dlg._dd_current_path())

# ---------- 删除：勾选「同时删除源文件」 ----------
_victim = rep.groups[0].members[1].path
ck(os.path.exists(_victim), "删除前文件在")

_seen = {}


class _AutoDlg:
    """替身：自动点「删除」，并记下它收到的参数。"""

    def __init__(self, targets, kind, in_db=None, parent=None):
        _seen["targets"] = list(targets)
        _seen["kind"] = kind
        _seen["in_db"] = list(in_db or [])
        self.delete_source = _seen["delete_source"]

    def exec(self):
        return QDialog.Accepted


_orig_dialog = uis.DupDeleteDialog
uis.DupDeleteDialog = _AutoDlg
try:
    _seen["delete_source"] = True
    dlg._dedupe_delete_file()
finally:
    uis.DupDeleteDialog = _orig_dialog

ck(_seen["kind"] == "file" and _seen["targets"] == [_victim], "删除文件时把路径原样交给确认框",
   (_seen["kind"], _seen["targets"]))
ck(not os.path.exists(_victim), "源文件已删除（进回收站）")
ck(db.media_id_by_path(_victim) is None, "索引里那条记录也没了")
ck(db.get_media(mC) is not None, "别的片没被误删")

# 结果树：该组只剩 1 份 → 整组从树里消失（不再是「跨目录重复」）
ck(dlg.dd_tree.topLevelItemCount() == 0, "删到只剩一份后，该重复组从结果树移除",
   dlg.dd_tree.topLevelItemCount())
ck("源文件已移入回收站" in dlg.dd_status.text(), "状态栏写清了怎么删的", dlg.dd_status.text())

# ---------- 删除：不勾选（只移除索引） ----------
rep2 = dup.find_duplicates(verify_exists=True, exclude_multipart=True)
ck(len(rep2.groups) == 0, "此时已没有重复组", len(rep2.groups))

# 再造一组，验证「只移除索引、文件留着」
D = os.path.join(LIB, "D", "ID-077")
E = os.path.join(LIB, "E", "ID-077")
for d in (D, E):
    os.makedirs(d, exist_ok=True)
VD = mkvideo(D, "ID-077.mp4")
VE = mkvideo(E, "ID-077.mp4")
mD = add(VD, "ID-077 另一部")
mE = add(VE, "ID-077 另一部")

rep = dup.find_duplicates(verify_exists=True, exclude_multipart=True)
dlg._dd_report = rep
dlg._dd_removed = set()
dlg._fill_dedupe_tree(rep)
top = dlg.dd_tree.topLevelItem(0)
dlg.dd_tree.setCurrentItem(top.child(1))
app.processEvents()

uis.DupDeleteDialog = _AutoDlg
try:
    _seen["delete_source"] = False
    dlg._dedupe_delete_file()
finally:
    uis.DupDeleteDialog = _orig_dialog

ck(os.path.exists(VE), "不勾选时源文件仍在磁盘上")
ck(db.media_id_by_path(VE) is None, "但索引记录已移除")
ck("仅移除索引" in dlg.dd_status.text(), "状态栏写明只动了索引", dlg.dd_status.text())

# ---------- 删除文件夹 ----------
VX = mkvideo(os.path.join(LIB, "A", "ID-063"), "extra.mp4")   # A 目录里再放一个
mX = add(VX, "ID-063 附加")
ck(os.path.isdir(A), "文件夹删除前存在")
uis.DupDeleteDialog = _AutoDlg
try:
    _seen["delete_source"] = True
    dlg._dedupe_do_delete(A, "folder")
finally:
    uis.DupDeleteDialog = _orig_dialog
ck(not os.path.isdir(A), "文件夹已被删除（进回收站）")
ck(db.media_id_by_path(VX) is None, "该文件夹下的影片索引也清了")
ck(_seen["kind"] == "folder", "确认框按「文件夹」来处理", _seen["kind"])

# ---------- 文本层面：确认框问的确实是「是否删除源文件」 ----------
_d = uis.DupDeleteDialog([VA], "file", [VA], None)
ck("同时删除源文件" in _d.chk.text(), "确认框有一个「同时删除源文件」勾选框", _d.chk.text())
ck(_d.chk.isChecked(), "默认勾选（用户点的就是删除）")
ck(_d.chk.isChecked() == _d.delete_source, "delete_source 跟着勾选走")
_d.chk.setChecked(False)
ck(_d.delete_source is False, "取消勾选后 delete_source=False")
ck("磁盘上的文件保持不动" in _d.tip.text(), "取消勾选时说明「文件保持不动」", _d.tip.text())
ck("移入回收站" in _d.chk.text(), "文案明确写了回收站（可还原）")
_d.close()

print()
print("FAILED:", FAIL if FAIL else "无")
print("ALL_OK" if not FAIL else "HAS_FAILURE")
shutil.rmtree(TMP, ignore_errors=True)
