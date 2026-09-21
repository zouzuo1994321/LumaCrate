# -*- coding: utf-8 -*-
"""
Windows 磨砂玻璃（系统级模糊）支持
=================================
两级实现，逐级降级：

1. **Win11 22H2+：DWM 系统背景材质** `DWMWA_SYSTEMBACKDROP_TYPE`（首选）
   - 2 = Mica（主窗口，跟随壁纸、模糊更强）
   - 3 = Acrylic / Transient（真正的磨砂玻璃，桌面内容透出最明显）
   - 4 = Tabbed
2. **Win10 1903+：`SetWindowCompositionAttribute` + `ACCENT_ENABLE_ACRYLICBLURBEHIND`**
   （老系统的亚克力，可自定义 tint 颜色）
3. 都不支持（或非 Windows / 关掉了 DWM）：返回失败，调用方自动退化为「经典暗色」纯色主题。

窗口客户区必须「不被不透明地绘制」，磨砂才透得出来 —— 这由 `style.qss` 里的半透明 rgba 负责。
"""
import ctypes
import os
import sys

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_SYSTEMBACKDROP_TYPE = 38

DWMSBT_AUTO = 0
DWMSBT_NONE = 1
DWMSBT_MAINWINDOW = 2       # Mica
DWMSBT_TRANSIENTWINDOW = 3  # Acrylic（磨砂玻璃）
DWMSBT_TABBEDWINDOW = 4

DWMWCP_DEFAULT = 0
DWMWCP_DONOTROUND = 1
DWMWCP_ROUND = 2

WCA_ACCENT_POLICY = 19
ACCENT_DISABLED = 0
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4


class _ACCENTPOLICY(ctypes.Structure):
    _fields_ = [("AccentState", ctypes.c_int),
                ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId", ctypes.c_int)]


class _WINCOMPATTRDATA(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int),
                ("Data", ctypes.c_void_p),
                ("SizeOfData", ctypes.c_size_t)]


def _hwnd(widget) -> int:
    try:
        return int(widget.winId())
    except Exception:
        return 0


def _dwm_set(hwnd: int, attr: int, value: int, size: int = 4) -> int:
    try:
        dwmapi = ctypes.windll.dwmapi
        v = ctypes.c_int(value)
        hr = dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), ctypes.c_uint(attr),
            ctypes.byref(v), ctypes.c_uint(size))
        return int(hr)
    except Exception:
        return -1


def _set_accent(hwnd: int, state: int, gradient_color: int = 0) -> bool:
    try:
        user32 = ctypes.windll.user32
        setter = getattr(user32, "SetWindowCompositionAttribute", None)
        if setter is None:
            return False
        policy = _ACCENTPOLICY()
        policy.AccentState = state
        policy.AccentFlags = int(os.environ.get("LMC_ACCENT_FLAGS", "2"))
        policy.GradientColor = gradient_color
        data = _WINCOMPATTRDATA()
        data.Attribute = WCA_ACCENT_POLICY
        data.Data = ctypes.cast(ctypes.pointer(policy), ctypes.c_void_p)
        data.SizeOfData = ctypes.sizeof(policy)
        setter(ctypes.c_void_p(hwnd), ctypes.byref(data))
        return True
    except Exception:
        return False


def is_windows() -> bool:
    return sys.platform.startswith("win")


def windows_build() -> int:
    if not is_windows():
        return 0
    try:
        return int(sys.getwindowsversion().build)
    except Exception:
        try:
            return int(ctypes.windll.ntdll.RtlGetVersion.__class__ and 0)
        except Exception:
            return 0


def apply_glass(widget, tint_bgra: int = 0xB01B1712, dark: bool = True,
                corner: bool = True) -> dict:
    """给窗口开启磨砂玻璃。

    tint_bgra: Win10 亚克力路径的 tint，格式 0xAABBGGRR。
    返回 {"ok": bool, "method": str, "detail": str}。
    """
    if not is_windows():
        return {"ok": False, "method": "none", "detail": "非 Windows 平台"}
    hwnd = _hwnd(widget)
    if not hwnd:
        return {"ok": False, "method": "none", "detail": "窗口句柄不可用"}

    if dark:
        _dwm_set(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
    if corner:
        _dwm_set(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)

    build = windows_build()
    detail = []
    # 1) Win11 22H2+：系统背景材质（Acrylic 磨砂）
    if build >= 22621 and os.environ.get("LMC_FORCE_WCA") != "1":
        bt = int(os.environ.get("LMC_DWMBT", str(DWMSBT_TRANSIENTWINDOW)))
        hr = _dwm_set(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, bt)
        if hr == 0:
            return {"ok": True, "method": "dwm-acrylic", "detail": f"Win11 build {build}"}
        detail.append(f"systembackdrop hr={hr}")
    # 2) Win10 1903+ / Win11 早期版本：SetWindowCompositionAttribute 亚克力
    if build >= 17763 or build == 0:
        if _set_accent(hwnd, ACCENT_ENABLE_ACRYLICBLURBEHIND, tint_bgra):
            return {"ok": True, "method": "wca-acrylic", "detail": f"build {build}"}
        detail.append("wca acrylic unavailable")
    # 3) 退一步：老式高斯模糊（无 tint）
    if _set_accent(hwnd, ACCENT_ENABLE_BLURBEHIND):
        return {"ok": True, "method": "wca-blur", "detail": f"build {build}"}
    return {"ok": False, "method": "none", "detail": "; ".join(detail) or "系统不支持"}


def remove_glass(widget) -> dict:
    """关闭磨砂，恢复系统默认（配合「经典暗色」主题）。"""
    if not is_windows():
        return {"ok": False, "method": "none", "detail": "非 Windows 平台"}
    hwnd = _hwnd(widget)
    if not hwnd:
        return {"ok": False, "method": "none", "detail": "窗口句柄不可用"}
    _set_accent(hwnd, ACCENT_DISABLED)
    hr = _dwm_set(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, DWMSBT_NONE)
    _dwm_set(hwnd, DWMWA_CAPTION_COLOR, -1)
    return {"ok": hr == 0 or True, "method": "none", "detail": f"hr={hr}"}


def apply_backdrop(widget, mode: str = "磨砂玻璃", level: str = "中",
                   dark: bool = True) -> dict:
    """按外观设置应用背景效果；返回结果字典（供界面提示）。"""
    if mode == "磨砂玻璃":
        tint = {"低": 0xCC1B1712, "中": 0xB01B1712, "高": 0x8C1B1712}.get(level, 0xB01B1712)
        env_tint = os.environ.get("LMC_TINT")          # 调试用：0xAABBGGRR
        if env_tint:
            tint = int(env_tint, 16)
        return apply_glass(widget, tint_bgra=tint, dark=dark)
    return remove_glass(widget)


def auto_apply(widget) -> dict:
    """读取当前外观设置并应用背景效果（主窗口 / 对话框通用）。"""
    try:
        import config as cfg
        ap = (cfg.get_settings().appearance or cfg.DEFAULT_APPEARANCE)
    except Exception:
        return apply_backdrop(widget)
    return apply_backdrop(widget, ap.get("mode", "磨砂玻璃"),
                           ap.get("level", "中"), True)
