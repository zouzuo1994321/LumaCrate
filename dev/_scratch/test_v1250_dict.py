# -*- coding: utf-8 -*-
"""自证：日语词典是否真的对齐到了「用户库里在用的中文词表」。

只读真库（`mode=ro`，不写任何东西），统计：
  A. 词典规模 / 冲突（必须为 0）
  B. 高频日语标签的翻译覆盖率
  C. **落到既有中文标签上的比例**（决定「会不会把词表撕成两半」的关键指标）
  D. 翻译后会**新造**出来的词（人工过目，确认没有同义重复）
"""
import collections
import os
import re
import sqlite3
import sys

ROOT = r"Z:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))
import tagopt

DB = os.path.join(ROOT, "index_data", "media_center.db")
KANA = re.compile(r"[\u3041-\u309f\u30a0-\u30ff]")

# ---------------------------------------------------------------- A
print("== A. 词典 ==")
print("  条目数:", len(tagopt.JA2ZH))
print("  冲突  :", len(tagopt.JA2ZH_CONFLICTS), tagopt.JA2ZH_CONFLICTS)
assert not tagopt.JA2ZH_CONFLICTS, "词典存在同键不同值，必须消掉"

# ---------------------------------------------------------------- 读真库
con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
rows = con.execute(
    "SELECT genres FROM media WHERE genres IS NOT NULL AND genres<>''").fetchall()
con.close()
cnt = collections.Counter()
for (g,) in rows:
    for t in str(g).split(","):
        t = t.strip()
        if t:
            cnt[t] += 1

vocab = {t for t in cnt if not KANA.search(t) and not t.startswith(tagopt.PREFIXES)}
ja_all = [(t, n) for t, n in cnt.most_common() if KANA.search(t)]
print(f"  真库：{len(rows):,} 行有 genres / {len(cnt):,} 个不同标签"
      f"（含假名 {len(ja_all):,} 个 / 中文英文 {len(vocab):,} 个）")

# ---------------------------------------------------------------- B/C/D
TOP = 400
top = ja_all[:TOP]
hit_existing, hit_new, untouched = [], [], []
for t, n in top:
    zh = tagopt.to_zh(t)
    if not zh:
        untouched.append((t, n))
    elif zh in vocab:
        hit_existing.append((t, n, zh))
    else:
        hit_new.append((t, n, zh))

print()
print(f"== B/C. 前 {TOP} 个高频日语标签的翻译情况 ==")
print(f"  能译出中文        : {len(hit_existing) + len(hit_new)} / {TOP}")
print(f"    ├ 落到既有标签  : {len(hit_existing)}   ← 这是「词表对齐」的关键指标")
print(f"    └ 会新造一个词  : {len(hit_new)}")
print(f"  词典没收录、保持原样: {len(untouched)}")

print()
print("  --- 落到既有中文标签上的（前 30）---")
for t, n, zh in hit_existing[:30]:
    print(f"    {n:>5}  {t:<28s} -> {zh}  (库里 {cnt.get(zh, 0):,} 次)")

print()
print("  --- 会新造出来的词（前 30，需人工确认没有同义重复）---")
for t, n, zh in hit_new[:30]:
    print(f"    {n:>5}  {t:<28s} -> {zh}")

print()
print("  --- 仍未收录的高频日语标签（前 25）---")
for t, n in [x for x in top if x in untouched][:25]:
    print(f"    {n:>5}  {t}")

# ---------------------------------------------------------------- 复合标签
print()
print("== D. 复合标签（含 ·/・）的解析 ==")
comp = [(t, n) for t, n in ja_all if re.search(r"[·・•‧]", t)][:20]
for t, n in comp:
    print(f"    {n:>5}  {t:<32s} -> {tagopt.to_zh(t) or '（不处理，保持原样）'}")

# ---------------------------------------------------------------- 关键个案
print()
print("== 关键个案 ==")
cases = ["中出し", "潮吹き", "フェラ", "パイズリ", "スレンダー", "お姊さん",
         "デカチン·巨根", "キス·接吻", "寝取り·寝取られ·ＮＴＲ", "アクメ·オーガズム",
         "淫乱·ハード系", "看护妇·ナース", "パンスト·タイツ", "調教・奴隶",
         "イラマチオ", "汗だく", "人妻·主妇", "姐·妹", "有码", "巨乳"]
ok = 0
for t in cases:
    zh = tagopt.to_zh(t)
    flag = "译出" if zh else "保持"
    if zh:
        ok += 1
    print(f"    {t:<26s} -> {zh or '（保持原样）':<16s} [{flag}]"
          + ("  ★命中既有词表" if zh in vocab else ""))

print()
print(f"关键个案译出 {ok}/{len(cases)}")
print("DONE")
