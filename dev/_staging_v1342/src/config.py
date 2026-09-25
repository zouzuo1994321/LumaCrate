# -*- coding: utf-8 -*-
"""
全局设置存储层
==============
不依赖浏览器 / 网络：所有偏好持久化到 exe 同级的 settings.json。
涵盖：导航菜单(显隐+排序)、首页模块(显隐)、内容卡片(显隐)、
媒体库(名称/类型/路径 —— 全部由用户自己命名，无内置库)、后台扫描任务(启用/库/时间/频率)。
"""
import os
import re
import sys
import json
import time
import colorsys


# 侧边栏导航项默认定义（order 即默认顺序，visible 控制显隐）。已去除图标。
DEFAULT_NAV = [
    {"key": "home",        "label": "首页",     "group": "",     "visible": True},
    {"key": "recent",      "label": "最近播放", "group": "",     "visible": True},
    {"key": "favorites",   "label": "我的收藏", "group": "",     "visible": True},
    {"key": "smart",       "label": "智能推荐", "group": "",     "visible": True},
    {"key": "folders",     "label": "文件夹",   "group": "",     "visible": True},
    {"key": "collections", "label": "合集",     "group": "",     "visible": True},
    {"key": "all",         "label": "全部",     "group": "分类", "visible": True},
    {"key": "actors",      "label": "演员库",   "group": "分类", "visible": True},
    {"key": "directors",   "label": "导演库",   "group": "分类", "visible": True},
]

# ---------------------------------------------------------------------------
# 媒体库（v1.12.0 起统一为「一份列表」）
# ---------------------------------------------------------------------------
# 历史包袱（v1.11.x 及以前）曾有**两套并存**的媒体库：写死在代码里的 6 个「内置媒体库」
# （media_libraries，删掉还会被默认值自动补回来、另配「恢复被删除的内置媒体库」按钮）
# 和用户自建的「命名媒体库」（libraries）。两者最终都只是往 media.library 写一个名字，
# 功能完全重叠，用户看到的是侧边栏两个分组 + 设置页两套管理入口。
#
# v1.12.0：**取消「内置库」概念** —— 只有一份 libraries，全部由用户自己命名。
# 下面这张表不再参与任何默认值注入，只用于**升级时识别旧内置条目**：
#   · 名字原封未动的旧内置库 → 直接丢弃（用户明确要求「不需要内置媒体库」）
#   · 被用户改过名 / 自建的条目 → 视作用户资产，迁移进统一列表
_LEGACY_BUILTIN_LIBS = {
    "movie": "电影", "tv": "电视", "anime": "番剧",
    "acg": "二次元", "banned": "禁片", "domestic": "国产",
}

# 媒体库「类型」候选项（仅作标签，扫描时按目录里实际的 nfo 判定电影/剧集）
LIBRARY_KINDS = ["电影", "剧集", "动画", "混合"]

# ---------- 数值输入框（QSpinBox / QDoubleSpinBox）的宽度口径（v1.34.1） ----------
# 背景（用户反馈「数值和上下 UI 重叠」的根因）：
#   style.qss 给 SpinBox 设了 `padding: 5px 10px`，内容区左右各被吃掉 10px；
#   再叠加「0.5 ~ 10.0」+ 1 位小数 + 上下箭头，Qt 自己算出的
#   `minimumSizeHint().width()` 在本机（Microsoft YaHei UI 9 / DPI 96）是 **131px**。
#   而代码里原来写死了 setFixedWidth(72)（引导行权重）与 setFixedWidth(88/96)
#   （自动填充 前 N / 权重）—— 比最小需求少 35~59px，Qt 只能把数字与箭头
#   强行挤在一格里 → **数字贴边、右侧箭头被裁**，视觉上就是「与上下重叠」。
# 结论：**任何装数值的 SpinBox 都不许写小于 SPIN_MIN_W 的固定宽**。
SPIN_MIN_W = 131      # = Qt 实测 minimumSizeHint 宽度，放行给足
SPIN_MAX_W = 160      # 上限：字体/DPI 变大时允许长一点，但不撑爆窄面板

DEFAULT_HOME_MODULES = {
    "recent": True,       # 首页「最近添加」快捷筛选
    "favorites": True,    # 首页「我的收藏」快捷筛选
    "collections": True,  # 首页「合集」快捷筛选
}

DEFAULT_CONTENT_CARDS = {
    "show_rating": True,     # 内容卡片显示评分
    "show_year": True,       # 内容卡片显示年份（v1.11.1 需求）
    "show_quality": True,    # 内容卡片显示分辨率/画质
    "show_actors": True,     # 内容卡片显示演员小字（v1.11.1 需求）
    "show_directors": True,  # 内容卡片显示导演小字（v1.11.1 需求）
    # v1.33.0（反馈 3）：删除「悬停时显示预告片（预留）」—— 该功能从未实现，
    # 留个永远无效果的开关只会误导用户。老配置里的 hover_trailer 键会被
    # Settings.load() 忽略（不在白名单的键直接丢弃），无需迁移。
}

# 首页表格可选列：(key, 标签) —— 参考 tinyMediaManager 的「选中可见栏」
HOME_COLUMNS = [
    ("title",         "标题"),
    ("actors",        "演员"),
    ("year",          "年份"),
    ("premiere",      "上映日期"),
    ("added_date",    "添加日期"),
    ("rating",        "评分"),
    ("user_rating",   "用户评分"),
    ("certification", "分级"),
    ("kind",          "类型"),
    ("collection",    "系列电影"),
    ("runtime_min",   "时长 [min]"),
    ("runtime",       "时长 [hh:mm]"),
    ("quality",       "格式 / 画质"),
    ("file_size",     "视频文件大小"),
    ("studio",        "来源 / 制片"),
    ("language",      "国家 / 地区"),
    ("filename",      "文件名"),
    ("path",          "路径"),
    ("library",       "媒体库"),
    ("play_count",    "已观看"),
    ("favorite",      "收藏"),
    ("plot",          "注释"),
]

DEFAULT_HOME_COLUMNS = ["title", "rating", "certification", "added_date", "premiere"]

# 媒体库（统一，v1.12.0 起）：
#   [{"name": str, "kind": str, "paths": [str], "filter": {}}]
# 默认**空** —— 不带任何内置库，全部由用户自己创建并命名。
DEFAULT_LIBRARIES = []

