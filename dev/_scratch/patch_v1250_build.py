# -*- coding: utf-8 -*-
"""v1.25.0 收尾：build_exe.py 的归档分支别再让根目录攒旧包。

现状（v1.24.1 引入）：根目录归档时若 `history/` 已有同名留档就打印 `[保留]` 并**原地不动**。
这条规则本意是「防止成品被重复搬进 dev/」，但**副作用是根目录永远留着上一个版本的 exe**：
本次构建 0035 之前，根目录同时躺着 0033 和 0034（各 48MB），再build几次就又是一个「1GB 纯重复」。

修法：同名留档**本来就是同一次构建复制出来的、字节相同**，直接 `os.replace` 覆盖即可
（原子操作，失败则源文件仍在）。这样根目录恒为「只有最新版」，history/ 仍是一版一份。
`os.replace` 若被 Z: 的安全钩子拦下，就退回原来的 `[保留]` 行为，绝不因此让构建失败。
"""
import os

ROOT = r"Z:\【01】自研软件\【26-19】本地影视中心"
p = os.path.join(ROOT, "build_exe.py")

OLD = '''            if os.path.exists(dst):
                # history 里已经有同名留档 → 通常说明这份就是刚被复制回根目录的成品。
                # 绝不能退而写 dev/（那正是 dev/ 攒满 45MB 重复 exe 的原因），直接留在原处。
                print(f"[保留] 根目录 {f}：history/ 已有同名留档，不再重复归档")
                continue'''

NEW = '''            if os.path.exists(dst):
                # history 里已经有同名留档。它本来就是同一次构建复制出来的**字节相同**的
                # 副本（0033/0034 实测同尺寸同内容），所以正确做法是覆盖回去，而不是
                # 「留在原地」—— 后者会让根目录每构建一次就多攒一个 48MB 旧包
                # （v1.25.0 构建前根目录已同时躺着 0033 与 0034）。
                # 绝不退而写 dev/（那正是 dev/ 攒满 45MB 重复 exe 的原因）。
                try:
                    os.replace(src, dst)      # 原子；失败时源文件仍在
                    print(f"[归档] {f} -> history/{f}（覆盖字节相同的同名留档）")
                except Exception as e:
                    print(f"[保留] 根目录 {f}：history/ 有同名留档且覆盖失败（{e}）")
                continue'''

with open(p, encoding="utf-8", newline="") as f:
    s = f.read()
n = s.count(OLD)
if n != 1:
    print(f"[失败] 锚点命中 {n} 次（期望 1）")
    raise SystemExit(1)
with open(p, "w", encoding="utf-8", newline="") as f:
    f.write(s.replace(OLD, NEW, 1))
print("[OK] build_exe.py 归档分支改为 os.replace 覆盖")
