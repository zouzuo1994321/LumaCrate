# -*- coding: utf-8 -*-
"""侧边栏「实时状态」面板（v1.27.0 新增）

需求（反馈 2）：导航栏底部的「数据统计」信息上移，下面新增一块**实时状态** ——
CPU / 内存 / GPU 用**横条**显示当前占用百分比，另加「网络 · Ollama 状态」与
「当前使用模型」两项文字。横条靠左键名、右侧百分比；下面两行是「名称 + 值」
合成的一个富文本标签（侧栏只有 170px，左右分列会被裁，见 ``_kv_row``）。

设计要点
--------
1. **零硬依赖**：采集走降级链，任一环缺失都不报错，只是那一行显示「—」。

   ==========  ===================================  ==============================
   指标        首选                                  兜底
   ==========  ===================================  ==============================
   CPU%        ``psutil.cpu_percent()``             ``ctypes`` ``GetSystemTimes`` 差分
   内存%       ``psutil.virtual_memory()``          ``ctypes`` ``GlobalMemoryStatusEx``
   GPU%        ``nvidia-smi --query-gpu=…``         没有 N 卡 / 没有 nvidia-smi → 「—」
   网络        ``psutil.net_io_counters()``          ``ctypes`` ``InternetGetConnectedState``
   Ollama      本地 HTTP ``/api/tags``（0.4s 超时）  连不上 → 「未启动」
   ==========  ===================================  ==============================

   psutil 已在 venv 里（7.2.2，PyInstaller 有 ``hook-psutil.py`` 会被自动收集），
   但**打包后拿不到也照样能用** —— 这就是留 ctypes 分支的意义。

2. **采集全在后台线程**：``nvidia-smi`` 要起进程（几十~几百 ms），Ollama 探测还有
   0.4s 超时 —— 放 GUI 线程会把界面拖住（v1.21.0 首页卡顿的同款教训）。统一交给
   ``SysMonWorker(QThread)``，GUI 只接 ``sampled(dict)`` 改标签。

3. **横条自绘**（``MiniBar``）：**绝不给自绘控件写 ``setStyleSheet("background:…")``**
   —— 父控件背景会盖掉自绘区（v1.25.0 踩过，见项目记忆「Qt 样式坑」）。填充色在
   ``paintEvent`` 里现取 ``main_window.ACCENT_RGB``，跟随「外观 → 高亮色」；
   拿不到就回落默认朱红 ``(192, 57, 43)``。

4. **采集线程是「进程级单例」**（见 ``shared_worker()``），**绝不能挂在面板下**。
   ``MainWindow._apply_settings()`` 会 ``deleteLater()`` 整个侧栏再重建（改设置 / 写标签 /
   编辑媒体库都会走），线程若挂在面板下就会「连同运行中的 QThread 一起被销毁」——
   Qt 报 ``QThread: Destroyed while thread is still running`` 并**直接 abort 进程**。
   面板只负责 ``connect``；Qt 在接收者析构时会自动断开，不需要也不应该由面板管线程生死。
   全局在 ``MainWindow.closeEvent`` / ``app.aboutToQuit`` 里停一次。
5. 环境变量 ``LMC_NO_SYSMON=1`` 可整个关掉（离屏冒烟 / 自动化测试用，同 ``LMC_NO_SPLASH``）。
"""
import os
import sys
import time
import ctypes
import subprocess
from ctypes import wintypes

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
                               QApplication)

import applog

# —— 颜色 ——
_TRACK = QColor(255, 255, 255, 26)          # 横条轨道
_ACCENT_FALLBACK = (192, 57, 43)            # 拿不到 ACCENT_RGB 时的朱红
_WARN = (0xD8, 0xA0, 0x4A)                  # 60~85% 琥珀
_ALERT = (0xD9, 0x63, 0x4A)                 # >85% 警示（资源占用，不是涨跌）
_DOT_ON = "#6fbf73"                         # 状态点：绿
_DOT_WARN = "#d8a04a"                       # 状态点：琥珀
_DOT_OFF = "#8b8071"                        # 状态点：灰

_AI_EVERY = 6                               # 每 6 次采样探一次 Ollama（约 9 秒）
_INTERVAL_MS = 1500


def sysmon_disabled():
    """``LMC_NO_SYSMON=1`` 时整个面板不启动（离屏冒烟 / 自动化测试用）。"""
    return str(os.environ.get("LMC_NO_SYSMON", "")).strip() in ("1", "true", "True", "yes")