DEFAULT_BACKGROUND = {"enabled": False, "library": "", "time": "03:00", "frequency": "每天"}

# ---------- 影片墙 / 演员库的「筛选 + 排序」偏好（v1.14.0） ----------
# 结构：{"sort": <排序键>, "asc": bool, "filters": {<筛选键>: 值}}
# 筛选键取值：None = 不筛；True/False = 是/否；数字 = 阈值/年份。
DEFAULT_WALL_PREFS = {"sort": "sort_title", "asc": True, "filters": {}, "facet_open": False}
DEFAULT_ACTOR_PREFS = {"sort": "works", "asc": False, "filters": {}}

# v1.17.0：多维筛选面板改为**默认收缩**（点「筛选」才展开），展开状态存 wall_prefs.facet_open。
# 同时「状态」「进度」两类筛选下线，不再纳入持久化白名单（旧偏好里的这两个键会在加载时被丢弃）。
WALL_FILTER_KEYS = ("favorite", "has_user_rating", "min_user_rating", "year_from", "year_to",
                    "quality", "kind", "genre", "certification", "collection", "library",
                    "genre_other", "country_other", "has_collection")
ACTOR_FILTER_KEYS = ("favorite", "pinned", "status", "has_photo", "min_works")

# ---------- v1.24.0 新增偏好 ----------
# 智能推荐：algo = normal（普通算法）/ ai（本地离线 AI 增强）；count = 一次推荐几部
DEFAULT_RECOMMEND = {
    "algo": "normal",
    "count": 24,
    "use_tags": True,          # 结合「我的收藏」影片的标签
    "use_actors": True,        # 结合演员库中收藏 / 置顶的演员
    "use_directors": True,     # 结合导演库中收藏 / 置顶的导演
    "use_userrating": False,   # 把「用户评分 ≥ 8.5」也当成弱信号
    "exclude_watched": True,   # 排除已看过的
    "diversity": 0.5,          # 多样性（MMR λ 的反面：越大越多样）
    # v1.25.0（反馈 1）：调用哪个本地模型 —— 空 = 自动（取 ollama list 里的第一个）
    "ai_model": "",
    # v1.25.0（反馈 3）：最近 N 轮推荐过的作品不再出现（0 = 不限制）
    "no_repeat_rounds": 3,
}
# 重复检测：exclude_multipart=True 时把「同一目录下的多份」当分片自动排除
DEFAULT_DEDUPE = {"exclude_multipart": True, "min_confidence": "低",
                  "algo": "normal", "fast": True}
# v1.34.0（需求 1）：「从画像自动填充」的偏好 —— 统计范围 + 各维度前 N + 各维度权重。
# 默认值刻意与旧版**硬编码的那套**完全一致（标签前 30 / 其余各 10，权重 1.5/1.3/1.2），
# 这样老用户升级后点「从画像自动填充」看到的结果与升级前一模一样。
DEFAULT_AUTOFILL = {
    "scope": "",            # 统计范围："" = 全部媒体库，否则媒体库名
    "favorites_only": False,  # 只统计「我的收藏」
    "dims": {
        "tag":      {"on": True, "top": 30, "w": 1.5},
        "studio":   {"on": True, "top": 10, "w": 1.3},
        "series":   {"on": True, "top": 10, "w": 1.2},
        "actor":    {"on": True, "top": 10, "w": 1.3},
        "director": {"on": True, "top": 10, "w": 1.2},
    },
}
# 数据导出 / 导入的可选分区（v1.24.0 反馈 9：细化到「收藏、演员收藏」等）
EXPORT_SECTIONS = [
    ("media",      "媒体索引（影片 / 剧集）"),
    ("people",     "演员与导演资料"),
    ("links",      "演员 / 导演 与作品的关联"),
    ("favorite",   "影片收藏标记"),
    ("play",       "观看次数 / 最近播放"),
    ("userrating", "用户评分"),
    ("people_fav", "演员 / 导演 的收藏与置顶"),
    ("config",     "媒体库与界面设置"),
]
DEFAULT_EXPORT = {"sections": [k for k, _ in EXPORT_SECTIONS]}
# 画像概览的统计范围（v1.24.1 反馈 4）：scope = "" 表示全部媒体库，否则是媒体库名
DEFAULT_INSIGHT = {"scope": "", "favorites_only": False}
# 标签优化（v1.25.0 反馈 4）：范围 / 算法 / 翻译 / 覆盖 / 备份
DEFAULT_TAGOPT = {
    "scope": "file",       # file（单一文件）/ folder（文件夹）/ library（媒体库）
    "path": "",            # 文件或文件夹路径
    "library": "",         # 媒体库名（scope=library 时用）
    "algo": "normal",      # normal（内置算法）/ ai（本地离线 AI）
    "translate": True,     # 日语标签转中文
    "overwrite": False,    # True = 中文替换原日语标签；False = 保留原文并另补一条中文
    "complete": True,      # 补全缺失标签（标题关键词 / 共现 / 片商 / 系列）
    "backup": True,        # 写入前把原 nfo 另存为 *.nfo.bak-<时间戳>
}


def _clean_prefs(raw, default: dict, filter_keys) -> dict:
    """把任意来源的偏好规整成安全结构（只留已知键、只留 JSON 标量）。"""
    out = {"sort": default["sort"], "asc": bool(default["asc"]), "filters": {}}
    if "facet_open" in default:                     # v1.17.0：影片墙筛选面板展开态
        out["facet_open"] = bool(default.get("facet_open", False))
    if not isinstance(raw, dict):
        return out
    if isinstance(raw.get("sort"), str) and raw["sort"]:
        out["sort"] = raw["sort"]
    if isinstance(raw.get("asc"), bool):
        out["asc"] = raw["asc"]
    if "facet_open" in default and isinstance(raw.get("facet_open"), bool):
        out["facet_open"] = raw["facet_open"]
    f = raw.get("filters")
    if isinstance(f, dict):
        for k, v in f.items():
            if k in filter_keys and isinstance(v, (bool, int, float, str)):
                out["filters"][k] = v
    return out

# 外观：磨砂玻璃（系统模糊）+ 玻璃浓度
APPEARANCE_MODES = ["磨砂玻璃", "经典暗色"]
GLASS_LEVELS = ["低", "中", "高"]
# 玻璃浓度 -> (页面底色不透明度, 面板不透明度)，255 = 完全不透明
_GLASS_ALPHA = {"低": (118, 138), "中": (146, 168), "高": (186, 206)}

