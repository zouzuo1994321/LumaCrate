# -*- coding: utf-8 -*-
"""v2.0.0 第三轮：整数元组 / 常量形态的旧色（hex 扫描覆盖不到的部分）。

涉及三块「视觉地基」，改完全局观感才统一：
  1. veil.default_backdrop —— 应用内磨砂底衬的兜底底图（原墨黑 + 朱红/鎏金柔光）；
     改为中性近黑 + **跟随高亮色**的柔光（懒读 main_window.ACCENT_RGB）。
  2. letter_index —— A-Z 条的 5 个常量（原暖灰 + 朱红 hover + 鎏金选中）。
  3. 各处自绘/常量里的朱红、旧金、暖白（主窗三角、收藏星、卡片状态色、
     文件夹卡 hover 描边、海报卡压暗渐变、开关轨道）。
"""
import io
import os

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\src"


def rd(fn):
    return io.open(os.path.join(SRC, fn), encoding="utf-8").read()


def wr(fn, s):
    io.open(os.path.join(SRC, fn), "w", encoding="utf-8").write(s)


def sub(s, old, new, tag, miss):
    if old not in s:
        miss.append(tag + "  << " + old[:66])
        return s
    print("OK   %s" % tag)
    return s.replace(old, new, 1)


miss = []

# ============================ veil.py ============================
s = rd("veil.py")
s = sub(s,
        'from PySide6.QtCore import Qt',
        'import sys\n\nfrom PySide6.QtCore import Qt', "veil 导入 sys", miss)

old = '''def default_backdrop(w: int, h: int) -> QPixmap:
    """没有剧照时的兜底底图：墨黑底 + 朱红/鎏金柔光，模糊后天然是磨砂质感。"""
    w, h = max(64, w), max(64, h)
    small = QPixmap(max(64, w // BLUR_FACTOR), max(64, h // BLUR_FACTOR))
    small.fill(QColor(11, 9, 8))
    p = QPainter(small)
    p.setRenderHint(QPainter.Antialiasing, True)
    sw, sh = small.width(), small.height()
    for (cx, cy, rad, color) in ((0.16, 0.10, 1.05, QColor(139, 43, 33, 210)),
                                 (0.92, 0.14, 0.85, QColor(201, 162, 74, 150)),
                                 (0.70, 0.98, 1.15, QColor(74, 32, 28, 200)),
                                 (0.05, 0.90, 0.75, QColor(120, 96, 42, 110))):'''
new = '''def accent_rgb():
    """当前高亮色 —— 懒读 `main_window.ACCENT_RGB`（反向 import 会成环）。

    拿不到时回落 HeroUI primary #006fee。底衬跟着高亮色走，换色时整块氛围一起变，
    与 QSS 令牌、自绘控件三处同源。
    """
    mw = sys.modules.get("main_window")
    rgb = getattr(mw, "ACCENT_RGB", None) if mw is not None else None
    try:
        if rgb is not None:
            r, g, b = (int(v) for v in tuple(rgb)[:3])
            return (r, g, b)
    except (TypeError, ValueError):
        pass
    return (0, 111, 238)


def default_backdrop(w: int, h: int) -> QPixmap:
    """没有剧照时的兜底底图（v2.0.0 HeroUI 暗色）：中性近黑 + 高亮色柔光。

    原来是「墨黑 + 朱红 + 鎏金」四处暖光，在 HeroUI 的中性色阶旁边会显出橘调，
    所以改成：底 = #0a0a0b，左上/右上两团**高亮色**低透明度柔光（54 / 26），
    右下/左下两团中性提亮。模糊后仍是磨砂质感，但不再与中性面板打架。
    """
    w, h = max(64, w), max(64, h)
    small = QPixmap(max(64, w // BLUR_FACTOR), max(64, h // BLUR_FACTOR))
    small.fill(QColor(10, 10, 11))
    p = QPainter(small)
    p.setRenderHint(QPainter.Antialiasing, True)
    sw, sh = small.width(), small.height()
    ar, ag, ab = accent_rgb()
    for (cx, cy, rad, color) in ((0.16, 0.10, 1.05, QColor(ar, ag, ab, 54)),
                                 (0.92, 0.14, 0.85, QColor(ar, ag, ab, 26)),
                                 (0.70, 0.98, 1.15, QColor(38, 38, 42, 200)),
                                 (0.05, 0.90, 0.75, QColor(24, 24, 27, 170))):'''
s = sub(s, old, new, "veil 兜底底图改中性+高亮柔光", miss)

s = sub(s,
        'painter.fillRect(0, 0, w, h, QColor(15, 13, 12))',
        'painter.fillRect(0, 0, w, h, QColor(10, 10, 11))', "veil 关闭态底色", miss)
s = sub(s,
        'painter.fillRect(0, 0, w, h, QColor(13, 11, 10, self._scrim))',
        'painter.fillRect(0, 0, w, h, QColor(10, 10, 11, self._scrim))', "veil 压暗色", miss)
wr("veil.py", s)

