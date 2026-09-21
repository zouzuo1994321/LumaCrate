# -*- coding: utf-8 -*-
"""v1.25.0 批量补丁 _c：ui_settings.py

对应 6 条反馈里的 5 条：
  反馈 1 —— 「智能推荐 → 推荐算法」加模型输入框 + ollama list 说明 + 示例 + 读取本机模型
  反馈 2 —— 数据导出/导入 页勾选区与下方按钮行之间的间距
  反馈 3 —— 「推荐范围与偏好」加「已经推荐的 N 轮内不再重复出现」+ 清空推荐历史
  反馈 4 —— 新增「标签优化」整页（范围 / 算法 / 标签转化 / 预览 / 写入）
  反馈 5 —— 「外观」加 12 种基础高亮色色板
"""
import os

ROOT = r"Z:/【01】自研软件/【26-19】本地影视中心"
SRC = os.path.join(ROOT, "src")
REPORT = []


def read(rel):
    with open(os.path.join(SRC, rel), encoding="utf-8") as f:
        return f.read()


def write(rel, text):
    with open(os.path.join(SRC, rel), "w", encoding="utf-8", newline="") as f:
        f.write(text)


def patch(rel, label, old, new, count=1):
    s = read(rel)
    n = s.count(old)
    if n != count:
        raise SystemExit(f"✗ [{rel} :: {label}] 锚点命中 {n} 次，期望 {count} 次\n"
                         f"----- 锚点 -----\n{old[:500]}\n----------------")
    write(rel, s.replace(old, new))
    REPORT.append(f"OK  {rel}  {label}")


R = "ui_settings.py"

# ---------------------------------------------------------------- 0. 导入 tagopt
patch(R, "导入 tagopt",
      "import applog\nimport backup as backup_mod\n",
      "import applog\nimport backup as backup_mod\n"
      "import tagopt as tagopt_mod\n")

# ---------------------------------------------------------------- 1. 新工作线程
patch(R, "新增 AiModelsWorker / TagOptScanWorker / TagOptRunWorker",
      "class VectorEditorDialog(QDialog):\n",
      'class AiModelsWorker(QThread):\n'
      '    """读取本机 Ollama 已安装的模型列表（v1.25.0 反馈 1）。\n'
      '\n'
      '    `ollama list` 的图形等价物：丢线程里跑，避免 0.5 秒超时把设置窗口卡住。\n'
      '    """\n'
      '\n'
      '    done = Signal(object)\n'
      '\n'
      '    def run(self):\n'
      '        try:\n'
      '            names = rec_mod.list_models()\n'
      '        except Exception as e:\n'
      '            applog.log(f"读取本机模型失败：{type(e).__name__}: {e}", "error")\n'
      '            names = []\n'
      '        self.done.emit(list(names or []))\n'
      '\n'
      '\n'
      'class TagOptScanWorker(QThread):\n'
      '    """标签优化：扫描 + 出计划（**只读盘、只算，绝不写盘**）（v1.25.0 反馈 4）。\n'
      '\n'
      '    真正落盘在用户看到预览并确认之后的 TagOptRunWorker 里 —— 两段拆开是为了\n'
      '    「先看会改成什么样，再决定要不要改」。\n'
      '    """\n'
      '\n'
      '    done = Signal(object, str)\n'
      '    progress = Signal(int, int, str)\n'
      '\n'
      '    def __init__(self, opt, scope, value, kw):\n'
      '        super().__init__()\n'
      '        self.opt = opt\n'
      '        self.scope = scope\n'
      '        self.value = value\n'
      '        self.kw = dict(kw or {})\n'
      '\n'
      '    def run(self):\n'
      '        try:\n'
      '            nfos = self.opt.collect(\n'
      '                self.scope, self.value,\n'
      '                progress=lambda i, n, m: self.progress.emit(i, n, m))\n'
      '            if not nfos:\n'
      '                self.done.emit([], "没有找到任何 .nfo —— 检查路径是否正确，"\n'
      '                                   "或这个媒体库下是否已经有刮削好的 nfo。")\n'
      '                return\n'
      '            plans = self.opt.plan(\n'
      '                nfos, progress=lambda i, n, m: self.progress.emit(i, n, m),\n'
      '                **self.kw)\n'
      '            self.done.emit(plans, "")\n'
      '        except Exception as e:\n'
      '            applog.log(f"标签优化扫描失败：{type(e).__name__}: {e}", "error")\n'
      '            self.done.emit([], f"{type(e).__name__}: {e}")\n'
      '\n'
      '\n'
      'class TagOptRunWorker(QThread):\n'
      '    """标签优化：把计划写回 nfo 并同步数据库（v1.25.0 反馈 4）。"""\n'
      '\n'
      '    done = Signal(object)\n'
      '    progress = Signal(int, int, str)\n'
      '\n'
      '    def __init__(self, opt, plans, backup):\n'
      '        super().__init__()\n'
      '        self.opt = opt\n'
      '        self.plans = list(plans or [])\n'
      '        self.backup = bool(backup)\n'
      '\n'
      '    def run(self):\n'
      '        try:\n'
      '            st = self.opt.apply(\n'
      '                self.plans, backup=self.backup,\n'
      '                progress=lambda i, n, m: self.progress.emit(i, n, m))\n'
      '        except Exception as e:\n'
      '            applog.log(f"标签优化写入失败：{type(e).__name__}: {e}", "error")\n'
      '            st = {"written": 0, "skipped": 0, "failed": 0, "db_synced": 0,\n'
      '                  "backups": [], "errors": [f"{type(e).__name__}: {e}"]}\n'
      '        self.done.emit(st)\n'
      '\n'
      '\n'
      'class VectorEditorDialog(QDialog):\n')

