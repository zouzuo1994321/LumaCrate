# -*- coding: utf-8 -*-
"""v2.0.0：把 dev/smoke_v1430.py 里「绑死在旧配色/旧形状」的断言改成 v2 口径。

原则：**不删断言、不放宽判据**，只把常量换成本版真值；每条都要求旧串命中，
否则报出来（防止模板漂了之后静默跳过）。
"""
import io
import os

P = r"E:\【01】自研软件\【26-19】本地影视中心\dev\smoke_v1430.py"
s = io.open(P, encoding="utf-8").read()
miss = []


def rep(old, new, tag):
    global s
    if old not in s:
        miss.append(tag)
        return
    s = s.replace(old, new, 1)
    print("OK   " + tag)


# 1) 主窗不透明底色：墨黑 #0d0b0a → HeroUI 页面底 #0a0a0b
rep('''check("QMainWindow 使用不透明底色（不再 transparent）",
      "QMainWindow { background: #0d0b0a; }" in qss)''',
    '''check("QMainWindow 使用不透明底色（v2.0.0：HeroUI 页面底 #0a0a0b）",
      "QMainWindow { background: #0a0a0b; }" in qss)''', "主窗底色 #0a0a0b")

# 2) 状态栏：面板色 #1c1815 / hover #241f1b → #111113 / #17171a
rep('''check("状态栏为不透明面板色（v1.43.4：不再是近纯黑 #0f0d0b）",
      "background: #1c1815" in qss and "background: #241f1b" in qss
      and "background: #0f0d0b" not in qss)''',
    '''check("状态栏为不透明面板色（v2.0.0：#111113，hover #17171a；不再是近纯黑 #0f0d0b）",
      "background: #111113" in qss and "background: #17171a" in qss
      and "background: #0f0d0b" not in qss)''', "状态栏面板色")

# 3) 滑块把手：v1.43.5 的 18×12 扁平方形 → v2.0.0 的 18×18 正圆
rep('''check("滑块把手为 18×12 圆角扁平方形（radius 4，不再是 16/radius 8）",
      "width: 18px; margin: -3px 0; border-radius: 4px;" in _qss2)''',
    '''check("滑块把手为 18×18 正圆（radius 9，HeroUI 纯白圆点）",
      "width: 18px; height: 18px; margin: -6px 0; border-radius: 9px;" in _qss2)''',
    "滑块把手 18x18")

# 4) 色卡：v1.43.4 的 30×24 扁平方形 → v2.0.0 的 28×28 正圆
rep('''check("色卡为 30x24 圆角扁平方形",
      bool(_sw) and all(b.width() == 30 and b.height() == 24 for b in _sw),
      f"{_sw[0].width()}x{_sw[0].height()}" if _sw else "无")''',
    '''check("色卡为 28x28 正圆（HeroUI 色点，选中套白环 + 勾）",
      bool(_sw) and all(b.width() == 28 and b.height() == 28 for b in _sw),
      f"{_sw[0].width()}x{_sw[0].height()}" if _sw else "无")''',
    "色卡 28x28")

# 5) 性别符号配色：旧粉/旧蓝 → HeroUI 玫红/天青
rep('''check("卡片显示 ♀（粉）", "♀" in _card_f._name.text() and "#e6739f" in _card_f._name.text())
check("卡片显示 ♂（蓝）", "♂" in _card_m._name.text() and "#5aa9e6" in _card_m._name.text())''',
    '''check("卡片显示 ♀（玫红 #f31260）",
      "♀" in _card_f._name.text() and "#f31260" in _card_f._name.text())
check("卡片显示 ♂（天青 #338ef7）",
      "♂" in _card_m._name.text() and "#338ef7" in _card_m._name.text())''',
    "性别符号配色")

# 6) 悬停卡不透明底：#17130f → #18181b
rep('''check("反馈2 悬停卡不再半透明（列表文字不会透上来）",
      "#17130f" in _card_seg and "__DLG__" not in _card_seg, _card_seg.split("}")[0])''',
    '''check("反馈2 悬停卡不再半透明（v2.0.0：#18181b，列表文字不会透上来）",
      "#18181b" in _card_seg and "__DLG__" not in _card_seg, _card_seg.split("}")[0])''',
    "悬停卡底色")

