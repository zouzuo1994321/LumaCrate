# -*- coding: utf-8 -*-
"""v1.25.0 patch _a 续跑：第 7 项锚点收窄 + 第 8~13 项。

_a 跑到第 7 项时发现锚点（count 收窄那段）在 load() 与 set_recommend() 各出现一次，
命中 2 次被断言拦下（前 6 项已落盘，幂等安全）。这里给锚点补上后置上下文使其唯一。
"""
import os

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


# --- 第 7 项（锚点已收窄：只命中 load() 里那一处）---
patch("config.py", "load(): recommend 收窄新键",
      '            self.recommend["count"] = 24\n'
      '        if isinstance(data.get("dedupe"), dict):\n',
      '            self.recommend["count"] = 24\n'
      '        self._sanitize_recommend()\n'
      '        if isinstance(data.get("dedupe"), dict):\n')

# --- 第 8 项 ---
patch("config.py", "save(): 落盘 smart_history / tagopt",
      '                    "seen_smart": self.seen_smart,\n',
      '                    "seen_smart": self.seen_smart,\n'
      '                    "smart_history": self.smart_history,\n'
      '                    "tagopt": self.tagopt,\n')

# --- 第 9 项：remember_smart -> 轮次 API ---
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

# --- 第 10 项 ---
patch("config.py", "set_recommend 收窄新键",
      '        for k in ("use_tags", "use_actors", "use_directors", "exclude_watched"):\n'
      '            self.recommend[k] = bool(self.recommend.get(k, True))\n',
      '        for k in ("use_tags", "use_actors", "use_directors", "exclude_watched"):\n'
      '            self.recommend[k] = bool(self.recommend.get(k, True))\n'
      '        self._sanitize_recommend()\n')

# --- 第 11 项 ---
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
print("config.py 全部完成")
