# -*- coding: utf-8 -*-
"""v2.0.5 探针：逐路径「统计 → 扫描」+ 新增/变更/减少 三态。

全程跑临时库，**绝不碰真实索引**。
"""
import os
import sys
import shutil
import ctypes

ROOT = r"E:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

TMP = r"C:/Users/zouzu/AppData/Local/Temp/lmc_probe_v205"
shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(TMP, exist_ok=True)

import database as db          # noqa: E402
import applog                  # noqa: E402

db.db_path = lambda: os.path.join(TMP, "probe.db")
applog.log_dir = lambda: os.path.join(TMP, "logs")
db.init_db()

import main_window as mw       # noqa: E402

LIB = os.path.join(TMP, "lib")
P1 = os.path.join(LIB, "path-1")
P2 = os.path.join(LIB, "path-2")


def mk(folder, title, video_name=None):
    """造一个「movie.nfo + 视频」的片目录。"""
    d = os.path.join(LIB, folder)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "movie.nfo"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>'
                '<movie><title>%s</title><year>2021</year></movie>' % title)
    v = os.path.join(d, (video_name or folder.replace("/", "_")) + ".mp4")
    with open(v, "wb") as f:
        f.write(b"\0" * 1024)
    return v


def run_worker(paths, mode="new"):
    w = mw.ScanWorker(paths, library_name="探针库", mode=mode)
    ticks, lives, done = [], [], []
    w.tick.connect(lambda d, t, m: ticks.append((d, t, m)))
    w.live.connect(lambda: lives.append(1))
    w.done.connect(lambda c: done.append(dict(c)))
    w.run()
    return w, ticks, lives, done


print("== ① 逐路径：分母是「本条路径」的片数，不是全局总数 ==")
mk("path-1/S_a", "第一路径片A")
mk("path-1/S_b", "第一路径片B")
V2 = mk("path-2/S_a", "第二路径片A")

w, ticks, lives, done = run_worker([P1, P2], mode="new")
paths_seen, denoms = [], []
for d, t, m in ticks:
    for seg in m.split(" · "):
        if seg.startswith("路径 ") and seg not in paths_seen:
            paths_seen.append(seg)
    if t and (not denoms or denoms[-1] != t):
        denoms.append(t)
print("路径顺序：", paths_seen)
print("出现过的分母：", denoms)
print("末条 tick：", ticks[-1] if ticks else None)
print("live 次数：", len(lives), " done：", done)
assert paths_seen == ["路径 1/2", "路径 2/2"], paths_seen
assert denoms == [2, 1], denoms        # 两条路径各数自己的（2 片 / 1 片）
assert done and done[0]["new"] == 3, done
assert done[0]["changed"] == 0 and done[0]["removed"] == 0, done
assert len(lives) >= 3, len(lives)     # 每条路径扫完各一次 + 收尾一次

print("== ② 未变：state 全是 same，不再重复刷新 ==")
w2, ticks2, lives2, done2 = run_worker([P1], mode="overwrite")
print("overwrite 复扫：", done2)
assert done2[0]["new"] == 0 and done2[0]["changed"] == 0, done2
assert done2[0]["removed"] == 0, done2

print("== ③ 变更：改了 nfo 标题 → changed，库里跟着变 ==")
p = os.path.join(P1, "S_a")
with open(os.path.join(p, "movie.nfo"), "w", encoding="utf-8") as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>'
            '<movie><title>改过名的片子</title><year>2022</year></movie>')
w3, _, _, done3 = run_worker([P1], mode="overwrite")
print("改名后：", done3)
assert done3[0]["changed"] == 1, done3
assert done3[0]["new"] == 0, done3
hit = [r["title"] for r in db.search_media("", limit=50)
       if "改过名" in (r.get("title") or "")]
print("库里的新标题：", hit)
assert hit, "标题没写进库"

print("== ④ 减少：删掉一个视频文件 → removed 1 ==")
victim = V2
ctypes.windll.kernel32.SetFileAttributesW(victim, 0x80)
ctypes.windll.kernel32.DeleteFileW(victim)
print("删除目标：", victim)
assert not os.path.exists(victim)
w4, _, _, done4 = run_worker([P2], mode="new")
print("删片后：", done4)
assert done4[0]["removed"] == 1, done4

print("== ⑤ 整条路径不可用（盘没插）时不误报减少 ==")
w5, _, _, done5 = run_worker([os.path.join(TMP, "not-exist")], mode="new")
print("不存在路径：", done5)
assert done5[0]["removed"] == 0 and done5[0]["new"] == 0, done5

print("== ⑥ upsert 三态直查 ==")
xf = os.path.join(TMP, "x.mp4")
mid, st = db.upsert_media_state(mode="overwrite", kind="movie", title="甲",
                                sort_title="a", file_path=xf)
print("首插：", mid, st)
assert st == "new"
mid2, st2 = db.upsert_media_state(mode="overwrite", kind="movie", title="甲",
                                  sort_title="a", file_path=xf)
print("复插同值：", mid2, st2)
assert mid2 == mid and st2 == "same"
mid3, st3 = db.upsert_media_state(mode="overwrite", kind="movie", title="乙",
                                  sort_title="a", file_path=xf)
print("改标题：", mid3, st3)
assert mid3 == mid and st3 == "changed"

print("== ⑦ 结果文案 ==")
txt = mw.scan_result_text({"new": 9, "movie": 7, "tvshow": 1, "episode": 1,
                           "changed": 3, "removed": 2})
print(txt)
assert "新增 9" in txt and "变更 3" in txt and "减少 2" in txt

print("ALL_OK")
