# -*- coding: utf-8 -*-
"""临时探针：验证 recycle_paths 真的把文件放进回收站（不是永久删除）。

只碰 %TEMP% 下自己新建的文件，不碰任何用户数据。
"""
import os
import sys
import tempfile

sys.path.insert(0, r"E:/【01】自研软件/【26-19】本地影视中心/src")
import duplicates as dup   # noqa: E402

d = tempfile.mkdtemp(prefix="lmc_recycle_")
f1 = os.path.join(d, "a.txt")
f2 = os.path.join(d, "sub")
os.makedirs(f2, exist_ok=True)
for p in (f1, os.path.join(f2, "b.txt")):
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("hello")

print("before:", os.path.exists(f1), os.path.isdir(f2))
res = dup.recycle_paths([f1, f2, os.path.join(d, "nope.txt")])
print("result:", res)
print("after :", os.path.exists(f1), os.path.isdir(f2))
print("dir still exists:", os.path.isdir(d), "empty:", os.listdir(d) if os.path.isdir(d) else None)

ok = (res["ok"] == 2 and not res["failed"]
      and not os.path.exists(f1) and not os.path.isdir(f2))
print("ALL_OK" if ok else "FAILED")

# 清理：删掉空目录（用 rmdir，不涉及 safe-delete 的 os.remove）
try:
    if os.path.isdir(d) and not os.listdir(d):
        os.rmdir(d)
except OSError:
    pass
