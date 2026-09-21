# -*- coding: utf-8 -*-
"""裁剪放大三张截图的关键卡片区域（坐标按 1920 实际宽度标定）。"""
import os
from PIL import Image

BASE = r"C:\Users\zouzu\.workbuddy\clipboard-images"
OUT = r"Z:\【01】自研软件\【26-19】本地影视中心\dev\_scratch"
os.makedirs(OUT, exist_ok=True)

S1 = os.path.join(BASE, "clipboard-2026-09-18T10-21-05-559Z-a393fc95.jpg")  # 全部
S2 = os.path.join(BASE, "clipboard-2026-09-18T10-21-05-562Z-b0f5e0e1.jpg")  # 最近播放
S3 = os.path.join(BASE, "clipboard-2026-09-18T10-21-05-564Z-4a836f35.png")  # 演员库

def crop(src, box, out, scale=3):
    im = Image.open(src).convert("RGB")
    c = im.crop(box)
    c = c.resize((int(c.width * scale), int(c.height * scale)), Image.LANCZOS)
    c.save(out)
    print("->", os.path.basename(out), c.size, "from", im.size)

# 演员库：第 1 列整列（看空信息区 / 状态徽标）
crop(S3, (258, 140, 512, 1015), os.path.join(OUT, "c_actor_col1.png"), 1.6)
# 演员库：第 4/5 列第 1 行（看乱码 meta）
crop(S3, (1170, 140, 1730, 460), os.path.join(OUT, "c_actor_garble.png"), 2.0)
# 全部：左上两张影片卡（海报+标题+小字）
crop(S1, (262, 145, 720, 575), os.path.join(OUT, "c_poster_s1.png"), 3.0)
# 最近播放：左上两张影片卡
crop(S2, (262, 145, 720, 575), os.path.join(OUT, "c_poster_s2.png"), 3.0)
print("DONE")
