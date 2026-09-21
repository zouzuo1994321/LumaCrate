# -*- coding: utf-8 -*-
"""标签优化（v1.25.0 反馈 4）
===========================
「工具箱 → 标签优化」：把 nfo 里的标签（`<genre>` 节点）**补全**，
并可按需把**日语标签转成中文**。作用范围：单一文件 / 一个文件夹 / 整个媒体库。

算法（与「智能推荐」同一套口径，用户可选）：

- **普通智能算法**：完全离线、零依赖 ——
  1. 内置「日语 → 中文」对照词典（`JA2ZH`，见文件底部 `_JA2ZH_PAIRS`）；
  2. 从**标题**里抽出词典命中的关键词（标题常写着「中出し」「巨乳」这类词，而标签是空的）；
  3. 从**全库标签共现**里补：与本文已有标签经常同时出现的标签（P(B|A) 高才采纳）；
  4. 把 nfo 的 `<studio>` / `<set>` 折成 `片商:` / `系列:` 伪标签（与库内既有约定一致）。
- **AI 智能算法**：在普通算法之上，把「标题 + 现有标签 + 简介」交给**本地 Ollama**，
  让它给出一组更贴合内容的中文标签（离线、不出网）；**不可用时静默降级**到普通算法。

安全约定（写的是用户磁盘上的 nfo 文件，必须稳妥）：

- **默认只预览不写入**；只有点「写入 nfo」才会改盘，且点之前会弹确认；
- 写入前把原文件另存为 `<文件名>.nfo.bak-<时间戳>`（可关闭）；
- **只改动 `<genre>` 节点**，其它内容（演员 / 评分 / 图片引用 / 简介 / 唯一 id…）原样保留；
- 写入成功后同步更新数据库里的 `media.genres`，界面立刻能看到新标签。

设计约束：本模块**不 import Qt**（纯计算 + 磁盘 IO），便于离屏冒烟与单独探针验证。
"""
import os
import re
import shutil
import time
import urllib.request
import json
from collections import Counter

import config as cfg
import database as db
import nfo_parser
import recommend as rec_mod

# 库内既有的伪标签前缀（`insight.split_tags` 与扫描器约定的写法）
PREFIXES = ("片商:", "发行:", "系列:", "导演:", "演员:", "标签:")
# 复用 nfo_parser 的技术标签正则，避免把 1080p / HDR10 / HEVC 当成内容标签
TECH_RE = nfo_parser._TECH_GENRE_RE


