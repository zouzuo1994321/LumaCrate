# -*- coding: utf-8 -*-
"""检测类工具的「普通算法 / AI 算法」公共基座（v1.32.0，反馈 1）
==============================================================
用户原话：「重复检测 和 图像检测 和 演员检测 一样引入 普通算法和AI算法，来加快检测和
复核功能」。

「演员检测」与「标签优化」早就有了这套模式，做法是：
**普通算法先把候选缩到可复核的规模 → 本地离线 AI 逐条下判断 → AI 不可用时自动降级**。
本模块把其中**与业务无关**的部分抽出来，让「重复检测」「图像检测」直接复用，
免得同一个 Ollama 探测 / 提示词拼装 / JSON 抠取逻辑在四个地方各写一遍。

设计要点
--------
1. **只读、只出建议**：AI 复核结果一律只写进结果对象（`group.meta` / `prob["ai"]`），
   绝不触发任何删除、覆盖、落盘动作。用户不点，数据就不会变。
2. **绝不静默降级**：AI 不可用时把原因原文带回界面（`note`），让用户知道
   「这次是普通算法的结论」而不是以为 AI 跑过了。
3. **极速模式（fast）**：只复核「普通算法自己拿不准」的条目 —— 铁证级的重复组、
   结构性缺图本来就没什么可判的，让模型再跑一遍纯属浪费 token 与时间。
   真机上一轮 Ollama 推理可能从几百毫秒抖到几秒，全量复核会让整页卡好几分钟。
4. **本模块不依赖 Qt**：便于 `dev/` 下的探针在离屏环境直接单测。

⚠ 为什么不用 `recommend` 的 `ollama_reachable()`
------------------------------------------------
`recommend` 里有两个不同口径的探测函数：`ollama_reachable()` 只看 HTTP 端口通不通，
`probe_ollama()` 还要确认**选定的模型真的在本地**。复核类任务必须能跑推理，
所以这里一律用 `probe_ollama()` —— 端口开着但模型没 pull 的情况下，
用前者会「探测成功」然后每一条都超时失败，界面上看着像卡死。
"""
import json
import re

import applog

try:
    import recommend as rec_mod          # 复用「智能推荐」的 Ollama 探测与模型解析
except Exception:                        # pragma: no cover - 极端环境下别让调用方挂掉
    rec_mod = None

#: 询问模型时最多送进去多少条候选（再多模型也判不过来，还白等）
MAX_ITEMS = 30

#: 单条最高等待秒数。本地小模型判一条通常 < 3s，给 60s 是给「模型刚加载冷启动」留余量
TIMEOUT = 60


def ai_available(model=None):
    """本机 Ollama 是否可用。返回 `(可用?, 说明文案)`。

    说明文案**原文返回**给界面，不做「已自动降级」这种含糊表述 ——
    用户需要知道到底是没装、没启动、还是模型没 pull。
    """
    if rec_mod is None:
        return False, "AI 模块不可用（recommend 导入失败），已按普通算法给出结果。"
    try:
        use = rec_mod.probe_ollama(0.6, model)
    except Exception as e:
        return False, "探测本地 Ollama 失败：%s，已按普通算法给出结果。" % e
    if not use:
        return False, ("未检测到可用的本地 Ollama 模型，已自动降级为普通算法。"
                       "启动 Ollama 并执行「ollama pull qwen2.5:7b」后重试（全程不出网）。")
    return True, "本地 Ollama（%s）已就绪，全程离线。" % use


def model_name(model=None):
    """当前实际会用的模型名（解析不出来就原样返回）。"""
    if rec_mod is None:
        return str(model or "")
    try:
        return rec_mod.resolve_model(model)
    except Exception:
        return str(model or "")