# ============================ letter_index.py ============================
s = rd("letter_index.py")
s = sub(s,
        'from PySide6.QtCore import Qt, Signal, QRect, QSize',
        'import sys\n\nfrom PySide6.QtCore import Qt, Signal, QRect, QSize', "letter 导入 sys", miss)

old = '''_COLOR_TEXT = QColor(201, 189, 167)     # #d4d4d8，与卡片信息值同色
_COLOR_DIM = QColor(107, 97, 82)        # 无数据的字母（不可点）
_COLOR_HOVER_BG = QColor(192, 57, 43, 60)
_COLOR_ACTIVE = QColor(212, 175, 55)    # #66a9ff 金色
_COLOR_ACTIVE_BG = QColor(212, 175, 55, 38)'''
new = '''# v2.0.0：换成 HeroUI 中性色阶；悬停/选中都**跟随「外观 → 高亮色」**（原来写死朱红+鎏金）
_COLOR_TEXT = QColor(212, 212, 216)     # #d4d4d8，与卡片信息值同色
_COLOR_DIM = QColor(82, 82, 91)         # #52525b，无数据的字母（不可点）
_COLOR_HOVER_BG = QColor(255, 255, 255, 20)   # 白 8%：HeroUI 的幽灵悬停底


def _accent_rgb():
    """现取高亮色（懒读 main_window.ACCENT_RGB，反向 import 会成环）。"""
    mw = sys.modules.get("main_window")
    rgb = getattr(mw, "ACCENT_RGB", None) if mw is not None else None
    try:
        if rgb is not None:
            r, g, b = (int(v) for v in tuple(rgb)[:3])
            return (r, g, b)
    except (TypeError, ValueError):
        pass
    return (0, 111, 238)'''
s = sub(s, old, new, "letter 常量改中性+高亮色", miss)

old = '''        p.fillRect(self.rect(), Qt.transparent)
        h = self.row_height()'''
new = '''        p.fillRect(self.rect(), Qt.transparent)
        ar, ag, ab = _accent_rgb()
        c_active = QColor(ar, ag, ab)
        c_active_bg = QColor(ar, ag, ab, 40)
        h = self.row_height()'''
s = sub(s, old, new, "letter 取高亮色", miss)

s = sub(s, 'p.fillRect(r, _COLOR_ACTIVE_BG)', 'p.fillRect(r, c_active_bg)',
        "letter 选中底", miss)
s = sub(s, 'p.setPen(_COLOR_ACTIVE if (on and lt == self._active) else',
        'p.setPen(c_active if (on and lt == self._active) else', "letter 选中字", miss)
wr("letter_index.py", s)

# ============================ main_window.py ============================
s = rd("main_window.py")
s = sub(s, 'ACCENT_RGB = (192, 57, 43)', 'ACCENT_RGB = (0, 111, 238)', "main 兜底高亮色", miss)
s = sub(s, 'p.setBrush(QColor(243, 240, 234))', 'p.setBrush(QColor(250, 250, 250))',
        "播放三角 暖白→纯白", miss)
s = sub(s, 'p.setBrush(QColor(247, 201, 72))', 'p.setBrush(QColor(245, 165, 36))',
        "收藏星 旧金→琥珀", miss)
s = sub(s, 'p.setPen(QPen(QColor(74, 52, 6, 210), 1.0))',
        'p.setPen(QPen(QColor(0, 0, 0, 160), 1.0))', "收藏星 描边→黑", miss)
s = sub(s, 'else QColor(246, 243, 238), 1.7))',
        'else QColor(236, 237, 238), 1.7))', "收藏星 未选白→中性白", miss)
s = sub(s, 'p.setPen(QPen(QColor(192, 57, 43, 205) if self._hover else QColor(255, 255, 255, 46),',
        'p.setPen(QPen(QColor(*ACCENT_RGB, 205) if self._hover else QColor(255, 255, 255, 46),',
        "文件夹卡 hover 描边→高亮色", miss)
s = sub(s, '''        if status == "现役":
            base, border = QColor(46, 122, 74, 92), QColor(116, 220, 140, 205)
        elif status == "退役":
            base, border = QColor(148, 120, 38, 86), QColor(236, 202, 96, 210)''',
        '''        if status == "现役":
            # v2.0.0：HeroUI 语义色（翡翠 #17c964）；底色收到 46 通透一点，小卡才不闷
            base, border = QColor(23, 201, 100, 46), QColor(23, 201, 100, 200)
        elif status == "退役":
            # 琥珀 #f5a524
            base, border = QColor(245, 165, 36, 46), QColor(245, 165, 36, 200)''',
        "演员卡 现役/退役 状态色", miss)
s = sub(s, 'p.fillRect(0, 0, w, h, QColor(13, 11, 10))',
        'p.fillRect(0, 0, w, h, QColor(10, 10, 11))', "main 自绘底→页面底", miss)
wr("main_window.py", s)