# ---------------------------------------------------------------------------
# 词典
# ---------------------------------------------------------------------------
_JA2ZH_PAIRS = """
# —— 玩法 / 题材 ——
単体作品=单体作品
単体=单体作品
専属=专属
企画=企划
ハメ撮り=自拍
痴女=痴女
中出し=中出
顔射=颜射
口内射精=口内射精
ぶっかけ=颜射
ごっくん=吞精
3P=3P
4P=4P
乱交=滥交
大乱交=滥交
素人=素人
人妻=人妻
若妻=少妇
熟女=熟女
美熟女=美熟女
美少女=美少女
美乳=美乳
巨乳=巨乳
爆乳=爆乳
微乳=贫乳
貧乳=贫乳
神乳=神乳
美尻=美臀
デカ尻=巨尻
美脚=美腿
長身=高个子
小柄=娇小
スレンダー=苗条
ぽっちゃり=微胖
パイパン=无毛
剛毛=浓毛
日焼け=晒痕
# —— 角色 / 服装 ——
制服=制服
女教師=女教师
教師=教师
家庭教師=家庭教师
ナース=护士
看護師=护士
医師=医生
女医=女医生
秘書=秘书
OL=OL
受付嬢=前台
キャビンアテンダント=空姐
メイド=女仆
巫女=巫女
レースクイーン=赛车女郎
アイドル=偶像
芸能人=艺人
モデル=模特
女子校生=女高中生
JK=JK
学園=学园
生徒=学生
教え子=学生
コスプレ=Cosplay
ランジェリー=内衣
水着=泳装
競泳水着=竞泳泳装
ブルマ=运动短裤
体操服=体操服
ナース服=护士服
# —— 关系 / 情境 ——
姉=姐姐
姉妹=姐妹
姉弟=姐弟
妹=妹妹
母=母亲
息子=儿子
親子=亲子
近親相姦=乱伦
義理=义理
幼馴染=青梅竹马
痴漢=痴汉
電車=电车
満員電車=满员电车
レイプ=强奸
調教=调教
縛り=捆绑
緊縛=紧缚
拘束=拘束
おもちゃ=玩物
バイブ=振动棒
電マ=按摩棒
アナル=肛交
フェラ=口交
パイズリ=乳交
手コキ=手交
足コキ=足交
素股=素股
潮吹き=潮吹
放尿=放尿
お漏らし=失禁
孕ませ=怀孕
妊婦=孕妇
母乳=母乳
寝取り=寝取
寝取られ=被寝取
浮気=出轨
不倫=不伦
略奪=掠夺
逆ナン=搭讪
ナンパ=搭讪
温泉=温泉
旅行=旅行
鬼畜=鬼畜
催眠=催眠
洗脳=洗脑
媚薬=媚药
催淫=催淫
時間停止=时间停止
透明人間=透明人
泥酔=泥醉
睡眠=睡眠
昏睡=昏睡
発情=发情
寸止め=寸止
大量=大量
黒人=黑人
外国人=外国人
白人=白人
五十路=五十路
還暦=花甲
高齢=高龄
# —— 企划 / 格式 ——
無修正=无码
独占配信=独家配信
配信限定=配信限定
ハイビジョン=高清
ベスト=精选
総集編=总集篇
大全集=大全集
ドキュメント=纪实
ドラマ=剧情
バラエティ=综艺
アニメ=动画
バーチャル=虚拟
主観=主观视角
一人称=第一人称
中国語字幕=中文字幕
字幕=字幕

# ===========================================================================
# v1.25.0 增补：对齐「用户库里真实在用的中文词表」+ 高频复合标签
# ---------------------------------------------------------------------------
# 每一条的目标词都是先在真机上统计过使用次数的；括号里的是库内现有频次。
# 目标词是库里已经在用的写法时，翻译结果会**直接并入既有标签**，而不是另造一个同义词，
# 否则词表会被撕成两半（「中出」22,545 次 vs「内射」0 次那种）。
# ===========================================================================

# —— 库内高频，必须用这个写法 ——
中出し系=中出
潮吹き系=潮吹
イラマチオ=深喉
汗だく=流汗
オモチャ=玩物
デカチン=巨根
デビュー作品=首次亮相
初撮り=首次亮相
ギャル=辣妹
美人=美女
美人妻=人妻
母乳=母乳
巨根物=巨根

# —— 人物称谓（「お姊さん」库里就有 298 次，整串也要能译） ——
お姉さん=姐姐
お姊さん=姐姐
姊=姐姐
お母さん=母亲
奥さん=人妻
奥様=人妻

# —— 复合标签（A·B）：整串收录，优先于拆分逻辑 ——
アクメ·オーガズム=绝顶高潮
キス·接吻=接吻
寝取り·寝取られ·ＮＴＲ=寝取
デカチン·巨根=巨根
淫乱·ハード系=淫乱真实
盗撮·のぞき=偷窥
パンスト·タイツ=连裤袜
看護婦·ナース=护士
看护妇·ナース=护士
放尿·お漏らし=放尿
調教・奴隶=调教
野外·露出=露出
貧乳·微乳=贫乳
姊·妹=姐妹
姐·妹=姐妹
エステ·マッサージ=美容院
マッサージ·リフレ=按摩
ローション·オイル=润滑油
キャバ嬢·风俗嬢=风俗娘
和服・丧服=和服

# —— 复合标签拆开后才认得的词根 ——
アクメ=绝顶
オーガズム=绝顶高潮
キス=接吻
盗撮=偷窥
のぞき=偷窥
パンスト=连裤袜
タイツ=连裤袜
看護婦=护士
エステ=美容院
マッサージ=按摩
リフレ=按摩
ローション=润滑油
オイル=润滑油
キャバ嬢=风俗娘
ハイクオリティ=高清
ハイクオリティVR=VR
ハイビジョンVR=VR
主觀=主观视角
一人称主観=第一人称

# —— 「无假名即中文」启发式的假阳性修正：这些「·」前后**两段都是日语汉字**，
#    整串收录才不会把「総集编 / 部活」当成中文释义直接留下来。
女优ベスト·総集编=总集篇
総集编=总集篇
総集編=总集篇
部活·マネージャー=社团活动
部活=社团活动
"""