# ---------------------------------------------------------------- 2. 导航注册新页
patch(R, "ORDER 加标签优化",
      '        self.ORDER = ["个性化设置", "画像概览", "演员刮削", "智能推荐",\n'
      '                      "服务管理", "重复检测", "数据与日志"]\n',
      '        # v1.25.0（反馈 4）：「标签优化」跟在「智能推荐」后面 —— 它俩同源\n'
      '        # （都用「普通智能算法 / AI 智能算法」那套本地离线能力），放在一起好找。\n'
      '        self.ORDER = ["个性化设置", "画像概览", "演员刮削", "智能推荐", "标签优化",\n'
      '                      "服务管理", "重复检测", "数据与日志"]\n')

patch(R, "stack 挂上标签优化页",
      '        self._pg_smart = self._page_scroll(self._build_smart())     # v1.24.0：智能推荐\n'
      '        self._pg_service = self._page_scroll(self._build_service())\n',
      '        self._pg_smart = self._page_scroll(self._build_smart())     # v1.24.0：智能推荐\n'
      '        self._pg_tagopt = self._page_scroll(self._build_tagopt())   # v1.25.0：标签优化\n'
      '        self._pg_service = self._page_scroll(self._build_service())\n')

patch(R, "stack.addWidget 列表加标签优化页",
      '        for pg in (self._pg_personal, self._pg_insight, self._pg_scraper, self._pg_smart,\n'
      '                   self._pg_service, self._pg_dedupe, self._pg_data):\n',
      '        for pg in (self._pg_personal, self._pg_insight, self._pg_scraper, self._pg_smart,\n'
      '                   self._pg_tagopt, self._pg_service, self._pg_dedupe, self._pg_data):\n')

patch(R, "_show 映射加标签优化",
      '            "智能推荐": self._pg_smart,\n'
      '            "服务管理": self._pg_service,\n',
      '            "智能推荐": self._pg_smart,\n'
      '            "标签优化": self._pg_tagopt,\n'
      '            "服务管理": self._pg_service,\n')