# v1.25.0（反馈 5）：12 种基础「高亮色」。
# 卡片选中的描边 + 外发光、按钮 / chip / 滑块的强调色，全部由它派生 ——
# 用户挑一个，整套界面（含自绘控件）跟着换。
ACCENT_COLORS = [
    ("朱红", "#c0392b"),
    ("绯粉", "#e2659a"),
    ("杏橙", "#e08a3c"),
    ("鎏金", "#d4af37"),
    ("竹青", "#5aa469"),
    ("青碧", "#2e9e8f"),
    ("天青", "#3fa9c9"),
    ("靛蓝", "#3b6fd4"),
    ("紫棠", "#8e5bd4"),
    ("藕荷", "#b07aa1"),
    ("玉白", "#c9d6dd"),
    ("石墨", "#7a8b99"),
]
ACCENT_DEFAULT = "#c0392b"
# v1.28.0（反馈 1）：侧栏底部「数据统计」/「实时状态」两块的显隐，放进「外观」里开关。
# v1.32.0（反馈 3）：`language` —— 界面语言（19 种，见 src/i18n.py），默认基准语言简体中文。
DEFAULT_APPEARANCE = {"mode": "磨砂玻璃", "level": "中", "accent": ACCENT_DEFAULT,
                      "show_stats": True, "show_sysmon": True,
                      "language": "zh_CN"}


def accent_name(hexv: str) -> str:
    for _n, h in ACCENT_COLORS:
        if h.lower() == str(hexv or "").lower():
            return _n
    return "自定义"


def _clamp8(v):
    return max(0, min(255, int(round(v))))


def accent_rgb(hexv: str = None):
    """高亮色 -> (r, g, b)。非法值回落到默认朱红。"""
    h = str(hexv or "").strip().lstrip("#")
    if len(h) != 6:
        h = ACCENT_DEFAULT.lstrip("#")
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        h = ACCENT_DEFAULT.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def accent_shades(hexv: str = None) -> dict:
    """由高亮色派生出一组明暗变体，供 QSS 令牌使用。

    base = 原色；dark = 按下/选中底；deep = 主按钮底；light = 亮描边。

    **为什么在 HSL 里派生，而不是 RGB 等比缩放**：原来的调色板是人工挑的，
    并不是同一个色的等比缩放 —— 例如朱红 #c0392b 在 QSS 里的描边色是 #e05243，
    它在 RGB 下的通道倍率是 (1.17, 1.44, 1.56)，三个通道根本不一致。用等比缩放
    的话，换成任何颜色描边都会偏灰偏暗（朱红描边会从 (224,82,67) 掉到 (225,67,50)），
    而描边恰恰是用户最容易看见「高亮效果」的地方。改成只动 HSL 里的明度/饱和度、
    保留色相，实测朱红能复现出 (223,84,68) ≈ 原来的 (224,82,67)；换成玉白这种
    极浅色时也不会缩放着缩着就糊成一团白。
    """
    r, g, b = accent_rgb(hexv)
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)

    def vari(l_delta, s_delta, l_lo=0.16, l_hi=0.94):
        ll = max(l_lo, min(l_hi, l + l_delta))
        ss = max(0.0, min(1.0, s + s_delta))
        rr, gg, bb = colorsys.hls_to_rgb(h, ll, ss)
        return (_clamp8(rr * 255), _clamp8(gg * 255), _clamp8(bb * 255))

    return {"base": (r, g, b),
            "dark": vari(-0.135, +0.05),     # 按下 / 列表选中底
            "deep": vari(-0.080, +0.03),     # 主按钮底
            "light": vari(+0.110, +0.08)}    # 亮描边 / 悬停边框


def appearance_alphas(appearance: dict):
    """返回 (页面底色 alpha, 面板 alpha)。经典暗色 = 全不透明。"""
    if (appearance or {}).get("mode") == "经典暗色":
        return 255, 255
    return _GLASS_ALPHA.get((appearance or {}).get("level", "中"), _GLASS_ALPHA["中"])


# ---------- 演员刮削 ----------
# 数据源定义：minnano-av 为日本 AV 女优资料站；IMDB 覆盖普通影视演员
SCRAPER_SOURCES = [
    {"key": "minnano", "name": "www.minnano-av.com", "desc": "日本 AV 女优资料站（日文名检索，含别名/生日/身高/专属头图）"},
    {"key": "imdb",    "name": "IMDB",               "desc": "国际影人库（英文名检索，含生日/出生地/简介/头图）"},
]

DEFAULT_SCRAPER = {
    "enabled": False,            # 总开关（设置页保存后生效）
    "sources": ["minnano", "imdb"],          # 数据源优先级（自上而下依次尝试）
    "sources_enabled": {"minnano": True, "imdb": True},
    "fill_alias": True,          # 补齐别名/爱称
    "fill_birthday": True,       # 补齐生日
    "fill_bio": True,            # 补齐简介/尺寸/出身地等说明
    "download_photo": True,      # 下载演员头像到本地
    "overwrite": False,          # 覆盖已有信息（默认只补空缺）
    "only_no_photo": True,       # 只处理还没有头像的演员
    "delay_ms": 900,             # 每次请求之间的间隔（避免被目标站限流）
    "timeout": 15,               # 单次请求超时（秒）
    "limit": 0,                  # 单次最多处理人数，0 = 不限
    "retry": 1,                  # 失败重试次数
    "proxy": "",                 # 代理，例 http://127.0.0.1:7890（minnano-av 常需代理）
    "photo_dir": "",             # 头像缓存目录，空 = exe 同级 cache/people
}



def config_path() -> str:
    """settings.json 存放位置：exe 同级(持久化)，开发期在项目根。

    v1.24.1：可用环境变量 `LMC_CONFIG` 覆盖 —— 真机验收脚本需要让打包后的 exe
    读一份**临时配置**（例如把画像概览的统计范围预设成「我的收藏」），
    这样既能验到那条路径，又完全不碰用户真实的 settings.json。
    """
    env = os.environ.get("LMC_CONFIG")
    if env:
        return env
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "settings.json")


