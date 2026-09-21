# -*- coding: utf-8 -*-
"""清理 screenshots_v1250 里的陈旧图，并把 preview 的目录清理改成显式 unlink。

背景：Z: 是同步盘，`shutil.rmtree(..., ignore_errors=True)` 会**静默失败** ——
上一轮的图留在目录里冒充本轮产物（我第一次重跑就被 02/04 的旧「网格特写」骗了）。
"""
import io
import os

ROOT = r"Z:/【01】自研软件/【26-19】本地影视中心"
OUT = os.path.join(ROOT, "dev", "screenshots_v1250")
PREVIEW = os.path.join(ROOT, "dev", "preview_v1250.py")

# 1) 删掉陈旧图
for f in sorted(os.listdir(OUT)):
    if "网格特写" in f:
        p = os.path.join(OUT, f)
        try:
            os.remove(p)
            print("[removed]", f)
        except OSError as e:
            print("[FAIL]", f, e)

# 2) 把 preview 里的 rmtree 换成显式 unlink
s = io.open(PREVIEW, encoding="utf-8", newline="").read()
OLD = ('shutil.rmtree(OUT, ignore_errors=True)      # 每次重跑都从干净的目录开始\n'
       'os.makedirs(OUT, exist_ok=True)')
NEW = ('os.makedirs(OUT, exist_ok=True)\n'
       '# Z: 是同步盘，`shutil.rmtree` 会**静默失败**（ignore_errors 把异常吞掉），\n'
       '# 上一轮的图就留在目录里冒充本轮产物 —— 改成逐个 unlink 并打印结果。\n'
       'for _f in os.listdir(OUT):\n'
       '    try:\n'
       '        os.remove(os.path.join(OUT, _f))\n'
       '    except OSError as _e:\n'
       '        print("  [警告] 清不掉旧图：", _f, _e)')
assert s.count(OLD) == 1, s.count(OLD)
io.open(PREVIEW, "w", encoding="utf-8", newline="").write(s.replace(OLD, NEW))
print("[OK] preview_v1250.py 的目录清理已改成显式 unlink")
print("剩余图片：", sorted(os.listdir(OUT)))