# ---------------------------------------------------------------- 3. 外观：12 色色板
patch(R, "外观加 12 色高亮色板",
      '        ophl.addWidget(self.op_val)\n'
      '        g0v.addWidget(oph)\n'
      '        self._refresh_backdrop_hint()\n',
      '        ophl.addWidget(self.op_val)\n'
      '        g0v.addWidget(oph)\n'
      '        # v1.25.0（反馈 5）：12 种基础「高亮色」。\n'
      '        # 卡片选中的描边 + 外发光、按钮 / chip / 滑块 / 勾选框的强调色，\n'
      '        # 全部由它派生（QSS 走令牌替换，自绘控件走 main_window.ACCENT_RGB），\n'
      '        # 所以换一个色，整套界面一起变。\n'
      '        acrow = QWidget()\n'
      '        ach = QHBoxLayout(acrow)\n'
      '        ach.setContentsMargins(0, 2, 0, 0)\n'
      '        ach.setSpacing(6)\n'
      '        ach.addWidget(QLabel("高亮色"))\n'
      '        self._accent_btns = {}\n'
      '        for _nm, _hex in cfg.ACCENT_COLORS:\n'
      '            b = QPushButton()\n'
      '            b.setFixedSize(26, 26)\n'
      '            b.setCursor(Qt.PointingHandCursor)\n'
      '            b.clicked.connect(lambda _c, h=_hex: self._apply_accent(h))\n'
      '            ach.addWidget(b)\n'
      '            self._accent_btns[_hex] = b\n'
      '        ach.addSpacing(10)\n'
      '        self.lb_accent = QLabel("—")\n'
      '        self.lb_accent.setStyleSheet("color:#d4af37;font-size:11px;")\n'
      '        ach.addWidget(self.lb_accent)\n'
      '        ach.addStretch(1)\n'
      '        g0v.addWidget(acrow)\n'
      '        self._paint_accent_btns()\n'
      '        self._refresh_backdrop_hint()\n')

patch(R, "外观：_apply_accent / _paint_accent_btns",
      '    def _refresh_backdrop_hint(self):\n',
      '    # ---------- 高亮色（v1.25.0 反馈 5） ----------\n'
      '    def _apply_accent(self, hexv):\n'
      '        """选中一个高亮色：落盘 → 刷新色板 → 走一遍 `_apply_appearance`\n'
      '        （它会重载样式表，main_window.render_style 顺手把 ACCENT_RGB 一起换掉，\n'
      '        自绘卡片的描边和外发光因此立刻跟着变）。"""\n'
      '        self.s.set_accent(hexv)\n'
      '        self._paint_accent_btns()\n'
      '        self._apply_appearance()\n'
      '\n'
      '    def _paint_accent_btns(self):\n'
      '        """把 12 个色块画成「本色填充 + 选中白边 + 勾」；未选中用暗描边。\n'
      '\n'
      '        注意：这里用**控件级**样式表，它会盖掉全局 QSS 的 padding —— 26px 的小方块\n'
      '        必须显式写 padding:0，否则全局 `QPushButton{padding:7px 14px}` 会把内容区\n'
      '        压成负数，勾号与底色都会画不出来（本项目复发过多次的老坑）。\n'
      '        """\n'
      '        cur = self.s.accent()\n'
      '        for hexv, b in getattr(self, "_accent_btns", {}).items():\n'
      '            on = str(hexv).lower() == str(cur).lower()\n'
      '            b.setStyleSheet(\n'
      '                "QPushButton{background:%s;border:2px solid %s;border-radius:13px;"\n'
      '                "padding:0;font-weight:700;color:#ffffff;}"\n'
      '                "QPushButton:hover{border-color:#ffffff;}"\n'
      '                % (hexv, "#ffffff" if on else "rgba(255,255,255,0.20)"))\n'
      '            b.setText("✓" if on else "")\n'
      '            b.setToolTip(f"{cfg.accent_name(hexv)} {hexv}"\n'
      '                         + ("（当前使用）" if on else "点击切换"))\n'
      '        lb = getattr(self, "lb_accent", None)\n'
      '        if lb is not None:\n'
      '            lb.setText(f"当前：{cfg.accent_name(cur)} {cur}")\n'
      '\n'
      '    def _refresh_backdrop_hint(self):\n')

