# -*- coding: utf-8 -*-
"""智能推荐（v1.24.0 新增）

需求（反馈 8）：导航里加「智能推荐」（可关闭 / 可排序，与其他导航一致）。
推荐依据 = **「我的收藏」里的影片（按标签 / 片商 / 系列 / 演员 / 导演）** +
**「演员库」里收藏的演员**。算法在「工具」里可选：

- **普通智能算法**：把收藏折成偏好向量 → 与全库作品做 IDF 加权余弦相似度 → MMR 去重。
- **AI 智能算法**：在普通算法之上再叠一层「本地离线 AI」：
  1. 内置**标签共现联想**（纯本地、无需任何依赖，把种子标签按 P(标签B|标签A) 扩展）；
  2. 若本机跑着 **Ollama**（`127.0.0.1:11434`），把种子词交给本地模型做语义扩词
     （离线、不出网）；不可用就静默降级到第 1 步，绝不阻塞、绝不报错。

与 nfo_profiler 的对应关系：逆向自它的 `recommender.py`（`Recommender.profile_tokens`
+ TF-IDF + MMR）与 `ai_engine.py`（`expand_terms` / `interpret`）。差异在于**打分对象**：
它给自己的 `movies` 表打分，这里给流明盒的 `media` 表打分，并且把
`genres` 里 `片商:` / `系列:` 这类伪标签拆桶后再入向量。

向量编辑：`config.settings.vector_overrides` = {维度: {键: 权重}}，
维度 ∈ tag / actor / director / studio / series；写进 `db.vector_overrides` 表（权威），
settings.json 存快照。weight > 0 加强、< 0 软排斥、= 0 屏蔽。
"""
import json
import math
import re
import urllib.request
from collections import Counter

import config as cfg
import database as db
import insight

# token 前缀 → 维度名 / 基础权重
DIMS = {
    "t": ("tag", 1.0),
    "a": ("actor", 0.70),
    "d": ("director", 0.85),
    "s": ("studio", 0.55),
    "x": ("series", 0.75),
}
_DIM_CN = {"tag": "标签", "actor": "演员", "director": "导演", "studio": "片商", "series": "系列"}
_OLLAMA = "http://127.0.0.1:11434"
# v1.24.1：探测地址对外公开（UI 的「检测本地 AI 引擎」要把探测目标写进提示文案，
# 否则用户只看到「没检测到」却不知道到底探的是哪个地址）。
OLLAMA_URL = _OLLAMA
OLLAMA_HOST = "127.0.0.1:11434"
# 「用户评分」当弱信号的阈值。**必须明显高于全库均值**：真机 4.7 万条里 user_rating≥7.5
# 的有 4.3 万条（nfo 里带的是来源评分，不是用户自己打的），拿 7.5 当门槛等于「全库都是喜欢的」。
USER_RATING_LIKE = 8.5


def dim_cn(dim: str) -> str:
    return _DIM_CN.get(dim, dim)


