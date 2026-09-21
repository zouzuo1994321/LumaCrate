# -*- coding: utf-8 -*-
"""v1.25.0 一次性源码补丁（6 条用户反馈）。

为什么用脚本而不是逐个 Edit：本文件要改 6 个源文件、几十处，且**同一文件多处**。
Edit 工具在同一文件并行/连续修改时会偶发「报成功但没落盘」（本项目已踩过两次），
这里改成「锚点精确匹配 + 命中数断言」，一次跑完并打印逐项报告；任何锚点对不上就直接抛错。
"""
import os
import re
import sys

ROOT = r"Z:/【01】自研软件/【26-19】本地影视中心"
SRC = os.path.join(ROOT, "src")
REPORT = []


def read(rel):
    with open(os.path.join(SRC, rel), encoding="utf-8") as f:
        return f.read()


def write(rel, text):
    with open(os.path.join(SRC, rel), "w", encoding="utf-8", newline="") as f:
        f.write(text)


def patch(rel, label, old, new, count=1):
    s = read(rel)
    n = s.count(old)
    if n != count:
        raise SystemExit(f"✗ [{rel} :: {label}] 锚点命中 {n} 次，期望 {count} 次\n"
                         f"----- 锚点 -----\n{old[:400]}\n----------------")
    write(rel, s.replace(old, new))
    REPORT.append(f"OK  {rel:18s} {label}")


# ===========================================================================
# 1) config.py
# ===========================================================================
patch("config.py", "import re/time",
      "import os\nimport sys\nimport json\n",
      "import os\nimport re\nimport sys\nimport json\nimport time\n")

patch("config.py", "高亮色 12 色 + DEFAULT_APPEARANCE",
      '# 外观：磨砂玻璃（系统模糊）+ 玻璃浓度\n'
      'APPEARANCE_MODES = ["磨砂玻璃", "经典暗色"]\n'
      'GLASS_LEVELS = ["低", "中", "高"]\n'
      '# 玻璃浓度 -> (页面底色不透明度, 面板不透明度)，255 = 完全不透明\n'
      '_GLASS_ALPHA = {"低": (118, 138), "中": (146, 168), "高": (186, 206)}\n'
      'DEFAULT_APPEARANCE = {"mode": "磨砂玻璃", "level": "中"}\n',
      '# 外观：磨砂玻璃（系统模糊）+ 玻璃浓度\n'
      'APPEARANCE_MODES = ["磨砂玻璃", "经典暗色"]\n'
      'GLASS_LEVELS = ["低", "中", "高"]\n'
      '# 玻璃浓度 -> (页面底色不透明度, 面板不透明度)，255 = 完全不透明\n'
      '_GLASS_ALPHA = {"低": (118, 138), "中": (146, 168), "高": (186, 206)}\n'
      '\n'
      '# v1.25.0（反馈 5）：12 种基础「高亮色」。\n'
      '# 卡片选中的描边 + 外发光、按钮 / chip / 滑块的强调色，全部由它派生 ——\n'
      '# 用户挑一个，整套界面（含自绘控件）跟着换。\n'
      'ACCENT_COLORS = [\n'
      '    ("朱红", "#c0392b"),\n'
      '    ("绯粉", "#e2659a"),\n'
      '    ("杏橙", "#e08a3c"),\n'
      '    ("鎏金", "#d4af37"),\n'
      '    ("竹青", "#5aa469"),\n'
      '    ("青碧", "#2e9e8f"),\n'
      '    ("天青", "#3fa9c9"),\n'
      '    ("靛蓝", "#3b6fd4"),\n'
      '    ("紫棠", "#8e5bd4"),\n'
      '    ("藕荷", "#b07aa1"),\n'
      '    ("玉白", "#c9d6dd"),\n'
      '    ("石墨", "#7a8b99"),\n'
      ']\n'
      'ACCENT_DEFAULT = "#c0392b"\n'
      'DEFAULT_APPEARANCE = {"mode": "磨砂玻璃", "level": "中", "accent": ACCENT_DEFAULT}\n'
      '\n'
      '\n'
      'def accent_name(hexv: str) -> str:\n'
      '    for _n, h in ACCENT_COLORS:\n'
      '        if h.lower() == str(hexv or "").lower():\n'
      '            return _n\n'
      '    return "自定义"\n'
      '\n'
      '\n'
      'def _clamp8(v):\n'
      '    return max(0, min(255, int(round(v))))\n'
      '\n'
      '\n'
      'def accent_rgb(hexv: str = None):\n'
      '    """高亮色 -> (r, g, b)。非法值回落到默认朱红。"""\n'
      '    h = str(hexv or "").strip().lstrip("#")\n'
      '    if len(h) != 6:\n'
      '        h = ACCENT_DEFAULT.lstrip("#")\n'
      '    try:\n'
      '        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))\n'
      '    except ValueError:\n'
      '        h = ACCENT_DEFAULT.lstrip("#")\n'
      '        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))\n'
      '\n'
      '\n'
      'def accent_shades(hexv: str = None) -> dict:\n'
      '    """由高亮色派生出一组明暗变体，供 QSS 令牌使用。\n'
      '\n'
      '    base = 原色；dark = 按下/选中底；deep = hover 底；light = 描边。\n'
      '    按比例缩放并夹到 0~255 —— 换任何基础色，层次关系都保持一致\n'
      '    （默认朱红缩放后与原先写死的几个色值基本重合，所以老用户观感不变）。\n'
      '    """\n'
      '    r, g, b = accent_rgb(hexv)\n'
      '\n'
      '    def scale(f):\n'
      '        return (_clamp8(r * f), _clamp8(g * f), _clamp8(b * f))\n'
      '\n'
      '    return {"base": (r, g, b), "dark": scale(0.73), "deep": scale(0.85),\n'
      '            "light": scale(1.17)}\n')

