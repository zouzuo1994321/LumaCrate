# -*- coding: utf-8 -*-
"""「工具 → 演员检测」页（v1.31.0，反馈 3）
=========================================
用户原话：「在重复检测 和 图像检测 之间 增加 演员检测 功能，运用 同 标签优化 一样的
普通算法+AI算法 可选的模式。将部分 虽然是不同艺名但是可能是同一人的情况 进行检测，
检测完毕后用户可以确认并进行关联。然后下方 也提供对 演员的信息进行手动编辑的功能，
同时也能上传头像。」

页面 = 上下两块（垂直分隔条）：
- **上**：「检测方式」（普通 / AI 二选一）→ 候选树（建议合并 簇 + 存疑对）→ 右侧详情
  （成员头像 / 作品数 / 刮削资料 / 判定依据 / AI 判定 / 保留谁 / 「确认关联」）；
- **下**：「演员信息手动编辑」—— 检索任意演员 → 改姓名/别名/罗马音/生日/状态/简介 +
  meta 里的身高/尺寸/罩杯/出身地/事务所 → 上传头像 → 保存进索引。

算法与铁律写在 `actorcheck.py` 的模块头（真机数据探查出来的三条结论）。
**本页只负责把结果摆出来并执行用户点下的那一次合并**，不做任何自动改动。

线程约定（沿用 v1.27.0 的教训）
------------------------------
worker 的父对象是**页面本身**，页面一直挂在复用的工具窗口上（不会被 deleteLater 连带
销毁）；同时在 `aboutToQuit` 上挂一次 `stop()`，保证进程退出时不留 running thread。
"""
import json
import os
import re
import shutil

from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QColor, QPixmap, QDesktopServices
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QComboBox, QRadioButton, QGroupBox, QTreeWidget,
                               QTreeWidgetItem, QProgressBar, QFileDialog, QMessageBox,
                               QSplitter, QAbstractItemView, QFormLayout, QLineEdit,
                               QTextEdit, QSpinBox, QListWidget, QListWidgetItem,
                               QScrollArea, QFrame, QApplication, QCheckBox)

import actorcheck as ack
import applog
import config as cf
import database as db

AVATAR_W, AVATAR_H = 64, 84          # 候选详情里的头像尺寸
EDIT_AVATAR_W, EDIT_AVATAR_H = 108, 144


def _rich(text) -> str:
    """把 `**强调**` 转成 `<b>`（与设置窗其它页同一口径）。"""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", str(text or ""))


