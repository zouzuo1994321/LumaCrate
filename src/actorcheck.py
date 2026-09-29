# -*- coding: utf-8 -*-
"""演员检测 —— 找出「不同艺名、其实是同一人」的候选（v1.31.0，反馈 3）
=====================================================================
用户原话：「运用 同 标签优化 一样的 普通算法+AI算法 可选的模式。将部分 虽然是不同
艺名但是可能是同一人的情况 进行检测，检测完毕后用户可以确认并进行关联。」

⚠ 为什么要先做数据探查（真机 5909 位演员，全程只读）
---------------------------------------------------
**第一层：单看 `romaji` 会得出完全相反的结论。**
`MOMOKANATSUKI` 下挂着 6 个名字、`NATSUMEREIKA` 下挂着 5 个，看着像「刮削把同一页的人
都写成同一个罗马音」的串号垃圾。把整组摊开才看清真相 —— 这 5 个人**生日、三围、身高、
事务所四项逐字相同**：

    夏目玲香 / 百瀬咲玖 / 岸杏南 / 白川みなみ / 明日香
      全部 = 生日 1983-10-17、尺寸 T152/B96(J)/W58/H87、身高 152cm、Life Promotion

nfo 里写的是不同艺名 → 索引建成了不同的 `people` 行，而刮削时**同一份资料被写进了每一行**。
`alias` 里那串「岸杏南、真木めぐみ、須藤美果、…」不是污染，**就是这位演员的旧艺名名单**。
反过来 `romaji = "LIST"` 的 48 个人画像各不相干，那才是真串号（按占位词整体排除）。

**第二层：画像本身也有样板值，不能无脑当证据。**
统计全库取值分布后发现 `身高` 只有 43 种取值（`160cm` 一个人人都在用）、`事务所` 219 种
（`T-POWERS` 313 人），`生日` 里 `1997-11-30` 27 人、`2006-01-01` 26 人 —— 真人不可能
这么撞。所以：**身高 / 事务所一律只做「矛盾检查」（差 ≥5cm 才算冲突），不做「一致证据」；
生日 / 尺寸取值在全库出现 > `MAX_VAL_OCC` 次就视为样板，直接弃用**。

**第三层：绝不能做传递闭包。**
按「任意高分成边 → 并查集」跑出来的第一个版本，把 30 个人并成了一簇（`Yagami Nanami`
通过一个样板生日 2006-01-01 + 共享小名「なみ」一路传染到 `辻井ほのか`(95 部)）。
所以最终改成 **「身份键分组」**：按 `姓名 → 罗马音` 优先级取一个键，**一个人只进一组、不跨键传递**。

**结论（写进 UI 文案的两条铁律）：**
1. 判据是「罗马音 + 画像交叉验证」，**不是**罗马音本身；
2. **绝不自动合并**。18 组罗马音相同但画像互相矛盾的（`千葉優花` 2005-03-18 vs
   `千葉ゆうか` 1996-11-13、`神菜美まい` vs `奏海麻衣` …）一律降级到「存疑」只提示。

本模块**不依赖 Qt**，页面（`ui_actorcheck`）只负责把结果摆出来。
"""
import json
import re
import time
import unicodedata
import urllib.request
from collections import Counter

import applog

try:
    import recommend as rec_mod          # 复用「智能推荐」的 Ollama 探测与模型解析
except Exception:                        # pragma: no cover - 极端环境下也别让本模块挂掉
    rec_mod = None

# ---------------------------------------------------------------------------
# 归一化
# ---------------------------------------------------------------------------
# 包装性尾巴：`横宮七海//`、`真木今日子 AV女優`、`及川うみさん`、`槙いずな【旧名】`
_WRAP_TAIL = re.compile(
    r"[（(【\[][^）)】\]]*[）)】\]]"          # （森野雫）/【旧名】
    r"|[／/|｜]{1,}"                          # //
    r"|[\s　]*(?:AV女優|ＡＶ女優|女優|さん|ちゃん|様)\s*$",
    re.I)
#: 别名里的分隔符（真机里既有日式顿号也有逗号/斜杠/中黒）
_ALIAS_SEP = re.compile(r"[、，,／/|｜;；・･]+")
#: 刮削占位垃圾（真机 x19 条 alias 就是这几个字）
_JUNK_TOKENS = {"データを編集", "データ編集", "編集", "不明", "なし", "無し",
                "n/a", "na", "none", "null", "-", "--", "?", "？", "未設定"}
#: 罗马音占位词 —— 真机里 48 位演员的 romaji 字面就是 `LIST`，画像各不相干
_ROM_PLACEHOLDER = {"LIST", "N/A", "NA", "UNKNOWN", "NONE", "NULL", "XXX",
                    "AAAA", "TEST", "AAA", "女性名", "名前"}


