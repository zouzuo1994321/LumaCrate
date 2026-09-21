# -*- coding: utf-8 -*-
"""① 高倍裁剪影片卡「文字区」；② 检查真实 nfo 是否含 director。"""
import os
import re
from PIL import Image

BASE = r"C:\Users\zouzu\.workbuddy\clipboard-images"
OUT = r"Z:\【01】自研软件\【26-19】本地影视中心\dev\_scratch"
os.makedirs(OUT, exist_ok=True)

S1 = os.path.join(BASE, "clipboard-2026-09-18T10-21-05-559Z-a393fc95.jpg")
S2 = os.path.join(BASE, "clipboard-2026-09-18T10-21-05-562Z-b0f5e0e1.jpg")

def crop(src, box, out, scale=4):
    im = Image.open(src).convert("RGB")
    c = im.crop(box).resize((int((box[2]-box[0])*scale), int((box[3]-box[1])*scale)), Image.LANCZOS)
    c.save(out)
    print("->", os.path.basename(out), c.size)

# 影片卡文字区（标题/副信息/演员导演小字）
crop(S1, (255, 320, 720, 420), os.path.join(OUT, "c_poster_text_s1.png"), 4)
crop(S2, (255, 320, 720, 420), os.path.join(OUT, "c_poster_text_s2.png"), 4)
# 整屏缩略（看栅格是否规律）
im = Image.open(S1).convert("RGB")
im.crop((230, 60, 1920, 1110)).resize((1183, 735), Image.LANCZOS).save(os.path.join(OUT, "c_s1_overview.png"))
print("-> c_s1_overview.png")

print("\n=== nfo director 检查 ===")
nfo_dir = r"Y:\【02】Jav严选"
cands = []
if os.path.isdir(nfo_dir):
    for d in sorted(os.listdir(nfo_dir))[:6]:
        p = os.path.join(nfo_dir, d)
        if not os.path.isdir(p):
            continue
        for f in os.listdir(p):
            if f.lower().endswith(".nfo"):
                cands.append(os.path.join(p, f))
print("找到 nfo:", len(cands))
for p in cands[:4]:
    try:
        txt = open(p, encoding="utf-8", errors="replace").read()
    except Exception as e:
        print("read err", p, e); continue
    print("\n---", os.path.basename(p), len(txt), "chars")
    for tag in ("director", "actor", "set", "studio", "credits"):
        found = re.findall(r"<%s\b[^>]*>(.*?)</%s>|<%s\b[^>]*/>" % (tag, tag, tag), txt, re.S)
        flat = [t for t in found if t]
        print("   <%s> x%d" % (tag, len(flat)), "|", " / ".join(x.strip()[:30] for x in flat[:5]))
    # 打印前 600 字符看结构
    print("   head:", re.sub(r"\s+", " ", txt[:420]))
