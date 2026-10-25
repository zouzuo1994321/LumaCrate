# -*- coding: utf-8 -*-
"""v1.46.4：① 状态栏常驻灰色进度条（载入/缓存时高亮）② 实时状态显示本程序内存。"""
import io
import ast

# ============================ sysmon：进程内存 ============================
P = r"E:/【01】自研软件/【26-19】本地影视中心/src/sysmon.py"
s = io.open(P, encoding="utf-8").read()

s = s.replace('''    def gpu(self):''',
'''    def proc_mem(self):
        """本进程的常驻内存（MB，RSS）。

        v1.46.4（反馈 2）：先走 psutil，没有就退回 Windows 的
        ``GetProcessMemoryInfo``（psapi），两者都失败返回 None。
        """
        try:
            if _PSUTIL:
                import psutil
                return psutil.Process().memory_info().rss / 1048576.0
        except Exception:
            pass
        try:
            import ctypes
            from ctypes import wintypes

            class _PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD),
                            ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]

            pmc = _PMC()
            pmc.cb = ctypes.sizeof(pmc)
            h = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
                return pmc.WorkingSetSize / 1048576.0
        except Exception:
            pass
        return None

    def gpu(self):''')

s = s.replace('''        out = {"cpu": None, "mem": None, "gpu": None, "gpu_name": "", "gpu_mem": None,''',
'''        out = {"cpu": None, "mem": None, "gpu": None, "gpu_name": "", "gpu_mem": None,
               "proc_mb": None,''')

# 采样时填 proc_mb（放在 mem 之后，保证任何分支都会算）
s = s.replace('''            out["mem"] = self.mem()''',
'''            out["mem"] = self.mem()
            try:
                out["proc_mb"] = self.proc_mem()
            except Exception:
                out["proc_mb"] = None''')

# 面板：GPU 行下面加「本程序内存」
s = s.replace('''        for key, text in self.KEYS:
            v.addWidget(self._bar_row(key, text))
        self.net_row = self._kv_row("网络 · Ollama")''',
'''        for key, text in self.KEYS:
            v.addWidget(self._bar_row(key, text))
        # v1.46.4（反馈 2）：GPU 下面显示**本程序**当前内存占用（RSS）
        self.proc_row = self._kv_row("本程序内存")
        v.addWidget(self.proc_row)
        self.net_row = self._kv_row("网络 · Ollama")''')

s = s.replace('''        # 网络 · Ollama：一个状态点同时编码两件事''',
'''        # 本程序内存（v1.46.4）
        try:
            mb = d.get("proc_mb")
            self.proc_row[1].setText("—" if mb is None else "%.0f MB" % mb)
            self.proc_row[0].setToolTip("本程序（含索引与封面缓存）当前的常驻内存")
            self.proc_row[1].setToolTip("本程序（含索引与封面缓存）当前的常驻内存")
        except Exception:
            pass

        # 网络 · Ollama：一个状态点同时编码两件事''')

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
ast.parse(s)
print("sysmon ok | proc_mem:", "def proc_mem" in s, "| row:", 'self.proc_row = self._kv_row' in s)

# ============================ main_window：状态栏进度条 ============================
P = r"E:/【01】自研软件/【26-19】本地影视中心/src/main_window.py"
s = io.open(P, encoding="utf-8").read()

# 1) 全局忙信号总线（谁都能上报，避免各处去拿主窗引用）
s = s.replace('''def _qt_alive(obj, child=None):''',
'''class BusyBus(QObject):
    """v1.46.4（反馈 1）：全局「忙」信号 —— 载入 / 缓存 / 扫描都能上报给状态栏进度条。

    用法：`set_busy(-1)` 表示**不确定进度**（高亮循环），`set_busy(0..100)` 是确定进度，
    `set_busy(None)` 表示回到空闲（灰色常驻）。
    """
    changed = Signal(object, str)      # progress: None / -1 / 0..100；text: 可选说明


BUSY = BusyBus()


def set_busy(progress=None, text=""):
    try:
        BUSY.changed.emit(progress, text or "")
    except Exception:
        pass


def _qt_alive(obj, child=None):''')