patch("config.py", "DEFAULT_RECOMMEND 增 ai_model / no_repeat_rounds",
      '    "exclude_watched": True,   # 排除已看过的\n'
      '    "diversity": 0.5,          # 多样性（MMR λ 的反面：越大越多样）\n'
      '}\n',
      '    "exclude_watched": True,   # 排除已看过的\n'
      '    "diversity": 0.5,          # 多样性（MMR λ 的反面：越大越多样）\n'
      '    # v1.25.0（反馈 1）：调用哪个本地模型 —— 空 = 自动（取 ollama list 里的第一个）\n'
      '    "ai_model": "",\n'
      '    # v1.25.0（反馈 3）：最近 N 轮推荐过的作品不再出现（0 = 不限制）\n'
      '    "no_repeat_rounds": 3,\n'
      '}\n')

patch("config.py", "DEFAULT_TAGOPT",
      '# 画像概览的统计范围（v1.24.1 反馈 4）：scope = "" 表示全部媒体库，否则是媒体库名\n'
      'DEFAULT_INSIGHT = {"scope": "", "favorites_only": False}\n',
      '# 画像概览的统计范围（v1.24.1 反馈 4）：scope = "" 表示全部媒体库，否则是媒体库名\n'
      'DEFAULT_INSIGHT = {"scope": "", "favorites_only": False}\n'
      '# 标签优化（v1.25.0 反馈 4）：范围 / 算法 / 翻译 / 覆盖 / 备份\n'
      'DEFAULT_TAGOPT = {\n'
      '    "scope": "file",       # file（单一文件）/ folder（文件夹）/ library（媒体库）\n'
      '    "path": "",            # 文件或文件夹路径\n'
      '    "library": "",         # 媒体库名（scope=library 时用）\n'
      '    "algo": "normal",      # normal（内置算法）/ ai（本地离线 AI）\n'
      '    "translate": True,     # 日语标签转中文\n'
      '    "overwrite": False,    # True = 中文替换原日语标签；False = 保留原文并另补一条中文\n'
      '    "complete": True,      # 补全缺失标签（标题关键词 / 共现 / 片商 / 系列）\n'
      '    "backup": True,        # 写入前把原 nfo 另存为 *.nfo.bak-<时间戳>\n'
      '}\n')