# ---------------------------------------------------------------- 4. 智能推荐：模型输入
patch(R, "推荐算法：模型输入 + 说明 + 示例 + 读取本机模型",
      '        self.ai_test.clicked.connect(self._refresh_ai_state)\n'
      '        g1v.addWidget(self.ai_test, alignment=Qt.AlignLeft)\n'
      '        v.addWidget(g1)\n',
      '        self.ai_test.clicked.connect(self._refresh_ai_state)\n'
      '        g1v.addWidget(self.ai_test, alignment=Qt.AlignLeft)\n'
      '\n'
      '        # v1.25.0（反馈 1）：默认用本机 Ollama，但**模型可以自己填**。\n'
      '        mrow = QHBoxLayout()\n'
      '        mrow.setSpacing(8)\n'
      '        mrow.addWidget(QLabel("调用模型"))\n'
      '        self.ed_ai_model = QLineEdit()\n'
      '        self.ed_ai_model.setPlaceholderText("留空 = 自动使用本机第一个模型")\n'
      '        self.ed_ai_model.setToolTip(\n'
      '            "填 Ollama 里的模型名（就是 `ollama list` 第一列那个名字，带标签）。\\n"\n'
      '            "例：qwen2.5:7b / llama3.1:8b / qwen3:4b / muse-glimmer:latest")\n'
      '        self.ed_ai_model.setText(str(self.s.recommend.get("ai_model") or ""))\n'
      '        self.ed_ai_model.editingFinished.connect(self._on_ai_model_edited)\n'
      '        mrow.addWidget(self.ed_ai_model, 1)\n'
      '        self.btn_ai_models = QPushButton("读取本机模型")\n'
      '        self.btn_ai_models.setObjectName("Ghost")\n'
      '        self.btn_ai_models.setToolTip("读取本机 Ollama 的模型清单（等价于命令行 `ollama list`）")\n'
      '        self.btn_ai_models.clicked.connect(self._load_ai_models)\n'
      '        mrow.addWidget(self.btn_ai_models)\n'
      '        g1v.addLayout(mrow)\n'
      '        self.cb_ai_model = QComboBox()\n'
      '        self.cb_ai_model.setToolTip("读取到的本机模型；选一个即自动填入上面的输入框")\n'
      '        self.cb_ai_model.addItem("（还没读取 —— 点右边「读取本机模型」）", "")\n'
      '        self.cb_ai_model.currentIndexChanged.connect(self._pick_ai_model)\n'
      '        g1v.addWidget(self.cb_ai_model)\n'
      '        mhint = QLabel(rich(\n'
      '            "**怎么填**：先启动 Ollama，然后在命令行执行 `ollama list` 查看已经安装的模型，"\n'
      '            "把第一列的完整名字填进上面的输入框即可。\\n"\n'
      '            "**输入示例**：qwen2.5:7b　/　llama3.1:8b　/　qwen3:4b　/　"\n'
      '            "gemma3:12b　/　muse-glimmer:latest　（冒号和标签都要带上）\\n"\n'
      '            "留空 = 自动使用本机第一个模型；填了但本机没装，会自动降级为内置联想，"\n'
      '            "并在下面的检测结果里告诉你本机到底装了哪些。"))\n'
      '        mhint.setWordWrap(True)\n'
      '        mhint.setStyleSheet("color:#a2967f;font-size:11px;")\n'
      '        g1v.addWidget(mhint)\n'
      '        v.addWidget(g1)\n')

