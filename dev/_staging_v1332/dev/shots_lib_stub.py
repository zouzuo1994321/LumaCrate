# -*- coding: utf-8 -*-
"""极简截图辅助（shots_lib 的最小替身）—— 只做水印。"""
from PIL import Image, ImageDraw, ImageFont
import os


def _font(sz):
    for f in ("msyh.ttc", "msyhbd.ttc"):
        p = os.path.join("C:/Windows/Fonts", f)
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()


def watermark(im, corner="br", text="肆月Aperture"):
    """右下角极淡水印。im 为 RGB Image。"""
    d = ImageDraw.Draw(im, "RGBA")
    f = _font(20)
    try:
        bb = d.textbbox((0, 0), text, font=f)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
    except Exception:
        w, h = len(text) * 12, 20
    pad = 14
    if corner == "br":
        x, y = im.width - w - pad, im.height - h - pad - 4
    elif corner == "tl":
        x, y = pad, pad
    else:
        x, y = im.width - w - pad, pad
    d.text((x, y), text, font=f, fill=(255, 255, 255, 60))
    return im