def ask(prompt, model=None, timeout=TIMEOUT, num_predict=200):
    """问一次本地模型，返回原始文本；任何异常都返回 None（**绝不抛给调用方**）。

    `applog` 里记的日志前缀刻意带上模块名，方便在真机 app.log 里一眼分辨
    是哪个检测页把 Ollama 问崩的。
    """
    if rec_mod is None:
        return None
    body = json.dumps({
        "model": rec_mod.resolve_model(model),
        "prompt": prompt,
        "stream": False,
        # temperature 压到 0.1：这几类任务都要「复现同一个结论」，不需要发挥
        "options": {"temperature": 0.1, "num_predict": int(num_predict)},
    }).encode("utf-8")
    try:
        import urllib.request
        req = urllib.request.Request(rec_mod.OLLAMA_URL + "/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        return data.get("response") or ""
    except Exception as e:
        applog.log("AI 复核：调用本地模型失败：%s" % e, "error")
        return None


def parse_json(text):
    """从模型回复里抠出一个 JSON 对象；先找最外层 `{…}`，失败再退化为逐字段正则。

    小模型极爱在 JSON 前后写「好的，我的判断是：」，所以不能直接 `json.loads`。
    """
    if not text:
        return None
    s = str(text)
    i, j = s.find("{"), s.rfind("}")
    if 0 <= i < j:
        try:
            d = json.loads(s[i:j + 1])
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    return None


def parse_bool(text, keys=("same", "duplicate", "broken", "match")):
    """从回复里抠出布尔判定（JSON 优先，退化到「关键词 + 是/否」）。"""
    d = parse_json(text)
    if isinstance(d, dict):
        for k in keys:
            v = d.get(k)
            if isinstance(v, bool):
                return v
            if isinstance(v, str) and v.strip().lower() in ("true", "yes", "1", "是"):
                return True
            if isinstance(v, str) and v.strip().lower() in ("false", "no", "0", "否", "不是"):
                return False
    m = re.search(r"(?:same|duplicate|同一|重复|是同一部)\D{0,8}(true|false|yes|no|是|不是)",
                  str(text or ""), re.I)
    if m:
        return m.group(1).lower() in ("true", "yes", "是")
    return None


def confidence_of(text, default="中"):
    """抠置信度（高/中/低）。模型不给就用 `default`。"""
    d = parse_json(text)
    if isinstance(d, dict):
        c = str(d.get("confidence") or "").strip()
        if c[:1] in ("高", "中", "低"):
            return c[:1]
        if c.lower() in ("high", "medium", "low"):
            return {"high": "高", "medium": "中", "low": "低"}[c.lower()]
    m = re.search(r"(?:confidence|置信度)\D{0,6}(高|中|低)", str(text or ""))
    if m:
        return m.group(1)
    return default


def reason_of(text, limit=60):
    """抠一句人话理由（超长就截断）。"""
    d = parse_json(text)
    if isinstance(d, dict):
        r = str(d.get("reason") or d.get("why") or "").strip()
        if r:
            return r[:limit]
    return ""


def review_batch(kind, items, build_prompt, apply_fn, model=None,
                 fast=False, fast_filter=None, progress=None, stop=None,
                 limit=MAX_ITEMS):
    """通用复核循环 —— 四个检测页共用的一段「逐个问 AI 并把结论写回」。

    :param kind: 日志/进度里显示的名字（如「重复检测」）
    :param items: 待复核对象列表
    :param build_prompt: `f(item) -> prompt 字符串`，或 `None` 表示 item 自带 `prompt`
    :param apply_fn: `f(item, verdict_dict)`，把判定写回 item（调用方自己决定写哪）
    :param fast: 极速模式，只复核 `fast_filter(item)` 为真的条目
    :param fast_filter: `f(item) -> bool`；`fast=True` 但没给时视为全部复核
    :return: `dict(ai, model, note, done, failed, skipped, jobs, fast)`

    这个函数的**唯一职责**就是把「探测 → 过滤 → 逐条问 → 写回 → 统计」串起来，
    业务语义全部由调用方通过 `build_prompt` / `apply_fn` 注入。
    """
    ok, note = ai_available(model)
    out = {"ai": bool(ok), "model": "", "note": note, "done": 0, "failed": 0,
           "skipped": 0, "jobs": 0, "fast": bool(fast), "kind": str(kind or "")}
    if not ok:
        return out
    out["model"] = model_name(model)

    pool = list(items or [])
    if fast and fast_filter is not None:
        picked = [it for it in pool if fast_filter(it)]
        out["skipped"] = len(pool) - len(picked)
        pool = picked
    pool = pool[:limit]
    out["jobs"] = len(pool)

    for i, it in enumerate(pool):
        if stop and stop():
            out["note"] = (out["note"] + "（已被用户中止，剩余 %d 条未复核）"
                           % (len(pool) - i))
            break
        if progress:
            progress(i, len(pool), "%s：AI 复核中… %d / %d" % (kind, i + 1, len(pool)))
        prompt = build_prompt(it) if callable(build_prompt) else str(it.get("prompt") or "")
        if not prompt:
            out["failed"] += 1
            continue
        text = ask(prompt, model)
        if not text:
            out["failed"] += 1
            continue
        try:
            apply_fn(it, text)
            out["done"] += 1
        except Exception as e:
            applog.log("%s：写回 AI 判定失败：%s" % (kind, e), "error")
            out["failed"] += 1
    return out


# ---------------------------------------------------------------------------
# 三个检测页各自的「判定 → 建议」包装
# ---------------------------------------------------------------------------
#: 重复检测的建议文案（AI 只是**建议**，绝不代劳删文件）
DUP_KEEP = "保留其一"
DUP_ALL = "全部保留"
DUP_MANUAL = "需人工核对"

#: 图像检测的建议文案
IMG_REPLACE = "建议替换"
IMG_IGNORE = "可忽略"
IMG_MANUAL = "需人工核对"


def _fmt_size(n):
    try:
        n = float(n or 0)
    except Exception:
        return "—"
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return ("%.0f %s" % (n, u)) if u == "B" else ("%.2f %s" % (n, u))
        n /= 1024.0
    return "—"


def dedupe_prompt(group_info):
    """给「重复检测」一组候选拼提示词。

    ⚠ 刻意**不送完整路径**：那是用户隐私最重的部分（盘符 + 目录名 + 番号）。
    只送「体积 / 时长 / 画质 / 是否同目录 / 目录数量」，足够判断是不是同一部片子。
    """
    lines = []
    for i, m in enumerate(group_info.get("members") or [], 1):
        bits = ["体积 %s" % _fmt_size(m.get("size"))]
        if m.get("duration"):
            bits.append("时长 %s" % m["duration"])
        if m.get("resolution"):
            bits.append("画质 %s" % m["resolution"])
        if m.get("folder_alias"):
            bits.append("位于目录「%s」" % m["folder_alias"])
        lines.append("%d. %s" % (i, "，".join(bits)))
    label = group_info.get("label") or ""
    safe_label = group_info.get("label_masked") or "（标识已隐去）"
    return (
        "你是影视库整理助手。下面是一个本地影视库里**疑似重复**的一组影片文件。\n"
        "判定依据是「番号 / 标题+年份」相同，但文件分散在不同目录。\n"
        "请判断它们是不是**同一部片子的多份副本**（而不是分片/不同剪辑/不同画质版本）。\n"
        "注意：\n"
        "· 体积完全一致 → 极可能是同一文件的复制；\n"
        "· 体积差异大但时长一致 → 可能是不同画质版本，仍算重复但建议保留大的；\n"
        "· 时长明显不同 → 可能是不同版本（无码/加长），不算简单重复；\n"
        "· 同一目录下的多份通常是分片（CD1/CD2），不算重复。\n"
        "只输出一个 JSON 对象，不要任何解释文字：\n"
        '{"duplicate": true 或 false, "confidence": "高/中/低",'
        ' "keep": "保留哪一份（写序号）", "reason": "不超过 50 字的中文理由"}\n\n'
        "候选标识：%s（已隐去敏感内容，序号与下表对应）\n" % safe_label
        + "候选：\n" + "\n".join(lines) + "\n")


def imagedetect_prompt(prob):
    """给「图像检测」一条问题拼提示词。同样不送路径，只送槽位/状态/细节/尺寸。"""
    bits = ["槽位 %s" % (prob.get("slot_cn") or prob.get("slot") or ""),
            "问题 %s" % (prob.get("state_cn") or prob.get("state") or ""),
            "细节 %s" % (prob.get("detail") or "")]
    if prob.get("file_size"):
        bits.append("文件大小 %s" % _fmt_size(prob["file_size"]))
    if prob.get("dimension"):
        bits.append("尺寸 %s" % prob["dimension"])
    if prob.get("aspect"):
        bits.append("比例 %s" % prob["aspect"])
    return (
        "你是影视库图片整理助手。下面是一条本地影视库里的**图片问题记录**（影视海报/"
        "缩略图/背景图）。请判断这条记录**是否真的需要用户去处理**。\n"
        "注意：\n"
        "· 缺少海报 / 背景图 → 值得处理，海报墙会空一块；\n"
        "· 缺少缩略图 → 多数界面不显示，优先级低，可忽略；\n"
        "· 文件被截断（JPEG 缺结束标记 / PNG 缺 IEND）→ 真破损，必须处理；\n"
        "· 文件过小（< 1KB）→ 多半是占位图或下载失败的残片，值得处理；\n"
        "· 图上只有纯色或大片灰块（比例异常）→ 解码容错填灰，真破损。\n"
        "只输出一个 JSON 对象，不要任何解释文字：\n"
        '{"handle": true 或 false, "priority": "高/中/低",'
        ' "reason": "不超过 40 字的中文理由"}\n\n'
        "记录：%s\n" % "，".join(bits))


def verdict_to_dup(text):
    """把模型回复翻成重复检测用的 `(advice, confidence, reason)`。"""
    dup = parse_bool(text, keys=("duplicate", "same"))
    conf = confidence_of(text)
    why = reason_of(text)
    if dup is None:
        return DUP_MANUAL, conf, why
    if dup:
        return (DUP_KEEP if conf in ("高", "中") else DUP_MANUAL), conf, why
    return DUP_ALL, conf, why


def verdict_to_img(text):
    """把模型回复翻成图像检测用的 `(advice, confidence, reason)`。"""
    handle = parse_bool(text, keys=("handle", "broken", "need_fix", "same"))
    conf = confidence_of(text)
    why = reason_of(text)
    if handle is None:
        return IMG_MANUAL, conf, why
    return (IMG_REPLACE if handle else IMG_IGNORE), conf, why
