# -*- coding: utf-8 -*-
"""「工具 → 手动修改」页（v1.30.0，反馈 3）
=========================================
用户原话：「检索并选择某在数据库中的影片，提供最全的 nfo 可编辑窗口和
-poster.jpg / -thumb.jpg / -fanart.jpg 对应上传功能，最后编辑完毕可以保存。」

左：**检索**（标题关键词）→ 结果列表；右：**三槽位配图 + 全字段表单 + 演员块**。

读写落点是 `nfo_editor`（那里已经处理了「同名 <actor> 节点复用」「写前自动备份」
「其它节点与缩进不动」这些脏活），本文件只负责把值搬进 Qt 控件、再搬回来。

为什么以 `db.get_media(id)` 的整行为锚
--------------------------------------
保存既要写 nfo（需要 nfo_path），也要同步索引（需要 id）；配图还需要 file_path
算出 `<番号>-poster.jpg` 的落盘位置 —— 三者都在这同一行里。
"""
import os

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QComboBox, QListWidget, QListWidgetItem, QLineEdit,
                               QTextEdit, QGroupBox, QFileDialog, QMessageBox,
                               QFormLayout, QFrame, QScrollArea)
from PySide6.QtGui import QPixmap, QDesktopServices

import database as db
import imagedetect as idm
import nfo_editor as nf
import applog

#: 演员行格式：`姓名` 或 `姓名 | 角色`
_ACTOR_SEP = "|"
_W = 150          # 配图预览宽


def _make_widget(kind, value):
    """按字段类型造控件：multiline → QTextEdit；multi → 逗号分隔的 QLineEdit。"""
    if kind == "multiline":
        w = QTextEdit()
        w.setFixedHeight(96)
        w.setPlainText(str(value or ""))
        return w
    if kind == "multi":
        txt = ", ".join(str(v) for v in value) if isinstance(value, (list, tuple)) else str(value or "")
        le = QLineEdit(txt)
        le.setPlaceholderText("多个用逗号分隔")
        return le
    return QLineEdit(str(value or ""))


