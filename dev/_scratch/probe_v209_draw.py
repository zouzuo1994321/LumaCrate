# -*- coding: utf-8 -*-
"""v2.0.9 四条反馈里前三条的像素核对（离屏，垫深底后再量墨迹）。

① 标签徽章里的 × 缩到 80%，且仍在圆心；
② 演员头像右上角的 × 在圆心；
③ 两处「＋」在图形正中央。

⚠ 取图的两个坑（本脚本已避开，见 grab_on 的注释）：
  1. `w.render(p)` 必须带 `QPoint(0,0)`，否则 PySide6 直接 TypeError；
  2. 二者（render / grab）都会**先按 QPalette.Window 铺一层底色**，离屏下这个色
     是 `#efefef` 的白 —— 于是整块图都被判成「亮像素」。诊断结果（probe_grab_diag.py）：
        裸 grab()            → (0,0) = #efefef
        palette 改透明 + grab → (0,0) = #efefef（改不动）
        WA_NoSystemBackground + grab → (0,0) = #000000  ← 只有这条真的不铺白底
"""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
TEMP = os.path.join(os.environ["LOCALAPPDATA"], "Temp", "lmc_probe_v209")
os.makedirs(TEMP, exist_ok=True)
os.environ["LMC_CONFIG"] = os.path.join(TEMP, "settings.json")
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtCore import Qt, QPoint                                     # noqa: E402
from PySide6.QtGui import QFontDatabase, QFont, QColor, QPainter, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton, QWidget          # noqa: E402

app = QApplication(sys.argv)
QFontDatabase.addApplicationFont(r"C:\Windows\Fonts\msyh.ttc")
app.setFont(QFont("Microsoft YaHei", 9))

import ui_hero as uh          # noqa: E402

BG = QColor("#0d0d10")


def grab_on(w, bg=BG):
    """把控件内容画到一张垫过深底的图上。"""
    w.adjustSize()
    # ★ 关键：不关掉背景填充，grab() 会用调色板 Window 色（离屏 = #efefef 白）铺满，
    #   下面 img.fill(bg) 被整块覆盖 → 阈值判据把全图算成墨迹。
    w.setAttribute(Qt.WA_NoSystemBackground, True)
    pm = w.grab()
    img = QImage(pm.size(), QImage.Format_ARGB32)
    img.fill(bg)
    p = QPainter(img)
    p.drawPixmap(0, 0, pm)
    p.end()
    return img


def ink_box(img, thr=150):
    """返回 (亮像素 bbox, 数量)；bbox = (x0,y0,x1,y1)。

    ⚠ 必须连 alpha 一起判：`WA_NoSystemBackground` 之后**透明区的 RGB 是未初始化的垃圾**，
    实测有 a0 却是 #ffffff 的像素 —— 只看 RGB 会把它们全算成墨迹。
    """
    xs, ys, n = [], [], 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = QColor(img.pixel(x, y))
            if c.alpha() >= 128 and max(c.red(), c.green(), c.blue()) >= thr:
                xs.append(x)
                ys.append(y)
                n += 1
    if not xs:
        return None, 0
    return (min(xs), min(ys), max(xs), max(ys)), n


def ctr(box):
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def wh(box):
    return (box[2] - box[0] + 1, box[3] - box[1] + 1)


ok, bad = [], []


def ck(name, cond, detail):
    (ok if cond else bad).append(name)
    print(("  OK   " if cond else "  FAIL ") + name + "  -> " + str(detail))


# ---------- ① 标签徽章 14px ----------
print("=== ① 标签徽章（TagChip 的 RoundClose 14px）===")
chip = uh.TagChip("人妻", on_delete=lambda: None)
chip.resize(chip.size())
img = grab_on(chip)
dot = chip._dot
sub = img.copy(int(dot.x()), int(dot.y()), dot.width(), dot.height())
box, n = ink_box(sub, 150)
print("  徽章 %dx%d @ (%d,%d)  胶囊净高 %d  墨迹 bbox %s n=%d"
      % (dot.width(), dot.height(), dot.x(), dot.y(), uh.TagChip.PILL_H, box, n))
theo = ((dot.width() - 1) / 2.0, (dot.height() - 1) / 2.0)
if box:
    c = ctr(box)
    ck("① 叉仍在圆心（偏移 ≤0.75px）",
       abs(c[0] - theo[0]) <= 0.75 and abs(c[1] - theo[1]) <= 0.75,
       "中心 (%.2f, %.2f) 理论 (%.1f, %.1f) 偏移 (%.2f, %.2f)"
       % (c[0], c[1], theo[0], theo[1], c[0] - theo[0], c[1] - theo[1]))

