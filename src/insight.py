# -*- coding: utf-8 -*-
"""画像概览（v1.24.0 新增）

需求（反馈 6）：读取 `nfo_profiler` 项目，**借鉴 / 逆向**它的「画像概览」功能，作为一项功能
放进「工具」页，位置：个性化设置 → **画像概览** → 演员刮削。

本模块是**纯计算层**（无 Qt 依赖，可离屏单测）：把索引里的作品元数据算成一份「口味画像」，
UI 由 `ui_settings._build_insight()` 渲染。对应 nfo_profiler 的这几块：

    · 一句话画像
    · 八维偏好雷达（标签广度 / 艺人专一度 / 片商忠诚度 / 高清偏好 /
                    长片偏好 / 打分积极度 / 系列收集度 / 追新度）
    · 高频榜（标签 / 演员 / 导演 / 片商 / 系列）
    · 分布（画质 / 评分 / 时长 / 年份 / 入库月）
    · 标签共现（哪两个标签老是一起出现）

与 nfo_profiler 的差异（**为流明盒的数据形态做的适配**）：
- 它读自己的 `movies` 表，这里读 `media` 表；番号列不存在 → 番号相关统计改为「按片名首词」，
  并新增**导演榜**（本项目的 `media_people` 里导演有 3.4 万条链接，值得单列）。
- `genres` 列里混着 `片商:` / `发行:` / `系列:` 前缀的「伪标签」→ 先按前缀拆桶再统计，
  避免把片商名混进标签 Top 榜（这是本项目数据最脏的一处）。
"""
import math
import re
from datetime import datetime
from collections import Counter

import database as db

# genres 里的伪标签前缀（全角/半角冒号都要认）
_PREFIXES = ("片商", "发行", "系列", "导演", "導演", "演员", "演員", "標籤", "标签")
_PREFIX_RE = re.compile(r"^(" + "|".join(_PREFIXES) + r")\s*[:：]\s*(.+)$")

_HD_WORDS = ("4k", "2160", "1080", "720", "hd", "bluray", "blu-ray", "蓝光", "高清", "fhd", "uhd")
_LONG_SEC = 90 * 60          # 「长片」阈值：90 分钟

# nfo 里没有真名时会写「未知演员 / 有码演员 / 未知导演 / 有码导演」这类**占位人名**。
# 实测这四个名字各占几千上万条链接，不剔除会直接霸榜（真机验证：Top1 曾是「未知演员 4921 部」）。
_JUNK_PERSON_RE = re.compile(r"^(未知|有码|无码|不明)\s*(演员|演員|导演|導演|女优|女優|监督|監督|优|優)$")


def is_junk_person(name: str) -> bool:
    s = str(name or "").strip()
    return (not s) or bool(_JUNK_PERSON_RE.match(s))


def split_tags(genres: str):
    """把 `genres` 拆成 (真标签, 片商, 发行, 系列)。

    本项目 `genres` 形如「巨乳, 片商:S1, 系列:xxx, 单体」——用逗号（中英文都算）分隔，
    带前缀的进各自的桶，其余算标签。空串 / 重复值会被剔除。
    """
    tags, studios, publishers, series = [], [], [], []
    for raw in re.split(r"[,，;；]", genres or ""):
        s = raw.strip()
        if not s:
            continue
        m = _PREFIX_RE.match(s)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if not val:
                continue
            if key in ("片商",):
                studios.append(val)
            elif key in ("发行",):
                publishers.append(val)
            elif key in ("系列",):
                series.append(val)
            else:
                tags.append(val)
        else:
            tags.append(s)
    return tags, studios, publishers, series