def norm_key(s) -> str:
    """比较用的归一化键：NFKC（全角→半角、大小写无关）+ 只保留字母数字与假名汉字。

    这样 `MINAMO` / `minamo`、`ミランダ·みゆ` / `ミランダ・みゆ`、
    `りか 22歳 大学生` / `りか22歳大学生`、`＠Alinya` / `@Alinya`、`横宮七海` / `横宮七海//`
    都能对上。
    """
    s = unicodedata.normalize("NFKC", str(s or ""))
    return "".join(ch for ch in s.upper() if ch.isalnum())


def strip_wrap(s) -> str:
    """剥掉包装性后缀后再归一化（`川上ゆう（森野雫）` → 川上ゆう）。"""
    t = unicodedata.normalize("NFKC", str(s or ""))
    for _ in range(3):
        new = _WRAP_TAIL.sub("", t).strip()
        if new == t:
            break
        t = new
    return norm_key(t)


def paren_alias(s) -> list:
    """把姓名/别名里括号包着的内容当**另外的艺名**抠出来（`川上ゆう（森野雫）`）。"""
    t = unicodedata.normalize("NFKC", str(s or ""))
    out = []
    for m in re.finditer(r"[（(【\[]([^）)】\]]{2,40})[）)】\]]", t):
        for part in _ALIAS_SEP.split(m.group(1)):
            part = part.strip()
            if part and not is_junk_token(part):
                out.append(part)
    return out


def is_junk_token(t) -> bool:
    """别名 token 是不是垃圾（占位文案 / 太短 / 纯符号 / 明显是一句话）。"""
    t = str(t or "").strip()
    if not t or len(t) < 2:
        return True
    if t.lower() in _JUNK_TOKENS:
        return True
    if any(k in t for k in ("編集", "データ", "プロフィール", "サイズ")):
        return True
    if not norm_key(t):
        return True
    return False


def split_aliases(raw) -> list:
    """拆别名串。**整串名单也照拆** —— 真机里那串「岸杏南、真木めぐみ、…」就是
    这位演员的旧艺名列表，正是最有价值的信号（探查后改过一次口径，见模块头注释）。"""
    out = []
    for part in _ALIAS_SEP.split(unicodedata.normalize("NFKC", str(raw or ""))):
        part = part.strip()
        if part and not is_junk_token(part):
            out.append(part)
    return out


# ---------------------------------------------------------------------------
# 人物画像
# ---------------------------------------------------------------------------
def parse_meta(raw) -> dict:
    """解析 `people.meta`。老库里有非法 JSON（被截断 / 未转义引号）→ 尽力抠键值对。

    这里不复用 `main_window._parse_meta`：`main_window → ui_settings → ui_actorcheck
    → actorcheck` 会绕成循环导入，所以检测层自带一份（口径与那边一致）。
    """
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        d = json.loads(raw)
        return d if isinstance(d, dict) else {}
    except Exception:
        pass
    out = {}
    for m in re.finditer(r'"([^"]{1,24})"\s*:\s*"([^"]*)(?:"|$)', str(raw)):
        out.setdefault(m.group(1), m.group(2))
    return out


def profile_of(person) -> dict:
    """取刮削画像四项（生日 / 尺寸 / 身高 / 事务所）。"""
    meta = parse_meta(person.get("meta"))
    return {
        "生日": str(person.get("birthday") or "").strip(),
        "尺寸": str(meta.get("尺寸") or "").strip(),
        "身高": str(meta.get("身高") or "").strip(),
        "事务所": str(meta.get("事务所") or "").strip(),
    }


def describe(person, occ=None) -> dict:
    """把一行 people 摊成检测需要的形状。

    :param occ: 取值频次表（`_value_counts` 的产物），用来判定「样板值」；
                为 None 时退化为「不判样板」（冒烟/单测用）。
    """
    name = str(person.get("name") or "").strip()
    rom = norm_key(person.get("romaji"))
    rom_placeholder = bool(rom) and rom in _ROM_PLACEHOLDER
    alias_raw = str(person.get("alias") or "").strip()
    aliases = split_aliases(alias_raw) + paren_alias(name)
    if rom_placeholder:
        rom = ""
    prof = profile_of(person)
    try:
        works = int(person.get("works") or 0)
    except (TypeError, ValueError):
        works = 0
    # 「可信证据」= 生日 / 尺寸里**没有被刮削滥用**的分量。身高/事务所基数太低，
    # 只做矛盾检查，永不当一致证据（见模块头注释第二层）。
    ev = {}
    for k in ("生日", "尺寸"):
        v = prof[k]
        if v and (occ is None or occ.get((k, v), 0) <= MAX_VAL_OCC):
            ev[k] = v
    return {
        "id": int(person.get("id") or 0),
        "name": name,
        "works": works,
        "alias_raw": alias_raw,
        "aliases": aliases,
        "romaji": str(person.get("romaji") or "").strip(),
        "rom_key": rom,
        "rom_placeholder": rom_placeholder,
        "prof": prof,
        "prof_n": sum(1 for v in prof.values() if v),
        "ev": ev,
        "ev_n": len(ev),
        "name_key": norm_key(name),
        "name_bare": strip_wrap(name),
        "photo": str(person.get("photo_path") or person.get("thumb") or "").strip(),
        "status": str(person.get("status") or "").strip(),
    }


