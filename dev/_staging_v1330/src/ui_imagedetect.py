# -*- coding: utf-8 -*-
"""「工具 → 图像检测」页（v1.30.0，反馈 2）
=========================================
用户原话：对着截图说「图片破损（整块灰色 + 顶上一条真图）亦或是没有图片（大字母 K 占位）
的情况进行检测，然后提供 -poster.jpg / -thumb.jpg / -fanart.jpg 对应上传并替换的功能」。

整页自己管自己的线程（`ImageScanWorker`），对外只暴露 `ImageDetectPage`。

为什么检测不走 Qt（写在 imagedetect.py 的模块头）
------------------------------------------------
把一张正常 JPEG 砍掉一半再让 Qt 读，它照样返回非空图像 —— libjpeg 的容错解码
把缺的部分**填成灰色**，正是截图里那块灰的来源。所以结构 Ok 与否由纯 Python 判定
（JPEG 要有 EOI / PNG 要有 IEND / 小于 1KB 一律可疑），Qt 只做 PNG 中段损坏的兜底。

线程约定（踩过 v1.27.0 的坑）
----------------------------
worker 的父对象是**页面本身**，页面又一直挂在复用的工具窗口上 → 不会被 deleteLater
连带销毁；同时在 `aboutToQuit` 上挂一次 `stop()`，保证进程退出时不会留下 running thread。
"""
import os

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QComboBox, QCheckBox, QGroupBox, QTreeWidget, QTreeWidgetItem,
                               QProgressBar, QFileDialog, QMessageBox, QSplitter, QAbstractItemView,
                               QFormLayout, QRadioButton)
from PySide6.QtGui import QPixmap

import database as db
import imagedetect as idm
import applog


class ImageScanWorker(QThread):
    """后台逐部检查缺图 / 破损图。`imagedetect.scan()` 是纯计算，直接跑在这里。

    v1.32.0（反馈 1）：接入「普通 / AI」双算法 —— 普通算法（结构校验）跑完后，
    若选的是 AI 算法且本机 Ollama 可用，再让本地模型逐条判「这条值不值得动手」。
    """

    progress = Signal(int, int, str)
    done = Signal(object)          # ImageReport
    failed = Signal(str)

    def __init__(self, library, slots, algo="normal", model="", fast=True, parent=None):
        super().__init__(parent)
        self.library = library or ""
        self.slots = tuple(slots) or idm.SLOTS
        self.algo = "ai" if algo == "ai" else "normal"
        self.model = model or ""
        self.fast = bool(fast)

    def run(self):
        try:
            rows = db.media_for_imagescan(self.library or None)
        except Exception as e:
            self.failed.emit(f"读取影片列表失败：{e}")
            return
        if not rows:
            self.done.emit(None)
            return

        def emit(i, total, msg):
            self.progress.emit(i, total, msg)

        try:
            rep = idm.scan(rows, progress=emit, library="", slots=self.slots)
        except Exception as e:
            applog.log(f"图像检测异常：{e}", "error")
            self.failed.emit(str(e))
            return
        if self.algo == "ai" and rep is not None:
            try:
                idm.review_with_ai(
                    rep, model=self.model or None, fast=self.fast,
                    progress=emit, stop=self.isInterruptionRequested)
            except Exception as e:
                # 复核失败**绝不能吞掉普通算法的结果**
                applog.log(f"图像检测：AI 复核异常：{e}", "error")
                rep.ai = {"ai": False, "done": 0, "failed": 0, "skipped": 0,
                          "jobs": 0, "fast": self.fast,
                          "note": "AI 复核出错（%s），以下为普通算法结果。" % e}
        self.done.emit(rep)


