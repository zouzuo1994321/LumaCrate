# -*- coding: utf-8 -*-
"""把用户提供的三张联系 logo 压缩 → base64 字面量，输出可直接粘进 main_window.py 的片段。

- 源图 300×300 RGBA 近白剪影，图标显示尺寸只有 22px（高 DPI 最多 44px）→
  统一缩放到 96×96 再编码，足够清晰，体积从 ~300KB 降到 ~几 KB。
- 输出写成 `dev/_scratch/contact_b64.txt`，供人工/脚本填入源码。
"""
import base64
import io
import os

from PIL import Image

SRC = r"C:\Users\zouzu\Desktop\联系logo"
OUT = r"C:\Users\zouzu\AppData\Local\Temp\lmc_v1310\dev\_scratch\contact_b64.txt"
TARGET = 96

FILES = {
    "github": "github-1.png",
    "bilibili": "bilibili-1.png",
    "weibo": "weibo-1.png",
}

lines = []
for kind, fn in FILES.items():
    src = os.path.join(SRC, fn)
    im = Image.open(src).convert("RGBA")
    im = im.resize((TARGET, TARGET), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    raw = buf.getvalue()
    b64 = base64.b64encode(raw).decode("ascii")
    lines.append("# %s  (%s)  %d bytes PNG → %d chars b64"
                 % (kind, fn, len(raw), len(b64)))
    lines.append('        "%s": (' % kind)
    # 每行 76 字符切段，便于阅读与人工 diff
    for i in range(0, len(b64), 76):
        lines.append('            "%s"' % b64[i:i + 76])
    lines.append("        ),")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print("OK ->", OUT)
_tot = 0
for _l in lines:
    if _l.strip().startswith('"'):
        _tot += len(_l.strip()) - 4
print("total b64 chars:", _tot)