# 7) 「强调色像素」计数：原来判红（r>110 且 r-g>40 且 r-b>35），换蓝色后恒为 0
rep('''def _accent_n(_im):
    _n = 0
    _px = _im.load()
    for _y in range(_im.height):
        for _x in range(_im.width):
            _r, _g, _b = _px[_x, _y]
            if _r > 110 and _r - _g > 40 and _r - _b > 35:
                _n += 1
    return _n''',
    '''def _accent_n(_im):
    """数「强调色」像素：与**当前高亮色**三通道差都 <= 46。

    v1 时这里写死判红（r>110 且 r-g>40 且 r-b>35）；v2.0.0 默认色换成 #006fee
    之后那套判据恒为 0（三条断言集体假红）。改成按 ACCENT_RGB 做距离判定，
    换任何高亮色都成立，也不再叫「朱红像素」。
    """
    _ar, _ag, _ab = tuple(mw.ACCENT_RGB)[:3]
    _n = 0
    _px = _im.load()
    for _y in range(_im.height):
        for _x in range(_im.width):
            _r, _g, _b = _px[_x, _y]
            if max(abs(_r - _ar), abs(_g - _ag), abs(_b - _ab)) <= 46:
                _n += 1
    return _n''', "强调色像素计数")

rep('''     _bg = _PILImage.new("RGB", (_iw, _ih), (34, 29, 25))'''.replace("     _bg", "    _bg"),
    '''    _bg = _PILImage.new("RGB", (_iw, _ih), (17, 17, 19))''', "垫底色改中性")

for _old, _new in (
        ('check("进度条不确定态高亮", _n1 > 0, "朱红像素=%d" % _n1)',
         'check("进度条不确定态高亮", _n1 > 0, "强调色像素=%d" % _n1)'),
        ('check("进度条确定态(45%)高亮", _n2 > 0, "朱红像素=%d" % _n2)',
         'check("进度条确定态(45%)高亮", _n2 > 0, "强调色像素=%d" % _n2)'),
        ('check("快闪后 30ms 仍可见朱红（最短可见时长）", _n3 > 0,\n      "朱红像素=%d（未修时恒为 0）" % _n3)',
         'check("快闪后 30ms 仍可见高亮色（最短可见时长）", _n3 > 0,\n      "强调色像素=%d（未修时恒为 0）" % _n3)'),
        ('check("进度条空闲 = 空槽（0 朱红像素）", _accent_n(_img_of(_bb)) == 0,',
         'check("进度条空闲 = 空槽（0 强调色像素）", _accent_n(_img_of(_bb)) == 0,'),
):
    rep(_old, _new, "措辞：" + _new[:26])

# 8) 迁移顺序的文本序判据是错的（ACCENT_COLORS 在文件顶部还有定义处），改成功能性验证：
#    真造一份「accent = 旧朱红」的 settings.json，走一遍 load()，看是否落到新色板。
rep('''# load() 里迁移必须发生在「必须是色板之一」的归一闪**之前**，否则等于没迁
_src_cfg = open(os.path.join(ROOT, "src", "config.py"), encoding="utf-8").read()
_i_map = _src_cfg.find("LEGACY_ACCENT_MAP.get")
_i_norm = _src_cfg.find('ACCENT_COLORS')
check("load() 里的迁移点出现在色板归一之前（文本序）",
      _i_map > 0 and _i_norm > 0 and _i_map < _i_norm,
      "map@%d colors@%d" % (_i_map, _i_norm))''',
    '''# load() 里迁移必须发生在「必须是色板之一」的归一闪**之前**。
# 别用文本序判（ACCENT_COLORS 在文件顶部还有定义处，find 到的是那一处），
# 直接造老配置跑一遍 load() —— 这才是真行为。
import json as _json
_cfg_file = cfg.config_path()
_old_settings = getattr(cfg, "_SETTINGS", None)
try:
    for _old_hex, _want in (("#c0392b", "#f31260"), ("#d4af37", "#eab308"),
                            ("#f31260", "#f31260")):
        with open(_cfg_file, "w", encoding="utf-8") as _f:
            _json.dump({"appearance": {"accent": _old_hex, "style": "glass"}},
                       _f, ensure_ascii=False)
        cfg._SETTINGS = None
        _got = cfg.get_settings().appearance.get("accent")
        check("老配置 accent=%s 载入后迁成 %s（迁移幂等，已在新色板的值不动）"
              % (_old_hex, _want),
              _got == _want, str(_got))
finally:
    cfg._SETTINGS = _old_settings''', "迁移功能性验证")

io.open(P, "w", encoding="utf-8").write(s)
print()
if miss:
    print("!! 未命中 %d 条：" % len(miss))
    for m in miss:
        print("   ", m)
else:
    print("全部命中。")
