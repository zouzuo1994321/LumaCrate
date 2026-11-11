# -*- coding: utf-8 -*-
"""出 v2.0.14 的对照预览图 `docs/preview/v2014_fix.png`。

上排 = 需求 1（右键菜单圆角外的黑角）：左是用户截图，右是修复后 exe 真机截图；
下排 = 需求 2（右侧清空小叉）：左是「打进字之后」的输入框右端，右是同一块的 ×6 放大。

两张真机图都由 `dev/_scratch/live_v2014_exe.py` 抓。
"""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
SHOTS = os.path.join(ROOT, "dev", "screenshots")
USER = (r"C:\Users\zouzu\.workbuddy\clipboard-images"
        r"\clipboard-2026-11-11T12-07-07-836Z-eca90b81.png")
OUT = os.path.join(ROOT, "docs", "preview", "v2014_fix.png")

W, PAD = 1320, 44
BG = (16, 16, 20)
CARD = (24, 24, 27)
LINE = (48, 48, 54)
TXT = (237, 237, 238)
DIM = (150, 150, 158)
ACCENT = (228, 88, 124)
GOLD = (232, 189, 110)
RED = (232, 106, 106)
GREEN = (126, 200, 140)


def font(size, bold=False):
    f = r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"
    if not os.path.exists(f):
        f = r"C:\Windows\Fonts\msyh.ttc"
    return ImageFont.truetype(f, size)


F_TITLE = font(34, True)
F_H2 = font(22, True)
F_BODY = font(17)
F_SMALL = font(15)


def wrap(d, text, f, max_w):
    out, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=f) > max_w:
            out.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def fit(im, h):
    s = h / im.height
    return im.resize((max(1, int(im.width * s)), h), Image.LANCZOS)


# ---------------- 素材 ----------------
before = Image.open(USER).convert("RGB")                       # 用户截图：菜单本体 201x289
after = Image.open(os.path.join(SHOTS, "v2014_ctx_menu.png")).convert("RGB")
typed = Image.open(os.path.join(SHOTS, "v2014_typed.png")).convert("RGB")
cleared = Image.open(os.path.join(SHOTS, "v2014_cleared.png")).convert("RGB")

H_MENU = 330
ib, ia = fit(before, H_MENU), fit(after, H_MENU)

# 清空叉那两张：直接从真机整屏图里裁「输入框右端 45px」，再 ×8。
# 真机上列表搜索框 left=200 top=104 w=1185 h=35（坐标表给的），右端 x=1385。
BOX_R, BOX_T, BOX_B = 1385, 104, 139
ZOOM = 5


def right_end(im):
    c = im.crop((BOX_R - 45, BOX_T, BOX_R, BOX_B))
    return c.resize((c.width * ZOOM, c.height * ZOOM), Image.LANCZOS)


iz_typed, iz_cleared = right_end(typed), right_end(cleared)

img = Image.new("RGB", (W, 1900), BG)
d = ImageDraw.Draw(img)

y = PAD
d.text((PAD, y), "流明盒 v2.0.14 · 右键菜单无黑角 + 输入框清空小叉", font=F_TITLE, fill=TXT)
y += 56
d.text((PAD, y), "反馈 1「圆角外有黑色的小角」：v2.0.13 只把文字换成了中文，菜单仍是 Qt 自己造的 —— "
                 "窗口类 `QWindowPopupDropShadowSaveBits`，",
       font=F_BODY, fill=DIM)
y += 27
d.text((PAD, y), "Qt 会把投影直接画进菜单表面，光加「不要系统投影」的旗标去不掉（四角仍 #0f0f11）"
                 "→ 改用我们自己的圆角菜单壳。",
       font=F_BODY, fill=DIM)
y += 40

# ---- 上排：菜单 ----
card_top = y
CARD_H = H_MENU + 56
d.rounded_rectangle([PAD, card_top, W - PAD, card_top + CARD_H], 16, fill=CARD, outline=LINE)
cx = PAD + 30
for box, tag, colr in ((ib, "修复前 · 你的截图（圆角外一圈黑角）", RED),
                       (ia, "修复后 · exe 真机（圆角外真透明）", GREEN)):
    d.text((cx, card_top + 12), tag, font=F_SMALL, fill=colr)
    img.paste(box, (cx, card_top + 38))
    d.rectangle([cx - 1, card_top + 37, cx + box.width, card_top + 38 + box.height],
                outline=LINE)
    cx += box.width + 46

y = card_top + CARD_H + 34

