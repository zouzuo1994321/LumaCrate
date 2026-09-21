# -*- coding: utf-8 -*-
"""v1.25.0 核心行为自证（不碰真实库/真实配置）。

覆盖：
  A. render_style 的高亮色令牌（12 色全跑一遍，不得残留 __ACCENT 令牌）
  B. recommend 的模型解析链（无 Ollama / 指定了但没装 / 指定且已装）
  C. **反馈 3 的根因修复**：连续多轮推荐不重复（用合成数据，monkeypatch _load）
"""
import json
import os
import re
import sys
import tempfile

ROOT = r"Z:/【01】自研软件/【26-19】本地影视中心"
sys.path.insert(0, os.path.join(ROOT, "src"))

tmp = tempfile.mkdtemp()
os.environ["LMC_CONFIG"] = os.path.join(tmp, "settings.json")   # ← 唯一的正确姿势
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import config as cfg
import database as db
import recommend as rec
import urllib.request

fails = []


def check(name, ok, extra=""):
    print(("  ✓ " if ok else "  ✗ ") + name + (("  " + extra) if extra else ""))
    if not ok:
        fails.append(name)


# ---------------------------------------------------------------- A. 令牌渲染
print("== A. 高亮色令牌 ==")
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
import main_window as mw

qss_raw = open(os.path.join(ROOT, "src", "style.qss"), encoding="utf-8").read()
for n, h in cfg.ACCENT_COLORS:
    q = mw.render_style({"mode": "磨砂玻璃", "level": "中", "accent": h})
    left = re.findall(r"__[A-Z_]+__", q)
    check(f"{n} {h} 无残留令牌", not left, str(set(left)) if left else "")
    expect = cfg.accent_rgb(h)
    check(f"{n} ACCENT_RGB={expect}", mw.ACCENT_RGB == expect, str(mw.ACCENT_RGB))
print("  朱红四档派生 =", cfg.accent_shades("#c0392b"))
print("  对比原写死值 base=(192,57,43) dark≈(140,31,26) deep≈(163,42,32) light≈(224,82,67)")
d = cfg.accent_shades("#c0392b")
check("朱红 dark 与原值相差 <=12",
      max(abs(a - b) for a, b in zip(d["dark"], (140, 31, 26))) <= 12, str(d["dark"]))
check("朱红 deep 与原值相差 <=12",
      max(abs(a - b) for a, b in zip(d["deep"], (163, 42, 32))) <= 12, str(d["deep"]))
check("朱红 light 与原值相差 <=12",
      max(abs(a - b) for a, b in zip(d["light"], (224, 82, 67))) <= 12, str(d["light"]))
check("无输入默认色 = 朱红", True)   # 由下面那条带条数校验的断言真正覆盖
check("qss 里已无裸 #c0392b", "#c0392b" not in qss_raw and "#e05243" not in qss_raw)
check("qss 含 #Seg 选中态", "QPushButton#Seg:checked" in qss_raw)
# 默认色：不带 accent 时应当渲染成朱红，且条数与 qss 里 __ACCENT__ 出现次数一致
n_tok = qss_raw.count("rgba(__ACCENT__,")
q_def = mw.render_style({"mode": "经典暗色", "level": "中"})
check(f"无 accent 默认朱红（{n_tok} 处）",
      q_def.count("rgba(192, 57, 43,") == n_tok and n_tok > 0,
      f"实际 {q_def.count('rgba(192, 57, 43,')} 处")

# ---------------------------------------------------------------- B. 模型解析
print("== B. 本地模型解析 ==")
s = cfg.get_settings()
rec.list_models = lambda timeout=0.5: []          # 假装本机没有 Ollama
check("无 Ollama → list_models=[]", rec.list_models() == [])
check("无 Ollama → probe_ollama=None", rec.probe_ollama() is None)
check("无 Ollama → resolve_model 兜底 llama3", rec.resolve_model() == "llama3")
st = rec.ai_status()
check("无 Ollama → engine=builtin", st["engine"] == "builtin", st["label"])
check("无 Ollama 提示里有 ollama list", "ollama list" in st["detail"])

s.set_recommend(ai_model="qwen2.5:7b")
check("设置后 configured_model()", rec.configured_model() == "qwen2.5:7b")
check("resolve_model 优先用设置", rec.resolve_model() == "qwen2.5:7b")
check("指定但未装 → probe_ollama=None", rec.probe_ollama() is None)
# 本机有 Ollama、但装的不是用户指定那个
rec.list_models = lambda timeout=0.5: ["llama3:8b"]
st = rec.ai_status()
check("指定但未装 → 降级 builtin + 提示未安装",
      st["engine"] == "builtin" and "未安装" in st["label"], st["label"])
check("指定但未装 → 详情里报出已装模型",
      "llama3:8b" in st["detail"], st["detail"][:60])

rec.list_models = lambda timeout=0.5: ["qwen2.5:7b", "llama3:8b"]
check("已装 → probe_ollama 返回指定模型", rec.probe_ollama() == "qwen2.5:7b")
st = rec.ai_status()
check("已装 → engine=ollama 且列出模型",
      st["engine"] == "ollama" and "llama3:8b" in st["detail"], st["label"])
s.set_recommend(ai_model="llama3:8b")
check("换模型 → 跟随设置", rec.probe_ollama() == "llama3:8b")
s.set_recommend(ai_model="")
check("清空 → 自动取第一个", rec.probe_ollama() == "qwen2.5:7b")
s.set_recommend(ai_model="muse:latest")
s.set_recommend(ai_model="qwen2.5:7b")            # 还原