# ---------------------------------------------------------------- AI 引擎探测
def list_models(timeout=0.5) -> list:
    """本机 Ollama 里已经装好的模型名（= 命令行 `ollama list` 的第一列）。

    v1.25.0（反馈 1）：给「自己输入想调用的模型」用 —— 用户填的名字对不对，
    靠它来校验，而不是先发一次注定失败的 /api/generate。不可用时返回 []。
    """
    try:
        with urllib.request.urlopen(_OLLAMA + "/api/tags", timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return []
    out = []
    for m in (data.get("models") or []):
        name = m.get("name") or m.get("model")
        if name:
            out.append(str(name))
    return out


def configured_model() -> str:
    """用户在设置里填的模型名（空 = 自动挑本机第一个）。"""
    try:
        return str((cfg.get_settings().recommend or {}).get("ai_model") or "").strip()
    except Exception:
        return ""


def resolve_model(model=None) -> str:
    """决定这次到底调用哪个模型。

    优先级：显式传入 > 设置里填的 > 本机第一个已装模型 > llama3（兜底）。
    """
    want = str(model or "").strip() or configured_model()
    if want:
        return want
    names = list_models()
    return names[0] if names else "llama3"


def probe_ollama(timeout=0.5, model=None):
    """本机是否有可用的 Ollama（纯本地、离线）。返回**这次要用的模型名**或 None。

    与 v1.24.x 的区别：不再无条件取 /api/tags 的第一个 —— 如果用户在设置里指定了
    模型，就按指定的来；指定了但本机没装，返回 None（调用方会静默降级到内置联想，
    页面上的检测文案会明确告诉用户「这个模型没找到」以及列出本机已装的模型）。
    """
    names = list_models(timeout)
    if not names:
        return None
    want = str(model or "").strip() or configured_model()
    if want:
        return want if want in names else None
    return names[0]


def ai_status():
    """给「工具 → 智能推荐」页显示的状态（v1.25.0 反馈 1 后按模型是否装好分三种）。"""
    names = list_models()
    want = configured_model()
    if not names:
        return {"engine": "builtin", "label": "内置离线联想引擎",
                "detail": f"未检测到本地 Ollama（探测 {OLLAMA_HOST}），使用内置的标签共现联想"
                          "（纯本地、无需依赖）。需要更聪明的语义扩词时：启动 Ollama 后执行"
                          "「ollama list」查看已装模型，「ollama pull qwen2.5:7b」装一个"
                          "（或任意模型），再点一次「检测本地 AI 引擎」即可，全程不出网。"}
    shown = "、".join(names[:8])
    more = "…" if len(names) > 8 else ""
    if want and want not in names:
        return {"engine": "builtin", "label": f"内置离线联想引擎（指定模型 {want} 未安装）",
                "detail": f"设置里指定的是「{want}」，但本机 Ollama 里没有这个模型，"
                          f"已自动降级为内置联想。本机已装：{shown}{more}。"
                          f"可在设置里改成上面其中之一，或执行「ollama pull {want}」把它装上。"}
    use = want or names[0]
    tail = "（自动选取本机第一个）" if not want else "（设置里指定的）"
    return {"engine": "ollama", "label": f"本地 Ollama（{use}）{tail}",
            "detail": f"离线扩词已启用：会把偏好种子词交给本地模型做语义扩展，全程不出网。\n"
                      f"本机已装 {len(names)} 个模型：{shown}{more}。"}


def _ollama_expand(seed_terms, limit=40, timeout=25, model=None):
    """让本地模型把种子词扩成同类词（离线）。失败一律返回 []。

    v1.25.0（反馈 1）：`model` 不再是「探到谁就用谁」，而是走 resolve_model()
    —— 用户在设置里填的模型优先。
    """
    if not seed_terms:
        return []
    prompt = (
        "你是影视标签推荐助手。下面是用户收藏影片的高频标签/片商/演员名。\n"
        "请再给出 30 个**同类且更具体**的标签词（只输出词，逗号分隔，不要解释、不要编号）。\n"
        "种子：" + "、".join(seed_terms[:60]))
    body = json.dumps({
        "model": resolve_model(model),
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.4, "num_predict": 220},
    }).encode("utf-8")
    try:
        req = urllib.request.Request(_OLLAMA + "/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        text = data.get("response") or ""
    except Exception:
        return []
    words = [w.strip(" 　·、,，.。;；:：\"'()（）[]【】") for w in re.split(r"[,，、\n;；]", text)]
    return [w for w in words if 1 < len(w) <= 24][:limit]


# ---------------------------------------------------------------- 主引擎
class Recommender:
    """把「收藏 + 收藏的演员」折成偏好向量，给全库作品打分。"""

    def __init__(self, settings=None):
        self.s = settings or cfg.get_settings()
        self._cache = {}

    # ------------------------------------------------ 取数
    def _load(self, library=None, progress=None):
        key = library or ""
        if key in self._cache:
            return self._cache[key]

        def step(i, n, msg):
            if progress:
                progress(i, n, msg)

        step(0, 5, "正在读取作品元数据…")
        rows = db.media_for_insight(library)
        step(1, 5, f"已读取 {len(rows):,} 部作品")
        actors = db.people_links_map("Actor")
        step(2, 5, "正在统计演员关联…")
        directors = db.people_links_map("Director")
        step(3, 5, "正在统计导演关联…")
        self._cache[key] = (rows, actors, directors)
        return self._cache[key]

    # ------------------------------------------------ 作品 → token 集合
    @staticmethod
    def _tokens(row, actors, directors, min_len=1):
        """一部作品 → {token: 次数}。"""
        toks = Counter()
        tags, studios, _pubs, series = insight.split_tags(row.get("genres"))
        for t in tags:
            if len(t) >= min_len:
                toks["t:" + t] += 1
        for s in studios:
            toks["s:" + s] += 1
        if row.get("studio"):
            toks["s:" + str(row["studio"]).strip()] += 1
        if row.get("collection"):
            toks["x:" + str(row["collection"]).strip()] += 1
        for s in series:
            toks["x:" + s] += 1
        for a in actors.get(row["id"], ()):
            if not insight.is_junk_person(a):
                toks["a:" + a] += 1
        for d in directors.get(row["id"], ()):
            if not insight.is_junk_person(d):
                toks["d:" + d] += 1
        return toks

    def _overrides(self) -> dict:
        """手动权重：{维度: {键: 权重}}。

        **以数据库 `vector_overrides` 表为准**（向量编辑页写的就是它），
        settings.json 里那份只是随配置一起导出/导入的快照；表为空时回退到快照，
        这样「只恢复了 settings.json 的旧备份」也能用。
        """
        ov = {}
        try:
            for dim, key, w, _note, _u in db.vector_overrides():
                ov.setdefault(dim, {})[key] = float(w)
        except Exception:
            ov = {}
        if ov:
            return ov
        snap = self.s.vector_overrides or {}
        return {str(d): {str(k): float(v) for k, v in (vals or {}).items()}
                for d, vals in snap.items() if isinstance(vals, dict)}

    # ------------------------------------------------ 偏好向量
    def build_profile(self, rows=None, actors=None, directors=None, progress=None):
        """返回 (profile: {token: weight}, meta: {...})。"""
        rows = rows if rows is not None else self._load()[0]
        actors = actors if actors is not None else self._load()[1]
        directors = directors if directors is not None else self._load()[2]

        rec = dict(self.s.recommend or {})
        use_tags = bool(rec.get("use_tags", True))
        use_actors = bool(rec.get("use_actors", True))
        use_directors = bool(rec.get("use_directors", True))
        use_userrating = bool(rec.get("use_userrating", False))

        prof = Counter()
        fav_ids, like_ids = [], []
        used_fav_people = []
        for r in rows:
            if r.get("favorite"):
                fav_ids.append(r["id"])
                for t, c in self._tokens(r, actors, directors).items():
                    prof[t] += DIMS.get(t[0], ("", 1.0))[1] * (1.0 + 0.15 * (c - 1))
            elif use_userrating:
                try:
                    ur = float(r.get("user_rating") or 0)
                except (TypeError, ValueError):
                    ur = 0.0
                if ur >= USER_RATING_LIKE:          # 弱信号：只有明显高于全库的才算
                    like_ids.append(r["id"])
                    for t, c in self._tokens(r, actors, directors).items():
                        prof[t] += DIMS.get(t[0], ("", 1.0))[1] * 0.35

        # **归一化**：收藏贡献先缩到 max=1，否则 101 部收藏累加出来的标签权重（数百）
        # 会把「收藏的演员」（个位数权重）彻底淹没 —— 实测踩到：4 位收藏演员对结果毫无影响。
        if prof:
            mx = max(prof.values()) or 1.0
            for t in list(prof):
                prof[t] /= mx

        # 演员库里收藏的演员 / 导演：**最强信号**（用户明确表过态，权重高于任何标签）
        for p in db.favorite_people():
            name = str(p.get("name") or "").strip()
            if insight.is_junk_person(name):
                continue
            role = (p.get("role_type") or "").lower()
            if role.startswith("direct"):
                prof["d:" + name] += 1.2
            else:
                prof["a:" + name] += 1.2
            used_fav_people.append((name, p.get("role_type") or "Actor"))

        if progress:
            progress(3, 5, f"个人画像：{len(fav_ids)} 部收藏 / {len(like_ids)} 部高分 / "
                           f"{len(used_fav_people)} 位收藏人")

        # 开关：关掉的维度整类剔掉
        for t in list(prof):
            head = t[0]
            if head == "t" and not use_tags:
                del prof[t]
            elif head == "a" and not use_actors:
                del prof[t]
            elif head == "d" and not use_directors:
                del prof[t]

        # 向量编辑：手动加权覆盖（0 = 屏蔽）
        ov = self._overrides()
        applied = 0
        for t in list(prof):
            dim = DIMS.get(t[0], ("", 0))[0]
            key = t[2:]
            w = (ov.get(dim) or {}).get(key)
            if w is None:
                continue
            applied += 1
            if w == 0:
                del prof[t]
            else:
                prof[t] *= float(w)
        # 手动加进来的正向词（画像里原本没有的）
        for dim, vals in ov.items():
            for key, w in (vals or {}).items():
                if not w:
                    continue
                head = next((h for h, (d, _b) in DIMS.items() if d == dim), None)
                if head:
                    prof[head + ":" + key] += 1.0 * float(w)

        meta = {
            "favorites": len(fav_ids),
            "liked": len(like_ids),
            "fav_people": used_fav_people[:40],
            "fav_people_n": len(used_fav_people),
            "vector_applied": applied,
        }
        return dict(prof), meta

    # ------------------------------------------------ IDF
    @staticmethod
    def _idf(profile, item_tokens, n_items):
        """df(token) 从候选作品里数；idf = log(N/df) + 1（有下界，避免爆权重）。"""
        df = Counter()
        for toks in item_tokens:
            for t in toks:
                if t in profile:
                    df[t] += 1
        out = {}
        for t in profile:
            d = df.get(t, 0)
            out[t] = (math.log((n_items + 1) / (d + 1)) + 1.0)
        return out

    # ------------------------------------------------ 联想扩展（AI 模式）
    @staticmethod
    def _cooccur_expand(profile, item_tokens, top_k=10, factor=0.30, max_terms=60):
        """内置离线联想：用作品内的标签共现，给每个种子词补一批「常一起出现」的词。

        P(B|A) = count(A 与 B 同现) / count(A)；只补 P 高的前 top_k 个，
        权重 = 原权重 × P × factor（远低于原始种子，只做「拓宽」不做「改口」）。
        """
        seeds = [t for t in profile if t.startswith("t:")]
        if not seeds:
            return profile
        seed_set = set(seeds)
        co = {s: Counter() for s in seed_set}
        for toks in item_tokens:
            present = [t for t in toks if t in seed_set]
            if len(present) < 2:
                continue
            for a in present:
                for b in present:
                    if a != b:
                        co[a][b] += 1
        out = dict(profile)
        added = 0
        for s in seeds:
            total = sum(co[s].values())
            if total <= 0:
                continue
            for b, c in co[s].most_common(top_k):
                p = c / max(total, 1)
                if p < 0.25:
                    continue
                w = abs(profile[s]) * p * factor
                out[b] = out.get(b, 0.0) + w
                added += 1
                if added >= max_terms:
                    return out
        return out

    # ------------------------------------------------ 主入口
    def recommend(self, limit=24, algo="normal", library=None, exclude_ids=(),
                  explore=0.25, diversity=None, progress=None, with_reasons=True,
                  ai_model=None):
        """返回 {'picks': [row + score/reason], 'meta': {...}, 'algo': ...}。"""
        rec = dict(self.s.recommend or {})
        limit = int(limit or rec.get("count", 24))
        limit = max(6, min(120, limit))
        if diversity is None:
            diversity = float(rec.get("diversity", 0.35))
        exclude = set()
        for i in (exclude_ids or ()):
            try:
                exclude.add(int(i))
            except (TypeError, ValueError):
                continue
        use_directors = bool(rec.get("use_directors", True))
        excl_watched = bool(rec.get("exclude_watched", False))

        if progress:
            progress(0, 5, "正在准备候选池…")
        rows, actors, directors = self._load(library, progress)
        profile, meta = self.build_profile(rows, actors, directors, progress)
        if not profile:
            return {"picks": [], "meta": meta, "algo": algo, "engine": "none",
                    "empty": "还没有任何收藏 / 打分数据 —— 先给几部片子点星标，"
                             "或在演员库里收藏几位演员，推荐才有依据。"}

        item_tokens, item_rows = [], []
        for r in rows:
            if r.get("favorite"):
                continue                       # 已经收藏的不再推荐
            # v1.25.0（反馈 3）**根因修复**：`exclude` 上面算出来了，但这个循环里
            # 一直没有用它 —— 也就是说「换一批」从 v1.24.0 起实际从未生效，
            # 每点一次拿到的还是同一批 24 部（只是顺序可能不同）。补上真正的避让。
            if r["id"] in exclude:
                continue
            if excl_watched and int(r.get("play_count") or 0) > 0:
                continue
            toks = self._tokens(r, actors, directors)
            if not toks:
                continue
            item_tokens.append(toks)
            item_rows.append(r)
        n_items = max(len(item_rows), 1)
        if progress:
            progress(4, 5, f"候选池 {n_items:,} 部，正在打分…")

        idf = self._idf(profile, item_tokens, n_items)

        engine = "builtin"
        if algo == "ai":
            profile = self._cooccur_expand(profile, item_tokens)
            idf = self._idf(profile, item_tokens, n_items)
            seeds = [t[2:] for t in list(profile)[:40] if t.startswith("t:")]
            extra = _ollama_expand(seeds, model=ai_model or rec.get("ai_model"))
            for w in extra:
                if ("t:" + w) in profile or ("a:" + w) in profile:
                    continue
                profile["t:" + w] = 0.6
            if extra:
                engine = "ollama"
                idf = self._idf(profile, item_tokens, n_items)

        pvec, pnorm = self._normalize(profile, idf)
        scored = []
        for row, toks in zip(item_rows, item_tokens):
            s, norm, hit = self._cosine(pvec, pnorm, toks, idf)
            if s <= 0:
                continue
            # 真余弦：除 **两侧范数**。只除 item 那一侧会得到上万量级的「分数」，
            # 排序虽然还对，但界面上的数字毫无意义、也没法跨算法比较。
            s = s / max(pnorm * norm, 1e-9)
            s *= self._boost(row, rec)
            scored.append((s, row, toks, hit))
        if not scored:
            return {"picks": [], "meta": meta, "algo": algo, "engine": engine,
                    "empty": "没有算出可推荐的作品（候选池为空）。"}
        scored.sort(key=lambda x: -x[0])

        picks = self._mmr(scored[:1500], limit, diversity, idf)
        out = []
        for s, row, toks, hit in picks:
            item = dict(row)
            item["score"] = round(float(s), 4)
            if with_reasons:
                item["reason"] = self._reason(hit, algo, engine, s)
            out.append(item)
        if progress:
            progress(5, 5, f"推荐完成：{len(out)} 部")
        return {"picks": out, "meta": meta, "algo": algo, "engine": engine,
                "pool": n_items,
                "profile_top": [(t, round(w, 3)) for t, w in
                                sorted(profile.items(), key=lambda kv: -kv[1])[:24]]}

    # ------------------------------------------------ 打分辅助
    @staticmethod
    def _boost(row, rec):
        """年份越新略加分；随机排序里那套「抖动」这里用不到（推荐本身要稳定）。"""
        try:
            y = int(row.get("year") or 0)
        except (TypeError, ValueError):
            y = 0
        b = 1.0
        if y >= 2023:
            b += 0.06
        elif y >= 2020:
            b += 0.03
        return b

    @staticmethod
    def _normalize(profile, idf):
        vec = {t: w * idf.get(t, 1.0) for t, w in profile.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return vec, norm

    @staticmethod
    def _cosine(pvec, pnorm, toks, idf):
        dot = 0.0
        n2 = 0.0
        hit = []
        for t, c in toks.items():
            w = idf.get(t, 1.0) * (1.0 + 0.2 * (c - 1))
            n2 += w * w
            pv = pvec.get(t)
            if pv:
                dot += pv * w
                hit.append((t, pv * w))
        if n2 <= 0:
            return 0.0, 1.0, []
        hit.sort(key=lambda kv: -kv[1])
        return dot, math.sqrt(n2), hit[:4]

    @staticmethod
    def _reason(hit, algo, engine, score) -> str:
        if not hit:
            return "综合相似度 %.3f" % score
        bits = []
        for t, _v in hit[:3]:
            dim = DIMS.get(t[0], ("tag", 0))[0]
            bits.append(f"{dim_cn(dim)}「{t[2:]}」")
        if algo == "ai":
            tag = "AI 算法（本地 Ollama 扩词）" if engine == "ollama" else "AI 算法（内置离线联想）"
        else:
            tag = "普通算法"
        return f"{tag}：命中 " + "、".join(bits) + f"（相似度 {score:.3f}）"

    @staticmethod
    def _mmr(scored, k, diversity, idf):
        """最大边际相关：先拿最高分，之后每步减去「与已选作品的相似度」，
        避免一整屏都是同一系列 / 同一演员的片子。"""
        if not scored or k <= 0:
            return []
        picked = [scored[0]]
        pool = scored[1:]
        lam = max(0.0, min(0.9, float(diversity)))
        while pool and len(picked) < k:
            best_i, best_v = 0, None
            for i, (s, row, toks, hit) in enumerate(pool[:600]):
                worst = 0.0
                for _s2, _r2, toks2, _h2 in picked:
                    worst = max(worst, _jaccard(toks, toks2))
                    if worst >= 1.0:
                        break
                v = (1.0 - lam) * s - lam * worst
                if best_v is None or v > best_v:
                    best_i, best_v = i, v
            picked.append(pool.pop(best_i))
        return picked

    # ------------------------------------------------ 相似作品（详情页可用）
    def similar(self, media_id, limit=12, progress=None):
        rows, actors, directors = self._load(progress=progress)
        target = next((r for r in rows if r["id"] == int(media_id)), None)
        if target is None:
            return []
        ttok = self._tokens(target, actors, directors)
        if not ttok:
            return []
        out = []
        for r in rows:
            if r["id"] == target["id"]:
                continue
            toks = self._tokens(r, actors, directors)
            sim = _jaccard(ttok, toks)
            if sim > 0:
                out.append((sim, r))
        out.sort(key=lambda x: -x[0])
        return [dict(r, score=round(s, 4)) for s, r in out[:limit]]


def _jaccard(a, b) -> float:
    """集合余弦（用次数加权），比严格 Jaccard 更平滑。"""
    if not a or not b:
        return 0.0
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    dot = 0.0
    for t, c in small.items():
        c2 = large.get(t)
        if c2:
            dot += c * c2
    if dot <= 0:
        return 0.0
    na = math.sqrt(sum(c * c for c in a.values()))
    nb = math.sqrt(sum(c * c for c in b.values()))
    return dot / (na * nb or 1.0)


# ---------------------------------------------------------------- 便捷入口
def recommend(page=1, limit=24, algo=None, library=None, progress=None):
    """给 UI 用的一步函数：`page` 递增 = 换一批。

    v1.25.0（反馈 3）：避让范围从「只看上一批」改成「最近 N 轮」—— N 由
    「工具 → 智能推荐 → 推荐范围与偏好 → 已经推荐的 N 轮内不再出现」决定
    （0 = 不限制）。另外**不管第几页都会避让**：v1.24.x 只在 page > 1 时避让，
    于是重新进推荐页（page 回到 1）永远看到同一批。
    """
    s = cfg.get_settings()
    algo = algo or (s.recommend or {}).get("algo", "normal")
    excl = s.recent_smart_ids()
    r = Recommender(s)
    res = r.recommend(limit=limit, algo=algo, library=library,
                      exclude_ids=excl, progress=progress,
                      ai_model=(s.recommend or {}).get("ai_model"))
    ids = [p["id"] for p in res.get("picks", [])]
    if ids:
        s.push_smart_round(ids)
    res["excluded"] = len(excl)
    res["round"] = (s.smart_history[-1]["round"] if s.smart_history else 0)
    return res


__all__ = ["Recommender", "recommend", "ai_status", "probe_ollama", "list_models",
           "resolve_model", "configured_model", "DIMS", "dim_cn",
           "OLLAMA_URL", "OLLAMA_HOST"]