# ---------------------------------------------------------------- 5. 推荐范围：轮次
patch(R, "推荐范围与偏好：不重复轮次 + 清空历史",
      '        row.addStretch(1)\n'
      '        g2v.addLayout(row)\n'
      '\n'
      '        self.ck_tags = QCheckBox("结合收藏影片的标签 / 片商 / 系列")\n',
      '        row.addStretch(1)\n'
      '        g2v.addLayout(row)\n'
      '\n'
      '        # v1.25.0（反馈 3）：已经推荐过的，多少轮之内不再重复出现。\n'
      '        rowr = QHBoxLayout()\n'
      '        rowr.setSpacing(8)\n'
      '        rowr.addWidget(QLabel("已经推荐的"))\n'
      '        self.sp_rounds = QSpinBox()\n'
      '        self.sp_rounds.setRange(0, 50)\n'
      '        self.sp_rounds.setSuffix(" 轮")\n'
      '        self.sp_rounds.setValue(int(self.s.recommend.get("no_repeat_rounds", 3)))\n'
      '        self.sp_rounds.setToolTip(\n'
      '            "最近这么多轮推荐过的作品，不再重复出现。\\n"\n'
      '            "每点一次「换一批」、或每次进「智能推荐」页 = 1 轮；0 = 不限制。")\n'
      '        self.sp_rounds.valueChanged.connect(self._save_smart_prefs)\n'
      '        rowr.addWidget(self.sp_rounds)\n'
      '        rowr.addWidget(QLabel("内不再重复出现"))\n'
      '        rowr.addSpacing(16)\n'
      '        self.lb_hist = QLabel("—")\n'
      '        self.lb_hist.setStyleSheet("color:#8c8071;font-size:11px;")\n'
      '        rowr.addWidget(self.lb_hist)\n'
      '        b_hist = QPushButton("清空推荐历史")\n'
      '        b_hist.setObjectName("Ghost")\n'
      '        b_hist.setToolTip("忘掉之前推荐过哪些作品；下次推荐从头开始（收藏仍然不会被推荐）")\n'
      '        b_hist.clicked.connect(self._clear_smart_history)\n'
      '        rowr.addWidget(b_hist)\n'
      '        rowr.addStretch(1)\n'
      '        g2v.addLayout(rowr)\n'
      '\n'
      '        self.ck_tags = QCheckBox("结合收藏影片的标签 / 片商 / 系列")\n')

patch(R, "_build_smart 收尾刷新历史标签",
      '        v.addStretch(1)\n'
      '        QTimer.singleShot(0, self._refresh_ai_state)\n'
      '        self._refresh_vector_count()\n'
      '        return page\n',
      '        v.addStretch(1)\n'
      '        QTimer.singleShot(0, self._refresh_ai_state)\n'
      '        self._refresh_vector_count()\n'
      '        self._refresh_hist_label()\n'
      '        return page\n')

