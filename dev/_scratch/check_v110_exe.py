# -*- coding: utf-8 -*-
"""校验 v1.10.0 产物：根目录 exe + history 归档 + 冒烟脚本存在性。"""
import os
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def show(p):
    if os.path.exists(p):
        print("  OK  %-52s %12d bytes  mtime=%s" % (
            os.path.basename(p), os.path.getsize(p),
            __import__("datetime").datetime.fromtimestamp(os.path.getmtime(p)).strftime("%m-%d %H:%M")))
    else:
        print("  !!  MISSING %s" % p)

print("=== ROOT ===")
show(os.path.join(ROOT, "本地影视中心-v1.10.0-2609180011.exe"))
print("=== history ===")
show(os.path.join(ROOT, "history", "本地影视中心-v1.10.0-2609180011.exe"))
show(os.path.join(ROOT, "history", "本地影视中心-v1.9.0-2609180010.exe"))
print("=== dev smoke ===")
show(os.path.join(ROOT, "dev", "smoke_v110.py"))
show(os.path.join(ROOT, "dev", "render_preview.py"))
print("=== src ===")
for f in ("version.py", "main.py", "main_window.py", "database.py", "nfo_parser.py", "scanner.py", "scraper.py"):
    show(os.path.join(ROOT, "src", f))
print("=== README v1.10.0 entry? ===")
readme = os.path.join(ROOT, "README.md")
if os.path.exists(readme):
    txt = open(readme, encoding="utf-8", errors="replace").read()
    print("  v1.10.0 in README:", "v1.10.0" in txt)
