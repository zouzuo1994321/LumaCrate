# -*- coding: utf-8 -*-
"""v2.0.10 预览图：首页筛选面板能打中文了。

全部用真机截图拼（不画假图）：
  · 左：点表头漏斗弹出的面板，输入框里已经有「机器」两个字；
  · 右上 / 右下：筛选前 7 行 → 筛选后只剩「MIDA-210 机器猫」1 行。
"""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
SH = os.path.join(ROOT, "dev", "screenshots")
OUT = os.path.join(ROOT, "docs", "preview", "v2010_filter_cn.png")
FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_B = "C:/Windows/Fonts/msyhbd.ttc"

BG = (20, 20, 23)
CARD = (28, 28, 32)
LINE = (58, 58, 66)
TXT = (237, 237, 240)
DIM = (150, 150, 160)
ACC = (228, 88, 124)
OK = (74, 222, 128)


def f(sz, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, sz)


def load(n):
    return Image.open(os.path.join(SH, n)).convert("RGB")


W, H = 1400, 812
im = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(im)

d.text((44, 30), "v2.0.10 · 首页表头筛选：中文终于能打进去了", font=f(28, True), fill=TXT)
d.text((44, 72), "根因不是输入法，是窗口类型：Qt.Popup 在 Windows 上是「菜单类窗口」，"
                  "永远不会成为前台窗口，输入法挂不上 → 只能打英文。",
       font=f(15), fill=DIM)

# ---------------- 左：面板本体 ----------------
pop = load("v2010_popup_typed.png")
PW, PH = pop.width, pop.height
s = 2.6
pop2 = pop.resize((int(PW * s), int(PH * s)), Image.LANCZOS)
px, py = 44, 132
d.rounded_rectangle((px - 10, py - 10, px + pop2.width + 10, py + pop2.height + 10),
                    radius=10, fill=CARD, outline=LINE)
im.paste(pop2, (px, py))
d.text((px, py + pop2.height + 22), "点表头「标题」列的漏斗 → 面板弹出即拿到前台焦点",
       font=f(14), fill=DIM)
d.text((px, py + pop2.height + 46), "输入框里是刚打进去的中文「机器」（不是灰色占位提示）",
       font=f(14), fill=OK)

# ---------------- 右：筛选前 / 后 ----------------
CROP = (200, 143, 900, 400)


def listcrop(name, sc):
    c = load(name).crop(CROP)
    return c.resize((int(c.width * sc), int(c.height * sc)), Image.LANCZOS)


a = listcrop("v2010_home.png", 0.86)
b = listcrop("v2010_filtered.png", 0.86)
rx = 748
ry = 132
for tag, pic, col in (("筛选前：7 部片", a, DIM), ("输入「机器」回车后：只剩 1 部", b, ACC)):
    d.rounded_rectangle((rx - 8, ry - 8, rx + pic.width + 8, ry + pic.height + 8),
                        radius=10, fill=CARD, outline=LINE)
    im.paste(pic, (rx, ry))
    d.text((rx, ry - 34), tag, font=f(15, True), fill=col)
    ry += pic.height + 56

# ---------------- 底部结论 ----------------
by = 640
d.line((44, by - 16, W - 44, by - 16), fill=LINE)
facts = [
    ("窗口类型", "Qt.Popup（0x09）", "Qt.Dialog（0x03）"),
    ("EXSTYLE", "0x88 = TOOLWINDOW|TOPMOST（菜单类）", "0x00（普通可激活窗口）"),
    ("Windows 前台窗口", "永远不是", "是（实测 fg == 面板 hwnd）"),
    ("中文上屏", "打不出", "7 行 → 1 行，清空后 7 行全回来"),
]
colx = [44, 250, 700]
d.text((colx[0], by), "实测项", font=f(14, True), fill=DIM)
d.text((colx[1], by), "旧的 Qt.Popup", font=f(14, True), fill=DIM)
d.text((colx[2], by), "现在（Qt.Dialog + 自绘「点外面关闭」）", font=f(14, True), fill=DIM)
for i, (k, old, new) in enumerate(facts):
    y = by + 30 + i * 26
    d.text((colx[0], y), k, font=f(14), fill=TXT)
    d.text((colx[1], y), old, font=f(14), fill=(220, 120, 120))
    d.text((colx[2], y), new, font=f(14), fill=OK)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
im.save(OUT)
print("saved", OUT, im.size)
