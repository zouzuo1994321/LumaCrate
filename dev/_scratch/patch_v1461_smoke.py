# -*- coding: utf-8 -*-
"""v1.46.1：升版 + 冒烟新增「切页无弹窗 / 滚动增量换卡」断言。"""
import io

V = r"E:/【01】自研软件/【26-19】本地影视中心/src/version.py"
s = io.open(V, encoding="utf-8").read()
s = s.replace(
    'MINOR_ITER = 0           # 小版本迭代 -> 第三位（功能版本，Z 归 0）',
    'MINOR_ITER = 1           # 小版本迭代 -> 第三位（v1.46.1：修「切页弹窗/滚动闪烁」——tooltip 收起 + 绝对定位增量换卡 + 渲染失效保护）')
s = s.replace('BUILD_SEQ = "0102"', 'BUILD_SEQ = "0103"')
io.open(V, "w", encoding="utf-8", newline="\n").write(s)
print("version ok", "v1.46.1" in s and "0103" in s)

P = r"E:/【01】自研软件/【26-19】本地影视中心/dev/smoke_v1430.py"
t = io.open(P, encoding="utf-8").read()
t = t.replace('check("VERSION == v1.46.0", VER.VERSION == "v1.46.0", VER.VERSION)',
              'check("VERSION == v1.46.1", VER.VERSION == "v1.46.1", VER.VERSION)')
t = t.replace('check("BUILD == 2610230102", VER.BUILD == "2610230102", VER.BUILD)',
              'check("BUILD == 2610230103", VER.BUILD == "2610230103", VER.BUILD)')

block = '''
# ============================================================
print("== ⑬ v1.46.1：切页无弹窗 / 滚动增量换卡 ==")
_mw_src = open(os.path.join(ROOT, "src", "main_window.py"), encoding="utf-8").read()
check("切页时收起残留 tooltip", "QToolTip.hideText" in _mw_src)
check("虚拟化用绝对定位（不再先清后建）", "_cards" in _mw_src and "setGeometry(" in _mw_src)

# —— 同一实例滚一行：只应新建约 1 行的卡片
_sc2 = mw.QScrollArea(); _h2 = mw.QWidget(); _l2 = mw.QVBoxLayout(_h2)
_l2.setContentsMargins(0, 0, 0, 0)
_data = [{"id": i, "title": "V%d" % i} for i in range(3000)]
_vg2 = mw.LazyGrid(lambda o, l: _data[o:o + l],
                   lambda it: mw.QFrame().setFixedSize(200, 120) or None, len(_data),
                   kind="media", virtual=True)
# 上面 lambda 返回 None，换成品：直接用一个小工厂
class _Box(mw.QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedSize(200, 120)
_vg2._make = lambda it: _Box()
_l2.addWidget(_vg2); _sc2.setWidget(_h2); _sc2.setWidgetResizable(True)
_sc2.resize(900, 700); _sc2.show()
_vg2.attach_scroll(_sc2.verticalScrollBar(), _sc2.viewport())
for _ in range(6):
    app.processEvents()
_vg2._render()
for _ in range(3):
    app.processEvents()
_n0 = len(_vg2._cards)
_made = []
_orig_make = _vg2._make
_vg2._make = lambda it: (_made.append(1), _orig_make(it))[1]
_sb2 = _sc2.verticalScrollBar()
_sb2.setValue(_sb2.value() + _vg2._row_h)
for _ in range(3):
    app.processEvents()
_vg2._render()
check("滚一行只新建约一行卡片（增量换卡）",
      0 < len(_made) <= _vg2._cols * 2, "%d 张 / cols=%d" % (len(_made), _vg2._cols))
check("卡片总数保持在窗口规模", len(_vg2._cards) <= _n0 + _vg2._cols, len(_vg2._cards))
check("滚动后不残留旧窗口外控件", len(_vg2._cards) == len(_vg2._built))
_sc2.close()
'''
t = t.replace('print()\nprint("通过 %d/%d"', block + '\nprint()\nprint("通过 %d/%d"')
io.open(P, "w", encoding="utf-8", newline="\n").write(t)
print("smoke patched", "⑬ v1.46.1" in t)
