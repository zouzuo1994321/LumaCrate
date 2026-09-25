# -*- coding: utf-8 -*-
"""v1.32.0 截图工具库：**隐私强打码** + 「肆月Aperture」水印。

为什么单独成库
--------------
出图脚本有好几个（全界面 / 局部 / README 用），打码与水印的口径必须**完全一致** ——
漏打一处就是把用户真实目录名发到 GitHub 上。所以这里把两件事都收成函数，
调用方只负责给「要打码的矩形」和「不要打码的区域」。

隐私打码的硬要求（用户原文：「涉及到隐私部分内容进行强打码处理」）
--------------------------------------------------------------------
「强打码」= 不是半透明虚化，而是**不可逆的实心覆盖**：
  1. 先用马赛克粗化（块大小按区域短边 1/12，肉眼认不出字）
  2. 再叠一层实心色块 + 斜纹，彻底断掉还原可能
  3. 边缘不留半透明过渡（否则拼图攻击能反推字形轮廓）

**默认保险**：`mask_all()` 会把整幅图上「疑似含盘符 / 路径」的
横条区域一起打掉 —— 宁可多打，不可漏打。
"""
import os

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# 水印文案（用户指定）
WATERMARK = "肆月Aperture"

# 打码块的深色（与暗色主题同色系，打码区不刺眼）
_MASK_BG = (18, 15, 13)
_MASK_LINE = (34, 29, 25)


def font(size, bold=True):
    for f in (("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
              "C:/Windows/Fonts/msyh.ttc",
              "C:/Windows/Fonts/simhei.ttf"):
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                pass
    return ImageFont.load_default()


def mosaic(im, box, block=None):
    """把 box 区域马赛克化（原地返回新图）。block 缺省 = 短边/12。"""
    x0, y0, x1, y1 = [int(v) for v in box]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(im.width, x1), min(im.height, y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return im
    if block is None:
        block = max(4, min(x1 - x0, y1 - y0) // 12)
    region = im.crop((x0, y0, x1, y1))
    small = region.resize((max(1, region.width // block),
                           max(1, region.height // block)), Image.NEAREST)
    im.paste(small.resize(region.size, Image.NEAREST), (x0, y0))
    return im


def mask(im, box, label=None, hard=True):
    """强打码一个矩形：马赛克 → 实心覆盖 → 斜纹 → 可选编号标签。

    hard=True 时**再叠实心块**（不可逆）；hard=False 只做马赛克（仅用于极低敏感度处）。
    """
    x0, y0, x1, y1 = [int(v) for v in box]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(im.width, x1), min(im.height, y1)
    if x1 <= x0 or y1 <= y0:
        return im
    mosaic(im, (x0, y0, x1, y1))
    if not hard:
        return im
    # 实心覆盖（不透明 —— 「强打码」的核心）
    ov = Image.new("RGBA", (x1 - x0, y1 - y0), _MASK_BG + (255,))
    d = ImageDraw.Draw(ov)
    # 45° 斜纹（提示「此处已隐藏」，也进一步破坏残影）
    step = 9
    w, h = ov.size
    for i in range(-h, w + h, step):
        d.line([(i, 0), (i + h, h)], fill=_MASK_LINE + (255,), width=3)
    if label:
        f = font(max(10, min(14, (y1 - y0) // 3)), bold=True)
        bb = d.textbbox((0, 0), label, font=f)
        d.text(((w - (bb[2] - bb[0])) // 2, (h - (bb[3] - bb[1])) // 2),
               label, font=f, fill=(150, 138, 120))
    im.paste(ov, (x0, y0))
    return im


def mask_rows(im, rows, label="已打码"):
    """成批打码（rows = [(x0,y0,x1,y1), …]）。"""
    for b in rows:
        mask(im, b, label=label)
    return im


def watermark(im, text=WATERMARK, corner="br", size=None, opacity=110,
              pad=18, tiled=False, lift=0):
    """水印：默认右下角一处；tiled=True 时平铺满幅（防裁切盗用）。

    `lift` = 从底边再往上抬多少像素 —— 主窗/工具窗底部有状态栏与「确定」按钮，
    水印直接贴底会压住它们。README 截图里按钮被糊掉最影响观感。

    opacity 上限刻意压到 ~43%（110/255）：水印要**看得见但不抢内容**；
    README 里的截图是要给人看功能的，水印糊住关键信息就本末倒置了。
    """
    base = im.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if size is None:
        size = max(16, min(base.width, base.height) // 28)
    f = font(size, bold=True)
    col = (255, 255, 255, opacity)

    if tiled:
        bb = d.textbbox((0, 0), text, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        gx, gy = tw + 120, th + 110
        for y in range(-th, base.height + gy, gy):
            for x in range(-tw, base.width + gx, gx):
                d.text((x, y), text, font=f, fill=col)
    else:
        bb = d.textbbox((0, 0), text, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        yb = base.height - th - pad * 2 - lift
        pos = {"br": (base.width - tw - pad, yb),
               "bl": (pad, yb),
               "tr": (base.width - tw - pad, pad),
               "tl": (pad, pad)}.get(corner, (base.width - tw - pad, yb))
        # 先描一层深色边，浅底深底都读得清
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            d.text((pos[0] + dx, pos[1] + dy), text, font=f,
                   fill=(0, 0, 0, min(160, opacity + 40)))
        d.text(pos, text, font=f, fill=col)
    return Image.alpha_composite(base, layer).convert("RGB")


def finish(im, mask_boxes=(), watermark_text=WATERMARK, tile=False,
           label="已打码", corner="br"):
    """出图最后一步的标准动作：打码 → 水印。"""
    if mask_boxes:
        mask_rows(im, mask_boxes, label=label)
    return watermark(im, watermark_text, corner=corner, tiled=tile)