# ---------------------------------------------------------------- 6. 保存 / 新增方法
patch(R, "_save_smart_prefs 带上新键",
      '    def _save_smart_prefs(self, *_):\n'
      '        self.lb_div.setText(f"λ={self.sl_div.value() / 100:.2f}")\n'
      '        self.s.set_recommend(algo=("ai" if self.rb_ai.isChecked() else "normal"),\n'
      '                             count=int(self.sp_count.value()),\n'
      '                             use_tags=self.ck_tags.isChecked(),\n'
      '                             use_actors=self.ck_actors.isChecked(),\n'
      '                             use_directors=self.ck_directors.isChecked(),\n'
      '                             exclude_watched=self.ck_watched.isChecked(),\n'
      '                             use_userrating=self.ck_urating.isChecked(),\n'
      '                             diversity=self.sl_div.value() / 100.0)\n',
      '    def _save_smart_prefs(self, *_):\n'
      '        self.lb_div.setText(f"λ={self.sl_div.value() / 100:.2f}")\n'
      '        kw = dict(algo=("ai" if self.rb_ai.isChecked() else "normal"),\n'
      '                  count=int(self.sp_count.value()),\n'
      '                  use_tags=self.ck_tags.isChecked(),\n'
      '                  use_actors=self.ck_actors.isChecked(),\n'
      '                  use_directors=self.ck_directors.isChecked(),\n'
      '                  exclude_watched=self.ck_watched.isChecked(),\n'
      '                  use_userrating=self.ck_urating.isChecked(),\n'
      '                  diversity=self.sl_div.value() / 100.0)\n'
      '        # 用 getattr 兜一下：这两个控件是 v1.25.0 才加的，\n'
      '        # 万一日后有人把它们的构造顺序挪到信号连接之后，也不该直接崩。\n'
      '        ed = getattr(self, "ed_ai_model", None)\n'
      '        if ed is not None:\n'
      '            kw["ai_model"] = ed.text().strip()\n'
      '        sp = getattr(self, "sp_rounds", None)\n'
      '        if sp is not None:\n'
      '            kw["no_repeat_rounds"] = int(sp.value())\n'
      '        self.s.set_recommend(**kw)\n'
      '        self._refresh_hist_label()\n'
      '\n'
      '    # ---------- v1.25.0（反馈 1）：模型选择 ----------\n'
      '    def _on_ai_model_edited(self):\n'
      '        """输入框改完（回车 / 失焦）：落盘 + 重新检测，让下面的结论立刻反映新模型。"""\n'
      '        self._save_smart_prefs()\n'
      '        self._refresh_ai_state()\n'
      '\n'
      '    def _load_ai_models(self):\n'
      '        w = getattr(self, "_ai_models_worker", None)\n'
      '        if w is not None and w.isRunning():\n'
      '            return\n'
      '        self.btn_ai_models.setEnabled(False)\n'
      '        self.btn_ai_models.setText("读取中…")\n'
      '        self._ai_models_worker = AiModelsWorker()\n'
      '        self._ai_models_worker.done.connect(self._on_ai_models)\n'
      '        self._ai_models_worker.start()\n'
      '\n'
      '    def _on_ai_models(self, names):\n'
      '        self.btn_ai_models.setEnabled(True)\n'
      '        self.btn_ai_models.setText("读取本机模型")\n'
      '        names = [str(x) for x in (names or []) if x]\n'
      '        self.cb_ai_model.blockSignals(True)\n'
      '        self.cb_ai_model.clear()\n'
      '        if not names:\n'
      '            self.cb_ai_model.addItem("（没读到模型：Ollama 没启动，或还没 pull 过任何模型）", "")\n'
      '        else:\n'
      '            self.cb_ai_model.addItem(f"本机已装 {len(names)} 个模型（点选即填入）", "")\n'
      '            for nm in names:\n'
      '                self.cb_ai_model.addItem(nm, nm)\n'
      '        self.cb_ai_model.setCurrentIndex(0)\n'
      '        self.cb_ai_model.blockSignals(False)\n'
      '        self._refresh_ai_state()\n'
      '\n'
      '    def _pick_ai_model(self, idx):\n'
      '        nm = self.cb_ai_model.itemData(idx) if idx is not None and idx >= 0 else None\n'
      '        if not nm:\n'
      '            return\n'
      '        self.ed_ai_model.setText(str(nm))\n'
      '        self._on_ai_model_edited()\n'
      '\n'
      '    # ---------- v1.25.0（反馈 3）：推荐历史 ----------\n'
      '    def _refresh_hist_label(self):\n'
      '        lb = getattr(self, "lb_hist", None)\n'
      '        if lb is None:\n'
      '            return\n'
      '        n = len(self.s.smart_history or [])\n'
      '        lb.setText(f"已记录 {n} 轮 / 当前避让 {len(self.s.recent_smart_ids())} 部"\n'
      '                   if n else "还没有推荐记录")\n'
      '\n'
      '    def _clear_smart_history(self):\n'
      '        self.s.clear_smart_history()\n'
      '        lb = getattr(self, "lb_hist", None)\n'
      '        if lb is not None:\n'
      '            lb.setText("已清空 —— 下次推荐从头开始")\n'
      '        applog.log("[智能推荐] 已清空推荐历史")\n')

print("\n".join(REPORT))
print(f"patch _c 完成：{len(REPORT)} 项")
