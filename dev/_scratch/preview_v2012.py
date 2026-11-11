# -*- coding: utf-8 -*-
"""出 v2.0.12 的对照预览图 `docs/preview/v2012_fix.png`。

素材全部是真机像素：
  · v2012_probe_menu.png / v2012_probe_psd.png —— 同进程真窗口 + `grabWindow(0)`
    （合成后），垫亮蓝底，圆角外是不是透明一眼可见；
  · v2012_home.png —— exe 真机截图，裁表头左上角（本轮第三个问题）。
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
SHOTS = os.path.join(ROOT, "dev", "screenshots")
OUT = os.path.join(ROOT, "docs", "preview", "v2012_fix.png")

W = 1440
PAD = 44
ROW_H = 330

BG = (16, 16, 20)
CARD = (24, 24, 27)
LINE = (48, 48, 54)
TXT = (237, 237, 238)
DIM = (150, 150, 158)
ACCENT = (228, 88, 124)
GOLD = (232, 189, 110)


def font(size, bold=False):
    for f in ((r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
              r"C:\Windows\Fonts\msyh.ttc"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


F_TITLE = font(36, True)
F_H2 = font(23, True)
F_BODY = font(17)
F_SMALL = font(15)
F_MONO = font(15)


def fit(im, box_w, box_h):
    """等比缩放到装进 box（不放大超过 3.2 倍，免得糊）。"""
    s = min(box_w / im.width, box_h / im.height, 3.2)
    return im.resize((int(im.width * s), int(im.height * s)), Image.NEAREST)


def wrap(draw, text, f, max_w):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=f) > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


img = Image.new("RGB", (W, 1600), BG)
d = ImageDraw.Draw(img)

y = PAD
d.text((PAD, y), "流明盒 v2.0.12 · 圆角外面那圈黑框没了", font=F_TITLE, fill=TXT)
y += 58
d.text((PAD, y), "根因：QMenu / 无边框 QDialog 都是顶层窗口，窗口表面永远不透明；"
                 "QSS 只把底色画进圆角路径里，路径外没有任何东西去绘制 → 露出纯黑。",
       font=F_BODY, fill=DIM)
y += 30
d.text((PAD, y), "修法：uiwin.bare() 开 WA_TranslucentBackground + FramelessWindowHint + "
                 "NoDropShadowWindowHint（创建前设）；圆角与底色改由内层容器画。",
       font=F_BODY, fill=DIM)
y += 46

# ---------------- 三个卡片 ----------------
menu = Image.open(os.path.join(SHOTS, "v2012_probe_menu.png")).convert("RGB")
psd = Image.open(os.path.join(SHOTS, "v2012_probe_psd.png")).convert("RGB")
home = Image.open(os.path.join(SHOTS, "v2012_home.png")).convert("RGB")
hdr = home.crop((188, 134, 316, 190))          # 表头左上角（真机，只取到表头下边框）

CARDS = [
    (menu, 1.9, "① 右键菜单（QMenu）", [
        ("修法", "全部菜单改由 uiwin.menu() 创建（9 处），子菜单再套一层 bare()"),
        ("真机", "四角像素与「关掉菜单后」逐通道相同：差 0 / 0 / 0 / 0"),
        ("实测", "menu 141×201 · EXSTYLE 0x00080088（含 WS_EX_LAYERED）"),
        ("", "圆角外 = #1f7ae0（身后底色原色），不再是 #000000"),
    ]),
    (psd, 1.55, "② 「替换演员」弹层（400×314）", [
        ("修法", "uiwin.bare(self) + 新增内层容器 #PSDBody 承担圆角与底色"),
        ("原因", "半透明顶层窗口的「根控件」不画 QSS 底色（矩阵实测四种组合 alpha 全 0）"),
        ("实测", "四角 #1f79de = 身后底色；内侧 93% 像素是深色面板色 #18181b"),
        ("", "输入框仍拿得到焦点：打「机器」→ 亮字 0 → 85，列表 7 行 → 1 行"),
    ]),
    (hdr, 3.6, "③ 表格顶部圆角（表头首列）", [
        ("现象", "不是黑框，而是方形表头把表格 14px 圆角的缺口压成了深色楔形"),
        ("修法", "QHeaderView::section:first/:last 补 13px 顶部圆角（与表格同心）"),
        ("实测", "缺口 #207be0 = 页面底色，与表头正文 #2980e1 同一档，不再发暗"),
        ("", "另删掉全局 QDialog 的 16px 圆角：带原生标题栏的窗口只会被削出四个洞"),
    ]),
]

for i, (im, scale, title, rows) in enumerate(CARDS):
    top = y + i * (ROW_H + 22)
    d.rounded_rectangle([PAD, top, W - PAD, top + ROW_H], 16, fill=CARD, outline=LINE)
    # 图：先留出 34px 给图注，避免图把字压掉
    d.text((PAD + 26, top + 10),
           ("亮蓝底 · 真机合成截图 ×%.1f" % scale) if i < 2
           else "真机截图 · 3.6 倍放大", font=F_SMALL, fill=DIM)
    box = fit(im, 462, ROW_H - 78)
    ix, iy = PAD + 30, top + 40 + (ROW_H - 78 - box.height) // 2
    img.paste(box, (ix, iy))
    d.rectangle([ix - 1, iy - 1, ix + box.width, iy + box.height], outline=LINE)
    # 文字
    tx = PAD + 26 + 470 + 34
    d.text((tx, top + 24), title, font=F_H2, fill=GOLD)
    ty = top + 68
    for (k, v) in rows:
        if k:
            d.text((tx, ty), k, font=F_SMALL, fill=ACCENT)
        for ln in wrap(d, v, F_BODY, W - PAD - 26 - tx - (44 if k else 0)):
            d.text((tx + (44 if k else 0), ty), ln, font=F_BODY, fill=TXT)
            ty += 25
        ty += 6

y = PAD + 46 + 3 * (ROW_H + 22) + 26
d.line([PAD, y, W - PAD, y], fill=LINE)
y += 26
d.text((PAD, y), "验收（exe 真机 + 离屏冒烟，全部通过）", font=F_H2, fill=GOLD)
y += 40
for ln in ("· 真机 live_v2012_exe.py：29 / 29 全绿（LIVE_V2012_ALL_OK）——含中文输入全链路回归，"
           "半透明窗口仍能成为前台窗口、输入法照常上屏。",
           "· 离屏冒烟：812 / 812 全绿（新增 ㊳ 段 29 条：窗口属性 + 源码级无裸 QMenu( + 三浮层 grab 像素 + 表头缺口像素）。",
           "· 未动 QToolTip：Qt 不给 show 之前的时机，实测它渲染成方形深色块，黑角与自身底色几乎无差，看不出来。"):
    d.text((PAD, y), ln, font=F_SMALL, fill=DIM)
    y += 27

img = img.crop((0, 0, W, y + 30))
img.save(OUT)
print("->", OUT, img.size)