def _build_map(pairs_text):
    """解析 `ja=zh` 行式词典，返回 (映射, 冲突键列表)。"""
    out, dup = {}, []
    for line in (pairs_text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if not k or not v:
            continue
        if k in out and out[k] != v:
            dup.append(k)
        if k == v:
            continue                     # 同名不需要翻译
        out[k] = v
    return out, dup


JA2ZH, JA2ZH_CONFLICTS = _build_map(_JA2ZH_PAIRS)


# 复合标签的分隔符：库里 `A·B` 形式有 331 个（キス·接吻 / デカチン·巨根 / 調教・奴隶…）
_COMPOUND_SEP = re.compile(r"[·・•‧/／]")
# 平假名 + 片假名。用于判断「这一段是不是还需要翻译」
_KANA_RE = re.compile(r"[\u3041-\u309f\u30a0-\u30ff]")


def has_kana(text) -> bool:
    """串里有没有假名 —— 没有的话本来就是中文/英文，不需要翻译。"""
    return bool(_KANA_RE.search(str(text or "")))


def to_zh(tag: str) -> str:
    """日语标签 → 中文（没收录 / 不需要翻译时返回空串）。

    v1.25.0：库里含假名的标签有 11,968 个，其中一大类是 `A·B` 的**复合标签**
    （キス·接吻、デカチン·巨根、寝取り·寝取られ·ＮＴＲ、パンスト·タイツ…）——
    这类标签有一半本来就附了中文释义。所以按三级来：
      1) 整串命中词典 → 直接返回（高频复合词都整串收录了）；
      2) 按 `·` / `・` / `•` / `/` 拆开，**有哪一段不含假名就用那一段**
         （那一段就是人工写好的中文释义，比机器翻译准）；
      3) 各段都还要译时，逐段查词典、用 `·` 拼回去（去重）。
    三级都不成 → 返回空串，调用方会保留原标签不动。
    """
    t = clean_tag(tag)
    if not t:
        return ""
    # ① 整串命中词典 → 直接返回。**这一步必须在 has_kana 之前**：
    #    词典里有大批「纯日语汉字」条目（単体作品 / 単体 / 専属 / 企画 / 大乱交 / 総集编…），
    #    它们一个假名都没有，可恰恰是用户库里最高频的一类
    #    （単体作品 真机上有 27,899 次）。先判 has_kana 会让这些词永远译不出来，
    #    而且返回空串时调用方会「原样保留」，界面上完全看不出异常。
    hit = JA2ZH.get(t)
    if hit:
        return hit
    # ② 没整串命中，才要求含假名 —— 免得把纯中文标签当成日语去拆/去译
    if not has_kana(t):
        return ""
    parts = [p.strip() for p in _COMPOUND_SEP.split(t) if p.strip()]
    if len(parts) < 2:
        return ""
    plain = [p for p in parts if not has_kana(p) and len(p) >= 2]
    if plain:
        # 「没假名」不等于「是中文」——「総集编」「部活」也是没有假名的日语汉字。
        # 所以先拿整段查一次词典，查得到就用词典（译得准），查不到才当它是中文释义。
        for p in sorted(plain, key=len, reverse=True):
            hit = JA2ZH.get(p)
            if hit:
                return hit
        return max(plain, key=len)[:40]
    zh = [JA2ZH.get(p, "") for p in parts]
    zh = [x for x in zh if x]
    return "·".join(dict.fromkeys(zh))[:40] if zh else ""


def clean_tag(tag) -> str:
    """规整一个标签：去空白 / 逗号 / 包裹引号，限长。"""
    t = str(tag if tag is not None else "").strip()
    t = t.strip(",，、;；|").strip()
    t = re.sub(r"\s+", " ", t)
    return t[:40]


def is_tech(tag: str) -> bool:
    return bool(TECH_RE.match(clean_tag(tag)))


def split_genres(genres):
    """`genres` 字符串 → (普通标签, 伪标签)。技术标签直接丢掉。"""
    plain, pref = [], []
    for raw in str(genres or "").split(","):
        t = clean_tag(raw)
        if not t or is_tech(t):
            continue
        (pref if t.startswith(PREFIXES) else plain).append(t)
    return plain, pref


def tags_from_title(title, translate=True, limit=12):
    """从标题里抽词典命中的关键词（标题常写着玩法词，而标签是空的）。"""
    t = str(title or "")
    if not t:
        return []
    out = []
    for ja, zh in JA2ZH.items():
        if ja and ja in t:
            out.append(zh if translate else ja)
            if len(out) >= limit:
                break
    return out


# ---------------------------------------------------------------------------
# 全库标签统计（共现）
# ---------------------------------------------------------------------------
def library_tag_stats(progress=None):
    """扫一遍索引，返回 (标签出现次数, {标签: Counter(同时出现的标签)})。

    数据源用 `db.media_for_insight()`（分析用投影，够用且省内存）。
    复杂度 O(作品数 × 标签数²)，4.8 万条实测 1~3 秒，结果在实例里缓存。
    """
    counts, co = Counter(), {}
    try:
        rows = db.media_for_insight()
    except Exception:
        return counts, co
    n = len(rows)
    for i, r in enumerate(rows):
        plain, _pref = split_genres(r.get("genres"))
        uniq = sorted(set(plain))
        for t in uniq:
            counts[t] += 1
        for t in uniq:
            c = co.get(t)
            if c is None:
                c = co[t] = Counter()
            for u in uniq:
                if u != t:
                    c[u] += 1
        if progress and i % 4000 == 0:
            progress(i, n, f"正在统计全库标签… {i:,}/{n:,}")
    return counts, co


def suggested_from_cooccur(seed_tags, co, min_ratio=0.35, min_count=3, limit=10):
    """与已有标签**经常同时出现**的标签（P(B|A) 够高才采纳）。"""
    cand = Counter()
    seeds = {clean_tag(t) for t in (seed_tags or []) if clean_tag(t)}
    for a in seeds:
        c = co.get(a)
        if not c:
            continue
        total = sum(c.values()) or 1
        for b, n in c.items():
            if b in seeds or is_tech(b) or b.startswith(PREFIXES):
                continue
            if n >= min_count and (n / total) >= min_ratio:
                cand[b] += n
    return [t for t, _ in cand.most_common(limit)]


# ---------------------------------------------------------------------------
# 本地 AI（Ollama）：结合标题 / 现有标签 / 简介 给中文标签
# ---------------------------------------------------------------------------
def ai_suggest(title, tags, plot="", model=None, timeout=45, limit=14):
    """让本地模型给一组中文标签（离线）。任何异常一律返回 []，绝不阻塞主流程。"""
    model = (model or "").strip() or (rec_mod.resolve_model()[0] or "")
    if not model:
        return []
    prompt = (
        "你是影片标签整理助手。请根据下面信息，给出 8~14 个**中文**标签"
        "（题材 / 玩法 / 场景 / 服装 / 人物类型）。\n"
        "只输出标签本身，用中文逗号分隔，不要解释、不要编号、不要重复已有标签。\n"
        "信息不足时宁可少给，也不要编造。\n\n"
        f"标题：{str(title or '')[:120]}\n"
        f"已有标签：{'、'.join(list(tags or [])[:30])}\n"
        f"简介：{str(plot or '')[:400]}\n")
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 220},
    }).encode("utf-8")
    try:
        req = urllib.request.Request(rec_mod.OLLAMA_URL + "/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        text = data.get("response") or ""
    except Exception:
        return []
    words = [clean_tag(w.strip(" 　·、,，.。;；:：\"'()（）[]【】"))
             for w in re.split(r"[,，、\n;；|/]", text)]
    out = []
    for w in words:
        if not w or len(w) > 20 or is_tech(w) or w in out:
            continue
        out.append(w)
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# 引擎
# ---------------------------------------------------------------------------
def nfo_for_video(video_path):
    """从一个视频文件定位同目录的 nfo（优先级与 scanner._resolve_nfo_for 一致）。"""
    p = str(video_path or "")
    if not p:
        return None
    stem = os.path.splitext(os.path.basename(p))[0].lower()
    folder = os.path.dirname(p)
    if not os.path.isdir(folder):
        return None
    cands = []
    if stem:
        cands.append(stem + ".nfo")
    folder_name = os.path.basename(os.path.normpath(folder)).lower()
    if folder_name:
        cands.append(folder_name + ".nfo")
    cands += ["movie.nfo", "tvshow.nfo"]
    try:
        entries = {e.lower(): e for e in os.listdir(folder)}
    except OSError:
        return None
    for c in cands:
        real = entries.get(c.lower())
        if real:
            full = os.path.join(folder, real)
            if os.path.isfile(full):
                return full
    return None


class TagOptimizer:
    """标签优化的执行体（不依赖 Qt）。"""

    def __init__(self, settings=None):
        self.s = settings or cfg.get_settings()
        self._counts = None
        self._co = None

    # ------------------------------------------------ 全库统计（懒加载 + 缓存）
    def ensure_stats(self, progress=None):
        if self._co is None:
            self._counts, self._co = library_tag_stats(progress)
        return self._counts, self._co

    # ------------------------------------------------ 目标收集
    def resolve_nfo(self, path):
        """把用户给的路径变成 nfo 绝对路径（可能是 nfo 本身或视频文件）。"""
        p = str(path or "").strip().strip('"')
        if not p:
            return None
        p = os.path.abspath(p)
        if os.path.isfile(p):
            if p.lower().endswith(".nfo"):
                return p
            return nfo_for_video(p)
        return None

    def collect(self, scope, value, progress=None):
        """按范围列出要处理的 nfo（去重、稳定排序）。"""
        scope = str(scope or "file")
        out, seen = [], set()

        def add(full):
            key = os.path.normcase(os.path.abspath(full))
            if key in seen:
                return
            seen.add(key)
            out.append(os.path.abspath(full))

        if scope == "file":
            nfo = self.resolve_nfo(value)
            if nfo and os.path.isfile(nfo):
                add(nfo)
        else:
            roots = []
            if scope == "folder":
                v = str(value or "").strip().strip('"')
                if v and os.path.isdir(v):
                    roots = [v]
            elif scope == "library":
                lib = self.s.library(str(value or "")) or {}
                roots = [p for p in (lib.get("paths") or []) if p and os.path.isdir(p)]
            for root in roots:
                for dirpath, _dirnames, filenames in os.walk(root):
                    for fn in filenames:
                        if fn.lower().endswith(".nfo") and not _is_backup_name(fn):
                            add(os.path.join(dirpath, fn))
                    if progress:
                        progress(len(out), 0, f"正在扫描目录…已找到 {len(out)} 个 nfo")
        return sorted(out, key=lambda x: x.lower())

    # ------------------------------------------------ 单个 nfo → 计划
    def plan_one(self, nfo, algo="normal", translate=True, overwrite=False,
                 complete=True, use_cooccur=True, ai_model=None, ai_limit=14):
        """算出这个 nfo 的目标标签（**不碰磁盘**）。返回 dict。"""
        out = {"nfo": nfo, "title": "", "before": [], "after": [],
               "added": [], "removed": [], "translated": [], "engine": "builtin",
               "error": ""}
        try:
            info = nfo_parser.parse_any(nfo) or {}
        except Exception as e:
            out["error"] = f"{type(e).__name__}: {e}"
            return out

        title = str(info.get("title") or "")
        out["title"] = title
        # v1.25.0：`before` 取**磁盘上的原文**（含 1080p / HEVC 这类技术标签）。
        # parse_*() 的 genres 是给卡片徽章用的、已经滤过技术标签；拿它当 before 的话，
        # 「补全标签」会把 <genre>1080p</genre> 一起写没，违反本模块「原有标签一个不丢」的承诺。
        before = []
        for t in (nfo_parser.read_genres(nfo) or []):
            t = clean_tag(t)
            if t and t not in before:
                before.append(t)
        if not before:                      # 兜底：read_genres 读不到时退回旧路径
            before = [clean_tag(t) for t in str(info.get("genres") or "").split(",")]
            before = [t for t in before if t]
        out["before"] = before
        after = list(before)

        # 1) 日语 → 中文（overwrite=True 时用中文**替换**源日语标签，否则额外补一条中文）
        if translate:
            rebuilt = []
            for t in after:
                zh = to_zh(t)
                if not zh or zh == t:
                    rebuilt.append(t)
                    continue
                if overwrite:
                    rebuilt.append(zh)
                else:
                    rebuilt.extend([t, zh])
                out["translated"].append((t, zh))
            after = rebuilt

        # 种子词别喂技术标签（1080p / HEVC…）—— 共现里它们只会污染候选
        plain_seed = [t for t in after
                      if not t.startswith(PREFIXES) and not is_tech(t)][:60]

        # 2) 标题关键词
        if complete:
            for zh in tags_from_title(title, translate=translate):
                if zh not in after:
                    after.append(zh)

        # 3) 片商 / 系列 伪标签（与库内既有约定一致）
        studio = str(info.get("studio") or "").strip()
        if studio and ("片商:" + studio) not in after:
            after.append("片商:" + studio)
        coll = str(info.get("collection") or "").strip()
        if coll and ("系列:" + coll) not in after:
            after.append("系列:" + coll)

        # 4) 全库共现补全
        if complete and use_cooccur and plain_seed:
            _c, co = self.ensure_stats()
            for t in suggested_from_cooccur(plain_seed, co):
                if t not in after:
                    after.append(t)

        # 5) AI 补全（失败静默降级）
        if str(algo) == "ai":
            words = ai_suggest(title, plain_seed,
                               plot=str(info.get("plot") or ""), model=ai_model,
                               limit=ai_limit)
            if words:
                out["engine"] = "ollama"
            for w in words:
                zh = to_zh(w) or w
                if zh and zh not in after:
                    after.append(zh)

        # 收尾：去重（保序）+ 只丢弃空项；**原有标签一个不丢**
        final, seen = [], set()
        for t in after:
            t = clean_tag(t)
            if not t:
                continue
            k = t.lower()
            if k in seen:
                continue
            seen.add(k)
            final.append(t)
        out["after"] = final
        bset = {t.lower() for t in before}
        aset = {t.lower() for t in final}
        out["added"] = [t for t in final if t.lower() not in bset]
        out["removed"] = [t for t in before if t.lower() not in aset]
        return out

    def plan(self, nfos, progress=None, **kw):
        """批量出计划（progress(i, n, msg)）。"""
        plans = []
        n = len(nfos)
        for i, nfo in enumerate(nfos):
            plans.append(self.plan_one(nfo, **kw))
            if progress:
                progress(i + 1, n, f"已分析 {i + 1}/{n}：{os.path.basename(nfo)}")
        return plans

    # ------------------------------------------------ 写回
    def apply(self, plans, backup=True, progress=None):
        """把计划写回 nfo + 同步数据库。返回统计 dict。"""
        stats = {"written": 0, "skipped": 0, "failed": 0, "db_synced": 0,
                 "backups": [], "errors": []}
        n = len(plans or [])
        for i, p in enumerate(plans or []):
            nfo = p.get("nfo") or ""
            name = os.path.basename(nfo)
            if not nfo or p.get("error"):
                stats["skipped"] += 1
                continue
            if list(p.get("before") or []) == list(p.get("after") or []):
                stats["skipped"] += 1
                if progress:
                    progress(i + 1, n, f"跳过（标签没有变化）：{name}")
                continue
            if backup:
                bak = f"{nfo}.bak-{time.strftime('%Y%m%d%H%M%S')}"
                try:
                    if not os.path.exists(bak):
                        shutil.copy2(nfo, bak)
                    stats["backups"].append(bak)
                except Exception as e:
                    stats["failed"] += 1
                    stats["errors"].append(f"{name} 备份失败：{e}")
                    continue
            if not nfo_parser.write_genres(nfo, p.get("after")):
                stats["failed"] += 1
                stats["errors"].append(f"{name} 写入失败")
                continue
            stats["written"] += 1
            mid = db.media_id_by_nfo(nfo)
            if mid:
                try:
                    db.update_media_fields(mid, genres=",".join(p.get("after") or []))
                    stats["db_synced"] += 1
                except Exception:
                    pass
            if progress:
                progress(i + 1, n, f"已写入：{name}")
        return stats


def _is_backup_name(fn: str) -> bool:
    return ".bak-" in str(fn).lower() or str(fn).lower().endswith(".bak")


__all__ = ["TagOptimizer", "JA2ZH", "JA2ZH_CONFLICTS", "to_zh", "has_kana", "clean_tag",
           "is_tech",
           "split_genres", "tags_from_title", "library_tag_stats",
           "suggested_from_cooccur", "ai_suggest", "nfo_for_video", "PREFIXES"]
