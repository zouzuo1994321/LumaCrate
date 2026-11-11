# -*- coding: utf-8 -*-
"""出 v2.0.13 的对照预览图 `docs/preview/v2013_fix.png`。

左 = 用户反馈的截图（英文菜单，原始像素）；右 = 修复后 exe 真机截图（中文菜单，
由 `dev/_scratch/live_v2013_exe.py` 抓的 `v2013_ctx_menu_live.png`）。
"""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
SHOTS = os.path.join(ROOT, "dev", "screenshots")
USER = (r"C:\Users\zouzu\.workbuddy\clipboard-images"
        r"\clipboard-2026-11-11T11-47-06-748Z-982d30d6.png")
OUT = os.path.join(ROOT, "docs", "preview", "v2013_fix.png")

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
    return im.resize((int(im.width * s), h), Image.LANCZOS)


before = Image.open(USER).convert("RGB").crop((145, 20, 346, 299))   # 菜单本体
after = Image.open(os.path.join(SHOTS, "v2013_ctx_menu_live.png")).convert("RGB")

H_IMG = 330
ib, ia = fit(before, H_IMG), fit(after, H_IMG)

img = Image.new("RGB", (W, 1200), BG)
d = ImageDraw.Draw(img)

y = PAD
d.text((PAD, y), "流明盒 v2.0.13 · 输入框右键菜单中文化", font=F_TITLE, fill=TXT)
y += 56
d.text((PAD, y), "根因：这串字根本不归我们管 —— 它是 `QLineEdit` 的**标准上下文菜单**，"
                 "文字由 Qt 自己 translate(\"QLineEdit\", \"&Undo\") 出来，",
       font=F_BODY, fill=DIM)
y += 27
d.text((PAD, y), "软件从没装过 QTranslator，就只能回退英文源串。（i18n.py 那套词典只管我们自己的业务文案。）",
       font=F_BODY, fill=DIM)
y += 40

# ---- 两张图并排 ----
card_top = y
CARD_H = H_IMG + 56
d.rounded_rectangle([PAD, card_top, W - PAD, card_top + CARD_H], 16, fill=CARD, outline=LINE)
cx = PAD + 30
for box, tag, colr in ((ib, "修复前 · 你的截图", RED), (ia, "修复后 · exe 真机", GREEN)):
    d.text((cx, card_top + 12), tag, font=F_SMALL, fill=colr)
    img.paste(box, (cx, card_top + 38))
    d.rectangle([cx - 1, card_top + 37, cx + box.width, card_top + 38 + box.height],
                outline=LINE)
    cx += box.width + 46

y = card_top + CARD_H + 30

# ---- 三条要点 ----
d.text((PAD, y), "修法", font=F_H2, fill=GOLD)
y += 36
rows = [
    ("新增 src/qtlang.py", "install(app, code) 按界面语言装 Qt 自带的 qtbase_<locale>.qm；"
                           "四个候选目录（含 onefile 解包目录），任一命中即可。"),
    ("启动时装、切语言时装", "main.py 在建任何界面之前装，app.log 留一行「Qt 标准文本：已装 …｜ 示例 撤消(U) / 重做(R)」；"
                            "设置里换语言时跟着重装。"),
    ("文件其实一直在包里", "查 v2.0.12 的 exe：PySide6/translations/qtbase_zh_CN.qm 早就在（32 个 qtbase 齐全），"
                       "缺的从来不是文件，是运行时那一行装翻译器的代码。build_exe.py 的 --add-data 只作版本间保险。"),
    ("一起变中文的还有", "QMessageBox 按钮（是/否/确定/取消）、文件对话框、QTextEdit 右键。"
                        "19 种界面语言里 Qt 官方有 15 种（印地/泰/越/印尼语没有 → 静默回退英文）。"),
]
TEXT_X = PAD + 240
TEXT_W = (W - PAD) - TEXT_X - 14          # 右边框以内，别算出界（首版多算 24px，字被切）
for k, v in rows:
    d.text((PAD, y), k, font=F_SMALL, fill=ACCENT)
    for ln in wrap(d, v, F_BODY, TEXT_W):
        d.text((TEXT_X, y), ln, font=F_BODY, fill=TXT)
        y += 25
    y += 7

y += 12
d.line([PAD, y, W - PAD, y], fill=LINE)
y += 24
d.text((PAD, y), "验收（全部真机 / 真文本，不是属性自证）", font=F_H2, fill=GOLD)
y += 38
for ln in ("· 离屏冒烟 812 → 827/827：新增 ㊴ 段 15 条，直接比对 QLineEdit 标准菜单的**真实文本**"
           "（装前 Undo → 装后 撤消(U)/重做(R)/剪切(T)/复制(C)/粘贴(P)/删除/全选），并验切 en 回英文、再切回幂等。",
           "· exe 真机 live_v2013_exe.py 38/38：app.log 里 `已装 …/_MEIxxxx/PySide6/translations/qtbase_zh_CN.qm`"
           " —— 证明 onefile 里找得到 qm；菜单 171×267（7 项）弹得出、Esc 能关、四角 (22,22,25) 不是黑。",
           "· v2.0.12 的链路一并回归：我们自己的右键菜单四角差仍 [0,0,0,0]，中文「机器」筛选 7 行 → 1 行 → 清空回 7 行。"):
    for seg in wrap(d, ln, F_SMALL, W - 2 * PAD):
        d.text((PAD, y), seg, font=F_SMALL, fill=DIM)
        y += 26

img = img.crop((0, 0, W, y + 28))
img.save(OUT)
print("->", OUT, img.size)
