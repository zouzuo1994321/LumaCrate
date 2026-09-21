import os
base = r"Z:\【01】自研软件\【26-19】本地影视中心"
for rel in ["src/test_smoke.py", "src/ui_smoke.py", "index_data/media_center.db"]:
    p = os.path.join(base, rel)
    if os.path.exists(p):
        os.remove(p)
        print("removed", p)
    else:
        print("absent", p)