# ---- 下排：清空小叉 ----
d.text((PAD, y), "反馈 2「输入框输入内容后靠右出现小 X，可以删除输入的内容」", font=F_H2, fill=GOLD)
y += 40
sub_top = y
SUB_H = max(iz_typed.height, iz_cleared.height) + 62
d.rounded_rectangle([PAD, sub_top, W - PAD, sub_top + SUB_H], 16, fill=CARD, outline=LINE)
cx = PAD + 30
for box, tag, colr in ((iz_typed, "有内容 · 右端浮出小叉", GREEN),
                       (iz_cleared, "点一下叉 · 内容清空、叉自己消失", DIM)):
    d.text((cx, sub_top + 12), tag, font=F_SMALL, fill=colr)
    img.paste(box, (cx, sub_top + 38))
    d.rectangle([cx - 1, sub_top + 37, cx + box.width, sub_top + 38 + box.height],
                outline=LINE)
    cx += box.width + 40
# 右侧文字说明
tx = cx + 6
tw = W - PAD - 24 - tx
ty = sub_top + 38
for ln in ("· 图标不是系统那颗：SP_LineEditClearButton 在暗色下是",
           "  深色叉，压在 #18181b 上几乎看不见（亮像素 16）。",
           "· 换自绘圆头叉后亮像素 48。只能 qproperty-icon，",
           "  image: 无效 —— 那颗按钮是无名 QToolButton，图标由",
           "  setIcon() 直接塞进去，image: 被它盖掉。",
           "· 数字框 / 下拉框内部自带的 QLineEdit 已剔除。",
           "· 显隐只认 text() 有没有字：textChanged 自己",
           "  setVisible()，IME 提交 / 粘贴 / 程序 setText 都算数。"):
    d.text((tx, ty), ln, font=F_SMALL, fill=DIM)
    ty += 26

y = sub_top + SUB_H + 34

# ---- 修法 ----
d.text((PAD, y), "修法", font=F_H2, fill=GOLD)
y += 36
rows = [
    ("新增 src/editfix.py", "应用级事件过滤器拦 `QEvent.ContextMenu`，把 `createStandardContextMenu()` 的 actions "
                            "搬进 `uiwin.menu()` 再弹 —— 文本仍由 `qtlang` 中文化、启用态仍按选区算。"),
    ("action 转交所有权", "action 的父对象是那份临时菜单，必须 `setParent(我们的菜单)`；"
                          "否则临时菜单一析构就把 action 带走（弹出正常、点下去没反应）。"),
    ("装在 load_style() 里", "main.py / 工具窗 / dev 下几十个出图脚本都会先调它；挂主入口会让冒烟与真机验的"
                             "不是同一套行为。幂等。"),
    ("清空叉 + 显隐自管", "`setClearButtonEnabled(True)` + QSS `qproperty-icon` 换图标；"
                           "再让 `textChanged` 自己 `setVisible()`，不看 Qt 内部刷新时机的脸色。"),
]
TEXT_X = PAD + 252
TEXT_W = (W - PAD) - TEXT_X - 14
for k, v in rows:
    d.text((PAD, y), k, font=F_SMALL, fill=ACCENT)
    for ln in wrap(d, v, F_BODY, TEXT_W):
        d.text((TEXT_X, y), ln, font=F_BODY, fill=TXT)
        y += 25
    y += 7

y += 12
d.line([PAD, y, W - PAD, y], fill=LINE)
y += 24
d.text((PAD, y), "验收（全部真机 / 真像素，不是属性自证）", font=F_H2, fill=GOLD)
y += 38
for ln in ("· 离屏冒烟 854/854：㊵ 段 27 条 —— glyphs 的 close 真落盘、QSS 用 qproperty-icon 且渲染后无残留占位符、"
           "新建输入框有叉而 QSpinBox/QComboBox 没有、空文本自动隐藏、菜单带 NoDropShadowWindowHint + "
           "WA_TranslucentBackground、grab 像素四角 alpha=0 而内部 ≥200、9 项且文本仍是中文、action 所有权已转交、"
           "菜单开着点「全选」真有反应、关闭后被回收。",
           "· exe 真机 live_v2014_exe.py 25/25：菜单窗口类是 QWindowPopupSaveBits（不含 DropShadow）、"
           "四角与「关掉后同位置」逐个相等、Esc 能关；粘贴 → 右端浮出 8×8 小叉（距右边 16px）→ 真鼠标点它 → "
           "框里只剩插入光标、叉自己消失；app.log 零未捕获异常。",
           "· 一个被自己推翻的结论：连续两轮真机「打字后叉不出现」，其实框里的 Z 底下有点线下划线 —— "
           "那是输入法组字串（preedit），没提交；回车一按叉就出来，按的是「提交」不是「刷新」。"
           "功能本来是对的，是验收脚本被输入法骗了；现在改用 Ctrl+V 粘贴来造已提交文本。"):
    for seg in wrap(d, ln, F_SMALL, W - 2 * PAD):
        d.text((PAD, y), seg, font=F_SMALL, fill=DIM)
        y += 26

img = img.crop((0, 0, W, y + 40))
img.save(OUT)
print("->", OUT, img.size)
