# -*- coding: utf-8 -*-
"""v1.26.0（Round 4 反馈 1/2/3）源码补丁。

三条反馈：
1. 换了「外观 → 高亮色」之后，设置页里所有**自绘开关（ToggleSwitch）**的轨道仍是朱红 ——
   根因是 `ToggleSwitch._ON = (0xc0,0x39,0x2b)` 写死，跟 QSS 令牌那条链完全脱钩。
2. 底部状态栏只有「版本 | Copyright」，要接上开源声明（跟在 Copyright 之后）。
3. 侧栏副标题「LocalMediaCenter」末尾的 r 被裁 —— 11px 量出 127px、可用 122px。

一律用 `open(..., newline="")` 写回，避免 Write/Edit 把 LF 转成 CRLF（本项目实测过）。
每处都断言 `s.count(old) == count`，命中数不对就整脚本退出，绝不「改错地方还继续」。
"""
import io
import os
import sys

ROOT = r"Z:/【01】自研软件/【26-19】本地影视中心"
SRC = os.path.join(ROOT, "src")

FAILED = []


def patch(rel, label, old, new, count=1):
    p = os.path.join(SRC, rel)
    with io.open(p, encoding="utf-8", newline="") as f:
        s = f.read()
    n = s.count(old)
    if n != count:
        FAILED.append(f"{label}：锚点命中 {n} 次（期望 {count}）")
        print(f"[FAIL] {label}：锚点命中 {n} 次（期望 {count}）")
        return False
    s = s.replace(old, new, count)
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    with io.open(p, encoding="utf-8", newline="") as f:
        back = f.read()
    if new not in back:
        FAILED.append(f"{label}：写回后回读没找到新片段")
        print(f"[FAIL] {label}：写回后回读没找到新片段")
        return False
    # 顺带确认没把文件写成 CRLF
    with open(p, "rb") as f:
        raw = f.read()
    crlf = raw.count(b"\r\n")
    print(f"[OK] {label}  (CRLF={crlf})")
    return True


# ---------------------------------------------------------------- 1. 开关跟随高亮色
patch("ui_settings.py", "①import sys",
      "import subprocess\nimport zipfile\n",
      "import subprocess\nimport sys\nimport zipfile\n")

patch("ui_settings.py", "②ToggleSwitch 轨道色现取",
      """    # 轨道底色：关 #4a4038 → 开 #c0392b
    _OFF = (0x4a, 0x40, 0x38)
    _ON = (0xc0, 0x39, 0x2b)

    def paintEvent(self, e):""",
      """    # 轨道底色：关 #4a4038 → 开 <当前高亮色>。
    # v1.26.0（反馈 1）：原来这里写死朱红 —— 用户在「外观 → 高亮色」里换成藕荷/天青后，
    # 设置页里所有自绘开关的轨道**仍然是红的**（截图：色板高亮停在藕荷，开关全是朱红）。
    # 现在改成每次绘制时现取高亮色（与 QSS 令牌同源）。_ON 保留为兜底值 = ACCENT_DEFAULT。
    _OFF = (0x4a, 0x40, 0x38)
    _ON = (0xc0, 0x39, 0x2b)

    @staticmethod
    def accent_on():
        \"\"\"当前高亮色的 RGB（跟随「外观 → 高亮色」）。

        为什么懒读 `main_window.ACCENT_RGB` 而不是模块级 `import main_window`：
        `main_window` 顶部就有 `from ui_settings import SettingsDialog, LibraryEditDialog`，
        这里反向 import 会成环（导入期类还没定义 → 窗口直接建不起来）。
        所以走 `sys.modules` 取「已加载完的那个模块对象」；拿不到时回落到 settings.json 的 accent。
        `render_style()` 每次重载样式表都会刷新 `ACCENT_RGB`，两边取到的必然是同一个值。
        \"\"\"
        mw = sys.modules.get("main_window")
        rgb = getattr(mw, "ACCENT_RGB", None) if mw is not None else None
        try:
            if rgb is not None:
                r, g, b = (int(v) for v in tuple(rgb)[:3])
                return (r, g, b)
        except (TypeError, ValueError):
            pass
        try:
            return tuple(cfg.accent_rgb(cfg.get_settings().accent()))
        except Exception:
            return ToggleSwitch._ON

    def paintEvent(self, e):""")

patch("ui_settings.py", "③paintEvent 用现取的轨道色",
      "        p.setBrush(QColor(*[int(a + (b - a) * t) for a, b in zip(self._OFF, self._ON)]))",
      "        on = self.accent_on()\n"
      "        p.setBrush(QColor(*[int(a + (b - a) * t) for a, b in zip(self._OFF, on)]))")

patch("ui_settings.py", "④换色后刷新所有开关",
      """        self.s.set_accent(hexv)
        self._paint_accent_btns()
        self._apply_appearance()""",
      """        self.s.set_accent(hexv)
        self._paint_accent_btns()
        self._refresh_toggles()
        self._apply_appearance()""")

patch("ui_settings.py", "⑤新增 _refresh_toggles",
      """    def _refresh_backdrop_hint(self):
        mode = self.s.appearance.get("mode")""",
      """    def _refresh_toggles(self):
        \"\"\"换高亮色后让设置页里所有自绘开关**立刻**重画。

        轨道色是 paintEvent 里现取的，但 Qt 不会因为「某个模块级变量变了」就自动重绘 ——
        不显式 update() 的话要等鼠标划过才变色，用户会以为「这个开关没跟着变」。
        \"\"\"
        for sw in self.findChildren(ToggleSwitch):
            sw.update()

    def _refresh_backdrop_hint(self):
        mode = self.s.appearance.get("mode")""")

# ---------------------------------------------------------------- 2. 底部开源声明
patch("main_window.py", "⑥状态栏接上开源声明",
      """        self.statusBar().showMessage(f"{ver.FULL_VERSION}  |  {ver.COPYRIGHT}")""",
      """        # v1.26.0（反馈 2）：用户要求把开源声明也放到最底部，且要**跟在 Copyright 之后**。
        self.statusBar().showMessage(
            f"{ver.FULL_VERSION}  |  {ver.COPYRIGHT}  |  {ver.LICENSE_NOTE}")""")

# ---------------------------------------------------------------- 3. 副标题字号
patch("style.qss", "⑦副标题字号 11px → 10px",
      "QLabel#Sub { color: #8c8071; font-size: 11px; letter-spacing: 2px; }",
      "/* v1.26.0（反馈 3）：11px 下「LocalMediaCenter」量出 127px、品牌区只有 122px，\n"
      "   末尾的 r 被裁掉；降到 10px 并把字距收到 1.5px，实测 113px（余 9px）。 */\n"
      "QLabel#Sub { color: #8c8071; font-size: 10px; letter-spacing: 1.5px; }")

print()
if FAILED:
    print("[结果] 有 %d 处未落盘：" % len(FAILED))
    for f in FAILED:
        print("   -", f)
    sys.exit(1)
print("[结果] 7 处补丁全部落盘并回读确认。")