# ============================ ui_hero.py 压暗渐变 ============================
s = rd("ui_hero.py")
for old, new, tag in (
        ('g.setColorAt(0.00, QColor(12, 10, 9, 0))', 'g.setColorAt(0.00, QColor(10, 10, 11, 0))', "海报压暗 0.00"),
        ('g.setColorAt(0.45, QColor(12, 10, 9, 52))', 'g.setColorAt(0.45, QColor(10, 10, 11, 52))', "海报压暗 0.45"),
        ('g.setColorAt(0.70, QColor(12, 10, 9, 104))', 'g.setColorAt(0.70, QColor(10, 10, 11, 104))', "海报压暗 0.70"),
        ('g.setColorAt(0.92, QColor(12, 10, 9, 150))', 'g.setColorAt(0.92, QColor(10, 10, 11, 150))', "海报压暗 0.92"),
        ('g.setColorAt(1.00, QColor(15, 13, 12, 255))', 'g.setColorAt(1.00, QColor(17, 17, 19, 255))', "海报压暗 1.00"),
        ('g2.setColorAt(0.0, QColor(12, 10, 9, 120))', 'g2.setColorAt(0.0, QColor(10, 10, 11, 120))', "左侧压暗 0.0"),
        ('g2.setColorAt(0.55, QColor(12, 10, 9, 34))', 'g2.setColorAt(0.55, QColor(10, 10, 11, 34))', "左侧压暗 0.55"),
        ('g2.setColorAt(1.0, QColor(12, 10, 9, 0))', 'g2.setColorAt(1.0, QColor(10, 10, 11, 0))', "左侧压暗 1.0"),
        ('flow.addWidget(_label("（还没有标签，点「＋」添加）", 12, False, "#8c8073"))',
         'flow.addWidget(_label("（还没有标签，点「＋」添加）", 12, False, "#71717a"))', "空标签提示→弱文字"),
        ('"background:#27272a;color:#e6d6b8;border:1px solid #4a3b28;"',
         '"background:#27272a;color:#d4d4d8;border:1px solid #3f3f46;"', "标签 chip 配色"),
):
    s = sub(s, old, new, "ui_hero " + tag, miss)
wr("ui_hero.py", s)

# ============================ ui_settings.py ============================
s = rd("ui_settings.py")
s = sub(s, '    # 轨道底色：关 #4a4038 → 开 <当前高亮色>。',
        '    # 轨道底色：关 #3f3f46 → 开 <当前高亮色>。', "开关 注释", miss)
s = sub(s, '    _OFF = (0x4a, 0x40, 0x38)', '    _OFF = (0x3f, 0x3f, 0x46)', "开关 关态轨道", miss)
s = sub(s, '    _ON = (0xc0, 0x39, 0x2b)', '    _ON = (0x00, 0x6f, 0xee)', "开关 开态兜底", miss)
s = sub(s, 'p.setPen(QPen(QColor("#338ef7"), 2.0))',
        'p.setPen(QPen(QColor("#338ef7"), 2.0))', "雷达 描边(不变)", miss) if False else s
s = sub(s, 'p.setBrush(QBrush(QColor(95, 176, 255, 62)))',
        'p.setBrush(QBrush(QColor(51, 142, 247, 62)))', "雷达 填充→天青", miss)
s = sub(s, 'p.setBrush(QColor("#8fd0ff"))', 'p.setBrush(QColor("#8fc0ff"))', "雷达 顶点", miss)
s = sub(s, 'p.setPen(QColor("#e2d7c3"))', 'p.setPen(QColor("#a1a1aa"))', "雷达 轴标签", miss)
s = sub(s, 'accent="#C63975"', 'accent="#f31260"', "条形默认色→玫红", miss)
s = sub(s, '<span style="color:#cdbd9f">%s%s</span>',
        '<span style="color:#a1a1aa">%s%s</span>', "条形标签色", miss)
s = sub(s, '"#e08e8e")', '"#f87171")', "扫描出错提示→danger", miss)
wr("ui_settings.py", s)

# ============================ ui_imagedetect.py ============================
s = rd("ui_imagedetect.py")
s = sub(s, '"缺图": "#9aa7b8"', '"缺图": "#a1a1aa"', "缺图状态色", miss)
s = sub(s, 'it.setForeground(C_AI, QColor("#6b6257"))',
        'it.setForeground(C_AI, QColor("#71717a"))', "AI 列前景→弱文字", miss)
wr("ui_imagedetect.py", s)

# ============================ sysmon.py ============================
s = rd("sysmon.py")
s = sub(s, '_ACCENT_FALLBACK = (192, 57, 43)            # 拿不到 ACCENT_RGB 时的朱红',
        '_ACCENT_FALLBACK = (0, 111, 238)            # 拿不到 ACCENT_RGB 时的 HeroUI 蓝', "sysmon 兜底高亮色", miss)
wr("sysmon.py", s)

print()
if miss:
    print("!! 未命中 %d 条：" % len(miss))
    for m in miss:
        print("   ", m)
else:
    print("全部命中，无遗漏。")