def _value_counts(items) -> dict:
    """统计 (字段, 取值) 的全库出现次数 —— 用来识别刮削样板值。"""
    from collections import Counter
    c = Counter()
    for x in items:
        for k, v in x["prof"].items():
            if v:
                c[(k, v)] += 1
    return c


# ---------------------------------------------------------------------------
# 阈值与打分
# ---------------------------------------------------------------------------
MAX_VAL_OCC = 4         # 生日 / 尺寸取值出现次数 > 此值 → 刮削样板，不作证据
MAX_ROM_GROUP = 12      # 同罗马音组人数 > 此值 → 判为串号，不自动成簇（真机 LIST 组 48 人）
MAX_GROUP = 24          # 兜底：任何一簇都不超过这么多人
HEIGHT_TOL = 5          # 身高相差 ≥ 此值（cm）视为矛盾

S_ROM_EV2 = 96          # 罗马音同 + ≥2 项可信资料一致
S_ROM_EV1 = 88          # 罗马音同 + 1 项可信资料一致
S_NAME_BARE = 84        # 剥包装后姓名完全相同
S_NAME_KEY = 80         # 归一化姓名完全相同（大小写 / 全角 / 空格差异）
S_ROM_NOPROF = 76       # 罗马音同 + 双方都没有可比对的资料
S_ALIAS = 72            # 别名 token 命中对方主名
S_ROM_ONE_SIDE = 70     # 罗马音同 + 只有一方有资料可比对
S_ROM_CONFLICT = 46     # 罗马音同但资料互相矛盾 → 存疑
S_ROM_OVERSIZE = 40     # 罗马音同但同组人数离谱 → 存疑
S_BIRTH = 18            # 生日相同（只能凑分，不单独成立）
S_SHARED_ALIAS = 10     # 有共同别名（同理，只凑分）
S_NAMEPART = 16         # 姓名前后缀包含（同理，只凑分）

SUSPECT_MIN = 18        # ≥ 此分才有资格进「存疑」列表
TIERS = ((90, "铁证"), (80, "很高"), (70, "高"), (46, "中"), (0, "低"))


def tier_of(score) -> str:
    for lo, name in TIERS:
        if score >= lo:
            return name
    return "低"


def _height_num(s):
    m = re.search(r"(\d{3})", str(s or ""))
    return int(m.group(1)) if m else None


def conflicts(a, b) -> list:
    """双方刮削资料里**互相矛盾**的地方（矛盾意味着「不是同一个人」）。

    只有「双方都可信」的两个不同值才算矛盾 —— 样板值（`2006-01-01`、`T / B / W / H / S`）
    撞车不算。身高基数太低（全库只有 43 种取值）不能当一致证据，但差 ≥5cm 绝对是冲突。
    """
    out = []
    for k in ("生日", "尺寸"):
        va, vb = a["prof"][k], b["prof"][k]
        if not va or not vb or va == vb:
            continue
        if a["_occ"].get((k, va), 0) <= MAX_VAL_OCC and a["_occ"].get((k, vb), 0) <= MAX_VAL_OCC:
            out.append("%s 对不上（%s ≠ %s）" % (k, va, vb))
    ha, hb = _height_num(a["prof"]["身高"]), _height_num(b["prof"]["身高"])
    if ha and hb and abs(ha - hb) >= HEIGHT_TOL:
        out.append("身高相差 %dcm（%s ≠ %s）"
                   % (abs(ha - hb), a["prof"]["身高"], b["prof"]["身高"]))
    return out


