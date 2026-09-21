# -*- coding: utf-8 -*-
"""回滚 settings.json 污染。

起因：验证 config.py 新 API 的临时脚本把配置目录覆盖写成了不存在的名字
（`config.CONFIG_DIR` / `config.CONFIG_PATH` —— 本项目根本没有这两个模块级变量），
于是 `Settings()` 走 `config_path()` 读到了**真实**的 `settings.json`（开发期 = 项目根），
随后几次 `save()` 把测试数据写了进去。

污染项（逐条可定位）：
  1. seen_smart：真实的 63 个 id 后面被追加了测试用的 1~7
  2. smart_history：整键新增（round 1 是迁移副本，round 2~4 是测试注入的 [1,2,3]/[3,4,5]/[6,7]）
  3. tagopt：整键新增
  4. recommend.ai_model / recommend.no_repeat_rounds：两个新键被写进文件
  5. appearance.accent：被 set_accent('#5aa469') 写成了竹青

还原依据：load() 的迁移逻辑是 `smart_history = [{"round":1,"ids": list(seen_smart)}]`，
所以 smart_history[0]["ids"] 就是原始 seen_smart 的逐字副本 —— 用它反推，不需要额外备份。
"""
import json
import os
import shutil
import time

ROOT = r"Z:/【01】自研软件/【26-19】本地影视中心"
P = os.path.join(ROOT, "settings.json")
BAK_DIR = os.path.join(ROOT, "dev", "_scratch")

with open(P, encoding="utf-8") as f:
    d = json.load(f)

# 0) 先留一份污染版取证
os.makedirs(BAK_DIR, exist_ok=True)
bak = os.path.join(BAK_DIR, f"settings.polluted-{time.strftime('%Y%m%d-%H%M%S')}.json")
shutil.copy2(P, bak)
print("取证备份 ->", os.path.relpath(bak, ROOT))

before = {k: (len(v) if isinstance(v, list) else type(v).__name__) for k, v in d.items()}

# 1) seen_smart 还原
orig_seen = None
for r in (d.get("smart_history") or []):
    if int(r.get("round") or 0) == 1 and r.get("ids"):
        orig_seen = [int(i) for i in r["ids"]]
        break
if not orig_seen:
    raise SystemExit("✗ 找不到 round=1 的历史，无法反推原始 seen_smart，中止")
cur_seen = [int(i) for i in (d.get("seen_smart") or [])]
print(f"seen_smart: 当前 {len(cur_seen)} 项 -> 还原 {len(orig_seen)} 项")
assert cur_seen[:len(orig_seen)] == orig_seen, "✗ 前缀对不上，拒绝改写"
assert cur_seen[len(orig_seen):] == [1, 2, 3, 4, 5, 6, 7], \
    f"✗ 尾部不是预期的测试注入值：{cur_seen[len(orig_seen):]}"
d["seen_smart"] = orig_seen

# 2~5) 删除本轮注入的键
removed = []
for key in ("smart_history", "tagopt"):
    if key in d:
        d.pop(key)
        removed.append(key)
rec = d.get("recommend") or {}
for key in ("ai_model", "no_repeat_rounds"):
    if key in rec:
        rec.pop(key)
        removed.append("recommend." + key)
app = d.get("appearance") or {}
if "accent" in app:
    app.pop("accent")
    removed.append("appearance.accent")
print("已删除注入键 ->", removed or "（无）")

with open(P, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

print("---- 还原后 ----")
print("top keys:", sorted(d.keys()))
print("recommend:", json.dumps(d["recommend"], ensure_ascii=False))
print("appearance:", json.dumps(d["appearance"], ensure_ascii=False))
print("seen_smart:", len(d["seen_smart"]), "首=", d["seen_smart"][:3], "尾=", d["seen_smart"][-3:])
print("size:", os.path.getsize(P))