class ImageDetectPage(QWidget):
    """检测缺图 / 破损图，并逐个上传替换到 `<番号>-poster|thumb|fanart.jpg`。"""

    MAX_ROWS = 4000      # 树上最多塞多少行（再多用户也没法一个个改，先给个上限）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ImageDetectPage")
        self._worker = None
        self._report = None
        self._rows = []              # problem dict，顺序与树对齐
        self._build()
        self._reload_libraries()
        # 进程退出时兜底收线程 —— 绝不能让 QThread 在 running 状态下被销毁
        app = self._app()
        if app is not None:
            app.aboutToQuit.connect(self.stop)

    @staticmethod
    def _app():
        from PySide6.QtWidgets import QApplication
        return QApplication.instance()

    # ---------- UI ----------
    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(12)

        # --- 范围 ---
        g = QGroupBox("检测范围")
        f = QFormLayout(g)
        self.lib_box = QComboBox()
        self.lib_box.setMinimumWidth(220)
        f.addRow("媒体库：", self.lib_box)

        opt_row = QWidget()
        oh = QHBoxLayout(opt_row)
        oh.setContentsMargins(0, 0, 0, 0)
        oh.setSpacing(12)
        self.chk = {}
        for slot in idm.SLOTS:
            c = QCheckBox(idm.SLOT_CN[slot])
            c.setChecked(True)
            c.setToolTip(idm.SLOT_CN[slot])
            self.chk[slot] = c
            oh.addWidget(c)
        oh.addStretch(1)
        f.addRow("检查槽位：", opt_row)

        self.only_missing = QCheckBox("只看缺图")
        self.only_broken = QCheckBox("只看破损")
        self.only_missing.toggled.connect(lambda on: on and self.only_broken.setChecked(False))
        self.only_broken.toggled.connect(lambda on: on and self.only_missing.setChecked(False))
        state_row = QWidget()
        sh = QHBoxLayout(state_row)
        sh.setContentsMargins(0, 0, 0, 0)
        sh.setSpacing(12)
        sh.addWidget(self.only_missing)
        sh.addWidget(self.only_broken)
        sh.addStretch(1)
        f.addRow("问题类型：", state_row)
        v.addWidget(g)

        # --- v1.32.0（反馈 1）：检测方式（与「重复检测 / 演员检测」同一套写法）---
        ag = QGroupBox("检测方式")
        av = QVBoxLayout(ag)
        av.setContentsMargins(10, 8, 10, 8)
        av.setSpacing(6)
        arow = QWidget()
        arh = QHBoxLayout(arow)
        arh.setContentsMargins(0, 0, 0, 0)
        arh.setSpacing(14)
        self.rb_normal = QRadioButton("普通算法（结构校验，秒出结果）")
        self.rb_ai = QRadioButton("AI 算法（本地离线 AI 复核，较慢）")
        self.rb_normal.setChecked(True)
        for rb in (self.rb_normal, self.rb_ai):
            arh.addWidget(rb)
        self.fast_chk = QCheckBox("极速模式：只复核普通算法拿不准的条目")
        self.fast_chk.setChecked(True)
        self.fast_chk.setToolTip(
            "打开（默认）：结构完好的破损条目直接采纳普通算法结论，只把「缺图 / 过小 /"
            "比例异常」这类有疑点的送去 AI。\n"
            "关闭：全部问题都让 AI 过一遍。真机上「缺缩略图」能占七八成，全量复核要等很久。")
        arh.addWidget(self.fast_chk)
        self.ai_btn = QPushButton("检测本地 AI 引擎")
        self.ai_btn.setObjectName("Ghost")
        self.ai_btn.setCursor(Qt.PointingHandCursor)
        self.ai_btn.clicked.connect(self._probe_ai)
        arh.addWidget(self.ai_btn)
        arh.addStretch(1)
        av.addWidget(arow)
        self.ai_state = QLabel("选「AI 算法」时会自动探测本机 Ollama；"
                               "用哪个模型跟「智能推荐」页共用同一项设置。")
        self.ai_state.setWordWrap(True)
        self.ai_state.setStyleSheet("color:#8c8071;font-size:11px;")
        av.addWidget(self.ai_state)
        self.rb_ai.toggled.connect(lambda on: on and self._probe_ai())
        v.addWidget(ag)

        # --- 动作 ---
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
        # v1.33.0（反馈 1）：结果文件导入 / 导出 —— 全库 4~5 万张逐张读文件，
        # 当天没换完的导出来，第二天导入接着换，不必重新检测。
        self.exp_btn = QPushButton("导出结果文件…")
        self.exp_btn.setObjectName("Ghost")
        self.exp_btn.setCursor(Qt.PointingHandCursor)
        self.exp_btn.setToolTip("把本次检测结果存成一个 JSON，下次可导入继续处理（不必重新检测）")
        self.exp_btn.clicked.connect(self._export_result)
        ah.addWidget(self.exp_btn)
        self.imp_btn = QPushButton("导入结果文件…")
        self.imp_btn.setObjectName("Ghost")
        self.imp_btn.setCursor(Qt.PointingHandCursor)
        self.imp_btn.setToolTip("导入上次导出的检测结果，直接查看/替换/继续 AI 复核，无需重新检测")
        self.imp_btn.clicked.connect(self._import_result)
        ah.addWidget(self.imp_btn)
        self.status_lbl = QLabel("尚未检测")
        self.status_lbl.setStyleSheet("color:#a2967f;font-size:11px;")
        ah.addWidget(self.status_lbl)
        ah.addStretch(1)
        v.addWidget(act)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.bar.setVisible(False)
        v.addWidget(self.bar)

        # --- 结果 + 右侧详情 ---
        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(6)

        self.tree = QTreeWidget()
        # v1.32.0（反馈 1）：「AI 建议」列只在选了 AI 算法时才加（`_fill_tree` 里动态设表头）
        self.tree.setHeaderLabels(["影片", "槽位", "问题", "说明"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(False)      # 同「重复检测」：QSS 未定义列表交替底色，开了会白底
        self.tree.setUniformRowHeights(True)          # 上千行时显著更快
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setColumnWidth(0, 260)
        self.tree.setColumnWidth(1, 70)
        self.tree.setColumnWidth(2, 58)
        self.tree.itemSelectionChanged.connect(self._on_select)
        self.tree.itemDoubleClicked.connect(lambda *_: self._open_folder())
        split.addWidget(self.tree)

        # --- 右侧 ---
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(10, 8, 10, 8)
        rv.setSpacing(8)
        self.title_lbl = QLabel("选中左侧任一问题即可处理")
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setStyleSheet("color:#e8ddc8;font-size:13px;font-weight:700;")
        rv.addWidget(self.title_lbl)

        self.preview = QLabel()
        self.preview.setFixedSize(240, 160)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background:#1b1613;border:1px solid #3a3129;color:#8c8071;")
        rv.addWidget(self.preview, 0, Qt.AlignHCenter)

        self.meta_lbl = QLabel("")
        self.meta_lbl.setWordWrap(True)
        self.meta_lbl.setStyleSheet("color:#a2967f;font-size:11px;")
        rv.addWidget(self.meta_lbl)

        self.target_lbl = QLabel("")
        self.target_lbl.setWordWrap(True)
        self.target_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.target_lbl.setStyleSheet("color:#c9bda7;font-size:11px;")
        rv.addWidget(self.target_lbl)

        btn_row = QWidget()
        bh = QHBoxLayout(btn_row)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(8)
        self.upload_btn = QPushButton("上传替换")
        self.upload_btn.setObjectName("Primary")
        self.upload_btn.setCursor(Qt.PointingHandCursor)
        self.upload_btn.setEnabled(False)
        self.upload_btn.clicked.connect(self._upload_replace)
        bh.addWidget(self.upload_btn)
        self.folder_btn = QPushButton("打开目录")
        self.folder_btn.setObjectName("Ghost")
        self.folder_btn.setCursor(Qt.PointingHandCursor)
        self.folder_btn.setEnabled(False)
        self.folder_btn.clicked.connect(self._open_folder)
        bh.addWidget(self.folder_btn)
        btn_row.layout().addStretch(1)
        rv.addWidget(btn_row)

        tip = QLabel("替换即把选好的图片**复制**成 `<番号>-poster/thumb/fanart.jpg`"
                     "（源图不动），并同步回索引；原文件不删除。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#8c8071;font-size:11px;")
        rv.addWidget(tip)
        rv.addStretch(1)
        right.setMinimumWidth(300)
        split.addWidget(right)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 0)

        v.addWidget(split, 1)

    # ---------- 数据 ----------
    def _reload_libraries(self):
        self.lib_box.blockSignals(True)
        self.lib_box.clear()
        self.lib_box.addItem("全部媒体库", "")
        try:
            for name in db.libraries():
                self.lib_box.addItem(str(name), str(name))
        except Exception as e:
            applog.log(f"读取媒体库列表失败：{e}", "error")
        self.lib_box.blockSignals(False)

    def current_library(self) -> str:
        return str(self.lib_box.currentData() or "")

    def _slots(self):
        return tuple(s for s in idm.SLOTS if self.chk[s].isChecked())

    # ---------- 算法（v1.32.0，反馈 1） ----------
    def _algo(self):
        return "ai" if self.rb_ai.isChecked() else "normal"

    def _ai_model_name(self):
        """本地 AI 用哪个模型 —— 与「智能推荐」页共用配置。"""
        try:
            import config as cf
            return str(cf.get_settings().smart.get("ai_model") or "")
        except Exception:
            return ""

    def _probe_ai(self):
        """探测本机 Ollama，结论写进 `ai_state`（口径与另外三个检测页完全一致）。"""
        try:
            import aireview as ar
            ok, note = ar.ai_available(self._ai_model_name())
        except Exception as e:
            self.ai_state.setText("探测失败：%s" % e)
            self.ai_state.setStyleSheet("color:#e8b76a;font-size:11px;")
            return
        self.ai_state.setText(("✓ " if ok else "✗ ") + note)
        self.ai_state.setStyleSheet(
            ("color:#8fd18f;font-size:11px;" if ok else "color:#e8b76a;font-size:11px;"))

    # ---------- 检测 ----------
    def _run(self):
        if self._worker is not None and self._worker.isRunning():
            return
        slots = self._slots()
        if not slots:
            QMessageBox.information(self, "图像检测", "至少勾选一个槽位。")
            return
        self.tree.clear()
        self._rows = []
        self._report = None
        self.bar.setVisible(True)
        self.bar.setValue(0)
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        algo = self._algo()
        self.status_lbl.setText("正在读取影片列表…")
        self._worker = ImageScanWorker(self.current_library(), slots,
                                       algo=algo, model=self._ai_model_name(),
                                       fast=self.fast_chk.isChecked(), parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        app = self._app()
        if app is not None:
            app.processEvents()
        self._worker.start()

    def stop(self):
        """停止后台检测（进程退出也会走这里，避免 running thread 被析构）。"""
        w = self._worker
        if w is not None and w.isRunning():
            try:
                w.requestInterruption()
            except Exception:
                pass
            try:
                w.wait(800)
            except Exception:
                pass
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.bar.setVisible(False)

    def _on_progress(self, done, total, msg):
        try:
            self.bar.setMaximum(max(1, int(total)))
            self.bar.setValue(min(int(done), int(total)))
        except RuntimeError:
            return
        self.status_lbl.setText(str(msg))

    def _on_failed(self, msg):
        self.status_lbl.setText(f"检测失败：{msg}")
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.bar.setVisible(False)

    def _on_done(self, rep):
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.bar.setVisible(False)
        if rep is None or not rep.scanned:
            self.status_lbl.setText("没有可检测的影片。")
            return
        self._report = rep
        rows = [p for p in rep.problems if self._keep(p)]
        rows.sort(key=lambda p: ((p.get("title") or ""), p.get("slot", "")))
        self._rows = rows
        self._fill_tree(rows)
        s = rep.summary()
        shown = len(rows)
        extra = ""
        if shown > self.MAX_ROWS:
            extra = f"（树里只列出前 {self.MAX_ROWS} 条）"
        # v1.32.0（反馈 1）：算法与 AI 复核量如实写出来；AI 不可用时必须能看见原因
        algo_note = ""
        if rep.algo == "ai":
            ai = rep.ai or {}
            if ai.get("ai"):
                algo_note = (f" · AI 复核 {s['ai_done']} 条"
                             + (f"（{s['ai_skipped']} 条按极速模式跳过）"
                                if s["ai_skipped"] else "")
                             + (f" · {s['ai_failed']} 条复核失败" if s["ai_failed"] else ""))
            else:
                algo_note = " · AI 不可用，已按普通算法给出结果"
        self.status_lbl.setText(
            f"[{'AI 算法' if rep.algo == 'ai' else '普通算法'}] "
            f"扫描 {s['scanned']} 部 · 缺图 {s['missing']} 处 · 破损 {s['broken']} 处 "
            f"· 耗时 {s['elapsed']} 秒 · 当前列出 {shown} 条{extra}{algo_note}")
        if rep.algo == "ai" and s.get("ai_note"):
            self.status_lbl.setToolTip(str(s["ai_note"]))

    # ---- v1.33.0（反馈 1）：结果文件导出 / 导入 ----
    def _export_result(self):
        """把本次检测结果存成可再次导入的结果文件。"""
        rep = getattr(self, "_report", None)
        if rep is None:
            QMessageBox.information(self, "提示", "请先执行一次检测（或先导入上次的结果）。")
            return
        default = "图像检测结果.json"
        path, _sel = QFileDialog.getSaveFileName(self, "导出检测结果", default, "结果文件 (*.json)")
        if not path:
            return
        try:
            p = idm.export_json(rep, path)
            QMessageBox.information(
                self, "完成",
                f"已导出：\n{p}\n\n共 {len(rep.problems)} 条问题。"
                f"\n下次用「导入结果文件…」载入本文件，即可接着替换 / 继续 AI 复核。")
            applog.log(f"[图像检测] 已导出结果文件：{p}（{len(rep.problems)} 条）")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _import_result(self):
        """导入上次导出的结果 → 直接填结果树（不必重新检测）。"""
        path, _sel = QFileDialog.getOpenFileName(self, "导入检测结果", "",
                                                 "结果文件 (*.json);;所有文件 (*)")
        if not path:
            return
        try:
            rep = idm.import_json(path)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"{e}\n\n请确认选的是本页「导出结果文件…」"
                                                  f"产出的文件。")
            applog.log(f"[图像检测] 导入结果失败：{e}", "error")
            return
        self._on_done(rep)      # 复用正常检测完成的渲染路径
        self.status_lbl.setText(self.status_lbl.text()
                                + f"　（本结果是**导入**的：{os.path.basename(path)}）")
        applog.log(f"[图像检测] 已导入结果文件：{path}（{len(rep.problems)} 条）")
        QMessageBox.information(
            self, "导入完成",
            f"已载入 {len(rep.problems)} 条问题。\n"
            f"可以直接逐个替换配图，或切到「AI 算法」对这些结果做复核。")

    def _keep(self, p):
        if self.only_missing.isChecked() and p.get("state") != idm.MISSING:
            return False
        if self.only_broken.isChecked() and p.get("state") != idm.BROKEN:
            return False
        return True

    # ---------- 结果树 ----------
    ROLE_ROW = Qt.UserRole + 1

    _STATE_COLOR = {"缺图": "#9aa7b8", "破损": "#e8b76a"}

    def _fill_tree(self, rows):
        from PySide6.QtGui import QColor
        # v1.32.0（反馈 1）：AI 建议列只在本次用了 AI 算法时才出现
        show_ai = bool(self._report is not None and self._report.algo == "ai")
        heads = (["影片", "槽位", "问题", "AI 建议", "说明"] if show_ai
                 else ["影片", "槽位", "问题", "说明"])
        self.tree.setColumnCount(len(heads))
        self.tree.setHeaderLabels(heads)
        C_AI = 3 if show_ai else -1
        C_NOTE = 4 if show_ai else 3
        self.tree.setUpdatesEnabled(False)
        try:
            for i, p in enumerate(rows[:self.MAX_ROWS]):
                state_cn = idm.STATE_CN.get(p.get("state"), p.get("state") or "")
                ai = p.get("ai") or {}
                cells = [p.get("title") or "(无标题)",
                         p.get("slot_cn") or "",
                         state_cn]
                if show_ai:
                    cells.append(("%s（%s）" % (ai.get("advice") or "", ai.get("confidence") or ""))
                                 if ai else "—")
                cells.append(p.get("detail") or "")
                it = QTreeWidgetItem(cells)
                it.setData(0, self.ROLE_ROW, i)
                it.setToolTip(0, p.get("file_path") or "")
                it.setToolTip(C_NOTE, p.get("detail") or "")
                it.setForeground(2, QColor(self._STATE_COLOR.get(state_cn, "#c9bda7")))
                if show_ai:
                    if ai:
                        adv = ai.get("advice") or ""
                        # 「可忽略」压成暗色，「需人工核对」用琥珀色提醒，其余正常高亮
                        it.setForeground(C_AI, QColor(
                            "#8c8071" if adv == "可忽略" else
                            ("#f0c674" if adv == "需人工核对" else "#8fd18f")))
                        if ai.get("reason"):
                            it.setToolTip(C_AI, "%s\n%s" % (adv, ai["reason"]))
                    else:
                        it.setForeground(C_AI, QColor("#6b6257"))
                self.tree.addTopLevelItem(it)
        finally:
            self.tree.setUpdatesEnabled(True)
        if show_ai:
            self.tree.setColumnWidth(3, 108)

    def _current_row(self):
        items = self.tree.selectedItems()
        if not items:
            return None, None
        i = items[0].data(0, self.ROLE_ROW)
        if i is None:
            return None, None
        i = int(i)
        if not (0 <= i < len(self._rows)):
            return None, None
        item, row = items[0], self._rows[i]
        if row.get("_fixed"):
            return None, None
        return item, row

    def _on_select(self):
        _item, row = self._current_row()
        if row is None:
            self.title_lbl.setText("选中左侧任一问题即可处理")
            self.preview.setPixmap(QPixmap())
            self.preview.setText("—")
            self.meta_lbl.setText("")
            self.target_lbl.setText("")
            self.upload_btn.setEnabled(False)
            self.folder_btn.setEnabled(False)
            return
        self.title_lbl.setText(row.get("title") or "(无标题)")
        ai = row.get("ai") or {}
        ai_line = ""
        if self._report is not None and self._report.algo == "ai":
            if ai:
                ai_line = ("\nAI 建议：%s（%s）%s"
                           % (ai.get("advice") or "", ai.get("confidence") or "",
                              ("　" + (ai.get("reason") or "")) if ai.get("reason") else ""))
            else:
                ai_line = "\nAI 建议：（本次未复核此条）"
        self.meta_lbl.setText(
            f"{row.get('slot_cn')} · {idm.STATE_CN.get(row.get('state'), '')}"
            f" · {row.get('detail') or ''}"
            + (f" · {row.get('dimension')}" if row.get("dimension") else "")
            + f"\n当前图：{row.get('path') or '（无）'}" + ai_line)
        self.target_lbl.setText("将上传为：" + (row.get("target") or "（无法定位影片目录）"))
        self._show_preview(row.get("path") or "")
        self.upload_btn.setEnabled(bool(row.get("target")))
        self.folder_btn.setEnabled(bool(row.get("target")))

    def _show_preview(self, path):
        if not path or not os.path.exists(path):
            self.preview.setPixmap(QPixmap())
            self.preview.setText("无图")
            return
        pm = QPixmap(path)
        if pm.isNull():
            self.preview.setPixmap(QPixmap())
            self.preview.setText("无法解码")
            return
        self.preview.setText("")
        self.preview.setPixmap(pm.scaled(self.preview.size(), Qt.KeepAspectRatio,
                                         Qt.SmoothTransformation))

    # ---------- 替换 ----------
    def _upload_replace(self):
        _item, row = self._current_row()
        if row is None:
            return
        media = {"id": row.get("media_id"), "title": row.get("title"),
                 "file_path": row.get("file_path"), "nfo_path": ""}
        # target_path 需要 stem_of 能从 media 里推出番号；补上 nfo_path 提高命中率
        media = self._full_media(row.get("media_id"), media)
        default_dir = idm.media_dir(media) or ""
        path, _f = QFileDialog.getOpenFileName(
            self, f"选择替换「{row.get('slot_cn')}」的图片", default_dir,
            "图片文件 (*.jpg *.jpeg *.png *.webp *.bmp);;所有文件 (*.*)")
        if not path:
            return
        ok, target, err = idm.replace_image(media, row.get("slot"), path)
        if not ok:
            QMessageBox.warning(self, "替换失败", err or "未知错误")
            return
        # 同步回索引：让海报墙下一帧就用上新图
        try:
            db.update_media_fields(int(row["media_id"]), **{row.get("slot"): target})
        except Exception as e:
            applog.log(f"图像替换后同步索引失败：{e}", "error")
        row["_fixed"] = True
        row["path"] = target
        self._mark_fixed(row)
        self.status_lbl.setText(f"已替换并同步：{os.path.basename(target)}")
        self.preview.setPixmap(QPixmap(target).scaled(
            self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _full_media(self, media_id, fallback):
        """用完整行替换只有几个字段的字典（stem/target 才能算准）。"""
        try:
            m = db.get_media(int(media_id))
        except Exception:
            m = None
        if isinstance(m, dict) and m:
            m.setdefault("nfo_path", "")
            return m
        return fallback

    def _mark_fixed(self, row):
        items = self.tree.selectedItems()
        if not items:
            return
        it = items[0]
        # v1.32.0（反馈 1）：说明列的位置随「AI 建议」列是否出现而变，别再硬编码 3
        show_ai = bool(self._report is not None and self._report.algo == "ai")
        c_note = 4 if show_ai else 3
        it.setText(2, "已修复")
        it.setText(c_note, os.path.basename(row.get("path") or ""))
        f = it.font(0)
        f.setStrikeOut(True)
        for c in range(self.tree.columnCount()):
            it.setFont(c, f)

    def _open_folder(self):
        _item, row = self._current_row()
        if row is None:
            return
        d = os.path.dirname(row.get("target") or row.get("path") or "")
        if not d or not os.path.isdir(d):
            media = self._full_media(row.get("media_id"),
                                     {"file_path": row.get("file_path")})
            d = idm.media_dir(media)
        if not d or not os.path.isdir(d):
            return
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl.fromLocalFile(d))
