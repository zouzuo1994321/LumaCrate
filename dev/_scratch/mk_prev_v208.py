# -*- coding: utf-8 -*-
"""v2.0.8 预览图：全部从**真机截图**裁出来（不重绘、不摆拍）。

产出（docs/preview/）：
  v208_header_hover.png  ③ 表头图标只在鼠标所在那一列（上：不悬停 / 下：悬停「名称」）
  v208_rate_gold.png     ② 详情页 ★ 评分改金 + 评分按钮改白字
  v208_tag_x.png         ① 标签药丸圆角恢复 + 右上角圆形 ×
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
SHOT = os.path.join(ROOT, "dev", "screenshots")
OUT = os.path.join(ROOT, "docs", "preview")
os.makedirs(OUT, exist_ok=True)

FONT = r"C:\Windows\Fonts\msyh.ttc"
BG = (17, 17, 19)
FG = (212, 212, 216)
DIM = (113, 113, 122)
ACC = (228, 88, 124)
LINE = (39, 39, 42)


def font(px, bold=False):
    try:
        return ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc" if bold else FONT, px)
    except Exception:
        return ImageFont.truetype(FONT, px)


def crop(name, box, zoom=2):
    im = Image.open(os.path.join(SHOT, name)).convert("RGB")
    c = im.crop(box)
    return c.resize((c.width * zoom, c.height * zoom), Image.LANCZOS)


def panel(title, note, blocks, pad=22, gap=14):
    """blocks: [(图片, 说明文字 或 None), ...] 竖排成一张带标题的图。"""
    ft, fn, fc = font(21, True), font(15), font(13)
    wid = max(b.width for b, _c in blocks) + pad * 2
    head_h = 56 + (26 if note else 0)
    cap_h = sum((26 if c else 0) for _b, c in blocks)
    hgt = head_h + sum(b.height for b, _c in blocks) + cap_h + gap * len(blocks) + pad

    im = Image.new("RGB", (wid, hgt), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, wid, 3], fill=ACC)
    d.text((pad, 14), title, font=ft, fill=(250, 250, 250))
    y = 46
    if note:
        d.text((pad, y), note, font=fn, fill=DIM)
        y += 26
    y += 8
    for blk, cap in blocks:
        if cap:
            d.text((pad, y), cap, font=fc, fill=DIM)
            y += 26
        x = (wid - blk.width) // 2
        im.paste(blk, (x, y))
        d.rectangle([x, y, x + blk.width - 1, y + blk.height - 1], outline=LINE)
        y += blk.height + gap
    return im


# ---------------- ③ 表头：只有悬停列才有图标 ----------------
h_idle = crop("v208_home_idle.png", (200, 140, 884, 192), 2)
h_hov = crop("v208_home_hover_title.png", (200, 140, 884, 192), 2)
im3 = panel(
    "③ 表头的漏斗 / 排序三角：只在鼠标所在那一列显示",
    "真机 1920×1080 截图裁切放大 2×。鼠标停在「名称」列上，其余三列一个图标都没有。",
    [(h_idle, "鼠标不在表头 → 四列全空（原来四列常驻，满屏都是小图标）"),
     (h_hov, "鼠标停在「名称」列 → 只有这一列出现左漏斗 ▽ 和右排序三角 △")],
)
im3.save(os.path.join(OUT, "v208_header_hover.png"))

# ---------------- ② 评分：★ 金色 / 按钮白字 ----------------
# 按钮行取自**未评分**的 CCC-003（按钮才显示「评分」）；元数据行取自 MIDA-846（有评分）。
RATE_BTN = os.path.join(os.environ["LOCALAPPDATA"], "Temp", "lmc_exe_v208", "ratebtn.png")
bx = Image.open(RATE_BTN).convert("RGB").crop((198, 348, 700, 400))
btns = bx.resize((bx.width * 2, bx.height * 2), Image.LANCZOS)
meta = crop("v208_media_detail.png", (198, 452, 700, 482), 2)  # 与按钮行同宽 1004
im2 = panel(
    "② 详情页评分：★ 金色，评分按钮改白字",
    "「评分」按钮原先用强调色实心，现在与「刷新 / 更多」同色（白）；"
    "下面 ★ 7.0 由链接蓝改成金 #f5a524。",
    [(btns, "未评分的片：按钮显示「评分」，白字（与「刷新 / 更多」一致）"),
     (meta, "元数据行：★ 7.0 金色；年份 /「我评 7.5★」/ 类型仍按原样灰白")],
)
im2.save(os.path.join(OUT, "v208_rate_gold.png"))

# ---------------- ① 标签：药丸圆角 + 圆形 × ----------------
im1 = panel(
    "① 标签芯片：圆角恢复成药丸，右上角一枚圆形 ×",
    "3 枚标签并排，每枚右上的圆形删号都落在圆的几何中心（两条线自绘，不再依赖字体位置）。",
    [(crop("v208_media_detail.png", (198, 778, 620, 850), 3),
      "半径 = 药丸高度 / 2，永远是药丸；× 悬停变红")],
)
im1.save(os.path.join(OUT, "v208_tag_x.png"))

for n in ("v208_header_hover.png", "v208_rate_gold.png", "v208_tag_x.png"):
    p_ = os.path.join(OUT, n)
    print(n, os.path.getsize(p_), Image.open(p_).size)