# 2) 状态栏加常驻进度条（在 toast 右侧最右端）
s = s.replace('''        self._toast_timer = QTimer(self)''',
'''        # v1.46.4（反馈 1）：信息栏右侧**常驻**灰色进度条；有载入/缓存时高亮
        self._busy_bar = QProgressBar()
        self._busy_bar.setObjectName("BusyBar")
        self._busy_bar.setTextVisible(False)
        self._busy_bar.setFixedSize(110, 6)
        self._busy_bar.setRange(0, 1)
        self._busy_bar.setValue(0)
        self._busy_bar.setProperty("busy", False)
        self._busy_bar.setToolTip("载入 / 缓存进度（空闲时为灰色）")
        sb.addPermanentWidget(self._busy_bar, 0)
        BUSY.changed.connect(self._on_busy)
        self._busy_idle_timer = QTimer(self)
        self._busy_idle_timer.setSingleShot(True)
        self._busy_idle_timer.timeout.connect(lambda: self._on_busy(None, ""))

        self._toast_timer = QTimer(self)''')

# 3) 处理函数
s = s.replace('''    # ---------- 底部临时消息（v1.44.0）----------''',
'''    # ---------- 状态栏进度条（v1.46.4）----------
    def _on_busy(self, progress, text=""):
        """None=空闲；-1=不确定进度（高亮循环）；0..100=确定进度。"""
        bar = getattr(self, "_busy_bar", None)
        if bar is None:
            return
        try:
            if progress is None:
                bar.setRange(0, 1)
                bar.setValue(0)
                active = False
            elif isinstance(progress, (int, float)) and progress < 0:
                bar.setRange(0, 0)          # 不确定态：Qt 自己画循环块
                active = True
            else:
                bar.setRange(0, 100)
                bar.setValue(max(0, min(100, int(progress))))
                active = True
            if bool(bar.property("busy")) != active:
                bar.setProperty("busy", active)
                bar.style().unpolish(bar)
                bar.style().polish(bar)
            if active:
                # 兜底：1.5s 没有后续更新就自动回落，避免高亮卡住
                self._busy_idle_timer.start(1500)
            else:
                self._busy_idle_timer.stop()
        except Exception:
            pass

    def busy(self, progress=None, text=""):
        set_busy(progress, text)

    # ---------- 底部临时消息（v1.44.0）----------''')

# 4) LazyGrid 渲染/取数时上报（首页载入、切页载入都能看到）
s = s.replace('''        self._busy = True
        try:
            rows = self._fetch(self._loaded, self.batch) or []''',
'''        self._busy = True
        if self._loaded <= 0:
            set_busy(-1, "载入中")
        try:
            rows = self._fetch(self._loaded, self.batch) or []''')
s = s.replace('''        if not rows:
            self._total = self._loaded          # 到底了
        self._busy = False''',
'''        if not rows:
            self._total = self._loaded          # 到底了
        self._busy = False
        if self._loaded >= self._total:
            set_busy(None)''')

# 5) 虚拟网格：首次渲染上报
s = s.replace('''        rows = self._safe_fetch(r0 * cols, (r1 - r0 + 1) * cols)''',
'''        if not self._cards:
            set_busy(-1, "载入中")
        rows = self._safe_fetch(r0 * cols, (r1 - r0 + 1) * cols)''')
s = s.replace('''        self._loaded = min(self._total, (r1 + 1) * cols)
        self._update_head()

    def eventFilter''',
'''        self._loaded = min(self._total, (r1 + 1) * cols)
        set_busy(None)
        self._update_head()

    def eventFilter''')

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
ast.parse(s)
print("main ok | bus:", "BUSY = BusyBus()" in s, "| bar:", "_busy_bar" in s,
      "| hooks:", s.count("set_busy("))