class ManualEditPage(QWidget):
    """检索选片 → 编辑 nfo → 换图 → 保存。"""

    SEARCH_LIMIT = 300

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ManualEditPage")
        self._media = None            # 当前选中的 media 行（dict）
        self._host = None             # 右栏当前的根 widget（换片时整块重建）
        self._fields = {}             # key -> widget
        self._slot_labels = {}
        self._actors_edit = None
        self.save_lbl = None
        self._build_shell()
        QTimer.singleShot(0, self._search)

    # ---------- 外壳（左右分裂） ----------
    def _build_shell(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(8)
        lb = QLabel("检索并选择影片")
        lb.setStyleSheet("font-size:14px;font-weight:700;color:#d4af37;")
        lv.addWidget(lb)

        srow = QWidget()
        sh = QHBoxLayout(srow)
        sh.setContentsMargins(0, 0, 0, 0)
        sh.setSpacing(6)
        self.kw = QLineEdit()
        self.kw.setPlaceholderText("输入标题关键词后回车…")
        self.kw.returnPressed.connect(self._search)
        sh.addWidget(self.kw, 1)
        btn = QPushButton("搜索")
        btn.setObjectName("Primary")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self._search)
        sh.addWidget(btn)
        lv.addWidget(srow)

        self.lib_box = QComboBox()
        self.lib_box.setMinimumWidth(160)
        lv.addWidget(self.lib_box)

        self.list = QListWidget()
        # 隔行变色关掉：style.qss 只给 QTableWidget 配了 `alternate-background-color`，
        # 列表类的交替行会落到默认调色板 → 白底黑字，在暗色界面里非常刺眼。
        # （「重复检测」的 dd_tree 当年也是因此显式关掉的，沿用同一口径。）
        self.list.setAlternatingRowColors(False)
        self.list.itemSelectionChanged.connect(self._on_pick)
        lv.addWidget(self.list, 1)

        self.cnt_lbl = QLabel("")
        self.cnt_lbl.setStyleSheet("color:#8c8071;font-size:11px;")
        lv.addWidget(self.cnt_lbl)
        left.setMinimumWidth(240)
        left.setMaximumWidth(360)
        root.addWidget(left)

        self.scroll = _NoHScroll()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(self.scroll, 1)
        self._show_placeholder("← 在左侧选一部影片，这里会列出它的 nfo 全部字段。")

    @staticmethod
    def _mktitle(text):
        l = QLabel(text)
        l.setStyleSheet("font-size:14px;font-weight:700;color:#d4af37;")
        return l

    def _set_scroll_widget(self, host):
        """换掉右栏根 widget。

        `QScrollArea.setWidget` **会接管所有权**——直接 set 新的，旧的会被 Qt 一起
        删掉，再自己去 `deleteLater()` 就变成「同一对象删两次」（冒烟里抓到过：
        RuntimeError: Internal C++ object (QWidget) already deleted）。
        所以先把旧的 `takeWidget()` 摘出来（所有权转回 Python 侧），再统一 deleteLater。
        """
        old = self.scroll.takeWidget()
        self.scroll.setWidget(host)
        if old is not None and old is not host:
            old.deleteLater()

    def _show_placeholder(self, text):
        host = QWidget()
        v = QVBoxLayout(host)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        hint = QLabel(text)
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8c8071;font-size:12px;")
        v.addWidget(hint)
        v.addStretch(1)
        self._host = host
        self._set_scroll_widget(host)

    # ---------- 检索 ----------
    def _reload_libraries(self):
        self.lib_box.blockSignals(True)
        self.lib_box.clear()
        self.lib_box.addItem("全部媒体库", "")
        try:
            for name in db.libraries():
                self.lib_box.addItem(str(name), str(name))
        except Exception as e:
            applog.log(f"手动修改：读取媒体库列表失败：{e}", "error")
        self.lib_box.blockSignals(False)

    def _search(self):
        if self.lib_box.count() <= 1:
            self._reload_libraries()
        kw = (self.kw.text() or "").strip()
        lib = self.lib_box.currentData() or None
        try:
            rows = db.search_media(keyword=kw, library=lib, light=True,
                                   limit=self.SEARCH_LIMIT, sort="sort_title", asc=True)
        except Exception as e:
            applog.log(f"手动修改检索失败：{e}", "error")
            self.cnt_lbl.setText(f"检索失败：{e}")
            rows = []
        rows = list(rows or [])
        self.list.blockSignals(True)
        self.list.clear()
        for r in rows:
            title = r.get("title") or "(无标题)"
            year = r.get("year") or ""
            it = QListWidgetItem(f"{title}    ({year})" if year else str(title))
            it.setData(Qt.UserRole, int(r.get("id") or 0))
            it.setToolTip(r.get("file_path") or "")
            self.list.addItem(it)
        self.list.blockSignals(False)
        tail = f"（只取前 {self.SEARCH_LIMIT} 部）" if len(rows) >= self.SEARCH_LIMIT else ""
        self.cnt_lbl.setText(f"共 {len(rows)} 部{tail}")

    def _on_pick(self):
        items = self.list.selectedItems()
        if not items:
            return
        mid = items[0].data(Qt.UserRole)
        if not mid:
            return
        try:
            m = db.get_media(int(mid))
        except Exception as e:
            applog.log(f"读取影片失败：{e}", "error")
            return
        if not isinstance(m, dict) or not m:
            return
        self._media = m
        self._build_form(m)

    # ---------- 编辑表单 ----------
    def _build_form(self, media):
        host = QWidget()
        v = QVBoxLayout(host)
        v.setContentsMargins(0, 0, 0, 4)
        v.setSpacing(10)

        data = nf.from_media(media)
        head = QLabel(media.get("title") or "(无标题)")
        head.setStyleSheet("font-size:15px;font-weight:700;color:#e8ddc8;")
        head.setWordWrap(True)
        v.addWidget(head)
        if media.get("file_path"):
            fp = QLabel(media["file_path"])
            fp.setWordWrap(True)
            fp.setTextInteractionFlags(Qt.TextSelectableByMouse)
            fp.setStyleSheet("color:#8c8071;font-size:11px;")
            v.addWidget(fp)
        if not data.get("nfo_exists"):
            warn = QLabel("⚠ 这部影片没有 nfo 文件 —— 下面的字段是数据库里的现值，"
                          "保存时**无法**写入 nfo（索引仍会同步）。")
            warn.setWordWrap(True)
            warn.setStyleSheet("color:#e8b76a;font-size:11px;")
            v.addWidget(warn)

        # --- 配图 ---
        v.addWidget(self._build_images(media))
        # --- 字段 ---
        v.addWidget(self._build_fields(data))
        # --- 演员 ---
        v.addWidget(self._build_actors(data))
        # --- 底部 ---
        v.addWidget(self._build_footer())
        v.addStretch(1)

        self._host = host
        self._set_scroll_widget(host)
        for slot in idm.SLOTS:
            self._refresh_slot(slot)

    def _build_images(self, media):
        box = QGroupBox("配图（上传即复制为 `<番号>-poster|thumb|fanart.jpg`，源文件不动）")
        ig = QHBoxLayout(box)
        ig.setSpacing(10)
        self._slot_labels = {}
        for slot in idm.SLOTS:
            cell = QWidget()
            cv = QVBoxLayout(cell)
            cv.setContentsMargins(0, 0, 0, 0)
            cv.setSpacing(5)
            lab = QLabel(idm.SLOT_CN[slot])
            lab.setStyleSheet("color:#c9bda7;font-size:11px;")
            lab.setAlignment(Qt.AlignHCenter)
            prev = QLabel()
            prev.setObjectName(f"slotprev_{slot}")     # 离屏冒烟按名字找
            prev.setFixedSize(_W, int(_W * 2 / 3))
            prev.setAlignment(Qt.AlignCenter)
            prev.setStyleSheet("background:#1b1613;border:1px solid #3a3129;color:#8c8071;")
            up = QPushButton("上传…")
            up.setObjectName("Ghost")
            up.setCursor(Qt.PointingHandCursor)
            up.clicked.connect(lambda _c, s=slot: self._pick_image(s))
            tgt = QLabel("")
            tgt.setObjectName(f"slottarget_{slot}")
            tgt.setWordWrap(True)
            tgt.setTextInteractionFlags(Qt.TextSelectableByMouse)
            tgt.setStyleSheet("color:#8c8071;font-size:10px;")
            for w in (lab, prev, up, tgt):
                cv.addWidget(w, 0, Qt.AlignHCenter)
            ig.addWidget(cell)
            self._slot_labels[slot] = (prev, tgt)
        return box

    def _build_fields(self, data):
        box = QGroupBox("nfo 字段")
        form = QFormLayout()
        form.setContentsMargins(6, 4, 6, 4)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._fields = {}
        for key, label, kind in nf.FIELDS:
            w = _make_widget(kind, data.get(key))
            self._fields[key] = w
            form.addRow(label, w)
        host = QVBoxLayout(box)
        host.addLayout(form)
        return box

    def _build_actors(self, data):
        box = QGroupBox("演员")
        av = QVBoxLayout(box)
        self._actors_edit = QTextEdit()
        self._actors_edit.setObjectName("actors_edit")
        self._actors_edit.setFixedHeight(110)
        self._actors_edit.setPlaceholderText(
            "每行一位，可写 `姓名` 或 `姓名 | 角色`（清空即删除所有演员节点）")
        lines = []
        for a in (data.get("actor") or []):
            nm = (a or {}).get("name") or ""
            role = (a or {}).get("role") or ""
            lines.append(f"{nm} {_ACTOR_SEP} {role}" if role else nm)
        self._actors_edit.setPlainText("\n".join(lines))
        av.addWidget(self._actors_edit)
        return box

    def _build_footer(self):
        foot = QWidget()
        fh = QHBoxLayout(foot)
        fh.setContentsMargins(0, 0, 0, 0)
        fh.setSpacing(8)
        save = QPushButton("保存到 nfo 与索引")
        save.setObjectName("Primary")
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(self._save)
        fh.addWidget(save)
        rel = QPushButton("重新载入")
        rel.setObjectName("Ghost")
        rel.setCursor(Qt.PointingHandCursor)
        rel.clicked.connect(lambda: self._build_form(self._media) if self._media else None)
        fh.addWidget(rel)
        op = QPushButton("打开影片目录")
        op.setObjectName("Ghost")
        op.setCursor(Qt.PointingHandCursor)
        op.clicked.connect(self._open_dir)
        fh.addWidget(op)
        fh.addStretch(1)
        self.save_lbl = QLabel("")
        self.save_lbl.setStyleSheet("color:#8c8071;font-size:11px;")
        fh.addWidget(self.save_lbl)
        return foot

    # ---------- 配图 ----------
    def _refresh_slot(self, slot, path=""):
        got = self._slot_labels.get(slot)
        if not got:
            return
        prev, tgt = got
        media = self._media or {}
        tgt.setText(idm.target_path(media, slot) or "（无法定位影片目录）")
        path = path or next((p for p in idm.candidate_paths(media, slot)
                             if p and os.path.exists(p)), "")
        if path and os.path.exists(path):
            pm = QPixmap(path)
            if not pm.isNull():
                prev.setText("")
                prev.setPixmap(pm.scaled(prev.size(), Qt.KeepAspectRatio,
                                         Qt.SmoothTransformation))
                return
        prev.setPixmap(QPixmap())
        prev.setText("无图")

    def _pick_image(self, slot):
        media = self._media
        if not media:
            return
        d = idm.media_dir(media) or ""
        path, _f = QFileDialog.getOpenFileName(
            self, f"选择「{idm.SLOT_CN[slot]}」图片", d,
            "图片文件 (*.jpg *.jpeg *.png *.webp *.bmp);;所有文件 (*.*)")
        if not path:
            return
        ok, target, err = idm.replace_image(media, slot, path)
        if not ok:
            QMessageBox.warning(self, "替换失败", err or "未知错误")
            return
        try:
            db.update_media_fields(int(media["id"]), **{slot: target})
        except Exception as e:
            applog.log(f"手动修改：配图同步索引失败：{e}", "error")
        self._refresh_slot(slot, target)
        if self.save_lbl is not None:
            self.save_lbl.setText(f"已替换{idm.SLOT_CN[slot]}：{os.path.basename(target)}")

    def _open_dir(self):
        media = self._media or {}
        d = idm.media_dir(media)
        if not d or not os.path.isdir(d):
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(d))

    # ---------- 保存 ----------
    def _collect(self) -> dict:
        data = {}
        for key, _label, kind in nf.FIELDS:
            w = self._fields.get(key)
            if w is None:
                continue
            if isinstance(w, QTextEdit):
                data[key] = w.toPlainText().strip()
            else:
                txt = w.text().strip()
                data[key] = ([p.strip() for p in txt.split(",") if p.strip()]
                             if kind == "multi" else txt)
        actors = []
        for line in (self._actors_edit.toPlainText() if self._actors_edit else "").splitlines():
            line = line.strip()
            if not line:
                continue
            nm, role = (line.split(_ACTOR_SEP, 1) + [""])[:2] if _ACTOR_SEP in line else (line, "")
            nm = nm.strip()
            if nm:
                actors.append({"name": nm, "role": role.strip()})
        data["actor"] = actors
        return data

    def _save(self):
        media = self._media
        if not media:
            return
        data = self._collect()
        try:
            res = nf.save(media, data)
        except Exception as e:
            applog.log(f"手动修改保存异常：{e}", "error")
            QMessageBox.critical(self, "保存失败", str(e))
            return
        parts = []
        if res.get("nfo_ok"):
            bak = os.path.basename(res.get("backup") or "")
            parts.append("nfo 已写入" + (f"（备份 {bak}）" if bak else ""))
        else:
            parts.append("nfo 未写入：" + (res.get("err") or "未知原因"))
        if res.get("db_ok"):
            parts.append("索引已同步（" + "、".join(res.get("db_fields") or []) + "）")
        text = "；".join(parts)
        if self.save_lbl is not None:
            self.save_lbl.setText(text)
        if res.get("nfo_ok"):
            applog.log(f"[手动修改] 已保存《{media.get('title')}》：{text}")
        else:
            QMessageBox.warning(self, "未完全保存", text)


class _NoHScroll(QScrollArea):
    """横向滚动条常驻会吃掉编辑区宽度，表单本身也会换行 → 关掉横向，只上下滚。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
