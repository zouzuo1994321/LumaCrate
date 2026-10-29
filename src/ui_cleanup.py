# -*- coding: utf-8 -*-
"""演员库清理（v1.43.0）
========================
删除**没有任何作品关联**（works=0）的演员 / 导演记录 —— 反复刮削、改名、
合并、删片之后最容易堆下来的冗余条目。

边界（刻意保守）：
  · 只删**索引记录**（people + media_people 关联），不动头像文件、不动任何媒体文件；
  · 默认**排除收藏 / 置顶**的人（那是用户主动留下的，不算冗余）；
  · 列表默认**全部不勾选**，必须自己勾或点「全选」才会删 —— 不给「一进来就误删」的机会。
"""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QCheckBox, QDialog, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout,
                               QWidget)

import applog
import database as db
import version as ver


class PeopleCleanDialog(QDialog):
    def __init__(self, parent=None, on_done=None):
        super().__init__(parent)
        self.setWindowTitle("演员库清理")
        self.setModal(True)
        self.resize(760, 560)
        self._on_done = on_done
        self._rows = []
        self._build()
        self.reload()

    # ---------- UI ----------
    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 14)
        v.setSpacing(10)

        title = QLabel("演员库清理 · 删除没有任何作品关联的冗余条目")
        title.setStyleSheet("font-size:15px;font-weight:bold;color:#ecedee;")
        v.addWidget(title)

        hint = QLabel(
            "这些条目在索引里存在，但没有任何影片关联（反复刮削 / 改名 / 合并 / 删片后的残留）。\n"
            "删除只清索引记录（people 与作品关联），不会动头像文件，也不会动任何媒体文件；"
            "收藏 / 置顶的人默认不列入。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#a1a1aa;font-size:11px;")
        v.addWidget(hint)

        row = QWidget()
        rh = QHBoxLayout(row)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.setSpacing(12)
        self.ck_actor = QCheckBox("演员库")
        self.ck_actor.setChecked(True)
        self.ck_actor.toggled.connect(self.reload)
        self.ck_director = QCheckBox("导演库")
        self.ck_director.setChecked(True)
        self.ck_director.toggled.connect(self.reload)
        rh.addWidget(QLabel("清理范围："))
        rh.addWidget(self.ck_actor)
        rh.addWidget(self.ck_director)
        rh.addStretch(1)
        self.count_lbl = QLabel("—")
        self.count_lbl.setStyleSheet("color:#a1a1aa;font-size:11px;")
        rh.addWidget(self.count_lbl)
        v.addWidget(row)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.NoSelection)
        # 只连一次（reload 反复调用，若在 reload 里 connect 会重复叠加）
        self.list.itemChanged.connect(self._update_sel)
        v.addWidget(self.list, 1)

        btns = QHBoxLayout()
        btns.setContentsMargins(0, 0, 0, 0)
        btns.setSpacing(8)
        b_all = QPushButton("全选")
        b_all.setObjectName("Ghost")
        b_all.clicked.connect(lambda: self._set_all(True))
        b_none = QPushButton("全不选")
        b_none.setObjectName("Ghost")
        b_none.clicked.connect(lambda: self._set_all(False))
        # v1.45.5（反馈 3）：清理口径（无作品 / 无头像 / 无任何资料 / 无性别）
        self.kind = QComboBox()
        for _k, _lab in db.CLEANUP_KINDS:
            self.kind.addItem(_lab, _k)
        self.kind.currentIndexChanged.connect(lambda *_: self.reload())
        btns.addWidget(self.kind)
        b_csv = QPushButton("导出清单…")
        b_csv.setObjectName("Ghost")
        b_csv.clicked.connect(self._export_csv)
        btns.addWidget(b_csv)
        b_re = QPushButton("重新检测")
        b_re.setObjectName("Ghost")
        b_re.clicked.connect(self.reload)
        self.del_btn = QPushButton("删除所选…")
        self.del_btn.setObjectName("Primary")
        self.del_btn.clicked.connect(self._delete)
        btns.addWidget(b_all)
        btns.addWidget(b_none)
        btns.addWidget(b_re)
        btns.addStretch(1)
        self.sel_lbl = QLabel("已选 0 项")
        self.sel_lbl.setStyleSheet("color:#71717a;font-size:11px;")
        btns.addWidget(self.sel_lbl)
        btns.addWidget(self.del_btn)
        v.addLayout(btns)

    def _export_csv(self):
        """v1.45.5：把当前清单导出 CSV（删除前留证）。"""
        import csv
        import os
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        if not getattr(self, "_rows", None):
            QMessageBox.information(self, "提示", "当前没有可导出的条目。")
            return
        default = os.path.join(os.path.expanduser("~"), "演员库清理清单.csv")
        path, _ = QFileDialog.getSaveFileName(self, "导出清理清单", default, "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["姓名", "类型", "口径", "作品数", "头像", "性别", "来源", "刮削时间"])
                for p in self._rows:
                    w.writerow([p.get("name"), p.get("role_type"),
                                self.kind.currentText(),
                                p.get("works"), "有" if (p.get("photo_path") or "").strip() else "无",
                                p.get("gender") or "", p.get("source") or "",
                                p.get("scraped_at") or ""])
            QMessageBox.information(self, "已导出", path)
        except Exception as e:
            applog.log(f"导出清理清单失败：{e}", "error")
            QMessageBox.warning(self, "导出失败", str(e))

    def showEvent(self, e):
        super().showEvent(e)
        try:
            import backdrop
            backdrop.auto_apply(self)
        except Exception:
            pass

    # ---------- 数据 ----------
    def reload(self):
        roles = []
        if self.ck_actor.isChecked():
            roles.append("Actor")
        if self.ck_director.isChecked():
            roles.append("Director")
        self._rows = []
        for r in roles:
            try:
                self._rows.extend(db.people_for_cleanup(self.kind.currentData() or "orphan", r))
            except Exception as e:
                applog.log(f"演员库清理：查询 {r} 失败（{e}）", "error")
        self.list.clear()
        for p in self._rows:
            name = p.get("name") or "(无名)"
            role = "演员" if p.get("role_type") == "Actor" else "导演"
            has_photo = bool((p.get("photo_path") or "").strip())
            _kind = self.kind.currentData() or "orphan"
            _tag = {"orphan": "无作品", "nophoto": "无头像", "empty": "无资料",
                    "nogender": "无性别"}.get(_kind, "无作品")
            bits = [name, role, _tag, "有头像" if has_photo else "无头像"]
            it = QListWidgetItem("　·　".join(bits))
            it.setData(Qt.UserRole, p.get("id"))
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            self.list.addItem(it)
        n = len(self._rows)
        self.count_lbl.setText(f"共发现 {n} 条无作品记录" if n else "没有需要清理的记录")
        self._update_sel()

    def _update_sel(self, *_):
        n = len(self._checked_ids())
        self.sel_lbl.setText(f"已选 {n} 项")
        self.del_btn.setEnabled(n > 0)

    def _checked_ids(self):
        out = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.checkState() == Qt.Checked:
                out.append(it.data(Qt.UserRole))
        return out

    def _set_all(self, on):
        state = Qt.Checked if on else Qt.Unchecked
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(state)
        self.list.blockSignals(False)
        self._update_sel()

    def _delete(self):
        ids = self._checked_ids()
        if not ids:
            return
        msg = (f"确认删除 {len(ids)} 条没有任何作品关联的记录？\n\n"
               "只清索引记录（人物与其作品关联），不会删除头像文件，也不会动任何媒体文件；"
               "此操作不可撤销。")
        if QMessageBox.question(self, "删除确认", msg) != QMessageBox.Yes:
            return
        try:
            n = db.delete_people(ids)
        except Exception as e:
            applog.log(f"演员库清理失败：{e}", "error")
            QMessageBox.warning(self, "删除失败", str(e))
            return
        applog.log(f"演员库清理：删除 {n} 条无作品记录（{ver.FULL_VERSION}）")
        QMessageBox.information(self, "清理完成", f"已删除 {n} 条冗余记录。")
        self.reload()
        if self._on_done:
            self._on_done()