def _pair_signals(a, b) -> tuple:
    """给一对人打分。返回 `(score, [理由…], 是否可进合并簇)`。"""
    reasons, score, hard = [], 0, False

    if a["rom_key"] and a["rom_key"] == b["rom_key"]:
        conf = conflicts(a, b)
        if conf:
            score = S_ROM_CONFLICT
            reasons.append("罗马音相同（%s），但刮削资料互相矛盾：%s → 很可能是同名不同人"
                           % (a["romaji"], "；".join(conf[:2])))
        else:
            same = sorted(k for k in a["ev"] if a["ev"].get(k) == b["ev"].get(k))
            if len(same) >= 2:
                score, hard = S_ROM_EV2, True
                reasons.append("罗马音相同（%s），且 %d 项刮削资料一致（%s）"
                               % (a["romaji"], len(same),
                                  "、".join(a["ev"][k] for k in same)))
            elif len(same) == 1:
                score, hard = S_ROM_EV1, True
                reasons.append("罗马音相同（%s），且%s一致（%s）"
                               % (a["romaji"], same[0], a["ev"][same[0]]))
            elif a["ev_n"] == 0 and b["ev_n"] == 0:
                score, hard = S_ROM_NOPROF, True
                # 资料其实有，只是全是「样板值」（同值在全库被大量复用）。此时样板值
                # **仍然相同**这件事本身有信息量：说明同一份刮削资料被写进了多行。
                same_boiler = sorted(k for k in a["prof"]
                                     if a["prof"][k] and a["prof"][k] == b["prof"][k])
                if same_boiler:
                    reasons.append(
                        "罗马音相同（%s），且两者被复用的样板资料也一致（%s）→ "
                        "同一份刮削资料被写进了多行" % (
                            a["romaji"], "；".join(a["prof"][k] for k in same_boiler[:3])))
                else:
                    reasons.append("罗马音相同（%s），双方都没有可比对的刮削资料" % a["romaji"])
            else:
                score, hard = S_ROM_ONE_SIDE, True
                richer = a if a["ev_n"] >= b["ev_n"] else b
                reasons.append("罗马音相同（%s）；%s有资料（%s），另一方没有 → 无从证伪"
                               % (a["romaji"], richer["name"],
                                  "、".join(richer["ev"].values())))

    if a["name_bare"] and a["name_bare"] == b["name_bare"]:
        if a["name_key"] != b["name_key"]:
            score, hard = max(score, S_NAME_BARE), True
            reasons.append("姓名去掉包装后缀后完全相同（%s ↔ %s）" % (a["name"], b["name"]))
        else:
            score, hard = max(score, S_NAME_KEY), True
            reasons.append("姓名完全相同（仅大小写 / 全半角 / 空格差异）")

    hit_ab = norm_key(a["name"]) in {norm_key(t) for t in b["aliases"]}
    hit_ba = norm_key(b["name"]) in {norm_key(t) for t in a["aliases"]}
    if hit_ab or hit_ba:
        who, other = (b, a) if hit_ab else (a, b)
        score, hard = max(score, S_ALIAS), True
        reasons.append("「%s」的别名里写着「%s」" % (who["name"], other["name"]))
    else:
        shared = sorted(({norm_key(a["name"])} | {norm_key(t) for t in a["aliases"]})
                        & ({norm_key(b["name"])} | {norm_key(t) for t in b["aliases"]})
                        - {norm_key(a["name"]), norm_key(b["name"])})
        if shared and score:
            score += S_SHARED_ALIAS
            reasons.append("双方有共同别名：%s" % "、".join(shared[:3]))

    if score:                       # 弱信号只做「佐证」，不单独成立
        if a["prof"]["生日"] and a["prof"]["生日"] == b["prof"]["生日"]:
            score += S_BIRTH
            reasons.append("生日相同（%s）" % a["prof"]["生日"])
        na, nb = a["name_bare"], b["name_bare"]
        if na and nb and na != nb:
            short, long_ = sorted((na, nb), key=len)
            if len(short) >= 3 and (long_.startswith(short) or long_.endswith(short)):
                score += S_NAMEPART
                reasons.append("姓名互相包含（%s ⊂ %s）" % (short, long_))
    return min(100, score), reasons, hard