def _runtime_sec(text) -> int:
    """`runtime` 列形如 "01:23:45"（也可能是 "83" 分钟或空）→ 秒。"""
    s = str(text or "").strip()
    if not s:
        return 0
    if ":" in s:
        parts = [p for p in s.split(":") if p.strip().isdigit()]
        try:
            nums = [int(p) for p in parts]
        except ValueError:
            return 0
        if len(nums) == 3:
            return nums[0] * 3600 + nums[1] * 60 + nums[2]
        if len(nums) == 2:
            return nums[0] * 60 + nums[1]
        return nums[0] * 60 if nums else 0
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) * 60 if digits else 0


def _quality_bucket(q) -> str:
    s = str(q or "").strip().lower()
    if not s:
        return "未标注"
    if "4k" in s or "2160" in s or "uhd" in s:
        return "4K"
    if "1080" in s or "fhd" in s:
        return "1080P"
    if "720" in s:
        return "720P"
    if "蓝光" in s or "bluray" in s or "blu-ray" in s:
        return "蓝光"
    if "hd" in s:
        return "HD"
    return "其他"


def _added_month(added_date, added_time=None) -> str:
    """入库月。

    真机数据里 `added_time` 是 **Unix 时间戳**（float），而且整库同月（一次批量入库），
    统计出来只有一根柱子没有任何信息；`added_date` 才是 nfo 记的日期字符串（79 个月份）。
    所以**优先用 added_date，退回 added_time 时间戳**。
    """
    s = str(added_date or "").strip()
    m = re.match(r"(\d{4})[-/](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    try:
        ts = float(added_time)
    except (TypeError, ValueError):
        return ""
    if ts <= 0:
        return ""
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m")
    except (OSError, OverflowError, ValueError):
        return ""


def _bar(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _soft(x: float, k: float) -> float:
    """软饱和归一：x/(x+k)。

    固定分母（x/300、x/0.7 之类）在真机上会**同时顶到 1.0**（实测 标签广度 7829/300、
    长片 86%/70%、追新 58%/35% 三项全满），雷达直接变成一块饼。改成 x/(x+k) 后
    每维都落在中段，八个轴才真的有区分度。
    """
    x = max(0.0, float(x))
    return _bar(x / (x + k)) if (x + k) else 0.0


class Portrait:
    """一次性算完整份画像。

    典型用法（UI 里放在线程里跑，`progress` 用来推进度条）::

        p = Portrait(library="Jav-library")
        data = p.build(progress=lambda i, n, msg: ...)
    """

    MAX_TAGS = 600          # 高频标签榜长度上限（雷达「标签广度」按 300 归一）

    def __init__(self, library: str = None, favorites_only: bool = False):
        self.library = library or None
        # v1.24.1（反馈 4）：统计范围可以只算「我的收藏」
        self.favorites_only = bool(favorites_only)

    # ---------------------------------------------------------------- 取数
    def build(self, progress=None):
        def step(i, n, msg):
            if progress:
                progress(i, n, msg)

        step(0, 6, "正在读取作品元数据…")
        rows = db.media_for_insight(self.library, favorites_only=self.favorites_only)
        step(1, 6, f"已读取 {len(rows):,} 部作品")

        actors = db.people_links_map("Actor")
        step(2, 6, "正在统计演员关联…")
        directors = db.people_links_map("Director")
        step(3, 6, "正在统计导演关联…")
        # v1.24.1（反馈 4）：关联条数**按当前统计范围**算。
        # 原来取的是全库 media_people 行数，一旦把范围收窄到某个库（或「我的收藏」），
        # 就会显示成「100 部作品 / 57,000 条关联」这种明显不对的数字。
        actor_links = 0
        director_links = 0

        tag_c = Counter()
        stu_c = Counter()
        pub_c = Counter()
        ser_c = Counter()
        act_c = Counter()
        dir_c = Counter()
        q_c = Counter()
        r_c = Counter()
        len_c = Counter()
        year_c = Counter()
        mon_c = Counter()
        pair_c = Counter()

        n = len(rows)
        fav_n = 0
        hd_n = 0
        long_n = 0
        rated_n = 0
        series_n = 0
        rating_sum = 0.0
        rating_cnt = 0
        total_sec = 0
        total_size = 0
        years = []
        tag_sets = []            # [(media_id, set(tags))] 供共现矩阵用

        for r in rows:
            if r.get("favorite"):
                fav_n += 1
            tags, studios, pubs, series = split_tags(r.get("genres"))
            for t in tags:
                tag_c[t] += 1
            for s in studios:
                stu_c[s] += 1
            for p in pubs:
                pub_c[p] += 1
            for s in series:
                ser_c[s] += 1
            if r.get("studio"):
                stu_c[str(r["studio"]).strip()] += 1
            if r.get("collection"):
                series_n += 1
                ser_c[str(r["collection"]).strip()] += 1
            elif series:
                series_n += 1
            for a in actors.get(r["id"], ()):
                actor_links += 1
                if not is_junk_person(a):
                    act_c[a] += 1
            for d in directors.get(r["id"], ()):
                director_links += 1
                if not is_junk_person(d):
                    dir_c[d] += 1

            q = _quality_bucket(r.get("quality"))
            q_c[q] += 1
            if q in ("4K", "1080P") or any(w in str(r.get("quality") or "").lower()
                                           for w in _HD_WORDS):
                hd_n += 1

            sec = _runtime_sec(r.get("runtime"))
            total_sec += sec
            if sec >= _LONG_SEC:
                long_n += 1
            len_c[_len_bucket(sec)] += 1

            try:
                rat = float(r.get("rating") or 0)
            except (TypeError, ValueError):
                rat = 0.0
            if rat > 0:
                rating_sum += rat
                rating_cnt += 1
            r_c[_rating_bucket(rat)] += 1
            if r.get("user_rating"):
                rated_n += 1

            try:
                y = int(r.get("year") or 0)
            except (TypeError, ValueError):
                y = 0
            if 1900 <= y <= 2100:
                years.append(y)
                year_c[y] += 1
            m = _added_month(r.get("added_date"), r.get("added_time"))
            if m:
                mon_c[m] += 1
            try:
                total_size += int(r.get("file_size") or 0)
            except (TypeError, ValueError):
                pass
            tag_sets.append(set(tags))

        step(4, 6, "正在计算标签共现…")
        top_tags = [t for t, _ in tag_c.most_common(26)]
        idx = {t: i for i, t in enumerate(top_tags)}
        for ts in tag_sets:
            hit = [idx[t] for t in ts if t in idx]
            if len(hit) < 2:
                continue
            hit.sort()
            for i in range(len(hit)):
                for j in range(i + 1, len(hit)):
                    pair_c[(top_tags[hit[i]], top_tags[hit[j]])] += 1

        step(5, 6, "正在生成画像…")
        if self.favorites_only:
            scope = (f"{self.library} · 我的收藏" if self.library else "我的收藏")
        else:
            scope = self.library or "全部媒体库"
        overview = {
            "scope": scope,
            "media": n,
            "favorite": fav_n,
            "actors": len(act_c),
            "directors": len(dir_c),
            "actor_links": actor_links,
            "director_links": director_links,
            "series": len(ser_c),
            "studios": len(stu_c),
            "tags": len(tag_c),
            "avg_rating": (rating_sum / rating_cnt) if rating_cnt else 0.0,
            "total_hours": total_sec / 3600.0,
            "total_size": total_size,
        }

        new_n = 0
        if years:
            ymax = max(years)
            new_n = sum(1 for y in years if y >= ymax - 2)
        radar = self._radar(n, fav_n, hd_n, long_n, rated_n, series_n,
                            tag_c, act_c, stu_c, new_n, max(years) if years else 0)
        data = {
            "overview": overview,
            "radar": radar,
            "tags": tag_c.most_common(self.MAX_TAGS),
            "actors": act_c.most_common(30),
            "directors": dir_c.most_common(30),
            "studios": stu_c.most_common(30),
            "publishers": pub_c.most_common(20),
            "series": ser_c.most_common(30),
            "dist": {
                "画质": q_c.most_common(),
                "评分": [(_k, r_c[_k]) for _k in _RATING_ORDER if r_c.get(_k)],
                "时长": [(_k, len_c[_k]) for _k in _LEN_ORDER if len_c.get(_k)],
                "年份": _year_dist(year_c),
                "入库月": sorted(mon_c.items())[-18:],
            },
            "cooc": pair_c.most_common(18),
        }
        data["line"] = self._one_line(data)
        step(6, 6, "画像完成")
        return data

    # ---------------------------------------------------------------- 雷达
    @staticmethod
    def _radar(n, fav_n, hd_n, long_n, rated_n, series_n, tag_c, act_c, stu_c,
               new_n=0, max_year=0):
        """八维偏好雷达。每维返回 (标签, 0~1 归一值, 人话说明)。"""
        def share(x):
            return (x / n) if n else 0.0

        # 标签广度：不同标签数（300 个算满）
        distinct = len(tag_c)
        # 艺人专一度：前 20 位演员占全部关联的比例
        links = sum(act_c.values())
        top20 = sum(c for _a, c in act_c.most_common(20))
        conc = (top20 / links) if links else 0.0
        # 片商忠诚度：头名片商的作品占比
        top_stu = (stu_c.most_common(1)[0][1] / n) if (stu_c and n) else 0.0
        return [
            ("标签广度", _soft(distinct, 1500.0), f"{distinct:,} 个不同标签"),
            ("艺人专一度", _soft(conc, 0.25), f"前 20 位演员占 {conc * 100:.0f}%"),
            ("片商忠诚度", _soft(top_stu, 0.15),
             (f"头名片商占 {top_stu * 100:.0f}%" if top_stu else "无片商数据")),
            ("高清偏好", _soft(share(hd_n), 0.35),
             f"高清 / 蓝光占 {share(hd_n) * 100:.0f}%"),
            ("长片偏好", _soft(share(long_n), 0.45),
             f"90 分钟以上占 {share(long_n) * 100:.0f}%"),
            ("打分积极度", _soft(share(rated_n), 0.30),
             f"打过分的占 {share(rated_n) * 100:.0f}%"),
            ("系列收集度", _soft(share(series_n), 0.35),
             f"属于某系列占 {share(series_n) * 100:.0f}%"),
            ("追新度", _soft(share(new_n), 0.40),
             (f"{max_year - 2} 年以后占 {share(new_n) * 100:.0f}%"
              if max_year else "无年份数据")),
        ]

    # ---------------------------------------------------------------- 文案
    @staticmethod
    def _one_line(data):
        ov = data["overview"]
        parts = []
        if ov["media"]:
            # 范围本身就是「我的收藏」时（media == favorite），再说「其中收藏 N 部」是废话
            if ov["favorite"] >= ov["media"]:
                parts.append(f"收藏了 {ov['media']:,} 部作品")
            else:
                parts.append(f"索引里共 {ov['media']:,} 部作品")
        if ov["favorite"] and ov["favorite"] < ov["media"]:
            parts.append(f"其中收藏 {ov['favorite']:,} 部")
        tg = data["tags"][:3]
        if tg:
            parts.append("口味最集中在 " + "、".join(f"「{t}」" for t, _ in tg) + " 这些标签上")
        st = data["studios"][:2]
        if st:
            parts.append("片商偏爱 " + "、".join(f"{s}（{c} 部）" for s, c in st))
        ac = data["actors"][:2]
        if ac:
            parts.append("看的最多的是 " + "、".join(f"{a}（{c} 部）" for a, c in ac))
        if ov["series"]:
            parts.append(f"一共涉及 {ov['series']:,} 个系列")
        if ov["avg_rating"]:
            parts.append(f"平均评分 {ov['avg_rating']:.1f}")
        if ov["total_hours"]:
            parts.append(f"累计时长约 {ov['total_hours']:.0f} 小时")
        return "；".join(parts) + "。" if parts else "索引里还没有可统计的作品。"

    # ---------------------------------------------------------------- 给推荐用
    def token_weights(self, data=None, limit_tags=120, limit_people=60):
        """把画像折算成 {token: 权重}，供 `recommend.py` 做「无收藏时的冷启动种子」。"""
        data = data or self.build()
        w = {}
        for t, c in data["tags"][:limit_tags]:
            w["t:" + t] = float(c)
        for a, c in data["actors"][:limit_people]:
            w["a:" + a] = float(c) * 0.5
        for d, c in data["directors"][:limit_people]:
            w["d:" + d] = float(c) * 0.6
        for s, c in data["studios"][:40]:
            w["s:" + s] = float(c) * 0.7
        for s, c in data["series"][:40]:
            w["x:" + s] = float(c) * 0.8
        return w


# ---------------------------------------------------------------- 分桶工具
# 真机数据 `rating` 是 **10 分制**（min 0.2 / max 10.0，user_rating 集中在 7.5 附近），
# 所以分档必须按 10 分制来，否则九成作品会挤进「≥5」一个桶里（v1.24.0 实测踩到）。
_RATING_ORDER = ("<4", "4~6", "6~7", "7~7.5", "7.5~8", "8~9", "≥9", "未评分")
_LEN_ORDER = ("<30 分", "30~60 分", "60~90 分", "90~120 分", "120~180 分", "≥180 分", "未知")


def _rating_bucket(v: float) -> str:
    """10 分制分档（见 `_RATING_ORDER` 的注释）。"""
    if not v or v <= 0:
        return "未评分"
    if v < 4:
        return "<4"
    if v < 6:
        return "4~6"
    if v < 7:
        return "6~7"
    if v < 7.5:
        return "7~7.5"
    if v < 8:
        return "7.5~8"
    if v < 9:
        return "8~9"
    return "≥9"


def _len_bucket(sec: int) -> str:
    if sec <= 0:
        return "未知"
    if sec < 1800:
        return "<30 分"
    if sec < 3600:
        return "30~60 分"
    if sec < 5400:
        return "60~90 分"
    if sec < 7200:
        return "90~120 分"
    if sec < 10800:
        return "120~180 分"
    return "≥180 分"


def _year_dist(year_c, span=5):
    """年份分布：按 span 年一档归并，只保留最近 ~10 档。"""
    if not year_c:
        return []
    ymax = max(year_c)
    ymin = min(year_c)
    lo = max(ymin, ymax - span * 9)
    out = {}
    for y, c in year_c.items():
        if y < lo:
            key = f"≤{lo}"
        else:
            start = lo + ((y - lo) // span) * span
            key = f"{start}-{start + span - 1}"
        out[key] = out.get(key, 0) + c
    return sorted(out.items(), key=lambda kv: _year_key(kv[0]))


def _year_key(label: str):
    m = re.search(r"(\d{4})", label)
    return int(m.group(1)) if m else 0


def human_size(n) -> str:
    try:
        v = float(n or 0)
    except (TypeError, ValueError):
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if v < 1024 or unit == "PB":
            return f"{v:.1f} {unit}" if unit != "B" else f"{int(v)} B"
        v /= 1024
    return f"{v:.1f} PB"


def human_hours(h) -> str:
    try:
        v = float(h or 0)
    except (TypeError, ValueError):
        return "—"
    if v >= 10000:
        return f"{v / 1000:.1f} 千小时"
    return f"{v:,.0f} 小时"


def _entropy(counter: Counter):
    total = sum(counter.values())
    if not total:
        return 0.0
    e = 0.0
    for c in counter.values():
        p = c / total
        e -= p * math.log(p, 2)
    return e


__all__ = ["Portrait", "split_tags", "human_size", "human_hours"]