# —— A/B：同一段绘制、只把 K_RATIO 切回 v2.0.8 的 0.225，直接比墨迹大小 ——
def badge_ink(k_ratio):
    old = uh.RoundClose.K_RATIO
    uh.RoundClose.K_RATIO = k_ratio
    try:
        rc = uh.RoundClose(14, on_click=lambda: None)
        b, cnt = ink_box(grab_on(rc), 150)
        return b, cnt
    finally:
        uh.RoundClose.K_RATIO = old


b_new, n_new = badge_ink(0.18)
b_old, n_old = badge_ink(0.225)
print("  墨迹 A/B：v2.0.9(0.18) %s n=%d   v2.0.8(0.225) %s n=%d"
      % (wh(b_new) if b_new else None, n_new, wh(b_old) if b_old else None, n_old))
ck("① 叉确实比 v2.0.8 小（外接与像素数双降）",
   b_new and b_old and n_new < n_old
   and wh(b_new)[0] <= wh(b_old)[0] and wh(b_new)[1] <= wh(b_old)[1],
   "外接 %s → %s，像素 %d → %d（-%.0f%%）"
   % (wh(b_old), wh(b_new), n_old, n_new, (1 - n_new / float(n_old)) * 100))
k_now = 14 * uh.RoundClose.K_RATIO
ck("① 半臂长 = 直径 × 0.18（= 原 0.225 的 80%）",
   abs(uh.RoundClose.K_RATIO - 0.18) < 1e-9 and abs(k_now - 3.15 * 0.8) < 0.02,
   "K_RATIO=%.3f → k=%.2fpx（原 3.15px）" % (uh.RoundClose.K_RATIO, k_now))

# ---------- ② 演员头像右上角 18px ----------
print("=== ② 演员头像右上角 ×（RoundClose 18px）===")
rc = uh.RoundClose(18, on_click=lambda: None)
box2, n2 = ink_box(grab_on(rc), 150)
print("  bbox", box2, "n", n2)
if box2:
    c2 = ctr(box2)
    t2 = ((18 - 1) / 2.0, (18 - 1) / 2.0)
    ck("② 叉在圆心（偏移 ≤0.75px）",
       abs(c2[0] - t2[0]) <= 0.75 and abs(c2[1] - t2[1]) <= 0.75,
       "中心 (%.2f, %.2f) 理论 (%.1f, %.1f) 偏移 (%.2f, %.2f)"
       % (c2[0], c2[1], t2[0], t2[1], c2[0] - t2[0], c2[1] - t2[1]))

# ---------- ③ 两处「＋」 ----------
print("=== ③ 「＋」按钮（RoundPlus 28×24）===")
# 对照：原来那版 compact_button("＋")，看看字形落点偏多少（仅供参考，不计入通过率）
bq = QPushButton("＋")
bq.setFixedSize(28, 24)
bq.setFont(QFont("Microsoft YaHei", 9))
# 去掉按钮自带底色，只留字形墨迹 —— 否则 QSS 默认会把整块 28×24 填成浅灰，
# 阈值判据量到的是「整个按钮」而不是「＋」本身。
bq.setStyleSheet("background:transparent;border:none;color:#ecedee;")
qb, qn = ink_box(grab_on(bq), 150)
if qb:
    qc = ctr(qb)
    print("  〔对照〕QPushButton(\"＋\") 墨迹 %s 中心 (%.2f, %.2f) 框心 (13.5, 11.5) 偏移 (%.2f, %.2f)"
          % (wh(qb), qc[0], qc[1], qc[0] - 13.5, qc[1] - 11.5))

for label in ("标签", "演员信息"):
    rp = uh.RoundPlus(28, 24, tip="x")
    box3, n3 = ink_box(grab_on(rp), 150)
    print("  %s bbox %s n=%d  外接 %s" % (label, box3, n3, wh(box3) if box3 else None))
    if box3:
        c3 = ctr(box3)
        tw, th = (28 - 1) / 2.0, (24 - 1) / 2.0
        ck("③ %s「＋」在图形正中央（偏移 ≤0.75px）" % label,
           abs(c3[0] - tw) <= 0.75 and abs(c3[1] - th) <= 0.75,
           "中心 (%.2f, %.2f) 理论 (%.1f, %.1f) 偏移 (%.2f, %.2f)"
           % (c3[0], c3[1], tw, th, c3[0] - tw, c3[1] - th))
        w3, h3 = wh(box3)
        # 加号半臂 3px → 两臂合计 6px，加圆头线帽 1.35px → 外接落在 6~9
        ck("③ %s「＋」外接 6~9px（半臂 3px + 圆头线帽）" % label,
           6 <= w3 <= 9 and 6 <= h3 <= 9, "%dx%d" % (w3, h3))

print("=== 结果 ===")
print("通过 %d / %d" % (len(ok), len(ok) + len(bad)))
if bad:
    for b in bad:
        print("  失败:", b)
print("PROBE209_OK" if not bad else "PROBE209_FAIL")
