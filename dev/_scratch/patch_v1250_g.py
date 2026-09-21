# -*- coding: utf-8 -*-
"""v1.25.0 补丁 G —— 修「裸高亮色令牌被替换成非法 CSS」。

问题（写 smoke 时发现的）：
    `render_style()` 把高亮色令牌一律替换成 "r, g, b" 文本（因为 QSS 的 rgba()
    通道位写不了十六进制）。但 style.qss 里有一部分令牌是**裸用**的：

        QPushButton#Seg:checked { background: __ACCENT_DARK__; border: 1px solid __ACCENT_LIGHT__; }
        QCheckBox::indicator:checked { background: __ACCENT__; border-color: __ACCENT_LIGHT__; }

    替换后变成 `border: 1px solid 224, 82, 67;` —— 不是合法 CSS，Qt 会**整条声明丢弃**，
    于是这些描边 / 选中底色在真机上直接不生效（而且不报错，很难发现）。

修法：分两步替换
    1) `rgba(__TOKEN__,` → `rgba(r, g, b,`（通道位保留 "r, g, b" 文本形式）
    2) 剩下的**裸令牌** → `#rrggbb` 十六进制
"""
import io
import os

ROOT = r"Z:/【01】自研软件/【26-19】本地影视中心"
SRC = os.path.join(ROOT, "src")


def patch(rel, label, old, new, count=1):
    p = os.path.join(SRC, rel)
    s = io.open(p, encoding="utf-8", newline="").read()
    got = s.count(old)
    if got != count:
        raise SystemExit(f"[ABORT] {rel} / {label}: 锚点命中 {got} 次（期望 {count}）\n---\n{old[:400]}")
    s = s.replace(old, new, count)
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)
    print(f"[OK] {rel} / {label}")


patch("main_window.py", "render_style 裸令牌输出十六进制",
      '''    for token, key in (("__ACCENT_LIGHT__", "light"), ("__ACCENT_DARK__", "dark"),
                       ("__ACCENT_DEEP__", "deep"), ("__ACCENT__", "base")):
        qss = qss.replace(token, ", ".join(str(v) for v in shades[key]))
    return qss''',
      '''    for token, key in (("__ACCENT_LIGHT__", "light"), ("__ACCENT_DARK__", "dark"),
                       ("__ACCENT_DEEP__", "deep"), ("__ACCENT__", "base")):
        r, g, b = shades[key]
        # 1) `rgba(__TOKEN__, 0.75)`：QSS 的 rgba() 通道位不认十六进制，只能填 "r, g, b"。
        qss = qss.replace(f"rgba({token},", f"rgba({r}, {g}, {b},")
        # 2) 剩下的**裸令牌**（`border-color: __ACCENT_LIGHT__;` 这种直接当颜色值的）：
        #    必须换十六进制 —— 塞 "224, 82, 67" 进去不是合法 CSS，Qt 会把整条声明丢掉，
        #    表现为「换了高亮色但某些描边/选中底没变」，且不报错。
        qss = qss.replace(token, f"#{r:02x}{g:02x}{b:02x}")
    return qss''')

print("\n[ALL DONE]")