patch("config.py", "__init__ 增 smart_history / tagopt",
      '        self.vector_overrides = {}      # 向量编辑：{维度: {键: 权重}}（0 = 屏蔽）\n'
      '        self.seen_smart = []            # 智能推荐「换一批」避让用（最近推过的 media id）\n',
      '        self.vector_overrides = {}      # 向量编辑：{维度: {键: 权重}}（0 = 屏蔽）\n'
      '        self.seen_smart = []            # 智能推荐「换一批」避让用（最近推过的 media id）\n'
      '        # v1.25.0（反馈 3）：推荐历史按「轮次」记 —— [{"round": 1, "ids": [...], "ts": ...}]\n'
      '        self.smart_history = []\n'
      '        # v1.25.0（反馈 4）：标签优化偏好\n'
      '        self.tagopt = dict(DEFAULT_TAGOPT)\n')

patch("config.py", "load(): smart_history / tagopt / accent 校验",
      '        if isinstance(data.get("seen_smart"), list):\n'
      '            self.seen_smart = [int(x) for x in data["seen_smart"]\n'
      '                               if isinstance(x, (int, float))][-200:]\n'
      '        if isinstance(data.get("background"), dict):\n'
      '            self.background.update(data["background"])\n'
      '        if isinstance(data.get("appearance"), dict):\n'
      '            self.appearance.update(data["appearance"])\n',
      '        if isinstance(data.get("seen_smart"), list):\n'
      '            self.seen_smart = [int(x) for x in data["seen_smart"]\n'
      '                               if isinstance(x, (int, float))][-200:]\n'
      '        # v1.25.0（反馈 3）：推荐轮次历史；老配置只有扁平的 seen_smart → 当成第 1 轮迁过来\n'
      '        self.smart_history = self._clean_smart_history(data.get("smart_history"))\n'
      '        if not self.smart_history and self.seen_smart:\n'
      '            self.smart_history = [{"round": 1, "ids": list(self.seen_smart), "ts": 0.0}]\n'
      '        if isinstance(data.get("tagopt"), dict):\n'
      '            for k, v in data["tagopt"].items():\n'
      '                if k in DEFAULT_TAGOPT:\n'
      '                    self.tagopt[k] = v\n'
      '        self._sanitize_tagopt()\n'
      '        if isinstance(data.get("background"), dict):\n'
      '            self.background.update(data["background"])\n'
      '        if isinstance(data.get("appearance"), dict):\n'
      '            self.appearance.update(data["appearance"])\n'
      '        # 高亮色必须是我们提供的那 12 种之一（老配置没这个键 → 落到默认朱红）\n'
      '        if not any(h.lower() == str(self.appearance.get("accent") or "").lower()\n'
      '                   for _n, h in ACCENT_COLORS):\n'
      '            self.appearance["accent"] = ACCENT_DEFAULT\n')

patch("config.py", "load(): recommend 收窄新键",
      '        try:\n'
      '            self.recommend["count"] = max(6, min(120, int(self.recommend.get("count", 24))))\n'
      '        except Exception:\n'
      '            self.recommend["count"] = 24\n',
      '        try:\n'
      '            self.recommend["count"] = max(6, min(120, int(self.recommend.get("count", 24))))\n'
      '        except Exception:\n'
      '            self.recommend["count"] = 24\n'
      '        self._sanitize_recommend()\n')

patch("config.py", "save(): 落盘 smart_history / tagopt",
      '                    "seen_smart": self.seen_smart,\n',
      '                    "seen_smart": self.seen_smart,\n'
      '                    "smart_history": self.smart_history,\n'
      '                    "tagopt": self.tagopt,\n')