# ---------------------------------------------------------------------------
# 检测（普通算法）
# ---------------------------------------------------------------------------
def detect(people, progress=None, stop=None, min_works=0) -> dict:
    """普通算法：全表 →「建议合并」簇 +「存疑」对。

    分三步（刻意**不做传递闭包**，见模块头注释第三层）：
      1. 算出每个人的**身份键**：剥包装姓名 → 归一化姓名 → 罗马音（附可信资料）；
      2. 按「组越大越优先」贪心分配 —— 一个人只进一个簇，避免 A-B-C 传染成巨簇；
      3. 罗马音相同但对不上 / 同组人数离谱 / 生日相同 / 姓名包含的，进「存疑」只提示。

    :param people: `database.people_for_match()` 的行
    :param progress: 回调 (done, total, msg)
    :param stop: 回调 → True 表示用户中止
    """
    t0 = time.time()
    raw_people = list(people or [])
    # 先算全库取值频次，再建画像：样板值判定需要「全库视野」
    occ = _value_counts([{"prof": profile_of(p)} for p in raw_people])
    items = [describe(p, occ) for p in raw_people]
    for x in items:
        x["_occ"] = occ
    skipped_placeholder = sum(1 for x in items if x["rom_placeholder"])
    if min_works > 0:
        items = [x for x in items if x["works"] >= int(min_works)]
    total = len(items)
    by_id = {x["id"]: x for x in items}
    if progress:
        progress(0, 1, "正在建立比对索引…（%s 位演员）" % format(total, ","))

    # ---- 1) 收集候选身份键 ----
    key_members = {}          # ("bare"/"key"/"rom", value) -> [id…]
    for x in items:
        if x["name_bare"]:
            key_members.setdefault(("bare", x["name_bare"]), []).append(x["id"])
        if x["name_key"]:
            key_members.setdefault(("key", x["name_key"]), []).append(x["id"])
        if x["rom_key"]:
            key_members.setdefault(("rom", x["rom_key"]), []).append(x["id"])

    # 罗马音组人数离谱的（真机 LIST 组 48 人）→ 不给成簇，改走存疑
    oversized = {value for (kind, value), ids in key_members.items()
                 if kind == "rom" and len(ids) > MAX_ROM_GROUP}

    # ---- 2) 冲突拆分 + 贪心分配（一个人只进一簇，绝不跨键传递）----
    cand = []
    for (kind, value), ids in key_members.items():
        if len(ids) < 2 or (kind == "rom" and value in oversized):
            continue
        for sub in _split_by_conflict(ids, by_id):
            if len(sub) >= 2:
                cand.append((len(sub), {"bare": 3, "key": 2, "rom": 1}[kind],
                             kind, value, sub))
    cand.sort(key=lambda t: (-t[0], -t[1]))

    assigned = {}
    for size, _pri, kind, value, ids in cand:
        free = [i for i in ids if i not in assigned]
        if len(free) < 2:
            continue
        if len(free) > MAX_GROUP:
            free = free[:MAX_GROUP]
        gid = max(assigned.values() or [0]) + 1
        for i in free:
            assigned[i] = gid

    groups = {}
    for pid, gid in assigned.items():
        groups.setdefault(gid, []).append(pid)

    # ---- 3) 组内两两打分 ----
    pairs = {}

    def score_pair(ia, ib):
        key = (ia, ib) if ia < ib else (ib, ia)
        if key not in pairs:
            pairs[key] = list(_pair_signals(by_id[key[0]], by_id[key[1]]))
        return pairs[key]

    for gid, ids in groups.items():
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                score_pair(ids[i], ids[j])

    # ---- 4) 别名互指但没被上一步分到一组的（罗马音缺失那类）→ 补一对一的小簇 ----
    by_namekey = {}
    for x in items:
        if x["name_key"]:
            by_namekey.setdefault(x["name_key"], []).append(x["id"])
    for x in items:
        for t in x["aliases"]:
            k = norm_key(t)
            if not k or k == x["name_key"]:
                continue
            for yid in by_namekey.get(k, ()):
                if yid == x["id"]:
                    continue
                if x["id"] in assigned or yid in assigned:
                    continue
                s, _rs, hard = score_pair(x["id"], yid)
                if hard and s >= S_ALIAS:
                    gid = max(assigned.values() or [0]) + 1
                    groups[gid] = [x["id"], yid]
                    assigned[x["id"]] = assigned[yid] = gid

    if progress:
        progress(0, 1, "正在整理候选…（%s 对）" % format(len(pairs), ","))
    if stop and stop():
        raise KeyboardInterrupt

    # ---- 5) 建簇 ----
    clusters = []
    for gid, ids in groups.items():
        ids = sorted(ids)
        sids = set(ids)
        edges = [(k, v) for k, v in pairs.items() if k[0] in sids and k[1] in sids]
        if not edges:
            continue
        best = max(e[1][0] for e in edges)
        score = min(100, best + (4 if len(ids) >= 4 else (2 if len(ids) >= 3 else 0)))
        reasons = []
        for _k, v in sorted(edges, key=lambda x: -x[1][0]):
            for r in v[1]:
                if r not in reasons:
                    reasons.append(r)
        members = [by_id[i] for i in ids]
        keep = sorted(members, key=lambda m: (-m["works"], not m["photo"], m["id"]))[0]
        conflict_msgs = []
        for i in ids[1:]:
            for c in conflicts(by_id[ids[0]], by_id[i]):
                if c not in conflict_msgs:
                    conflict_msgs.append(c)
        clusters.append({
            "score": score, "tier": tier_of(score), "ids": ids, "members": members,
            "reasons": reasons[:6], "keep_id": keep["id"], "keep_name": keep["name"],
            "total_works": sum(m["works"] for m in members),
            "alias_union": _alias_union(members),
            "conflicts": conflict_msgs,
            "profile_consistent": not conflict_msgs,
        })
    clusters.sort(key=lambda c: (-c["score"], -len(c["ids"]), c["keep_name"]))

    # ---- 6) 存疑：只提示，不给合并按钮 ----
    suspects, seen = [], set()

    def add_suspect(ia, ib, score, reasons):
        key = (ia, ib) if ia < ib else (ib, ia)
        if key in seen:
            return
        seen.add(key)
        suspects.append({"score": score, "tier": "存疑", "reasons": reasons[:4],
                         "a": by_id[key[0]], "b": by_id[key[1]]})

    # ① 罗马音相同但对不上 / 同组人数离谱
    rom_index = {}
    for x in items:
        if x["rom_key"]:
            rom_index.setdefault(x["rom_key"], []).append(x["id"])
    for rom, ids in rom_index.items():
        if len(ids) < 2:
            continue
        big = rom in oversized
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                s, rs, _h = score_pair(ids[i], ids[j])
                if big:
                    add_suspect(ids[i], ids[j], S_ROM_OVERSIZE,
                                ["罗马音相同（%s），但同组有 %d 人 → 疑似刮削串号，"
                                 "请逐个核对" % (by_id[ids[i]]["romaji"] or rom, len(ids))]
                                + rs[:2])
                elif SUSPECT_MIN <= s < S_NAME_KEY:
                    add_suspect(ids[i], ids[j], s, rs)
    # ② 已打完分但没能进同一簇的（生日相同 / 姓名包含这类弱证据）
    for (ia, ib), (_s, _rs, _h) in pairs.items():
        if assigned.get(ia) is not None and assigned.get(ia) == assigned.get(ib):
            continue
        s, rs, _h2 = score_pair(ia, ib)
        if SUSPECT_MIN <= s < S_NAME_KEY:
            add_suspect(ia, ib, s, rs)
    suspects.sort(key=lambda x: (-x["score"], x["a"]["name"]))

    elapsed = round(time.time() - t0, 2)
    return {
        "scanned": total, "pairs": len(pairs), "clusters": clusters,
        "suspects": suspects, "elapsed": elapsed,
        "skipped_placeholder": skipped_placeholder,
        "boilerplate_values": sum(1 for _k, v in occ.items() if v > MAX_VAL_OCC),
        "merge_people": sum(len(c["ids"]) - 1 for c in clusters),
    }