# ============================================================ 采集
class SysMetrics:
    """本机性能采样。**只读、无 Qt 调用**，可以安全地在工作线程里跑。

    ``sample()`` 返回的 dict 里，任何取不到的项都是 ``None``（UI 侧显示「—」），
    绝不抛异常。
    """

    def __init__(self):
        self._psutil = None
        self._has_psutil = False
        try:
            import psutil
            self._psutil = psutil
            self._has_psutil = True
        except Exception:
            self._has_psutil = False
        self._nvsmi = self._find_nvidia_smi()
        self._cpu_n = 0
        self._prev_cpu = None                # ctypes 差分基线
        self._prev_net = None
        self._prev_net_t = None
        self._gpu_name = ""

    # ---------- 能力探测（写日志用，便于打包后核实降级到哪一级） ----------
    def source_note(self):
        return "psutil=%s nvidia-smi=%s" % (
            ("ok" if self._has_psutil else "missing"),
            (self._nvsmi or "missing"))

    @staticmethod
    def _find_nvidia_smi():
        """找 nvidia-smi：PATH → System32 → 老版 NVSMI 目录。"""
        cands = []
        try:
            import shutil
            p = shutil.which("nvidia-smi")
            if p:
                cands.append(p)
        except Exception:
            pass
        root = os.environ.get("SystemRoot", r"C:\Windows")
        cands.append(os.path.join(root, "System32", "nvidia-smi.exe"))
        cands.append(r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe")
        for c in cands:
            if c and os.path.exists(c):
                return c
        return None

    # ---------- 单项 ----------
    def cpu(self):
        if self._has_psutil:
            try:
                self._cpu_n += 1
                # 第一次调用只能拿到 0.0，所以首帧用短阻塞采样打底
                if self._cpu_n == 1:
                    return float(self._psutil.cpu_percent(interval=0.15))
                return float(self._psutil.cpu_percent(interval=None))
            except Exception:
                pass
        return self._ctypes_cpu()

    @staticmethod
    def _ft(ft):
        return (ft.dwHighDateTime << 32) | ft.dwLowDateTime

    def _ctypes_cpu(self):
        """兜底：``GetSystemTimes`` 两次差分（psutil 内部也是这么算的）。

        kern 时间**含** idle，所以总量 = (kern + user) 的增量，占用 = 1 - idle/总量。
        """
        class _FT(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD),
                        ("dwHighDateTime", wintypes.DWORD)]
        try:
            idle, kern, user = _FT(), _FT(), _FT()
            ok = ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user))
            if not ok:
                return None
            cur = (self._ft(idle), self._ft(kern), self._ft(user))
        except Exception:
            return None
        prev, self._prev_cpu = self._prev_cpu, cur
        if prev is None:
            return None
        d_idle = cur[0] - prev[0]
        d_total = (cur[1] - prev[1]) + (cur[2] - prev[2])
        if d_total <= 0:
            return None
        return max(0.0, min(100.0, 100.0 * (d_total - d_idle) / d_total))

    def mem(self):
        if self._has_psutil:
            try:
                return float(self._psutil.virtual_memory().percent)
            except Exception:
                pass
        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        try:
            m = _MS()
            m.dwLength = ctypes.sizeof(_MS)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return float(m.dwMemoryLoad)
        except Exception:
            pass
        return None

    def gpu(self):
        """返回 ``{"gpu":%, "gpu_name":str, "gpu_mem":(used,total)MiB}`` 或 ``None``。"""
        if not self._nvsmi:
            return None
        try:
            r = subprocess.run(
                [self._nvsmi,
                 "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, timeout=4,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception:
            return None
        if r.returncode != 0:
            return None
        lines = (r.stdout or b"").decode("utf-8", "replace").strip().splitlines()
        if not lines:
            return None
        parts = [p.strip() for p in lines[0].split(",")]
        if len(parts) < 4:
            return None
        try:
            self._gpu_name = parts[0]
            util = float(parts[1])
            used, total = float(parts[2]), float(parts[3])
        except Exception:
            return None
        return {"gpu": util, "gpu_name": self._gpu_name, "gpu_mem": (used, total)}

    def _net_connected(self):
        """有没有可用网络连接（``wininet``，不发任何报文）。"""
        try:
            flags = wintypes.DWORD(0)
            ok = ctypes.windll.wininet.InternetGetConnectedState(ctypes.byref(flags), 0)
            return bool(ok)
        except Exception:
            return None

    def net(self):
        """``{"net_on":bool|None, "net_up":KB/s|None, "net_down":KB/s|None}``。"""
        out = {"net_on": self._net_connected(), "net_up": None, "net_down": None}
        if not self._has_psutil:
            return out
        try:
            c = self._psutil.net_io_counters()
            t = time.time()
            prev, pt = self._prev_net, self._prev_net_t
            self._prev_net, self._prev_net_t = c, t
            if prev is not None and pt is not None and t > pt:
                dt = t - pt
                out["net_up"] = max(0.0, (c.bytes_sent - prev.bytes_sent) / dt / 1024.0)
                out["net_down"] = max(0.0, (c.bytes_recv - prev.bytes_recv) / dt / 1024.0)
        except Exception:
            pass
        return out

    # ---------- 一次完整采样 ----------
    def sample(self):
        out = {"cpu": None, "mem": None, "gpu": None, "gpu_name": "", "gpu_mem": None,
               "net_on": None, "net_up": None, "net_down": None,
               "src": self.source_note()}
        try:
            out["cpu"] = self.cpu()
        except Exception:
            pass
        try:
            out["mem"] = self.mem()
        except Exception:
            pass
        try:
            g = self.gpu()
            if g:
                out.update(g)
        except Exception:
            pass
        try:
            out.update(self.net())
        except Exception:
            pass
        return out


def probe_ai(timeout=0.4):
    """Ollama 状态 + 「当前使用模型」。

    复用 v1.25.0 的 ``recommend.list_models`` / ``configured_model``（**惰性导入**，
    避免和 recommend→config/database 形成模块级耦合）。任何失败都静默降级。
    """
    out = {"ollama_on": False, "model": "", "model_ok": True, "models": []}
    try:
        import recommend as rec
        names = rec.list_models(timeout)
        out["models"] = names
        want = rec.configured_model()
        out["ollama_on"] = bool(names)
        if names:
            if want:
                out["model"], out["model_ok"] = want, (want in names)
            else:
                out["model"], out["model_ok"] = names[0], True
        else:
            out["model"], out["model_ok"] = want, not want
    except Exception:
        pass
    return out


# ============================================================ 采集线程
class SysMonWorker(QThread):
    """后台采样线程：每 ``_INTERVAL_MS`` 采一次，AI 信息每 ``_AI_EVERY`` 次探一次。"""

    sampled = Signal(dict)

    def __init__(self, interval_ms=_INTERVAL_MS, parent=None):
        super().__init__(parent)
        self._interval = max(0.5, interval_ms / 1000.0)
        self._stop = False
        self._ai = {"ollama_on": False, "model": "", "model_ok": True, "models": []}

    def stop(self):
        """请求退出并等它自己收尾。

        单轮最坏耗时 = nvidia-smi 超时 4s + Ollama 超时 0.4s + 一个睡眠周期 1.5s ≈ 6s，
        所以等 8s；本应用退出走 ``main.py`` 的 ``os._exit()``，即使没等到也不会卡住进程。
        """
        self._stop = True
        if self.isRunning():
            self.wait(8000)

    def run(self):
        m = SysMetrics()
        try:
            applog.log("实时状态：采集能力 " + m.source_note())
        except Exception:
            pass
        n = 0
        while not self._stop:
            n += 1
            if n == 1 or n % _AI_EVERY == 0:
                try:
                    self._ai = probe_ai()
                except Exception:
                    pass
            try:
                d = m.sample()
            except Exception:
                d = {}
            d.update(self._ai)
            self.sampled.emit(d)
            slept = 0.0
            while slept < self._interval and not self._stop:
                time.sleep(0.1)
                slept += 0.1


# ============================================================ 进程级单例
_WORKER = None


def shared_worker():
    """全进程共用一个采集线程（**不要在面板里 new 线程**）。

    v1.27.0 真机验收抓到的缺陷：原先每个 ``SysMonitorPanel`` 自己 new 一个
    ``SysMonWorker(parent=self)``。而 ``MainWindow._apply_settings()`` 会

        self.h_layout.removeWidget(self.sidebar); self.sidebar.deleteLater()
        self.sidebar = self._build_sidebar()

    重建整个侧栏 —— 于是旧面板连同它下面**正在运行的 QThread** 一起被销毁，Qt 直接
    ``abort()`` 掉进程。证据：标签优化写入完成那一刻，``app.log`` 出现了**第二行**
    「实时状态：采集能力 …」（新面板建起来了），随后日志全停、真机脚本后面 4 张抓图
    全部 0×0（窗口已经不响应）。

    改成进程级单例后：重建侧栏只是新建一个面板去 ``connect`` 同一个线程，Qt 在接收者
    析构时自动断开信号，线程本身不受影响。
    """
    global _WORKER
    if _WORKER is None or not _WORKER.isRunning():
        w = SysMonWorker()
        app = QApplication.instance()
        if app is not None:
            w.setParent(app)                     # 挂到 app 上，面板怎么删都动不到它
            app.aboutToQuit.connect(w.stop)      # 兜底：正常退出也停一次
        w.start()
        _WORKER = w
    return _WORKER


def stop_shared_worker():
    """停掉进程级采集线程（`MainWindow.closeEvent` 调用；可重复调用）。"""
    global _WORKER
    w, _WORKER = _WORKER, None
    if w is not None:
        try:
            w.stop()
        except Exception:
            pass
    return w


# ============================================================ 控件
class MiniBar(QWidget):
    """细横条百分比进度（自绘）。

    轨道用极淡的白，填充取当前高亮色；占用偏高时转琥珀 / 警示橙，扫一眼就知道
    是不是「正在被压满」。**不要**用样式表画背景（父控件背景会盖掉自绘区）。
    """

    H = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pct = None
        self.setFixedHeight(self.H)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_StyledBackground, False)

    def pct(self):
        return self._pct

    def set_pct(self, pct):
        if pct is None:
            new = None
        else:
            new = max(0.0, min(100.0, float(pct)))
        if new == self._pct:
            return
        self._pct = new
        self.update()

    def _fill(self):
        if self._pct is not None and self._pct >= 85:
            return QColor(*_ALERT)
        if self._pct is not None and self._pct >= 60:
            return QColor(*_WARN)
        mw = sys.modules.get("main_window")
        rgb = getattr(mw, "ACCENT_RGB", None) if mw is not None else None
        return QColor(*(rgb or _ACCENT_FALLBACK))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(0, 0, self.width(), self.height())
        rad = r.height() / 2.0
        p.setPen(Qt.NoPen)
        p.setBrush(_TRACK)
        p.drawRoundedRect(r, rad, rad)
        if not self._pct:
            return
        w = max(r.height(), r.width() * self._pct / 100.0)
        p.setBrush(self._fill())
        p.drawRoundedRect(QRectF(0, 0, w, r.height()), rad, rad)


class SysMonitorPanel(QWidget):
    """侧边栏底部「实时状态」：CPU / 内存 / GPU 横条 + 网络·Ollama + 当前模型。

    参数一行高度对齐：三条横条走 ``KEY [bar] 12%``，下面两行走 ``KEY  值``（见
    ``_kv_row``）。整体约 110px 高，直接挂在侧栏 ``stat_label`` 下面。
    """

    KEYS = (("cpu", "CPU"), ("mem", "内存"), ("gpu", "GPU"))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SysMon")
        self._rows = {}
        self._worker = None

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 4)
        v.setSpacing(3)

        for key, text in self.KEYS:
            v.addWidget(self._bar_row(key, text))
        self.net_row = self._kv_row("网络 · Ollama")
        self.model_row = self._kv_row("当前模型")
        v.addWidget(self.net_row)
        v.addWidget(self.model_row)
        self.apply({})          # 先摆出「—」的初始态，别让两行文字只有名称没有值

        # 订阅**进程级**采集线程（见 shared_worker 的注释：线程绝不能挂在面板下）。
        if not sysmon_disabled():
            try:
                self._worker = shared_worker()
                self._worker.sampled.connect(self.apply)
            except Exception:
                self._worker = None
                try:
                    applog.log("实时状态：采集线程启动失败，面板保持空白")
                except Exception:
                    pass

    # ---------- 行构造 ----------
    def _bar_row(self, key, text):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 0, 8, 0)
        h.setSpacing(6)
        lab = QLabel(text)
        lab.setObjectName("SysKey")
        lab.setFixedWidth(28)
        bar = MiniBar()
        val = QLabel("—")
        val.setObjectName("SysVal")
        val.setFixedWidth(34)
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(lab)
        h.addWidget(bar, 1)
        h.addWidget(val)
        self._rows[key] = (bar, val)
        return row

    def _kv_row(self, text):
        """一行「名称 + 值」—— **合成同一个 QLabel**，不是左右分列。

        侧栏内容区只有 170px，而 QLabel 的 minimumSizeHint 就是它文本的完整宽度：
        左右分列时两边都不肯让，一旦放不下就会把面板顶宽、右侧被裁。合成一个左对齐的
        富文本标签后宽度天然够用（10px 下「网络 · Ollama ● 在线 · 运行中」约 132px），
        真超了也只在最右边截几个字，不会溢出。
        """
        lab = QLabel(text)
        lab.setObjectName("SysInfo")
        lab.setTextFormat(Qt.RichText)
        lab.setToolTip(str(text))
        return lab

    # ---------- 刷新 ----------
    def apply(self, d):
        """把一次采样结果刷到界面上（GUI 线程）。"""
        for key, _ in self.KEYS:
            bar, val = self._rows[key]
            p = d.get(key)
            bar.set_pct(p)
            val.setText("—" if p is None else "%d%%" % int(round(p)))

        gpu_name = d.get("gpu_name") or ""
        gm = d.get("gpu_mem")
        tips = []
        if d.get("gpu") is None:
            tips.append("未检测到可读取的 GPU（需要 NVIDIA 显卡 + nvidia-smi）")
        else:
            if gpu_name:
                tips.append(gpu_name)
            if gm:
                tips.append("显存 %.1f / %.1f GB" % (gm[0] / 1024.0, gm[1] / 1024.0))
        self._rows["gpu"][0].setToolTip(" · ".join(tips))
        self._rows["gpu"][1].setToolTip(" · ".join(tips))

        # 网络 · Ollama：一个状态点同时编码两件事
        net_on, ol = d.get("net_on"), d.get("ollama_on")
        if net_on is None:
            txt, dot = "未知", _DOT_OFF
        elif not net_on:
            txt, dot = "离线", _DOT_OFF
        elif ol:
            txt, dot = "在线 · 运行中", _DOT_ON
        else:
            txt, dot = "在线 · 未启动", _DOT_WARN
        up, down = d.get("net_up"), d.get("net_down")
        net_tip = ["网络：%s" % ("已连接" if net_on else "未连接" if net_on is False else "未知"),
                   "Ollama：%s" % ("运行中" if ol else "未检测到")]
        if up is not None and down is not None:
            net_tip.append("↑ %.1f KB/s   ↓ %.1f KB/s" % (up, down))
        self.net_row.setText(
            '<span style="color:#8b8071">网络 · Ollama</span>'
            '<span style="color:%s"> ● </span>'
            '<span style="color:#c9bda9">%s</span>' % (dot, txt))
        self.net_row.setToolTip("\n".join(net_tip))

        # 当前模型
        model = str(d.get("model") or "")
        ok = d.get("model_ok", True)
        head = '<span style="color:#8b8071">当前模型</span>'
        if not model:
            self.model_row.setText('%s <span style="color:%s">—</span>' % (head, _DOT_OFF))
            self.model_row.setToolTip(
                "未指定模型：智能推荐 / 标签优化会自动取本机 Ollama 里的第一个模型")
        elif ok and d.get("ollama_on"):
            self.model_row.setText('%s <span style="color:%s">%s</span>'
                                   % (head, _DOT_ON, _short(model)))
            self.model_row.setToolTip(model)
        elif not d.get("ollama_on"):
            self.model_row.setText('%s <span style="color:%s">%s</span>'
                                   % (head, _DOT_WARN, _short(model)))
            self.model_row.setToolTip(
                "Ollama 未启动，本次会退回内置离线联想。\n设置里指定的是：%s" % model)
        else:
            self.model_row.setText('%s <span style="color:%s">%s</span>'
                                   % (head, _DOT_WARN, _short(model)))
            self.model_row.setToolTip(
                "设置里指定「%s」，但本机 Ollama 没装这个模型。\n"
                "可用 `ollama pull %s` 安装，或在工具 → 智能推荐里改选。" % (model, model))

    # ---------- 生命周期 ----------
    def stop(self):
        """**只退订，不停线程** —— 线程是进程级的，由 closeEvent / aboutToQuit 统一停。

        （面板会被 ``_apply_settings()`` 反复重建，谁先被删是不确定的；线程生死不交给这里。）
        """
        w = self._worker
        self._worker = None
        if w is not None:
            try:
                w.sampled.disconnect(self.apply)
            except Exception:
                pass


def _short(text, n=16):
    """窄侧栏里放不下长模型名（如 huihui_ai/qwen2.5-abliterate:7b），首尾留中间省略。"""
    text = str(text)
    if len(text) <= n:
        return text
    keep = n - 1
    head = keep // 2 + 1
    return text[:head] + "…" + text[-(keep - head):]


__all__ = ["SysMetrics", "SysMonWorker", "MiniBar", "SysMonitorPanel",
           "sysmon_disabled", "probe_ai", "shared_worker", "stop_shared_worker"]