class Settings:
    def __init__(self):
        self.nav = [dict(x) for x in DEFAULT_NAV]
        self.home_modules = dict(DEFAULT_HOME_MODULES)
        self.content_cards = dict(DEFAULT_CONTENT_CARDS)
        self.home_columns = list(DEFAULT_HOME_COLUMNS)
        self.home_column_widths = {}        # 列 key -> 像素宽（持久化列宽）
        self.home_sort = {"key": None, "asc": True}   # 首页列表排序（列 key + 升降）
        self.home_split = []                # 首页「列表 / 详情」分栏宽度 [左, 右]
        self.window_opacity = 1.0          # 整窗透明度（0.2~1.0，1=不透明）
        self.libraries = [dict(x) for x in DEFAULT_LIBRARIES]   # 唯一的媒体库列表（全用户命名）
        self.wall_prefs = dict(DEFAULT_WALL_PREFS)      # 影片墙 筛选/排序（v1.14.0）
        self.actor_prefs = dict(DEFAULT_ACTOR_PREFS)    # 演员库 筛选/排序（v1.14.0）
        # v1.24.0：智能推荐 / 重复检测 / 数据导出
        self.recommend = dict(DEFAULT_RECOMMEND)
        self.dedupe = dict(DEFAULT_DEDUPE)
        self.export = {"sections": list(DEFAULT_EXPORT["sections"])}
        # v1.24.1：画像概览的统计范围（换过之后下次打开还是它）
        self.insight = dict(DEFAULT_INSIGHT)
        self.vector_overrides = {}      # 向量编辑：{维度: {键: 权重}}（0 = 屏蔽）
        # v1.34.0（需求 1）：画像自动填充偏好（范围 + 前 N + 权重）
        self.autofill = json.loads(json.dumps(DEFAULT_AUTOFILL))
        self.seen_smart = []            # 智能推荐「换一批」避让用（最近推过的 media id）
        # v1.25.0（反馈 3）：推荐历史按「轮次」记 —— [{"round": 1, "ids": [...], "ts": ...}]
        self.smart_history = []
        # v1.25.0（反馈 4）：标签优化偏好
        self.tagopt = dict(DEFAULT_TAGOPT)
        self.background = dict(DEFAULT_BACKGROUND)
        self.appearance = dict(DEFAULT_APPEARANCE)
        self.scraper = json.loads(json.dumps(DEFAULT_SCRAPER))
        self.load()

    # ---------- 读写 ----------
    def load(self):
        p = config_path()
        if not os.path.exists(p):
            return
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        if isinstance(data.get("nav"), list):
            # 仅沿用已保存的顺序与显隐；label/group 始终用新版默认（便于去图标等改版生效）
            saved = [x for x in data["nav"] if isinstance(x, dict) and x.get("key")]
            vis = {x["key"]: x.get("visible", True) for x in saved}
            default_keys = {d["key"] for d in DEFAULT_NAV}
            order = [x["key"] for x in saved if x["key"] in default_keys]
            merged = []
            for k in order:
                d = next(x for x in DEFAULT_NAV if x["key"] == k)
                item = dict(d)
                item["visible"] = vis.get(k, d["visible"])
                merged.append(item)
            # v1.24.0：新增的导航项（如「智能推荐」「导演库」）不再一律追加到末尾，
            # 而是**插到 DEFAULT_NAV 里它前一个已有条目的后面** —— 否则老用户升级后
            # 新导航会跑到底部，看着像坏了。用户自己的顺序与显隐仍然保持不变。
            default_order = [d["key"] for d in DEFAULT_NAV]
            for idx, d in enumerate(DEFAULT_NAV):
                if d["key"] in order:
                    continue
                anchor = next((k for k in reversed(default_order[:idx]) if k in order), None)
                if anchor is None:
                    merged.insert(0, dict(d))
                else:
                    merged.insert(merged.index(next(m for m in merged
                                                    if m["key"] == anchor)) + 1, dict(d))
            self.nav = merged
        if isinstance(data.get("home_modules"), dict):
            self.home_modules.update(data["home_modules"])
        if isinstance(data.get("content_cards"), dict):
            self.content_cards.update(data["content_cards"])
        if isinstance(data.get("home_columns"), list):
            valid = {k for k, _ in HOME_COLUMNS}
            self.home_columns = [k for k in data["home_columns"] if k in valid]
        if isinstance(data.get("home_column_widths"), dict):
            self.home_column_widths = {
                str(k): int(v) for k, v in data["home_column_widths"].items()
                if isinstance(v, (int, float))}
        if isinstance(data.get("home_sort"), dict):
            self.home_sort = {
                "key": data["home_sort"].get("key"),
                "asc": bool(data["home_sort"].get("asc", True))}
        if isinstance(data.get("home_split"), list):
            self.home_split = [int(x) for x in data["home_split"]
                               if isinstance(x, (int, float)) and int(x) > 0]
        if isinstance(data.get("window_opacity"), (int, float)):
            self.window_opacity = max(0.2, min(1.0, float(data["window_opacity"])))
        if isinstance(data.get("libraries"), list):
            self.libraries = self._sanitize_libraries(data["libraries"])
        # 升级迁移：旧版还有一份 media_libraries（含 6 个内置库）—— 见 _migrate_legacy_libraries
        self._migrate_legacy_libraries(data.get("media_libraries"))
        self.wall_prefs = _clean_prefs(data.get("wall_prefs"), DEFAULT_WALL_PREFS, WALL_FILTER_KEYS)
        self.actor_prefs = _clean_prefs(data.get("actor_prefs"), DEFAULT_ACTOR_PREFS,
                                        ACTOR_FILTER_KEYS)
        # v1.24.0：只接受已知键，避免旧配置里的脏值带进来
        if isinstance(data.get("recommend"), dict):
            for k, v in data["recommend"].items():
                if k in DEFAULT_RECOMMEND:
                    self.recommend[k] = v
        self.recommend["algo"] = "ai" if self.recommend.get("algo") == "ai" else "normal"
        try:
            self.recommend["count"] = max(6, min(120, int(self.recommend.get("count", 24))))
        except Exception:
            self.recommend["count"] = 24
        self._sanitize_recommend()
        if isinstance(data.get("dedupe"), dict):
            for k, v in data["dedupe"].items():
                if k in DEFAULT_DEDUPE:
                    self.dedupe[k] = v
        self.dedupe["exclude_multipart"] = bool(self.dedupe.get("exclude_multipart", True))
        # v1.32.0（反馈 1）：脏配置归一化 —— **绝不能写 `bool(v)`**，
        # `bool("0")` 是 True，而老配置文件里很可能存着字符串 "0"。
        if str(self.dedupe.get("algo") or "").lower() not in ("ai", "normal"):
            self.dedupe["algo"] = "normal"
        self.dedupe["fast"] = str(self.dedupe.get("fast", True)).strip().lower() \
            not in ("", "0", "false", "no", "off")
        if isinstance(data.get("export"), dict) and isinstance(data["export"].get("sections"), list):
            valid = {k for k, _ in EXPORT_SECTIONS}
            self.export = {"sections": [k for k in data["export"]["sections"] if k in valid]}
        if isinstance(data.get("vector_overrides"), dict):
            self.vector_overrides = {
                str(dim): {str(k): float(w) for k, w in (vals or {}).items()
                           if isinstance(w, (int, float))}
                for dim, vals in data["vector_overrides"].items() if isinstance(vals, dict)}
        # v1.34.0（需求 1）：画像自动填充偏好 —— 逐键白名单 + 范围钳制
        self.autofill = self._clean_autofill(data.get("autofill"))
        if isinstance(data.get("insight"), dict):
            raw_ins = data["insight"]
            self.insight["scope"] = str(raw_ins.get("scope") or "")
            self.insight["favorites_only"] = bool(raw_ins.get("favorites_only", False))
        if isinstance(data.get("seen_smart"), list):
            self.seen_smart = [int(x) for x in data["seen_smart"]
                               if isinstance(x, (int, float))][-200:]
        # v1.25.0（反馈 3）：推荐轮次历史；老配置只有扁平的 seen_smart → 当成第 1 轮迁过来
        self.smart_history = self._clean_smart_history(data.get("smart_history"))
        if not self.smart_history and self.seen_smart:
            self.smart_history = [{"round": 1, "ids": list(self.seen_smart), "ts": 0.0}]
        if isinstance(data.get("tagopt"), dict):
            for k, v in data["tagopt"].items():
                if k in DEFAULT_TAGOPT:
                    self.tagopt[k] = v
        self._sanitize_tagopt()
        if isinstance(data.get("background"), dict):
            self.background.update(data["background"])
        if isinstance(data.get("appearance"), dict):
            self.appearance.update(data["appearance"])
        # 高亮色必须是我们提供的那 12 种之一（老配置没这个键 → 落到默认朱红）
        if not any(h.lower() == str(self.appearance.get("accent") or "").lower()
                   for _n, h in ACCENT_COLORS):
            self.appearance["accent"] = ACCENT_DEFAULT
        # v1.28.0（反馈 1）：两个侧栏显隐开关。老配置没这两个键 → 默认都开。
        # 手改坏的 settings.json 也在这里归一：**不能直接 bool(v)** —— `bool("0")` 是 True，
        # 字符串得先按常见假值表判，写成 null 则当作「没设过」回到默认开。
        for _k in ("show_stats", "show_sysmon"):
            _v = self.appearance.get(_k, True)
            if isinstance(_v, str):
                _v = _v.strip().lower() not in ("", "0", "false", "no", "off")
            elif _v is None:
                _v = True
            self.appearance[_k] = bool(_v)
        # v1.32.0（反馈 3）：界面语言。老配置没这个键 → 落基准语言；
        # 手改成未知代码（`zh-Hans-CN`、`xx`）也在这里归一 —— 归一逻辑只在 i18n 里，
        # 别在这儿再写一份 `if code in ...`。
        import i18n as _i18n
        self.appearance["language"] = _i18n.normalize(self.appearance.get("language"))
        if isinstance(data.get("scraper"), dict):
            self.scraper.update(data["scraper"])
            # 数据源优先级：只保留已知源，并补上缺失的已知源
            known = [x["key"] for x in SCRAPER_SOURCES]
            order = [k for k in self.scraper.get("sources", []) if k in known]
            for k in known:
                if k not in order:
                    order.append(k)
            self.scraper["sources"] = order
            en = self.scraper.get("sources_enabled") or {}
            self.scraper["sources_enabled"] = {k: bool(en.get(k, True)) for k in known}
        # 后台任务指向的库可能已被删除（尤其是本次升级清掉的内置库）→ 复位为「全部库」
        self._drop_missing_background_library()

    # ---------- 媒体库：数据校验 / 升级迁移 ----------
    @staticmethod
    def _sanitize_libraries(saved) -> list:
        """把任意来源的列表规整成统一结构，按 name 去重（name 即媒体库身份）。"""
        out, seen = [], set()
        for x in (saved or []):
            if not isinstance(x, dict):
                continue
            name = str(x.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            out.append({"name": name,
                        "kind": str(x.get("kind") or "混合"),
                        "paths": [str(p) for p in (x.get("paths") or [])],
                        "filter": x.get("filter") if isinstance(x.get("filter"), dict) else {}})
        return out

    def _migrate_legacy_libraries(self, saved):
        """升级：处理旧版那份 `media_libraries`（v1.11.x 的「内置媒体库」+ 分类库）。

        规则（对应用户口径「不需要内置媒体库，全部都是可以自己命名的媒体库」）：
        - key 是旧内置 key 且**名字原封未动** → 丢弃（新版本不再自带任何库）；
        - 名字被改过 / key 非内置（用户自建）→ 迁入统一列表，保住用户的路径配置；
        - 已经写坏成「：xxx」这种残值的名字会被 sanitize 阶段之外的地方兜住，这里只做去重。
        """
        if not isinstance(saved, list):
            return
        names = {x["name"] for x in self.libraries}
        for x in saved:
            if not isinstance(x, dict):
                continue
            key = str(x.get("key") or "")
            name = str(x.get("name") or "").strip()
            if not name or name in names:
                continue
            if key in _LEGACY_BUILTIN_LIBS and name == _LEGACY_BUILTIN_LIBS[key]:
                continue                    # 原封未动的内置库 -> 按用户要求清掉
            self.libraries.append({
                "name": name,
                "kind": "混合",
                "paths": [str(p) for p in (x.get("paths") or [])],
                "filter": x.get("filter") if isinstance(x.get("filter"), dict) else {}})
            names.add(name)

    def _drop_missing_background_library(self):
        """后台任务选的库已不存在时复位，避免下拉框指向幽灵库。"""
        target = (self.background or {}).get("library") or ""
        if target and target not in {x["name"] for x in self.libraries}:
            self.background["library"] = ""


    def save(self):
        p = config_path()
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump({
                    "nav": self.nav,
                    "home_modules": self.home_modules,
                    "content_cards": self.content_cards,
                "home_columns": self.home_columns,
                "home_column_widths": self.home_column_widths,
                "home_sort": self.home_sort,
                "home_split": self.home_split,
                "window_opacity": self.window_opacity,
                "libraries": self.libraries,
                    "wall_prefs": self.wall_prefs,
                    "actor_prefs": self.actor_prefs,
                    "recommend": self.recommend,          # v1.24.0
                    "dedupe": self.dedupe,
                    "export": self.export,
                    "insight": self.insight,              # v1.24.1
                    "vector_overrides": self.vector_overrides,
                    "autofill": self.autofill,            # v1.34.0 画像自动填充偏好
                    "seen_smart": self.seen_smart,
                    "smart_history": self.smart_history,
                    "tagopt": self.tagopt,
                    "background": self.background,
                    "appearance": self.appearance,
                    "scraper": self.scraper,
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------- 导航菜单 ----------
    def nav_visible(self, key: str) -> bool:
        for x in self.nav:
            if x["key"] == key:
                return x.get("visible", True)
        return True

    def set_nav_visible(self, key: str, visible: bool):
        for x in self.nav:
            if x["key"] == key:
                x["visible"] = visible
        self.save()

    def move_nav(self, key: str, delta: int):
        idx = next((i for i, x in enumerate(self.nav) if x["key"] == key), None)
        if idx is None:
            return
        j = idx + delta
        if 0 <= j < len(self.nav):
            self.nav[idx], self.nav[j] = self.nav[j], self.nav[idx]
            self.save()

    # ---------- 首页列设置 ----------
    def set_home_columns(self, keys: list):
        valid = {k for k, _ in HOME_COLUMNS}
        self.home_columns = [k for k in keys if k in valid]
        self.save()

    def set_home_column_widths(self, widths: dict):
        self.home_column_widths = {
            str(k): int(v) for k, v in (widths or {}).items() if isinstance(v, (int, float))}
        self.save()

    def set_home_sort(self, key, asc: bool):
        self.home_sort = {"key": key, "asc": bool(asc)}
        self.save()

    def set_home_split(self, sizes: list):
        vals = [int(x) for x in (sizes or []) if isinstance(x, (int, float)) and int(x) > 0]
        self.home_split = vals[:2]
        self.save()

    def set_window_opacity(self, v: float):
        self.window_opacity = max(0.2, min(1.0, float(v)))
        self.save()

    # ---------- 影片墙 / 演员库 筛选 + 排序（v1.14.0） ----------
    def set_wall_prefs(self, sort: str = None, asc: bool = None, filters: dict = None):
        if sort:
            self.wall_prefs["sort"] = sort
        if isinstance(asc, bool):
            self.wall_prefs["asc"] = asc
        if filters is not None:
            self.wall_prefs = _clean_prefs(
                {"sort": self.wall_prefs["sort"], "asc": self.wall_prefs["asc"],
                 "filters": filters,
                 "facet_open": self.wall_prefs.get("facet_open", False)},
                DEFAULT_WALL_PREFS, WALL_FILTER_KEYS)
        self.save()

    def set_facet_open(self, open_: bool):
        """v1.17.0：记下影片墙筛选面板的展开 / 收缩状态（不触发列表重建）。"""
        self.wall_prefs["facet_open"] = bool(open_)
        self.save()

    def set_actor_prefs(self, sort: str = None, asc: bool = None, filters: dict = None):
        if sort:
            self.actor_prefs["sort"] = sort
        if isinstance(asc, bool):
            self.actor_prefs["asc"] = asc
        if filters is not None:
            self.actor_prefs = _clean_prefs(
                {"sort": self.actor_prefs["sort"], "asc": self.actor_prefs["asc"],
                 "filters": filters}, DEFAULT_ACTOR_PREFS, ACTOR_FILTER_KEYS)
        self.save()

    # ---------- v1.24.0：智能推荐 / 重复检测 / 数据导出 / 向量编辑 ----------
    def set_recommend(self, **kw):
        """更新智能推荐偏好（只认识 DEFAULT_RECOMMEND 里的键）。"""
        for k, v in kw.items():
            if k in DEFAULT_RECOMMEND:
                self.recommend[k] = v
        self.recommend["algo"] = "ai" if self.recommend.get("algo") == "ai" else "normal"
        try:
            self.recommend["count"] = max(6, min(120, int(self.recommend.get("count", 24))))
        except Exception:
            self.recommend["count"] = 24
        for k in ("use_tags", "use_actors", "use_directors", "exclude_watched"):
            self.recommend[k] = bool(self.recommend.get(k, True))
        self._sanitize_recommend()
        try:
            self.recommend["diversity"] = max(0.0, min(0.9, float(self.recommend.get("diversity", 0.35))))
        except Exception:
            self.recommend["diversity"] = 0.35
        self.save()

    def set_dedupe_prefs(self, **kw):
        if "exclude_multipart" in kw:
            self.dedupe["exclude_multipart"] = bool(kw["exclude_multipart"])
        if "min_confidence" in kw:
            self.dedupe["min_confidence"] = str(kw["min_confidence"])
        # v1.32.0（反馈 1）：重复检测也能选「普通 / AI」算法了，偏好跟另外几个
        # 检测页**同一套键名**（algo / fast），这样 setting 面板之间不会各存一份。
        if "algo" in kw:
            self.dedupe["algo"] = "ai" if str(kw["algo"]) == "ai" else "normal"
        if "fast" in kw:
            self.dedupe["fast"] = bool(kw["fast"])
        self.save()

    def set_export_sections(self, keys: list):
        valid = {k for k, _ in EXPORT_SECTIONS}
        self.export = {"sections": [k for k in (keys or []) if k in valid]}
        self.save()

    def export_sections(self) -> list:
        secs = self.export.get("sections") if isinstance(self.export, dict) else None
        return list(secs) if secs else [k for k, _ in EXPORT_SECTIONS]

    def set_insight_scope(self, scope=None, favorites_only=False):
        """记录画像概览的统计范围（v1.24.1 反馈 4）：scope=None 表示全部媒体库。"""
        self.insight = {"scope": str(scope or ""), "favorites_only": bool(favorites_only)}
        self.save()

    def set_vector_weight(self, dim: str, key: str, weight: float):
        """写一条向量编辑（0 = 屏蔽该键；None 权重传 0）。"""
        dim = str(dim)
        bucket = self.vector_overrides.setdefault(dim, {})
        if weight is None:
            bucket.pop(str(key), None)
        else:
            bucket[str(key)] = float(weight)
        if not bucket:
            self.vector_overrides.pop(dim, None)
        self.save()

    def clear_vector(self, dim: str = None):
        if dim is None:
            self.vector_overrides = {}
        else:
            self.vector_overrides.pop(str(dim), None)
        self.save()

    def remember_smart(self, ids: list):
        """记录「刚刚推荐过」的 media id（v1.25.0 起等价于「追加一轮」）。"""
        self.push_smart_round(ids)

    # ---------- v1.25.0（反馈 3）：推荐历史按轮次 ----------
    def push_smart_round(self, ids, keep=None):
        """把本轮推荐的作品记成 1 轮（每点一次「换一批」/ 重进推荐页 = 1 轮）。"""
        clean = []
        for i in (ids or []):
            try:
                i = int(i)
            except (TypeError, ValueError):
                continue
            if i not in clean:
                clean.append(i)
        if not clean:
            return
        rnd = (self.smart_history[-1]["round"] + 1) if self.smart_history else 1
        self.smart_history.append({"round": rnd, "ids": clean, "ts": time.time()})
        self._prune_smart_history(keep)
        # 兼容旧键：同步一份扁平列表（老版本 / 旧导出包只认它）
        flat = []
        for r in self.smart_history:
            for i in r.get("ids", []):
                if i not in flat:
                    flat.append(i)
        self.seen_smart = flat[-200:]
        self.save()

    def recent_smart_ids(self, rounds=None) -> list:
        """最近 N 轮推荐过的 id（顺序去重）。N <= 0 视为「不限制」→ 返回空列表。"""
        if rounds is None:
            try:
                rounds = int(self.recommend.get("no_repeat_rounds", 3))
            except (TypeError, ValueError):
                rounds = 3
        try:
            rounds = int(rounds)
        except (TypeError, ValueError):
            return []
        if rounds <= 0:
            return []
        out = []
        for r in (self.smart_history or [])[-rounds:]:
            for i in r.get("ids", []):
                if i not in out:
                    out.append(i)
        return out

    def clear_smart_history(self):
        """忘掉之前推荐过哪些作品（下次从头开始推，但「已收藏的不推荐」仍然生效）。"""
        self.smart_history = []
        self.seen_smart = []
        self.save()

    @staticmethod
    def _clean_smart_history(raw) -> list:
        """只接受 [{"round": int, "ids": [int, ...]}]，脏数据一律丢掉。"""
        out = []
        if not isinstance(raw, list):
            return out
        for item in raw:
            if not isinstance(item, dict):
                continue
            ids = []
            for i in (item.get("ids") or []):
                try:
                    i = int(i)
                except (TypeError, ValueError):
                    continue
                if i not in ids:
                    ids.append(i)
            if not ids:
                continue
            try:
                rnd = int(item.get("round") or (len(out) + 1))
            except (TypeError, ValueError):
                rnd = len(out) + 1
            try:
                ts = float(item.get("ts") or 0.0)
            except (TypeError, ValueError):
                ts = 0.0
            out.append({"round": rnd, "ids": ids, "ts": ts})
        return out

    def _prune_smart_history(self, keep=None):
        """只留最近 keep 轮；留的轮数必须 ≥ 用户设的「不重复轮数」，否则去重会失效。"""
        if keep is None:
            try:
                n = int(self.recommend.get("no_repeat_rounds", 3))
            except (TypeError, ValueError):
                n = 3
            keep = max(20, n * 3 + 5)
        keep = max(1, int(keep))
        if len(self.smart_history) > keep:
            self.smart_history = self.smart_history[-keep:]

    # ---------- v1.25.0：偏好清洗 ----------
    def _sanitize_recommend(self):
        """把 v1.25.0 新加的两个键收窄到合法范围（load / set_recommend 共用）。"""
        m = re.sub(r"[^0-9A-Za-z_.:\-/]", "",
                   str(self.recommend.get("ai_model") or "").strip())[:64]
        self.recommend["ai_model"] = m
        try:
            self.recommend["no_repeat_rounds"] = max(
                0, min(50, int(self.recommend.get("no_repeat_rounds", 3))))
        except (TypeError, ValueError):
            self.recommend["no_repeat_rounds"] = 3
        self.recommend["use_userrating"] = bool(
            self.recommend.get("use_userrating", False))

    # --------- v1.34.0（需求 1）：画像自动填充偏好 ---------
    AUTOFILL_DIMS = ("tag", "studio", "series", "actor", "director")
    # v1.34.2（用户反馈 2）：原来上限是 200，但「取前 N 个」的 SpinBox 宽度只够 2 位、
    # 第 3 位会被吞（实测只能写 99）；而且 insight.Portrait 榜单写死 most_common(30)
    # 截断，填 999 实际也只写 30 条。现在上限提到 999，且必须真正支持到 999
    # （见 insight.py 的 PORTRAIT_TOP 与榜单 most_common 对齐）。
    AUTOFILL_TOP_RANGE = (1, 999)
    AUTOFILL_W_RANGE = (0.0, 5.0)

    @classmethod
    def _clean_autofill(cls, raw=None) -> dict:
        """把落盘的 autofill 配置清洗成合法值（load 与 set_autofill 共用）。

        逐键白名单 + 范围钳制；任何脏值都退回默认，**绝不抛**。
        """
        out = json.loads(json.dumps(DEFAULT_AUTOFILL))
        if not isinstance(raw, dict):
            return out
        out["scope"] = str(raw.get("scope") or "")[:120]
        out["favorites_only"] = str(raw.get("favorites_only", False)).strip().lower() \
            not in ("", "0", "false", "no", "off")
        dims = raw.get("dims")
        if isinstance(dims, dict):
            lo_t, hi_t = cls.AUTOFILL_TOP_RANGE
            lo_w, hi_w = cls.AUTOFILL_W_RANGE
            for d in cls.AUTOFILL_DIMS:
                src = dims.get(d)
                if not isinstance(src, dict):
                    continue
                dst = out["dims"][d]
                dst["on"] = str(src.get("on", dst["on"])).strip().lower() \
                    not in ("", "0", "false", "no", "off")
                try:
                    dst["top"] = max(lo_t, min(hi_t, int(src.get("top", dst["top"]))))
                except (TypeError, ValueError):
                    pass
                try:
                    w = float(src.get("w", dst["w"]))
                    dst["w"] = round(max(lo_w, min(hi_w, w)), 2)
                except (TypeError, ValueError):
                    pass
        return out

    def set_autofill(self, **kw):
        """更新画像自动填充偏好（只认识 scope / favorites_only / dims）。"""
        raw = dict(self.autofill or {})
        for k in ("scope", "favorites_only", "dims"):
            if k in kw:
                raw[k] = kw[k]
        self.autofill = self._clean_autofill(raw)
        self.save()
        return self.autofill

    def _sanitize_tagopt(self):
        if self.tagopt.get("scope") not in ("file", "folder", "library"):
            self.tagopt["scope"] = "file"
        self.tagopt["algo"] = "ai" if self.tagopt.get("algo") == "ai" else "normal"
        for k in ("translate", "overwrite", "complete", "backup"):
            self.tagopt[k] = bool(self.tagopt.get(k, DEFAULT_TAGOPT[k]))
        self.tagopt["path"] = str(self.tagopt.get("path") or "")[:500]
        self.tagopt["library"] = str(self.tagopt.get("library") or "")[:120]

    # ---------- 媒体库（统一：名称即身份，全部由用户自己创建 / 命名 / 删除） ----------
    def library(self, name: str):
        """按名字取媒体库配置（不存在返回 None）。"""
        return next((x for x in self.libraries if x["name"] == name), None)

    def library_names(self):
        return [x["name"] for x in self.libraries]

    def add_library(self, name: str, kind: str, paths: list, filt: dict = None) -> bool:
        """新建媒体库；同名视为更新其配置。返回 True 表示写入成功。"""
        name = (name or "").strip()
        if not name:
            return False
        for x in self.libraries:
            if x["name"] == name:
                x["kind"] = kind or x.get("kind") or "混合"
                x["paths"] = list(paths or [])
                if filt is not None:
                    x["filter"] = filt
                self.save()
                return True
        self.libraries.append({"name": name, "kind": kind or "混合",
                               "paths": list(paths or []), "filter": filt or {}})
        self.save()
        return True

    def update_library(self, old_name: str, name: str, kind: str, paths: list) -> bool:
        """编辑已有媒体库（可能改名）。返回 True 表示成功。"""
        name = (name or "").strip()
        if not name:
            return False
        for x in self.libraries:
            if x["name"] == old_name:
                x["name"] = name
                x["kind"] = kind or x.get("kind") or "混合"
                x["paths"] = list(paths or [])
                self.save()
                return True
        return False

    def rename_library(self, old_name: str, new_name: str) -> bool:
        """只改名（类型 / 路径 / 筛选保持不变）。"""
        lib = self.library(old_name)
        if not lib:
            return False
        return self.update_library(old_name, new_name, lib.get("kind", "混合"),
                                   lib.get("paths", []))

    def set_library_paths(self, name: str, paths: list) -> bool:
        lib = self.library(name)
        if not lib:
            return False
        lib["paths"] = list(paths or [])
        self.save()
        return True

    def remove_library(self, name: str):
        """从列表移除媒体库（不删索引记录、不动磁盘文件）。删掉不会再自动恢复。"""
        self.libraries = [x for x in self.libraries if x["name"] != name]
        self.save()

    # ---------- 外观 ----------
    def set_appearance(self, mode: str = None, level: str = None, accent: str = None,
                       show_stats: bool = None, show_sysmon: bool = None,
                       language: str = None):
        if mode in APPEARANCE_MODES:
            self.appearance["mode"] = mode
        if level in GLASS_LEVELS:
            self.appearance["level"] = level
        if accent and any(h.lower() == str(accent).lower() for _n, h in ACCENT_COLORS):
            self.appearance["accent"] = str(accent)
        # v1.28.0（反馈 1）：侧栏「数据统计」/「实时状态」显隐
        if show_stats is not None:
            self.appearance["show_stats"] = bool(show_stats)
        if show_sysmon is not None:
            self.appearance["show_sysmon"] = bool(show_sysmon)
        # v1.32.0（反馈 3）：界面语言。**必须走 i18n.normalize()** ——
        # 校验和归一化只留一处真源，否则「设置里存的语言」和「实际生效的语言」
        # 会漂移（改天加了新语种就更容易出这种事）。
        if language is not None:
            import i18n
            self.appearance["language"] = i18n.normalize(language)
        self.save()

    # v1.32.0（反馈 3）：界面语言读写
    def language(self) -> str:
        import i18n
        return i18n.normalize(self.appearance.get("language"))

    # v1.25.0（反馈 5）：高亮色 —— 卡片选中 / 外发光 / 强调色都用它
    def accent(self) -> str:
        return self.appearance.get("accent") or ACCENT_DEFAULT

    def set_accent(self, hexv: str):
        self.set_appearance(accent=hexv)

    # ---------- v1.25.0（反馈 4）：标签优化 ----------
    def set_tagopt(self, **kw):
        for k, v in kw.items():
            if k in DEFAULT_TAGOPT:
                self.tagopt[k] = v
        self._sanitize_tagopt()
        self.save()

    def glass_alphas(self):
        return appearance_alphas(self.appearance)

    # ---------- 演员刮削 ----------
    def set_scraper(self, **kw):
        self.scraper.update(kw)
        self.save()

    def scraper_sources(self):
        """按优先级返回已启用且已勾选的数据源 key。"""
        en = self.scraper.get("sources_enabled") or {}
        return [k for k in self.scraper.get("sources", []) if en.get(k, True)]

    def move_scraper_source(self, key: str, delta: int):
        src = list(self.scraper.get("sources", []))
        if key not in src:
            return
        i = src.index(key)
        j = i + delta
        if 0 <= j < len(src):
            src[i], src[j] = src[j], src[i]
            self.scraper["sources"] = src
            self.save()

    def scraper_photo_dir(self) -> str:
        d = (self.scraper.get("photo_dir") or "").strip()
        if d:
            return d
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "cache", "people")


_SETTINGS = None


def get_settings() -> Settings:
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = Settings()
    return _SETTINGS