patch("config.py", "remember_smart -> 轮次 API + 清洗",
      '    def remember_smart(self, ids: list):\n'
      '        """记录「刚刚推荐过」的 media id（最多留 200 个），供下次换一批避让。"""\n'
      '        seen = [int(x) for x in (self.seen_smart or [])]\n'
      '        for i in ids:\n'
      '            try:\n'
      '                i = int(i)\n'
      '            except Exception:\n'
      '                continue\n'
      '            if i in seen:\n'
      '                seen.remove(i)\n'
      '            seen.append(i)\n'
      '        self.seen_smart = seen[-200:]\n'
      '        self.save()\n',
      '    def remember_smart(self, ids: list):\n'
      '        """记录「刚刚推荐过」的 media id（v1.25.0 起等价于「追加一轮」）。"""\n'
      '        self.push_smart_round(ids)\n'
      '\n'
      '    # ---------- v1.25.0（反馈 3）：推荐历史按轮次 ----------\n'
      '    def push_smart_round(self, ids, keep=None):\n'
      '        """把本轮推荐的作品记成 1 轮（每点一次「换一批」/ 重进推荐页 = 1 轮）。"""\n'
      '        clean = []\n'
      '        for i in (ids or []):\n'
      '            try:\n'
      '                i = int(i)\n'
      '            except (TypeError, ValueError):\n'
      '                continue\n'
      '            if i not in clean:\n'
      '                clean.append(i)\n'
      '        if not clean:\n'
      '            return\n'
      '        rnd = (self.smart_history[-1]["round"] + 1) if self.smart_history else 1\n'
      '        self.smart_history.append({"round": rnd, "ids": clean, "ts": time.time()})\n'
      '        self._prune_smart_history(keep)\n'
      '        # 兼容旧键：同步一份扁平列表（老版本 / 旧导出包只认它）\n'
      '        flat = []\n'
      '        for r in self.smart_history:\n'
      '            for i in r.get("ids", []):\n'
      '                if i not in flat:\n'
      '                    flat.append(i)\n'
      '        self.seen_smart = flat[-200:]\n'
      '        self.save()\n'
      '\n'
      '    def recent_smart_ids(self, rounds=None) -> list:\n'
      '        """最近 N 轮推荐过的 id（顺序去重）。N <= 0 视为「不限制」→ 返回空列表。"""\n'
      '        if rounds is None:\n'
      '            try:\n'
      '                rounds = int(self.recommend.get("no_repeat_rounds", 3))\n'
      '            except (TypeError, ValueError):\n'
      '                rounds = 3\n'
      '        try:\n'
      '            rounds = int(rounds)\n'
      '        except (TypeError, ValueError):\n'
      '            return []\n'
      '        if rounds <= 0:\n'
      '            return []\n'
      '        out = []\n'
      '        for r in (self.smart_history or [])[-rounds:]:\n'
      '            for i in r.get("ids", []):\n'
      '                if i not in out:\n'
      '                    out.append(i)\n'
      '        return out\n'
      '\n'
      '    def clear_smart_history(self):\n'
      '        """忘掉之前推荐过哪些作品（下次从头开始推，但「已收藏的不推荐」仍然生效）。"""\n'
      '        self.smart_history = []\n'
      '        self.seen_smart = []\n'
      '        self.save()\n'
      '\n'
      '    @staticmethod\n'
      '    def _clean_smart_history(raw) -> list:\n'
      '        """只接受 [{"round": int, "ids": [int, ...]}]，脏数据一律丢掉。"""\n'
      '        out = []\n'
      '        if not isinstance(raw, list):\n'
      '            return out\n'
      '        for item in raw:\n'
      '            if not isinstance(item, dict):\n'
      '                continue\n'
      '            ids = []\n'
      '            for i in (item.get("ids") or []):\n'
      '                try:\n'
      '                    i = int(i)\n'
      '                except (TypeError, ValueError):\n'
      '                    continue\n'
      '                if i not in ids:\n'
      '                    ids.append(i)\n'
      '            if not ids:\n'
      '                continue\n'
      '            try:\n'
      '                rnd = int(item.get("round") or (len(out) + 1))\n'
      '            except (TypeError, ValueError):\n'
      '                rnd = len(out) + 1\n'
      '            try:\n'
      '                ts = float(item.get("ts") or 0.0)\n'
      '            except (TypeError, ValueError):\n'
      '                ts = 0.0\n'
      '            out.append({"round": rnd, "ids": ids, "ts": ts})\n'
      '        return out\n'
      '\n'
      '    def _prune_smart_history(self, keep=None):\n'
      '        """只留最近 keep 轮；留的轮数必须 ≥ 用户设的「不重复轮数」，否则去重会失效。"""\n'
      '        if keep is None:\n'
      '            try:\n'
      '                n = int(self.recommend.get("no_repeat_rounds", 3))\n'
      '            except (TypeError, ValueError):\n'
      '                n = 3\n'
      '            keep = max(20, n * 3 + 5)\n'
      '        keep = max(1, int(keep))\n'
      '        if len(self.smart_history) > keep:\n'
      '            self.smart_history = self.smart_history[-keep:]\n'
      '\n'
      '    # ---------- v1.25.0：偏好清洗 ----------\n'
      '    def _sanitize_recommend(self):\n'
      '        """把 v1.25.0 新加的两个键收窄到合法范围（load / set_recommend 共用）。"""\n'
      '        m = re.sub(r"[^0-9A-Za-z_.:\\-/]", "",\n'
      '                   str(self.recommend.get("ai_model") or "").strip())[:64]\n'
      '        self.recommend["ai_model"] = m\n'
      '        try:\n'
      '            self.recommend["no_repeat_rounds"] = max(\n'
      '                0, min(50, int(self.recommend.get("no_repeat_rounds", 3))))\n'
      '        except (TypeError, ValueError):\n'
      '            self.recommend["no_repeat_rounds"] = 3\n'
      '        self.recommend["use_userrating"] = bool(\n'
      '            self.recommend.get("use_userrating", False))\n'
      '\n'
      '    def _sanitize_tagopt(self):\n'
      '        if self.tagopt.get("scope") not in ("file", "folder", "library"):\n'
      '            self.tagopt["scope"] = "file"\n'
      '        self.tagopt["algo"] = "ai" if self.tagopt.get("algo") == "ai" else "normal"\n'
      '        for k in ("translate", "overwrite", "complete", "backup"):\n'
      '            self.tagopt[k] = bool(self.tagopt.get(k, DEFAULT_TAGOPT[k]))\n'
      '        self.tagopt["path"] = str(self.tagopt.get("path") or "")[:500]\n'
      '        self.tagopt["library"] = str(self.tagopt.get("library") or "")[:120]\n')