def _split_by_conflict(ids, by_id) -> list:
    """把一个身份键下的成员再按「资料是否互相矛盾」切开。

    关键一步：`romaji = CHIBAYUUKA` 的两个人（`千葉優花` 2005-03-18 / `千葉ゆうか`
    1996-11-13）名字不一样、资料还打架 —— 他们**不能**因为罗马音撞车就并成一簇。
    同名组同理适用（两人同名但生日/三围都对不上 → 只是重名）。
    """
    ids = sorted(ids)
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if conflicts(by_id[ids[i]], by_id[ids[j]]):
                continue
            ri, rj = find(ids[i]), find(ids[j])
            if ri != rj:
                parent[rj] = ri
    out = {}
    for i in ids:
        out.setdefault(find(i), []).append(i)
    return list(out.values())


def _alias_union(members) -> str:
    """簇内所有名字 + 旧别名合起来，作为合并后写进 `alias` 的建议值。"""
    out, seen = [], set()
    for m in members:
        for t in [m["name"]] + list(m["aliases"]):
            t = str(t).strip()
            k = norm_key(t)
            if t and k and k not in seen:
                seen.add(k)
                out.append(t)
    return "、".join(out[:30])


# ---------------------------------------------------------------------------
# AI 算法（本地 Ollama 复核）
# ---------------------------------------------------------------------------
def ai_available(model=None):
    """本机 Ollama 是否可用。返回 (可用?, 说明文案)。

    v1.32.0：`ollama_reachable()` 与 `probe_ollama()` 口径不同 —— 前者只管
    HTTP 端口通不通，后者还要确认模型真的在本地。复核类任务用后者（必须能跑推理），
    存在性判断用前者。这里统一用 `probe_ollama`，并把失败原因原样带出来。
    """
    if rec_mod is None:
        return False, "AI 模块不可用（recommend 导入失败），已按普通算法给出结果。"
    try:
        use = rec_mod.probe_ollama(0.6, model)
    except Exception as e:
        return False, "探测本地 Ollama 失败：%s" % e
    if not use:
        return False, ("未检测到可用的本地 Ollama 模型，已自动降级为普通算法。"
                       "启动 Ollama 并执行「ollama pull qwen2.5:7b」后重试（全程不出网）。")
    return True, "本地 Ollama（%s）已就绪，全程离线。" % use


