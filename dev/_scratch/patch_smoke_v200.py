# -*- coding: utf-8 -*-
"""给 dev/smoke_v1430.py 打 v2.0.0 补丁：改版本断言 + 追加 ㉗ 段（HeroUI 组件套件）。"""
import io

P = r"E:\【01】自研软件\【26-19】本地影视中心\dev\smoke_v1430.py"
s = io.open(P, encoding="utf-8").read()

# ---- 1) 版本断言 ----
old = '''check("VERSION == v1.46.15", VER.VERSION == "v1.46.15", VER.VERSION)
check("BUILD == 2610290118", VER.BUILD == "2610290118", VER.BUILD)'''
new = '''check("VERSION == v2.0.0", VER.VERSION == "v2.0.0", VER.VERSION)
check("BUILD == 2610290119", VER.BUILD == "2610290119", VER.BUILD)'''
assert old in s, "版本断言未命中"
s = s.replace(old, new, 1)

# ---- 2) 追加 ㉗ 段 ----
TAIL = '''print("通过 %d/%d" % (TOTAL[0] - len(FAILS), TOTAL[0]))'''
assert TAIL in s, "结尾未命中"

SEC = '''# =============== ㉗ v2.0.0：组件套件切 HeroUI 暗色语言 ===============
print("== ㉗ v2.0.0：HeroUI 组件套件 / 色板迁移 / 拖拽条原样保留 ==")
import ui_actorcheck as uac

# ---- 色板 ----
check("色板换成 HeroUI 语义 11 色",
      len(cfg.ACCENT_COLORS) == 11, len(cfg.ACCENT_COLORS))
check("默认高亮色是 HeroUI primary #006fee",
      cfg.ACCENT_DEFAULT == "#006fee", cfg.ACCENT_DEFAULT)
check("色板里每个 hex 都合法且不重复",
      len({h for _n, h in cfg.ACCENT_COLORS}) == 11
      and all(len(h) == 7 and h.startswith("#") for _n, h in cfg.ACCENT_COLORS),
      str([h for _n, h in cfg.ACCENT_COLORS]))
check("默认色确实在色板里（否则载入会被归一闪打回默认，看不出差别）",
      cfg.ACCENT_DEFAULT in [h for _n, h in cfg.ACCENT_COLORS])

# ---- 旧色迁移表：必须**幂等**，否则老用户升级后每存一次配置就漂一格 ----
_MAP = cfg.LEGACY_ACCENT_MAP
check("旧朱红 #c0392b 迁到玫红 #f31260",
      _MAP.get("#c0392b") == "#f31260", _MAP.get("#c0392b"))
check("旧鎏金 #d4af37 迁到琥珀金 #eab308",
      _MAP.get("#d4af37") == "#eab308", _MAP.get("#d4af37"))
check("迁移表是幂等的：映射目标本身不再被映射（不会二次漂移）",
      all(v not in _MAP for v in _MAP.values()),
      str([v for v in _MAP.values() if v in _MAP]))
check("迁移目标全部落在新色板里（否则归一闪会把它打回默认）",
      all(v in [h for _n, h in cfg.ACCENT_COLORS] for v in _MAP.values()),
      str([v for v in _MAP.values() if v not in [h for _n, h in cfg.ACCENT_COLORS]]))

# load() 里迁移必须发生在「必须是色板之一」的归一闪**之前**，否则等于没迁
_src_cfg = open(os.path.join(ROOT, "src", "config.py"), encoding="utf-8").read()
_i_map = _src_cfg.find("LEGACY_ACCENT_MAP.get")
_i_norm = _src_cfg.find('ACCENT_COLORS')
check("load() 里的迁移点出现在色板归一之前（文本序）",
      _i_map > 0 and _i_norm > 0 and _i_map < _i_norm,
      "map@%d colors@%d" % (_i_map, _i_norm))

# ---- 派生色：亮度必须单调，不然按下态会比常态更亮 ----
def _lum(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


_sh = cfg.accent_shades("#006fee")
check("accent_shades 仍返回 base/dark/deep/light 四档",
      set(_sh) == {"base", "dark", "deep", "light"}, str(sorted(_sh)))
check("base 就是原色", _sh["base"] == (0, 111, 238), str(_sh["base"]))
check("dark < deep < base < light（亮度单调，按下不会比常态更亮）",
      _lum(_sh["dark"]) < _lum(_sh["deep"]) < _lum(_sh["base"]) < _lum(_sh["light"]),
      "%.1f/%.1f/%.1f/%.1f" % (_lum(_sh["dark"]), _lum(_sh["deep"]),
                              _lum(_sh["base"]), _lum(_sh["light"])))
check("对每个色板色都能派生（不抛异常、四档齐全）",
      all(set(cfg.accent_shades(h)) == {"base", "dark", "deep", "light"}
          for _n, h in cfg.ACCENT_COLORS))

# ---- QSS：新令牌渲染干净 + 旧墨金不再出现 ----
_q = mw.render_style({"accent": "#006fee", "style": "glass", "alpha": None})
_import_re = __import__("re")
# 注释里会提到「原来是与墨金底衬配套的 #1c1815」这类历史说明，检查必须去掉注释
_qb = _import_re.sub(r"/\\*.*?\\*/", "", _q, flags=_import_re.S)
check("渲染后没有剩下任何 __XXX__ 令牌",
      _import_re.search(r"__[A-Z_]+__", _q) is None,
      str(_import_re.findall(r"__[A-Z_]+__", _q)[:6]))
check("render_style 顺手把 ACCENT_RGB 刷成 (0, 111, 238)",
      tuple(mw.ACCENT_RGB) == (0, 111, 238), str(mw.ACCENT_RGB))
check("QSS 里已无旧鎏金 #d4af37", "#d4af37" not in _qb.lower())
check("QSS 里已无旧墨底 #1c1815", "#1c1815" not in _qb.lower())
check("QSS 用上了 HeroUI 中性色阶 #0a0a0b / #18181b / #27272a",
      all(c in _qb.lower() for c in ("#0a0a0b", "#18181b", "#27272a")))
check("选中态改成高亮色柔光底 rgba(0, 111, 238, 0.22)",
      "rgba(0, 111, 238, 0.22)" in _q)

# 裸令牌必须替换成 #rrggbb（塞 "r, g, b" 会让整条声明被 Qt 静默丢掉）
_bad = _import_re.findall(r":\\s*\\d+,\\s*\\d+,\\s*\\d+\\s*;", _q)
check("没有把 \\"r, g, b\\" 误填成裸值（那会让整条声明被丢掉）",
      not _bad, str(_bad[:4]))

# ---- 拖拽条：用户明确要求「只保留这两条拖拽条」→ handle 必须仍是透明的 ----
for _name in ("ActorSplitV", "ActorSplitH", "ImageSplitH"):
    _key = "QSplitter#%s::handle" % _name
    check("QSS 仍有 %s 规则（拖拽条不许被重写掉）" % _key, _key in _q, _key)
    _seg2 = _q.split(_key, 1)[1].split("}", 1)[0] if _key in _q else ""
    check("%s 仍是 transparent 且 margin: 0（把手靠自绘，不能被底色盖住）" % _name,
          "transparent" in _seg2 and "margin: 0" in _seg2,
          _seg2.strip().replace("\\n", " ")[:70])
check("自绘把手类 _GripHandle 仍在", hasattr(uac, "_GripHandle"))
check("_GripSplitter 仍在（5 点把手的分发器）", hasattr(uac, "_GripSplitter"))

# ---- 色卡：HeroUI 正圆 + 白环 + 勾 ----
check("_AccentSwatch 是 28×28 正圆尺寸", (uis._AccentSwatch.W, uis._AccentSwatch.H) == (28, 28),
      "%sx%s" % (uis._AccentSwatch.W, uis._AccentSwatch.H))
check("选中态用「色点缩一点 + 外环」两层（R_DOT_ON < R_DOT < R_RING）",
      uis._AccentSwatch.R_DOT_ON < uis._AccentSwatch.R_DOT < uis._AccentSwatch.R_RING,
      "%s/%s/%s" % (uis._AccentSwatch.R_DOT_ON, uis._AccentSwatch.R_DOT,
                    uis._AccentSwatch.R_RING))
_sw = uis._AccentSwatch("#006fee", "极光蓝")
_sw.set_on(True)
check("色卡实例的固定尺寸就是 28×28",
      (_sw.width(), _sw.height()) == (28, 28), "%dx%d" % (_sw.width(), _sw.height()))
_sw.set_on(False)
check("set_on(False) 可切回未选中（不抛异常）", True)

# ---- 开关轨道：旧的暖棕 → 中性，兜底开态 → HeroUI 蓝 ----
check("开关关态轨道换成 #3f3f46（原暖棕 #4a4038）",
      uis.ToggleSwitch._OFF == (0x3F, 0x3F, 0x46), str(uis.ToggleSwitch._OFF))
check("开关开态兜底换成 #006fee（原朱红 #c0392b）",
      uis.ToggleSwitch._ON == (0x00, 0x6F, 0xEE), str(uis.ToggleSwitch._ON))
check("开关绘制时仍现取高亮色（不自锁在兜底值）",
      uis.ToggleSwitch.accent_on() == (0, 111, 238), str(uis.ToggleSwitch.accent_on()))

# ---- 源码里不再有旧墨金色系（config.py 例外：迁移表的键就是旧值）----
_OLD_HEX = ("#d4af37", "#ece5d8", "#a2967f", "#8c8071", "#1c1815", "#2a241c",
            "#362e23", "#c0392b", "#e08a7a", "#9ecf8a")
_leak = []
for _fn in sorted(os.listdir(os.path.join(ROOT, "src"))):
    if not _fn.endswith(".py") or _fn in ("config.py", "version.py"):
        continue
    _txt = open(os.path.join(ROOT, "src", _fn), encoding="utf-8").read().lower()
    for _h in _OLD_HEX:
        if _h in _txt:
            _leak.append("%s:%s" % (_fn, _h))
check("src/*.py 里没有旧墨金色系残留（version.py 是历史记录、config.py 是迁移表）",
      not _leak, str(_leak[:8]))

# ---- 底衬跟着高亮色走（veil / 字母条都懒读 ACCENT_RGB）----
check("veil.accent_rgb() 取到当前高亮色",
      __import__("veil").accent_rgb() == (0, 111, 238),
      str(__import__("veil").accent_rgb()))
check("letter_index._accent_rgb() 取到当前高亮色",
      __import__("letter_index")._accent_rgb() == (0, 111, 238),
      str(__import__("letter_index")._accent_rgb()))

''' + TAIL

s = s.replace(TAIL, SEC, 1)
io.open(P, "w", encoding="utf-8").write(s)
print("patched:", len(s.splitlines()), "lines")