patch("config.py", "set_recommend 收窄新键",
      '        for k in ("use_tags", "use_actors", "use_directors", "exclude_watched"):\n'
      '            self.recommend[k] = bool(self.recommend.get(k, True))\n',
      '        for k in ("use_tags", "use_actors", "use_directors", "exclude_watched"):\n'
      '            self.recommend[k] = bool(self.recommend.get(k, True))\n'
      '        self._sanitize_recommend()\n')

patch("config.py", "set_appearance + set_accent + set_tagopt",
      '    # ---------- 外观 ----------\n'
      '    def set_appearance(self, mode: str = None, level: str = None):\n'
      '        if mode in APPEARANCE_MODES:\n'
      '            self.appearance["mode"] = mode\n'
      '        if level in GLASS_LEVELS:\n'
      '            self.appearance["level"] = level\n'
      '        self.save()\n',
      '    # ---------- 外观 ----------\n'
      '    def set_appearance(self, mode: str = None, level: str = None, accent: str = None):\n'
      '        if mode in APPEARANCE_MODES:\n'
      '            self.appearance["mode"] = mode\n'
      '        if level in GLASS_LEVELS:\n'
      '            self.appearance["level"] = level\n'
      '        if accent and any(h.lower() == str(accent).lower() for _n, h in ACCENT_COLORS):\n'
      '            self.appearance["accent"] = str(accent)\n'
      '        self.save()\n'
      '\n'
      '    # v1.25.0（反馈 5）：高亮色 —— 卡片选中 / 外发光 / 强调色都用它\n'
      '    def accent(self) -> str:\n'
      '        return self.appearance.get("accent") or ACCENT_DEFAULT\n'
      '\n'
      '    def set_accent(self, hexv: str):\n'
      '        self.set_appearance(accent=hexv)\n'
      '\n'
      '    # ---------- v1.25.0（反馈 4）：标签优化 ----------\n'
      '    def set_tagopt(self, **kw):\n'
      '        for k, v in kw.items():\n'
      '            if k in DEFAULT_TAGOPT:\n'
      '                self.tagopt[k] = v\n'
      '        self._sanitize_tagopt()\n'
      '        self.save()\n')

print("\n".join(REPORT))
print("config.py 完成")