def _esc(text) -> str:
    return (str(text if text is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _safe_name(name) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", str(name or "")).strip()[:40] or "person"


# ---------------------------------------------------------------------------
# 后台检测
# ---------------------------------------------------------------------------
class ActorCheckWorker(QThread):
    """跑 `actorcheck.detect`（纯计算）；AI 模式再叠一层 `actorcheck.ai_review`。"""

    progress = Signal(int, int, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, algo="normal", min_works=0, model="", fast=True, parent=None):
        super().__init__(parent)
        self.algo = "ai" if algo == "ai" else "normal"
        self.min_works = int(min_works or 0)
        self.model = model or ""
        self.fast = bool(fast)

    def run(self):
        try:
            rows = db.people_for_match("Actor")
        except Exception as e:
            self.failed.emit("读取演员列表失败：%s" % e)
            return
        if not rows:
            self.done.emit(None)
            return

        def emit(i, total, msg):
            self.progress.emit(int(i), int(total), str(msg))

        try:
            res = ack.detect(rows, progress=emit,
                             stop=self.isInterruptionRequested,
                             min_works=self.min_works)
        except KeyboardInterrupt:
            self.failed.emit("已停止")
            return
        except Exception as e:
            applog.log(f"演员检测异常：{e}", "error")
            self.failed.emit(str(e))
            return

        if self.algo == "ai":
            try:
                res["ai_review"] = ack.ai_review(
                    res, model=self.model or None, fast=self.fast, progress=emit,
                    stop=self.isInterruptionRequested)
            except KeyboardInterrupt:
                res["ai_review"] = {"ai": False, "note": "AI 复核被中止。"}
            except Exception as e:
                applog.log(f"演员检测：AI 复核异常：{e}", "error")
                res["ai_review"] = {"ai": False, "note": "AI 复核出错：%s" % e}
        self.done.emit(res)


# ---------------------------------------------------------------------------
# 页面
# ---------------------------------------------------------------------------
class ActorCheckPage(QWidget):
    """演员检测 + 演员信息手动编辑。"""

    MAX_ROWS = 3000          # 树上最多塞多少行

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ActorCheckPage")
        self.setMinimumHeight(720)
        self._worker = None
        self._res = None
        self._clusters = []
        self._suspects = []
        self._people_cache = None       # 手动编辑用的演员列表（懒加载）
        self._person = None             # 当前正在编辑的人（整行）
        self._avatar_new = ""           # 本次选中的新头像（未保存前只预览）
        self._search_done = False
        self._build()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop)

    def showEvent(self, e):
        """首次显示时才去读演员列表（免得打开工具窗口就白读 5909 条）。"""
        super().showEvent(e)
        if not self._search_done:
            self._search_done = True
            self._search_people()

    # ------------------------------------------------------------------ 构建
    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(0)
        split = QSplitter(Qt.Vertical)
        split.setHandleWidth(8)
        split.addWidget(self._build_detect())
        split.addWidget(self._build_editor())
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setSizes([430, 330])
        v.addWidget(split)

    # ---------------- 上半：检测 ----------------
    def _build_detect(self):
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        g = QGroupBox("检测方式")
        gv = QVBoxLayout(g)
        hint = QLabel(_rich(
            "找出「**不同艺名、其实是同一人**」的情况：同一演员在 nfo 里写过多个艺名，"
            "索引就会建成多条 `people` 记录（各带一部分作品），合并后作品才会归到一处。\n"
            "· **普通算法**：罗马音归并 + 姓名归一化 + 别名互指，再用**生日 / 三围**交叉验证"
            "（身高、事务所基数太低，只用来判冲突）；\n"
            "· **AI 算法**：在普通算法的候选之上叠加**本地离线 AI**（Ollama）逐个复核"
            "「是不是同一个人、该保留哪个艺名」，不可用时自动降级为普通算法。\n"
            "⚠ 判定依据不足的（同罗马音但生日 / 三围互相打架 —— 典型是**同名不同人**）"
            "只会列进「存疑」，需要你自己在下方手动核对。"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#a2967f;font-size:11px;")
        gv.addWidget(hint)

        row = QWidget()
        rh = QHBoxLayout(row)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.setSpacing(14)
        self.rb_normal = QRadioButton("普通算法（本地规则，秒出结果）")
        self.rb_ai = QRadioButton("AI 算法（本地离线 AI 复核，较慢）")
        self.rb_normal.setChecked(True)
        for rb in (self.rb_normal, self.rb_ai):
            rh.addWidget(rb)
        # v1.32.0（反馈 1）：与另外三个检测页口径一致的「极速模式」。
        # 铁证 / 很高分的簇本来就是同一个人（罗马音一致 + 生日三围逐字相同），
        # 送去让模型再确认一遍纯属浪费；真机上模型一慢整页就要等好几分钟。
        self.fast_chk = QCheckBox("极速模式：只复核普通算法拿不准的簇")
        self.fast_chk.setChecked(True)
        self.fast_chk.setToolTip(
            "打开（默认）：匹配度 ≥ 80 且无冲突的簇直接采纳普通算法结论，\n"
            "只把「有用例冲突 / 分数偏低」的簇和全部存疑对送 AI 复核。\n"
            "关闭：全部候选都让 AI 过一遍（结论更全，但可能要等几分钟）。")
        rh.addWidget(self.fast_chk)
        self.rb_ai.toggled.connect(self._on_algo_changed)
        rh.addWidget(QLabel("最少作品数"))
        self.min_works = QSpinBox()
        self.min_works.setRange(0, 9999)
        self.min_works.setValue(0)
        self.min_works.setFixedWidth(74)
        self.min_works.setToolTip("只看作品数 ≥ 这个值的演员（0 = 全部）")
        rh.addWidget(self.min_works)
        self.ai_btn = QPushButton("检测本地 AI 引擎")
        self.ai_btn.setObjectName("Ghost")
        self.ai_btn.setCursor(Qt.PointingHandCursor)
        self.ai_btn.clicked.connect(self._probe_ai)
        rh.addWidget(self.ai_btn)
        rh.addStretch(1)
        gv.addWidget(row)

        self.ai_state = QLabel("点「AI 算法」或上面的按钮会检测本机 Ollama 是否可用；"
                               "用哪个模型跟「智能推荐」页共用同一项设置。")
        self.ai_state.setWordWrap(True)
        self.ai_state.setStyleSheet("color:#8c8071;font-size:11px;")
        gv.addWidget(self.ai_state)

        act = QWidget()
        ah = QHBoxLayout(act)
        ah.setContentsMargins(0, 0, 0, 0)
        ah.setSpacing(10)
        self.run_btn = QPushButton("开始检测")
        self.run_btn.setObjectName("Primary")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self._run)
        ah.addWidget(self.run_btn)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("Ghost")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        ah.addWidget(self.stop_btn)
        # v1.33.0（反馈 1）：结果文件导入 / 导出 —— 普通算法很快，但 **AI 复核很贵**
        # （逐簇问本地模型）。当天没复核完的导出来，第二天导入接着复核，
        # 已复核过的簇带着结论一起回来，不必重问。
        self.exp_btn = QPushButton("导出结果文件…")
        self.exp_btn.setObjectName("Ghost")
        self.exp_btn.setCursor(Qt.PointingHandCursor)
        self.exp_btn.setToolTip("把本次检测结果（含 AI 复核结论）存成一个 JSON，下次可导入继续处理")
        self.exp_btn.clicked.connect(self._export_result)
        ah.addWidget(self.exp_btn)
        self.imp_btn = QPushButton("导入结果文件…")
        self.imp_btn.setObjectName("Ghost")
        self.imp_btn.setCursor(Qt.PointingHandCursor)
        self.imp_btn.setToolTip("导入上次导出的检测结果，直接查看/复核/合并，无需重新检测")
        self.imp_btn.clicked.connect(self._import_result)
        ah.addWidget(self.imp_btn)
        self.status_lbl = QLabel("尚未检测")
        self.status_lbl.setStyleSheet("color:#a2967f;font-size:11px;")
        ah.addWidget(self.status_lbl)
        ah.addStretch(1)
        gv.addWidget(act)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.bar.setVisible(False)
        gv.addWidget(self.bar)
        v.addWidget(g)

        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(6)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["候选", "人数", "匹配度", "判定依据"])
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(False)     # 同「重复检测」：QSS 未定义交替底色
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setColumnWidth(0, 196)
        self.tree.setColumnWidth(1, 44)
        self.tree.setColumnWidth(2, 52)
        self.tree.itemSelectionChanged.connect(self._on_select)
        split.addWidget(self.tree)

        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setFrameShape(QFrame.NoFrame)
        # v1.31.0：工具窗默认只有 1000x801，横向分栏实测 [486, 330] —— 右栏被自己的
        # minimumWidth 卡死，树把多余空间全吃掉，结果「要动手确认关联」的右栏反而最窄。
        # QSplitter 的 stretch 只在「双方都没到最小宽」时才管用，所以只能抬右栏的最小宽。
        self.detail_scroll.setMinimumWidth(404)
        self.detail_host = QWidget()
        self.detail = QVBoxLayout(self.detail_host)
        self.detail.setContentsMargins(10, 8, 10, 8)
        self.detail.setSpacing(8)
        self.detail_scroll.setWidget(self.detail_host)
        split.addWidget(self.detail_scroll)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        split.setSizes([420, 500])
        v.addWidget(split, 1)
        self._show_detail_placeholder("点「开始检测」，左侧会列出「建议合并」的簇和「存疑」的对。")
        return wrap

    # ---------------- 下半：手动编辑 ----------------
    def _build_editor(self):
        g = QGroupBox("演员信息手动编辑（含头像上传）")
        outer = QVBoxLayout(g)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(8)
        body = QHBoxLayout()
        body.setSpacing(10)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(6)
        srow = QWidget()
        sh = QHBoxLayout(srow)
        sh.setContentsMargins(0, 0, 0, 0)
        sh.setSpacing(6)
        self.kw = QLineEdit()
        self.kw.setPlaceholderText("姓名 / 别名 / 罗马音，回车检索…")
        self.kw.returnPressed.connect(self._search_people)
        sh.addWidget(self.kw, 1)
        b = QPushButton("检索")
        b.setObjectName("Primary")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(self._search_people)
        sh.addWidget(b)
        lv.addWidget(srow)
        self.plist = QListWidget()
        self.plist.setAlternatingRowColors(False)
        self.plist.itemSelectionChanged.connect(self._on_pick_person)
        lv.addWidget(self.plist, 1)
        self.pcount = QLabel("")
        self.pcount.setStyleSheet("color:#8c8071;font-size:11px;")
        lv.addWidget(self.pcount)
        left.setMinimumWidth(230)
        left.setMaximumWidth(320)
        body.addWidget(left)

        self.edit_scroll = QScrollArea()
        self.edit_scroll.setWidgetResizable(True)
        self.edit_scroll.setFrameShape(QFrame.NoFrame)
        self.edit_host = QWidget()
        self.edit = QVBoxLayout(self.edit_host)
        self.edit.setContentsMargins(0, 0, 6, 0)
        self.edit.setSpacing(8)
        self.edit_scroll.setWidget(self.edit_host)
        body.addWidget(self.edit_scroll, 1)
        outer.addLayout(body)
        self._build_edit_form(None)
        return g

    def _build_edit_form(self, person):
        """（重）建右侧编辑表单。person=None → 占位提示。"""
        self._clear_layout(self.edit)      # 走统一的回收路径（hide + setParent(None)）
        self._fields = {}
        self._person = person
        self._avatar_new = ""
        self.save_lbl = None

        if person is None:
            lab = QLabel("← 在左边检索并选一位演员，这里会列出可编辑的资料。")
            lab.setWordWrap(True)
            lab.setStyleSheet("color:#8c8071;font-size:12px;")
            self.edit.addWidget(lab)
            self.edit.addStretch(1)
            return

        prov = ack.parse_meta(person.get("meta"))
        head = QLabel("%s　（#%s）" % (person.get("name") or "", person.get("id") or ""))
        head.setStyleSheet("font-size:14px;font-weight:700;color:#e8ddc8;")
        head.setWordWrap(True)
        self.edit.addWidget(head)

        top = QHBoxLayout()
        top.setSpacing(12)
        av_box = QVBoxLayout()
        av_box.setSpacing(5)
        self.avatar = QLabel()
        self.avatar.setFixedSize(EDIT_AVATAR_W, EDIT_AVATAR_H)
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setStyleSheet("background:#1b1613;border:1px solid #3a3129;color:#8c8071;")
        av_box.addWidget(self.avatar)
        ab = QHBoxLayout()
        ab.setSpacing(6)
        up = QPushButton("上传头像…")
        up.setObjectName("Primary")
        up.setCursor(Qt.PointingHandCursor)
        up.clicked.connect(self._pick_avatar)
        ab.addWidget(up)
        clr = QPushButton("清除")
        clr.setObjectName("Ghost")
        clr.setCursor(Qt.PointingHandCursor)
        clr.clicked.connect(self._clear_avatar)
        ab.addWidget(clr)
        av_box.addLayout(ab)
        self.avatar_path_lbl = QLabel("")
        self.avatar_path_lbl.setWordWrap(True)
        self.avatar_path_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.avatar_path_lbl.setStyleSheet("color:#8c8071;font-size:10px;")
        self.avatar_path_lbl.setMaximumWidth(EDIT_AVATAR_W + 90)
        av_box.addWidget(self.avatar_path_lbl)
        top.addLayout(av_box)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(7)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        for key, label, tip in (
                ("name", "姓名", "有唯一约束，撞名会保存失败"),
                ("alias", "别名", "多个用「、」或「,」分隔（旧艺名 / 爱称）"),
                ("romaji", "罗马音", "跨站二次检索用，也是「演员检测」的归并依据"),
                ("birthday", "生日", "YYYY-MM-DD"),
        ):
            le = QLineEdit(str(person.get(key) or ""))
            le.setToolTip(tip)
            self._fields[key] = le
            form.addRow(label, le)
        self.status_box = QComboBox()
        self.status_box.addItem("未知（按作品年份推断）", "")
        for s in ("现役", "退役"):
            self.status_box.addItem(s, s)
        idx = self.status_box.findData(str(person.get("status") or ""))
        self.status_box.setCurrentIndex(max(0, idx))
        self._fields["status"] = self.status_box
        form.addRow("状态", self.status_box)

        self.bio_edit = QTextEdit()
        self.bio_edit.setFixedHeight(64)
        self.bio_edit.setPlainText(str(person.get("bio") or ""))
        self._fields["bio"] = self.bio_edit
        form.addRow("简介", self.bio_edit)
        top.addLayout(form, 1)
        self.edit.addLayout(top)

        mg = QGroupBox("刮削资料（meta）")
        mf = QFormLayout(mg)
        mf.setContentsMargins(8, 6, 8, 6)
        mf.setSpacing(7)
        mf.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        for key, label in (("身高", "身高"), ("尺寸", "尺寸"), ("罩杯", "罩杯"),
                           ("出身地", "出身地"), ("事务所", "事务所")):
            le = QLineEdit(str(prov.get(key) or ""))
            self._fields["meta:" + key] = le
            mf.addRow(label, le)
        self.edit.addWidget(mg)

        foot = QHBoxLayout()
        foot.setSpacing(8)
        save = QPushButton("保存到索引")
        save.setObjectName("Primary")
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(self._save_person)
        foot.addWidget(save)
        rel = QPushButton("重新载入")
        rel.setObjectName("Ghost")
        rel.setCursor(Qt.PointingHandCursor)
        rel.clicked.connect(lambda: self._load_person(self._person.get("id")
                                                      if self._person else None))
        foot.addWidget(rel)
        opend = QPushButton("打开头像目录")
        opend.setObjectName("Ghost")
        opend.setCursor(Qt.PointingHandCursor)
        opend.clicked.connect(self._open_avatar_dir)
        foot.addWidget(opend)
        foot.addStretch(1)
        self.save_lbl = QLabel("")
        self.save_lbl.setStyleSheet("color:#8c8071;font-size:11px;")
        foot.addWidget(self.save_lbl)
        self.edit.addLayout(foot)
        self.edit.addStretch(1)
        self._refresh_avatar()

    @staticmethod
    def _clear_layout(lay):
        """拆掉一个布局里的所有内容。

        注意：`takeAt()` 只是把控件**移出布局**，它的父对象还是宿主 —— 父对象不会替它
        抹掉已经画上去的像素，而 `deleteLater()` 要等下一次事件循环才真正回收
        （离屏 `processEvents()` 甚至根本不派发 `DeferredDelete`）。结果是旧内容
        **当场留在原地**，新内容再叠上去 —— 右栏那截「…存疑」的对。」就这么来的。
        所以必须先 `hide()` + `setParent(None)` 让它立刻脱离父子链。
        """
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
            elif item.layout() is not None:
                ActorCheckPage._clear_layout(item.layout())

    # ------------------------------------------------------------------ 数据
    def _algo(self) -> str:
        return "ai" if self.rb_ai.isChecked() else "normal"

    def _on_algo_changed(self, on):
        if on:
            self._probe_ai()

    def _probe_ai(self):
        try:
            import aireview as ar
            ok, note = ar.ai_available(self._ai_model_name())
        except Exception as e:
            ok, note = False, "探测失败：%s" % e
        self.ai_state.setText(("✅ " if ok else "⚠ ") + note)
        self.ai_state.setStyleSheet(
            "color:%s;font-size:11px;" % ("#7fdca0" if ok else "#e8b76a"))
        if not ok and self.rb_ai.isChecked():
            self.ai_state.setText("⚠ " + note + "（本次会按普通算法给出结果）")

    def _ai_model_name(self):
        """本地 AI 用哪个模型 —— 与「智能推荐」页共用配置，绝不各存一份。"""
        try:
            return str(cf.get_settings().smart.get("ai_model") or "")
        except Exception:
            return ""

    def _people(self):
        if self._people_cache is None:
            try:
                self._people_cache = db.people_for_match("Actor")
            except Exception as e:
                applog.log(f"演员检测：读取演员列表失败：{e}", "error")
                self._people_cache = []
        return self._people_cache

    # ------------------------------------------------------------------ 检测
    def _run(self):
        if self._worker is not None and self._worker.isRunning():
            return
        self.tree.clear()
        self._clusters = []
        self._suspects = []
        self._res = None
        self.bar.setVisible(True)
        self.bar.setValue(0)
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_lbl.setText("正在读取演员列表…")
        algo = self._algo()
        if algo == "ai":
            self._probe_ai()
        self._worker = ActorCheckWorker(algo=algo, min_works=self.min_works.value(),
                                        model=self._ai_model_name(),
                                        fast=self.fast_chk.isChecked(), parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        app = QApplication.instance()
        if app is not None:
            app.processEvents()
        self._worker.start()

    def stop(self):
        """停止后台检测（进程退出也走这里，避免 running thread 被析构）。"""
        w = self._worker
        if w is not None and w.isRunning():
            try:
                w.requestInterruption()
            except Exception:
                pass
            try:
                w.wait(1200)
            except Exception:
                pass
        try:
            self.run_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.bar.setVisible(False)
        except RuntimeError:
            pass

    def _on_progress(self, done, total, msg):
        try:
            self.bar.setMaximum(max(1, int(total)))
            self.bar.setValue(min(int(done), int(total)))
            self.status_lbl.setText(str(msg))
        except RuntimeError:
            return

    def _on_failed(self, msg):
        self.status_lbl.setText("检测失败：%s" % msg)
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.bar.setVisible(False)

    def _on_done(self, res):
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.bar.setVisible(False)
        if res is None:
            self.status_lbl.setText("演员库是空的，先扫描媒体库吧。")
            return
        self._res = res
        self._clusters = list(res.get("clusters") or [])
        self._suspects = list(res.get("suspects") or [])
        self._fill_tree()
        ai = res.get("ai_review") or {}
        tail = ""
        if ai.get("note"):
            tail = "　·　" + str(ai["note"])
        elif ai.get("done"):
            tail = "　·　AI 复核 %d 处（失败 %d）" % (ai.get("done", 0), ai.get("failed", 0))
        self.status_lbl.setText(
            "%d 位演员 · %d 对候选 · 建议合并 %d 簇（可省 %d 条记录）· 存疑 %d 对 · "
            "耗时 %s 秒%s"
            % (res.get("scanned", 0), res.get("pairs", 0), len(self._clusters),
               res.get("merge_people", 0), len(self._suspects), res.get("elapsed", 0), tail))

    # ---- v1.33.0（反馈 1）：结果文件导出 / 导入 ----
    def _export_result(self):
        """把本次检测结果（含 AI 复核结论）存成可再次导入的结果文件。"""
        res = getattr(self, "_res", None)
        if res is None:
            QMessageBox.information(self, "提示", "请先执行一次检测（或先导入上次的结果）。")
            return
        default = "演员检测结果.json"
        path, _sel = QFileDialog.getSaveFileName(self, "导出检测结果", default, "结果文件 (*.json)")
        if not path:
            return
        try:
            p = ack.export_json(res, path)
            n_ai = sum(1 for c in (res.get("clusters") or []) if c.get("ai"))
            QMessageBox.information(
                self, "完成",
                f"已导出：\n{p}\n\n"
                f"建议合并 {len(res.get('clusters') or [])} 簇 · 存疑 "
                f"{len(res.get('suspects') or [])} 对"
                + (f" · 其中 {n_ai} 簇带 AI 复核结论" if n_ai else "")
                + "\n\n下次用「导入结果文件…」载入，即可接着复核 / 合并，不必重新检测。")
            applog.log(f"[演员检测] 已导出结果文件：{p}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _import_result(self):
        """导入上次导出的结果 → 直接填结果树（不必重新检测）。"""
        path, _sel = QFileDialog.getOpenFileName(self, "导入检测结果", "",
                                                 "结果文件 (*.json);;所有文件 (*)")
        if not path:
            return
        try:
            res = ack.import_json(path)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"{e}\n\n请确认选的是本页「导出结果文件…」"
                                                  f"产出的文件。")
            applog.log(f"[演员检测] 导入结果失败：{e}", "error")
            return
        self._on_done(res)      # 复用正常检测完成的渲染路径（树 / 状态栏 / AI 标记）
        self.status_lbl.setText(self.status_lbl.text()
                                + f"　（本结果是**导入**的：{os.path.basename(path)}）")
        applog.log(f"[演员检测] 已导入结果文件：{path}"
                   f"（{len(res.get('clusters') or [])} 簇）")
        QMessageBox.information(
            self, "导入完成",
            f"已载入 {len(res.get('clusters') or [])} 簇建议合并、"
            f"{len(res.get('suspects') or [])} 对存疑。\n"
            f"可以直接逐簇复核 / 合并。")

    # ------------------------------------------------------------------ 结果树
    ROLE_KIND = Qt.UserRole + 1
    ROLE_INDEX = Qt.UserRole + 2

    _TIER_COLOR = {"铁证": "#7fdca0", "很高": "#9fd6b0", "高": "#e8d27a",
                   "存疑": "#e8b76a"}

    def _fill_tree(self):
        self.tree.setUpdatesEnabled(False)
        try:
            self.tree.clear()
            root_m = QTreeWidgetItem(["建议合并（%d 簇，共可减少 %d 条演员记录）"
                                      % (len(self._clusters),
                                         self._res.get("merge_people", 0) if self._res else 0),
                                      "", "", ""])
            root_s = QTreeWidgetItem(["存疑（%d 对，仅提示，请人工核对）"
                                      % len(self._suspects), "", "", ""])
            for r in (root_m, root_s):
                f = r.font(0)
                f.setBold(True)
                r.setFont(0, f)
                r.setForeground(0, QColor("#d4af37"))
                self.tree.addTopLevelItem(r)

            for i, c in enumerate(self._clusters[:self.MAX_ROWS]):
                names = [m["name"] for m in c.get("members") or []]
                label = " / ".join(names[:4]) + ("…" if len(names) > 4 else "")
                it = QTreeWidgetItem([label, "%d 人" % len(c.get("ids") or []),
                                      "%d %s" % (c["score"], c["tier"]),
                                      (c.get("reasons") or [""])[0]])
                it.setData(0, self.ROLE_KIND, "cluster")
                it.setData(0, self.ROLE_INDEX, i)
                it.setToolTip(0, " / ".join(names))
                it.setToolTip(3, "\n".join(c.get("reasons") or []))
                it.setForeground(2, QColor(self._TIER_COLOR.get(c["tier"], "#c9bda7")))
                if not c.get("profile_consistent", True):
                    it.setForeground(0, QColor("#e8b76a"))
                    it.setToolTip(0, " / ".join(names) + "\n⚠ 簇内刮削资料有互相矛盾的地方")
                root_m.addChild(it)

            for i, s in enumerate(self._suspects[:self.MAX_ROWS]):
                it = QTreeWidgetItem(["%s ↔ %s" % (s["a"]["name"], s["b"]["name"]),
                                      "2 人", "%d %s" % (s["score"], s["tier"]),
                                      (s.get("reasons") or [""])[0]])
                it.setData(0, self.ROLE_KIND, "suspect")
                it.setData(0, self.ROLE_INDEX, i)
                it.setToolTip(3, "\n".join(s.get("reasons") or []))
                it.setForeground(2, QColor(self._TIER_COLOR.get("存疑", "#e8b76a")))
                root_s.addChild(it)
            if not self._clusters:
                root_m.addChild(QTreeWidgetItem(["（没有达到自动关联标准的候选）", "", "", ""]))
            if not self._suspects:
                root_s.addChild(QTreeWidgetItem(["（没有需要人工核对的存疑对）", "", "", ""]))
            # ⚠ 展开必须在**子节点加完之后**再设：`QTreeWidgetItem.setExpanded(True)` 在
            # 项目还没进视图 / 还没有子节点时调用是空操作，等第一个子节点插进来 Qt 会把它
            # 重置回收起。写在前面的话，真机上跑完检测看到的是两个收起的根，
            # 得先手点一下才能看到候选（离屏测试也测不出来，因为两边都是「没展开」）。
            root_m.setExpanded(True)
            root_s.setExpanded(True)
        finally:
            self.tree.setUpdatesEnabled(True)

    def _current(self):
        """返回 `(kind, 对象, 下标)`；没选中返回 `(None, None, None)`。"""
        items = self.tree.selectedItems()
        if not items:
            return None, None, None
        it = items[0]
        kind = it.data(0, self.ROLE_KIND)
        idx = it.data(0, self.ROLE_INDEX)
        if kind is None or idx is None:
            return None, None, None
        idx = int(idx)
        if kind == "cluster" and 0 <= idx < len(self._clusters):
            return kind, self._clusters[idx], idx
        if kind == "suspect" and 0 <= idx < len(self._suspects):
            return kind, self._suspects[idx], idx
        return None, None, None

    # ------------------------------------------------------------------ 详情
    def _show_detail_placeholder(self, text):
        self._clear_layout(self.detail)
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setStyleSheet("color:#8c8071;font-size:12px;")
        self.detail.addWidget(lab)
        self.detail.addStretch(1)

    def _on_select(self):
        kind, obj, idx = self._current()
        if obj is None:
            self._show_detail_placeholder("点「开始检测」，左侧会列出「建议合并」的簇和"
                                          "「存疑」的对。")
            return
        self._clear_layout(self.detail)
        if kind == "cluster":
            self._detail_cluster(obj, idx)
        else:
            self._detail_suspect(obj, idx)

    def _member_block(self, m, extra=""):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(10)
        pic = QLabel()
        pic.setFixedSize(AVATAR_W, AVATAR_H)
        pic.setAlignment(Qt.AlignCenter)
        pic.setStyleSheet("background:#1b1613;border:1px solid #3a3129;color:#8c8071;"
                          "font-size:10px;")
        path = m.get("photo") or ""
        if path and os.path.exists(path):
            pm = QPixmap(path)
            if not pm.isNull():
                pic.setPixmap(pm.scaled(pic.size(), Qt.KeepAspectRatio,
                                        Qt.SmoothTransformation))
            else:
                pic.setText("无法解码")
        else:
            pic.setText("无头像")
        h.addWidget(pic)
        col = QVBoxLayout()
        col.setSpacing(2)
        nm = QLabel(_rich("%s　**%d** 部" % (_esc(m["name"]), m["works"])))
        nm.setTextFormat(Qt.RichText)
        nm.setStyleSheet("color:#e8ddc8;font-size:12px;")
        nm.setWordWrap(True)
        col.addWidget(nm)
        rom = QLabel("罗马音：%s" % (_esc(m["romaji"]) or "—"))
        rom.setStyleSheet("color:#a2967f;font-size:11px;")
        rom.setWordWrap(True)
        col.addWidget(rom)
        pf = []
        for k in ("生日", "尺寸", "身高", "事务所"):
            if m["prof"].get(k):
                pf.append("%s %s" % (k, m["prof"][k]))
        pl = QLabel("　·　".join(pf) or "刮削资料：—")
        pl.setStyleSheet("color:#a2967f;font-size:11px;")
        pl.setWordWrap(True)
        col.addWidget(pl)
        if m.get("alias_raw"):
            al = QLabel("别名：" + _esc(m["alias_raw"]))
            al.setStyleSheet("color:#8c8071;font-size:11px;")
            al.setWordWrap(True)
            col.addWidget(al)
        if extra:
            ex = QLabel(extra)
            ex.setStyleSheet("color:#7fdca0;font-size:11px;")
            ex.setWordWrap(True)
            col.addWidget(ex)
        h.addLayout(col, 1)
        return w

    def _detail_cluster(self, c, idx):
        head = QLabel("建议合并：%d 人（共 %d 部作品）" % (len(c["ids"]), c["total_works"]))
        head.setStyleSheet("color:#e8ddc8;font-size:13px;font-weight:700;")
        head.setWordWrap(True)
        self.detail.addWidget(head)

        badge = QLabel("匹配度 %d · %s" % (c["score"], c["tier"]))
        badge.setStyleSheet(
            "color:%s;font-size:11px;font-weight:700;"
            % self._TIER_COLOR.get(c["tier"], "#c9bda7"))
        self.detail.addWidget(badge)

        ai = c.get("ai")
        if ai:
            same = ai.get("same")
            verdict = "同一人" if same else ("不是同一人" if same is False else "无法判定")
            raw = ("AI 复核：**%s**（置信度 %s）%s\n%s"
                   % (verdict, _esc(ai.get("confidence") or "—"),
                      ("　建议保留「%s」" % _esc(ai.get("keep")))
                      if ai.get("keep") else "",
                      _esc(ai.get("reason") or "")))
            box = QLabel(_rich(raw))
            box.setTextFormat(Qt.RichText)
            box.setWordWrap(True)
            box.setStyleSheet("color:%s;font-size:11px;background:#1b1613;"
                              "border:1px solid #3a3129;padding:6px;"
                              % ("#7fdca0" if same else "#e8b76a"))
            self.detail.addWidget(box)

        # v1.31.0：动作行提到最前面 —— 详情区是个滚动区，3 人以上的簇光成员块就有 270px+，
        # 动作行原来排在成员块 / 理由 / 别名之后会掉到折叠线以下，等于「主操作藏起来了」。
        # 先给动作、再给证据，滚不滚都点得到。
        prow = QWidget()
        ph = QHBoxLayout(prow)
        ph.setContentsMargins(0, 0, 0, 0)
        ph.setSpacing(8)
        ph.addWidget(QLabel("保留："))
        self.keep_box = QComboBox()
        self.keep_box.setMinimumWidth(170)
        for m in c["members"]:
            self.keep_box.addItem("%s（%d 部）" % (m["name"], m["works"]), m["id"])
        ki = self.keep_box.findData(c["keep_id"])
        self.keep_box.setCurrentIndex(max(0, ki))
        ph.addWidget(self.keep_box, 1)
        self.detail.addWidget(prow)

        brow = QWidget()
        bh = QHBoxLayout(brow)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(8)
        go = QPushButton("确认关联（合并）")
        go.setObjectName("Primary")
        go.setCursor(Qt.PointingHandCursor)
        go.clicked.connect(lambda _c=False, cc=c, ii=idx: self._merge(cc, ii))
        bh.addWidget(go)
        tip = QPushButton("全部不合并")
        tip.setObjectName("Ghost")
        tip.setCursor(Qt.PointingHandCursor)
        tip.setToolTip("把这一簇标成「已忽略」，本次不再提示")
        tip.clicked.connect(lambda _c=False, ii=idx: self._dismiss(ii))
        bh.addWidget(tip)
        bh.addStretch(1)
        self.detail.addWidget(brow)

        for m in c["members"]:
            extra = ""
            if m["id"] == c["keep_id"]:
                extra = "★ 默认保留（作品最多 / 有头像）"
            self.detail.addWidget(self._member_block(m, extra))

        if c.get("conflicts"):
            wl = QLabel("⚠ 簇内存在矛盾：%s" % "；".join(c["conflicts"][:4]))
            wl.setWordWrap(True)
            wl.setStyleSheet("color:#e8b76a;font-size:11px;")
            self.detail.addWidget(wl)

        rl = QLabel("判定依据：\n· " + "\n· ".join(_esc(r) for r in (c.get("reasons") or ["—"])))
        rl.setWordWrap(True)
        rl.setStyleSheet("color:#a2967f;font-size:11px;")
        self.detail.addWidget(rl)

        if c.get("alias_union"):
            au = QLabel("合并后别名会写成：%s" % _esc(c["alias_union"]))
            au.setWordWrap(True)
            au.setStyleSheet("color:#8c8071;font-size:11px;")
            self.detail.addWidget(au)

        note = QLabel()
        note.setTextFormat(Qt.RichText)
        note.setWordWrap(True)
        note.setText(_rich(
            "合并会把其余人的作品关联搬到保留者名下（「%s」会被写成保留者的别名），"
            "并删除多余记录。**不会动任何视频 / nfo 文件**。"
            % _esc(c.get("alias_union") or "")))
        note.setStyleSheet("color:#8c8071;font-size:11px;")
        self.detail.addWidget(note)
        self.detail.addStretch(1)

    def _detail_suspect(self, s, idx):
        head = QLabel("存疑：可能同名不同人，未给出合并建议")
        head.setStyleSheet("color:#e8b76a;font-size:13px;font-weight:700;")
        head.setWordWrap(True)
        self.detail.addWidget(head)
        badge = QLabel("匹配度 %d（未达自动关联标准）" % s["score"])
        badge.setStyleSheet("color:#e8b76a;font-size:11px;")
        self.detail.addWidget(badge)
        ai = s.get("ai")
        if ai:
            same = ai.get("same")
            box = QLabel(_rich("AI 复核：**%s**（置信度 %s）%s"
                               % ("同一人" if same else ("不是同一人" if same is False
                                                        else "无法判定"),
                                  _esc(ai.get("confidence") or "—"),
                                  _esc(ai.get("reason") or ""))))
            box.setTextFormat(Qt.RichText)
            box.setWordWrap(True)
            box.setStyleSheet("color:#c9bda7;font-size:11px;")
            self.detail.addWidget(box)
        self.detail.addWidget(self._member_block(s["a"]))
        self.detail.addWidget(self._member_block(s["b"]))
        rl = QLabel("判定依据：\n· " + "\n· ".join(_esc(r) for r in (s.get("reasons") or ["—"])))
        rl.setWordWrap(True)
        rl.setStyleSheet("color:#a2967f;font-size:11px;")
        self.detail.addWidget(rl)
        hint = QLabel()
        hint.setTextFormat(Qt.RichText)
        hint.setWordWrap(True)
        hint.setText(_rich(
            "这类只做提示，**不提供自动合并**。如果确认是同一个人，请到下方"
            "「演员信息手动编辑」把资料改成一致（或把其中一个的姓名改成另一个），"
            "再重新检测 —— 资料一致后就会进「建议合并」。"))
        hint.setStyleSheet("color:#8c8071;font-size:11px;")
        self.detail.addWidget(hint)
        pick = QPushButton("在下方编辑其中一位")
        pick.setObjectName("Ghost")
        pick.setCursor(Qt.PointingHandCursor)
        pick.clicked.connect(lambda: self._load_person(s["a"]["id"]))
        self.detail.addWidget(pick, 0, Qt.AlignLeft)
        self.detail.addStretch(1)

    # ------------------------------------------------------------------ 合并
    def _merge(self, cluster, idx=None):
        keep_id = self.keep_box.currentData() if hasattr(self, "keep_box") else None
        keep_id = int(keep_id or cluster["keep_id"])
        drops = [i for i in cluster["ids"] if i != keep_id]
        if not drops:
            return
        keep_name = next((m["name"] for m in cluster["members"] if m["id"] == keep_id), "")
        names = [m["name"] for m in cluster["members"] if m["id"] in drops]
        q = QMessageBox(self)
        q.setWindowTitle("确认关联")
        q.setIcon(QMessageBox.Question)
        q.setText("要把这 %d 个艺名合并到「%s」吗？" % (len(drops), keep_name))
        q.setInformativeText(
            "将删除 %d 条演员记录：%s\n\n"
            "· 它们的作品关联会搬到「%s」名下（同一部片不会重复计入）；\n"
            "· 缺失的生日 / 罗马音 / 头像 / 简介会补齐（**已有值不覆盖**）；\n"
            "· 被合并的名字会写进「%s」的别名；\n"
            "· 视频与 nfo 文件**不受影响**。\n\n此操作不可撤销。"
            % (len(drops), "、".join(names), keep_name, keep_name))
        # 破坏性操作：默认按钮设成 No，避免手快回车
        q.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        q.setDefaultButton(QMessageBox.No)
        if q.exec() != QMessageBox.Yes:
            return

        moved = 0
        done, errors = [], []
        for pid in drops:
            try:
                r = db.merge_people(keep_id, pid)
            except Exception as e:
                applog.log(f"演员合并异常：{e}", "error")
                errors.append(str(e))
                continue
            if r.get("ok"):
                moved += int(r.get("moved") or 0)
                done.append(pid)
            else:
                errors.append(r.get("err") or "未知错误")
        self._people_cache = None          # 库里变了 → 手动编辑列表要重取
        if done:
            applog.log("[演员检测] 合并到「%s」：%s（搬移作品关联 %d 条）"
                       % (keep_name, "、".join(names), moved))
            self._mark_cell(idx, "已合并", "→ " + keep_name)
            self.tree.setCurrentItem(None)
            self._show_detail_placeholder(
                "已把 %s 合并到「%s」（搬移作品关联 %d 条）。"
                % ("、".join(names), keep_name, moved)
                + ("\n部分失败：%s" % "；".join(errors) if errors else ""))
        if errors and not done:
            QMessageBox.warning(self, "合并失败", "；".join(errors))

    def _mark_cell(self, idx, state, detail=""):
        """把树上那一行标成已处理（划掉）。按 `idx` 定位，避免重复簇误伤。"""
        if idx is None:
            return
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                it = top.child(j)
                if it.data(0, self.ROLE_KIND) == "cluster" and \
                        it.data(0, self.ROLE_INDEX) == idx:
                    it.setText(2, state)
                    it.setText(3, detail)
                    f = it.font(0)
                    f.setStrikeOut(True)
                    for cc in range(4):
                        it.setFont(cc, f)
                    return

    def _dismiss(self, idx):
        self._mark_cell(idx, "已忽略")
        self.tree.setCurrentItem(None)
        self._show_detail_placeholder("已忽略这一簇（本次不再提示）。")

    # ------------------------------------------------------------------ 手动编辑
    def _search_people(self):
        kw = (self.kw.text() or "").strip().casefold()
        rows = self._people()
        if kw:
            def hit(p):
                hay = "%s\n%s\n%s" % (p.get("name") or "", p.get("alias") or "",
                                      p.get("romaji") or "")
                return kw in hay.casefold()
            rows = [p for p in rows if hit(p)]
        rows = sorted(rows, key=lambda p: -(p.get("works") or 0))
        self.plist.blockSignals(True)
        self.plist.clear()
        for p in rows[:self.MAX_ROWS]:
            it = QListWidgetItem("%s    %s 部" % (p.get("name") or "", p.get("works") or 0))
            it.setData(Qt.UserRole, int(p.get("id") or 0))
            if p.get("alias"):
                it.setToolTip("别名：" + str(p["alias"]))
            self.plist.addItem(it)
        self.plist.blockSignals(False)
        tail = "（只列出前 %d 条）" % self.MAX_ROWS if len(rows) > self.MAX_ROWS else ""
        self.pcount.setText("共 %d 位%s" % (len(rows), tail))

    def _on_pick_person(self):
        items = self.plist.selectedItems()
        if not items:
            return
        self._load_person(items[0].data(Qt.UserRole))

    def _load_person(self, pid):
        if not pid:
            return
        try:
            p = db.get_person(int(pid))
        except Exception as e:
            applog.log(f"演员检测：读取演员失败：{e}", "error")
            return
        if not p:
            return
        self._build_edit_form(p)

    def _refresh_avatar(self, path=""):
        path = path or (self._person or {}).get("photo_path") or \
            (self._person or {}).get("thumb") or ""
        if path and os.path.exists(path):
            pm = QPixmap(path)
            if not pm.isNull():
                self.avatar.setText("")
                self.avatar.setPixmap(pm.scaled(self.avatar.size(), Qt.KeepAspectRatio,
                                                Qt.SmoothTransformation))
            else:
                self.avatar.setPixmap(QPixmap())
                self.avatar.setText("无法解码")
        else:
            self.avatar.setPixmap(QPixmap())
            self.avatar.setText("无头像")
        self.avatar_path_lbl.setText(path or "（尚未设置头像）")

    def _pick_avatar(self):
        if not self._person:
            return
        start = os.path.dirname((self._person.get("photo_path") or "").strip()) or ""
        path, _f = QFileDialog.getOpenFileName(
            self, "选择头像图片", start,
            "图片文件 (*.jpg *.jpeg *.png *.webp *.bmp);;所有文件 (*.*)")
        if not path:
            return
        self._avatar_new = path
        self._refresh_avatar(path)
        self.avatar_path_lbl.setText("（待保存）" + path)
        if self.save_lbl is not None:
            self.save_lbl.setText("已选好新头像，点「保存到索引」写入。")

    def _clear_avatar(self):
        if not self._person:
            return
        self._avatar_new = ""
        self._person["photo_path"] = ""
        self._person["thumb"] = ""
        self._refresh_avatar("")
        if self.save_lbl is not None:
            self.save_lbl.setText("已清空头像预览，点「保存到索引」生效。")

    def _open_avatar_dir(self):
        try:
            d = cf.get_settings().scraper_photo_dir()
        except Exception:
            d = ""
        if not d or not os.path.isdir(d):
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(d))

    def _copy_avatar(self, person_id, name, src):
        """把选中的图片复制进头像缓存目录，命名与刮削保持一致：`<id>_<名字>.<ext>`。"""
        try:
            d = cf.get_settings().scraper_photo_dir()
        except Exception as e:
            return "", "读取头像目录失败：%s" % e
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:
            return "", "头像目录不可写：%s" % e
        ext = os.path.splitext(src)[1].lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
            ext = ".jpg"
        dest = os.path.join(d, "%s_%s%s" % (person_id, _safe_name(name), ext))
        try:
            shutil.copy2(src, dest)
        except Exception as e:
            return "", "复制头像失败：%s" % e
        return dest, ""

    def _save_person(self):
        p = self._person
        if not p:
            return
        pid = int(p["id"])
        fields = {}
        for key, w in self._fields.items():
            if key.startswith("meta:"):
                continue
            if isinstance(w, QTextEdit):
                fields[key] = w.toPlainText().strip()
            elif isinstance(w, QComboBox):
                fields[key] = w.currentData() or ""
            else:
                fields[key] = w.text().strip()
        if not fields.get("name"):
            QMessageBox.warning(self, "无法保存", "姓名不能为空。")
            return
        # meta：在原 JSON 上改，不动其它键
        meta = ack.parse_meta(p.get("meta"))
        for key, w in self._fields.items():
            if not key.startswith("meta:"):
                continue
            k = key.split(":", 1)[1]
            v = w.text().strip()
            if v:
                meta[k] = v
            else:
                meta.pop(k, None)
        try:
            fields["meta"] = json.dumps(meta, ensure_ascii=False) if meta else ""
        except Exception:
            fields.pop("meta", None)

        # 头像：先落盘再写库，失败就不改库
        if self._avatar_new and self._avatar_new != (p.get("photo_path") or ""):
            dest, err = self._copy_avatar(pid, fields["name"], self._avatar_new)
            if err:
                QMessageBox.warning(self, "头像未保存", err)
            else:
                fields["photo_path"] = dest
                fields["thumb"] = dest

        try:
            n = db.set_person_fields(pid, **fields)
        except Exception as e:
            txt = str(e)
            if "UNIQUE" in txt.upper():
                QMessageBox.warning(self, "无法保存",
                                    "已经有一位叫「%s」的演员了 —— 姓名有唯一约束。\n"
                                    "如果你认为他们其实是同一人，请在「建议合并」里关联。"
                                    % fields["name"])
            else:
                applog.log(f"演员检测：保存失败：{e}", "error")
                QMessageBox.critical(self, "保存失败", txt)
            return
        self._people_cache = None
        msg = "已保存 %d 个字段（索引已更新）" % n
        self._load_person(pid)          # 重建表单（会重置 save_lbl）
        if self.save_lbl is not None:
            self.save_lbl.setText(msg)
        applog.log("[演员检测] 手动编辑已保存 #%s %s（%d 个字段）"
                   % (pid, fields["name"], n))