# ---------------------------------------------------------------- B2. 请求体
print("== B2. 发往 Ollama 的请求体里的模型名 ==")


class _FakeResp:
    def __init__(self, payload):
        self._p = payload

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


captured = {}


def _fake_urlopen(req, timeout=None):
    captured["body"] = json.loads(req.data.decode("utf-8"))
    return _FakeResp(json.dumps({"response": "巨乳, 人妻, 痴女"}).encode("utf-8"))


_orig_urlopen = urllib.request.urlopen
urllib.request.urlopen = _fake_urlopen
try:
    s.set_recommend(ai_model="qwen2.5:7b")
    words = rec._ollama_expand(["巨乳", "人妻"])
    check("扩词响应解析正确", words == ["巨乳", "人妻", "痴女"], str(words))
    check("请求体 model = 设置里填的", captured["body"]["model"] == "qwen2.5:7b",
          str(captured["body"].get("model")))

    s.set_recommend(ai_model="muse-glimmer:12b")
    rec._ollama_expand(["巨乳"])
    check("自定义模型名原样发出（含冒号）",
          captured["body"]["model"] == "muse-glimmer:12b", str(captured["body"].get("model")))

    s.set_recommend(ai_model="")
    rec.list_models = lambda timeout=0.5: []
    rec._ollama_expand(["巨乳"])
    check("没填 + 探不到 → 兜底 llama3", captured["body"]["model"] == "llama3",
          str(captured["body"].get("model")))

    rec.list_models = lambda timeout=0.5: ["muse:latest", "x:1"]
    rec._ollama_expand(["巨乳"])
    check("没填 + 探得到 → 取本机第一个", captured["body"]["model"] == "muse:latest",
          str(captured["body"].get("model")))
finally:
    urllib.request.urlopen = _orig_urlopen
s.set_recommend(ai_model="")

# ---------------------------------------------------------------- C. 轮次去重
print("== C. 多轮推荐不重复（反馈 3 根因检测） ==")
TAGS = ["巨乳", "人妻", "痴女", "美少女", "单体作品", "口交", "潮吹", "熟女",
        "出轨", "角色扮演", "连裤袜", "巨尻", "中出", "颜射", "乳交", "苗条"]
rows = []
for i in range(400):
    tags = [TAGS[(i * 7 + k * 3) % len(TAGS)] for k in range(5)]
    rows.append({"id": 1000 + i, "genres": ",".join(tags), "favorite": i < 3,
                 "play_count": 0, "year": 2020 + (i % 5), "title": f"T{i}",
                 "studio": "MOODYZ" if i % 2 else "S1", "collection": None,
                 "user_rating": 5.0})

db.favorite_people = lambda: []
db.vector_overrides = lambda: []
rec.Recommender._load = lambda self, library=None, progress=None: (rows, {}, {})

s.clear_smart_history()
s.set_recommend(count=24, no_repeat_rounds=3, diversity=0.43, algo="normal",
                use_tags=True, use_actors=True, use_directors=True,
                exclude_watched=False, use_userrating=False)
rounds = []
for _ in range(4):
    res = rec.recommend(limit=24, algo="normal")
    got = [p["id"] for p in res["picks"]]
    rounds.append(set(got))
    print(f"  第 {res.get('round')} 轮：{len(got)} 部，避让 {res.get('excluded')} 部")
check("每轮都拿到 24 部", all(len(r) == 24 for r in rounds), str([len(r) for r in rounds]))
overlaps = [len(rounds[a] & rounds[b])
            for a in range(len(rounds)) for b in range(a + 1, len(rounds))]
check("任意两轮交集为 0（N=3 轮内不重复）", max(overlaps) == 0, str(overlaps))
check("历史累计 4 轮", len(s.smart_history) == 4, str([r["round"] for r in s.smart_history]))
check("round 递增", [r["round"] for r in s.smart_history] == [1, 2, 3, 4])

print("  —— N=1：只避让最近 1 轮（第 3 轮可以与第 1 轮重合）——")
s.clear_smart_history()
s.set_recommend(no_repeat_rounds=1)
r1 = {p["id"] for p in rec.recommend(limit=24)["picks"]}
r2 = {p["id"] for p in rec.recommend(limit=24)["picks"]}
r3 = {p["id"] for p in rec.recommend(limit=24)["picks"]}
check("相邻两轮不重复", not (r1 & r2) and not (r2 & r3), f"{len(r1&r2)} {len(r2&r3)}")
check("相隔一轮可以重复（r1∩r3 有交集）", len(r1 & r3) > 0, str(len(r1 & r3)))

print("  —— N=0：不限制 ——")
s.clear_smart_history()
s.set_recommend(no_repeat_rounds=0)
a = {p["id"] for p in rec.recommend(limit=24)["picks"]}
b = {p["id"] for p in rec.recommend(limit=24)["picks"]}
check("N=0 时两轮完全一致（不避让）", a == b, f"交集 {len(a&b)}/24")

print("  —— 清空推荐历史 ——")
s.clear_smart_history()
check("history 清空后为空", s.smart_history == [] and s.seen_smart == [])

# ---------------------------------------------------------------- 收尾
s.set_recommend(no_repeat_rounds=3, count=24)
s.clear_smart_history()
print()
if fails:
    print(f"FAILED {len(fails)}: {fails}")
    sys.exit(1)
print("ALL PASS")
