# -*- coding: utf-8 -*-
"""v1.34.2 离屏冒烟：验证两条反馈修复（取前 N 上限 999 + 统计范围留白压缩）。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
sys.path.insert(0, SRC)

results = []


def chk(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL"), name, ("  " + extra) if extra else "")


from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

# 加载 style.qss（accent token 占位，使 CSS 合法；padding 规则决定 spinner 宽度）
qss = open(os.path.join(SRC, "style.qss"), encoding="utf-8").read()
for tok in ("__ACCENT__", "__ACCENT_DARK__", "__ACCENT_DEEP__", "__ACCENT_LIGHT__"):
    qss = qss.replace(tok, "#e05243")
app.setStyleSheet(qss)

import config as cfg

chk("AUTOFILL_TOP_RANGE==(1,999)", cfg.Settings.AUTOFILL_TOP_RANGE == (1, 999),
    str(cfg.Settings.AUTOFILL_TOP_RANGE))

import insight

chk("PORTRAIT_TOP==999", insight.PORTRAIT_TOP == 999, str(insight.PORTRAIT_TOP))
chk("MAX_TAGS>=999", insight.Portrait.MAX_TAGS >= 999, str(insight.Portrait.MAX_TAGS))

from collections import Counter

c = Counter({f"k{i}": i for i in range(1500)})
n = len(c.most_common(insight.PORTRAIT_TOP))
chk("most_common 上限=999", n == 999, f"len={n}")

# 模拟 AutoFillDialog 写入逻辑：取前 N=999 时应能切到 999 条
items = c.most_common(insight.PORTRAIT_TOP)
picked = items[:999]
chk("items[:999] 长度=999", len(picked) == 999, f"len={len(picked)}")

# ---- 对话框 UI 检查 ----
from ui_settings import AutoFillDialog

try:
    dlg = AutoFillDialog()
    dlg.show()                    # 必须先 show，否则几何未计算（g1.height() 会拿到默认值）
    app.processEvents()
    sp = dlg.dim_rows["tag"][1]
    chk("sp_top.max==999", sp.maximum() == 999, str(sp.maximum()))
    chk("sp_top 无后缀", sp.suffix() == "", repr(sp.suffix()))
    sp.setValue(999)
    chk("sp_top 显示 999", sp.text() == "999", repr(sp.text()))
    minw = sp.minimumSizeHint().width()
    chk("sp_top 三位宽够", minw >= 40, f"minW={minw}")

    dlg._fit_height()
    h = dlg.height()
    chk("对话框高度紧凑[420,900]", 420 <= h <= 900, str(h))
    print(f"  [info] dialog.height={h}")

    # 组框应钉 Fixed（不被拉伸）
    from PySide6.QtWidgets import QGroupBox, QSizePolicy
    gbs = dlg.findChildren(QGroupBox)
    chk("找到组框(>=2)", len(gbs) >= 2, str(len(gbs)))
    g1 = gbs[0] if gbs else None
    if g1 is not None:
        chk("统计范围组框 SizePolicy=Fixed", g1.sizePolicy().verticalPolicy() == QSizePolicy.Fixed,
            str(g1.sizePolicy().verticalPolicy()))
    else:
        chk("找到统计范围组框", False, "no groupbox")

    # v1.34.2 真根因回归：scope tip 必须「关闭换行 + 恒 1 行高」，组框不得虚高
    tip = dlg.lb_scope_tip
    chk("scope tip 不换行", tip.wordWrap() is False, str(tip.wordWrap()))
    lh = tip.fontMetrics().lineSpacing()
    chk("scope tip 恒 1 行高", tip.height() <= lh + 12, f"tipH={tip.height()} lh={lh}")
    if g1 is not None:
        chk("统计范围组框不再虚高", g1.height() < 140, f"g1H={g1.height()}")

    # 「取前 N=999」必须真正传进计划（面板 → _plan 的交接）
    for k in dlg.dim_rows:
        ck_, spt, spw = dlg.dim_rows[k]
        ck_.setChecked(True)
        spt.setValue(999)
    plan = dlg._plan()
    tops = [t for _k, _c, t, _w in plan]
    chk("_plan 收到 999", len(tops) == 5 and all(t == 999 for t in tops), str(tops))
except Exception as e:
    import traceback
    traceback.print_exc()
    chk("对话框实例化", False, str(e))

n_fail = sum(1 for _, c_, _ in results if not c_)
print("\n==== SMOKE v1.34.2:", "ALL PASS" if n_fail == 0 else f"{n_fail} FAIL ====")
sys.exit(1 if n_fail else 0)
