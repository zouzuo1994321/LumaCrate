# -*- coding: utf-8 -*-
"""从 live_v208_exe.py 剪出「只测第 ③ 段」的瘦探针。

目的：搞清楚为什么「悬停 收藏 列」时一个图标都没画出来 —— 是真的没画，
还是鼠标压根没落到那一列。做法是把 ④/②/① 整段换掉，改成
「逐列悬停 → 出图 → ①量该列两枚图标的墨迹 ②与初始图做像素差分，看哪一列真被重绘」。
"""
import io, os

SRC = r"E:\【01】自研软件\【26-19】本地影视中心\dev\_scratch\live_v208_exe.py"
OUT = r"E:\【01】自研软件\【26-19】本地影视中心\dev\_scratch\probe208_03.py"

src = io.open(SRC, encoding="utf-8").read()
MARK = "    # ④ 列表懒填充："
i = src.index(MARK)
j = src.index("finally:\n    kill_exe()")

BLOCK = r'''    # ============================================================
    # ③bis 逐列悬停：图标画了没 / 这一列到底被重绘了没
    # ============================================================
    p("========== ③bis 逐列悬停诊断 ==========")

    def ink_map(im):
        out = {}
        for k, c in COLS.items():
            fx, fy = c["funnel"]
            tx, ty = c["tri"]
            out[k] = (count_gray_icon(im, (fx - 9, fy - 9, fx + 9, fy + 9)),
                      count_gray_icon(im, (tx - 8, ty - 8, tx + 8, ty + 8)))
        return out

    def diff_map(a, b):
        """两张图在「各列表头条」上的像素差总数 —— 用来判断哪一列真的被重绘过。"""
        pa, pb = _px(a).load(), _px(b).load()
        res = {}
        for k, c in COLS.items():
            x0 = c["funnel"][0] - 6
            x1 = c["tri"][0] + 6
            y0, y1 = HDR["y"] - 15, HDR["y"] + 15
            n = 0
            for y in range(max(0, y0), min(a.height, y1)):
                for x in range(max(0, x0), min(a.width, x1)):
                    q, w = pa[x, y], pb[x, y]
                    if abs(q[0] - w[0]) + abs(q[1] - w[1]) + abs(q[2] - w[2]) > 60:
                        n += 1
            res[k] = n
        return res

    # 表头各列的真实边界（自己算，不依赖 _zones，避免「用被测代码验被测代码」）
    edges = []
    for _k, _c in COLS.items():
        pass
    x0h = HDR["x0"]
    acc = x0h
    for _c in HDR["cols"]:
        edges.append((_c["key"], acc, acc + _c["w"]))
        acc += _c["w"]
    p("  表头列边界: %s" % (edges,))

    hover(hwnd, 900, 760)
    im_idle = shot("probe208_idle")
    base = ink_map(im_idle)
    p("  [idle] %s" % (base,))

    for _k, _a, _b in edges:
        xm = (_a + _b) // 2
        # 两步移动：先到这一列左边界内侧，再挪到中心 —— 确保 Qt 收到真实 move 事件
        hover(hwnd, _a + 6, HDR["y"], wait=0.45)
        hover(hwnd, xm, HDR["y"], wait=1.0)
        im = shot("probe208_hov_%s" % _k)
        now = ink_map(im)
        d = diff_map(im_idle, im)
        p("  [hover %s @x=%d] ink=%s" % (_k, xm, now))
        p("                        diff=%s" % (d,))
        hit = _k
        check("③bis 悬停 %s 列 → 该列左漏斗有墨" % _k, now[hit][0] >= 8, now[hit][0])
        check("③bis 悬停 %s 列 → 该列右三角有墨" % _k, now[hit][1] >= 4, now[hit][1])
        check("③bis 悬停 %s 列 → 该列表头确实被重绘（与 idle 有像素差）" % _k,
              d.get(hit, 0) > 30, d.get(hit, 0))
        check("③bis 悬停 %s 列 → 其它列表头保持静止" % _k,
              max(v for kk, v in d.items() if kk != hit) < 30,
              dict((kk, v) for kk, v in d.items() if kk != hit))

    hover(hwnd, 900, 760)
    im_end = shot("probe208_leave")
    p("  [leave] %s" % (ink_map(im_end),))
    check("③bis 移开后全部归零",
          all(v[0] < 8 and v[1] < 4 for v in ink_map(im_end).values()),
          ink_map(im_end))

'''

io.open(OUT, "w", encoding="utf-8").write(src[:i] + BLOCK + src[j:])
print("written", OUT, os.path.getsize(OUT))