def _ollama_json(prompt, model=None, timeout=90):
    if rec_mod is None:
        return None
    body = json.dumps({
        "model": rec_mod.resolve_model(model),
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 200},
    }).encode("utf-8")
    try:
        req = urllib.request.Request(rec_mod.OLLAMA_URL + "/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        return data.get("response") or ""
    except Exception as e:
        applog.log(f"演员检测：AI 调用失败：{e}", "error")
        return None


def _parse_verdict(text):
    """从模型回复里抠出 JSON 判定。模型常带前后废话 → 先找 {…}，再退化为正则。"""
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
    out = {}
    m = re.search(r"(?:same|同一人)\D{0,6}(true|false|yes|no|是|不是)", s, re.I)
    if m:
        out["same"] = m.group(1).lower() in ("true", "yes", "是")
    m = re.search(r"(?:confidence|置信度)\D{0,6}(高|中|低)", s)
    if m:
        out["confidence"] = m.group(1)
    m = re.search(r"(?:keep|保留)\D{0,10}[\"「]?([^\"」,\n]{1,20})", s, re.I)
    if m:
        out["keep"] = m.group(1).strip()
    return out or None


def ai_judge_group(names_info, model=None, timeout=90):
    """让本地模型判「这几个人是不是同一个人的不同艺名」，并建议保留哪一个。

    :param names_info: [(名字, 补充说明), …]
    :return: dict(same, keep, confidence, reason, raw) 或 None
    """
    lines = []
    for i, (nm, extra) in enumerate(names_info, 1):
        lines.append("%d. %s%s" % (i, nm, ("　（%s）" % extra) if extra else ""))
    prompt = (
        "你是演员资料核对助手。下面是一批**疑似同一个人的不同艺名**（来自本地影视库的"
        "演员表，资料由网站刮削而来）。请判断它们是不是同一个人的不同艺名 / 旧名。\n"
        "注意：日本业界演员常用多个艺名；同姓不等于同人；刮削数据可能有串号；"
        "生日与三围一致是强证据，互相矛盾则基本可判不同人。\n"
        "只输出一个 JSON 对象，不要任何解释文字：\n"
        '{"same": true 或 false, "confidence": "高/中/低", "keep": "资料最全的那个艺名",'
        ' "reason": "不超过 40 字的中文理由"}\n\n'
        "候选：\n" + "\n".join(lines) + "\n")
    text = _ollama_json(prompt, model, timeout)
    d = _parse_verdict(text)
    if not d:
        return None
    d["raw"] = (text or "")[:400]
    return d


def ai_review(result, model=None, max_clusters=25, max_suspects=15,
              fast=False, progress=None, stop=None):
    """AI 算法：在普通算法的候选之上，让本地模型逐个复核（**只改判定，不动数据**）。

    与「标签优化」同一套思路：普通算法负责把候选缩到可复核的规模，AI 逐条下判断。

    v1.32.0（反馈 1）：`fast=True` 开启**极速模式** —— 只复核「普通算法自己拿不准」
    的对象，也就是有冲突的簇与全部存疑对；铁证 / 很高的簇本来就没什么可判的，
    AI 再把它们跑一遍纯属浪费（模型一慢就从「偶尔卡几秒」变成「整页几分钟」）。
    """
    ok, note = ai_available(model)
    out = {"ai": ok, "model": "", "note": note, "done": 0, "failed": 0, "fast": bool(fast)}
    if not ok:
        return out
    try:
        out["model"] = rec_mod.resolve_model(model)
    except Exception:
        out["model"] = str(model or "")

    clusters = list(result.get("clusters", []))
    if fast:
        # 只留「有冲突 / 匹配度 < 80」的簇：这些才是 AI 真能改变结论的
        clusters = [c for c in clusters
                    if c.get("conflicts") or float(c.get("score") or 0) < 80]
    clusters = clusters[:max_clusters]
    suspects = list(result.get("suspects", []))[:max_suspects]
    jobs = [("cluster", c) for c in clusters] + [("suspect", s) for s in suspects]
    out["jobs"] = len(jobs)
    for i, (kind, obj) in enumerate(jobs):
        if stop and stop():
            break
        members = obj["members"] if kind == "cluster" else [obj["a"], obj["b"]]
        info = []
        for m in members:
            bits = []
            if m["prof"]["生日"]:
                bits.append("生日 " + m["prof"]["生日"])
            if m["prof"]["尺寸"]:
                bits.append("尺寸 " + m["prof"]["尺寸"])
            if m["prof"]["身高"]:
                bits.append("身高 " + m["prof"]["身高"])
            if m["prof"]["事务所"]:
                bits.append("事务所 " + m["prof"]["事务所"])
            bits.append("作品 %d 部" % m["works"])
            info.append((m["name"], "，".join(bits)))
        if progress:
            progress(i, len(jobs), "AI 复核中… %d / %d" % (i + 1, len(jobs)))
        d = ai_judge_group(info, model)
        if d is None:
            out["failed"] += 1
            continue
        obj["ai"] = d
        out["done"] += 1
    return out


# =====================================================================
# v1.33.0（反馈 1）：结果导出 / 导入
# ---------------------------------------------------------------------
# 真机 5909 位演员跑一次「演员检测」约 0.2~0.3 秒（普通算法）不算贵，但**AI 复核**
# 很贵：逐簇问本地模型，25 簇就要好几分钟。用户当天没复核完，导出成文件、明天导入
# 接着复核 —— 已复核过的簇带着 `ai` 结论一起回来，不必重问。
# 信封格式与 duplicates.py / imagedetect.py 完全一致。
# =====================================================================
EXPORT_FORMAT = 1


def _plain(m) -> object:
    """递归剥掉不可 JSON 化的临时字段。

    两个坑：① `_occ` 的键是 `(字段名, 值)` **元组** —— `json.dump` 报
    `TypeError: keys must be str, … not tuple`；② 元组可能藏在任意深度的容器里
    （簇自身的 `_occ`、成员里的、存疑两侧的），只剥一层不够。
    这里同时把 dict 的**非字符串键**统一转成字符串，把 tuple 转 list，保证
    `json.dump` 永远不炸。
    """
    if isinstance(m, dict):
        out = {}
        for k, v in m.items():
            if str(k).startswith("_"):
                continue
            out[k if isinstance(k, str) else str(k)] = _plain(v)
        return out
    if isinstance(m, (list, tuple)):
        return [_plain(x) for x in m]
    return m


def _plain_cluster(c: dict) -> dict:
    d = _plain(c)
    return d if isinstance(d, dict) else {}


def _plain_suspect(s: dict) -> dict:
    d = _plain(s)
    return d if isinstance(d, dict) else {}


def export_json(result: dict, path: str) -> str:
    """把 `detect()` 的结果（含 AI 复核结论）导出为 JSON。"""
    import os
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    res = dict(result or {})
    res["clusters"] = [_plain_cluster(c) for c in (res.get("clusters") or [])]
    res["suspects"] = [_plain_suspect(s) for s in (res.get("suspects") or [])]
    payload = {"_app": "LumaCrate", "_kind": "actorcheck",
               "_format": EXPORT_FORMAT, "result": res}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return path


def import_json(path: str) -> dict:
    """从 `export_json` 产出的文件恢复 `detect()` 的结果字典（v1.33.0 反馈 1）。

    兼容两代：带信封的新格式，以及直接 dump 结果字典的裸格式。
    """
    import os
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        raise ValueError("文件内容不是 JSON 对象")
    if "_kind" in raw:
        if raw.get("_kind") != "actorcheck":
            raise ValueError("这不是「演员检测」的结果文件（_kind=%r）" % raw.get("_kind"))
        if int(raw.get("_format") or 0) > EXPORT_FORMAT:
            raise ValueError("结果文件来自更新的版本（格式 %s），请升级软件后再导入"
                             % raw.get("_format"))
        data = raw.get("result") or {}
    else:
        data = raw
    if "clusters" not in data and "suspects" not in data:
        raise ValueError("文件里没有检测结果（缺 clusters / suspects）")
    # 补回 `_occ`：`describe()` 出来的成员上没有它也能正常显示（页面只读 prof/works/…），
    # 但 `ai_review` 与手动编辑会用到 —— 给个空表即退化到「不判样板」，安全。
    for c in (data.get("clusters") or []):
        for m in (c.get("members") or []):
            m.setdefault("_occ", {})
    for s in (data.get("suspects") or []):
        for side in ("a", "b"):
            if isinstance(s.get(side), dict):
                s[side].setdefault("_occ", {})
    data.setdefault("clusters", [])
    data.setdefault("suspects", [])
    for k, v in (("scanned", 0), ("pairs", 0), ("elapsed", 0.0),
                 ("skipped_placeholder", 0), ("boilerplate_values", 0),
                 ("merge_people", 0)):
        data.setdefault(k, v)
    return data
