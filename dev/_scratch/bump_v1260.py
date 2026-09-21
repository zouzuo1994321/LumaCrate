# -*- coding: utf-8 -*-
"""v1.26.0 版本号 bump（Round 4）。"""
import io
import os
import sys

P = r"Z:/【01】自研软件/【26-19】本地影视中心/src/version.py"
with io.open(P, encoding="utf-8", newline="") as f:
    s = f.read()

pairs = [
    ("# 外部版本号 v1.25.0", "# 外部版本号 v1.26.0"),
    ("""MAJOR_ITER = 25          # 大版本迭代 -> 第二位（标签优化 / 12 色高亮 + 外发光 / AI 模型可指定 /
                         #                推荐轮次去重 / 首页快捷筛选选中态 / 导出页间距）""",
     """MAJOR_ITER = 26          # 大版本迭代 -> 第二位（开关轨道跟随高亮色 / 底部开源声明 /
                         #                侧栏副标题防裁字 / 性能基准测试与《性能基线》）"""),
    ("""# 内部构建号 YYMMDDNNNN (2026-09-21 第三十五次构建，末四位按「每次打包自增」连续计数)
# 0034：v1.25.0 六条反馈（标签优化页为新增模块）
# 0035：0034 打包后从 app.log 捡到 QTimer 已析构崩溃（v1.24.1 起就存在），修复后重打
BUILD_DATE = "260921"
BUILD_SEQ = "0035\"""",
     """# 内部构建号 YYMMDDNNNN (2026-09-21 第三十六次构建，末四位按「每次打包自增」连续计数)
# 0034：v1.25.0 六条反馈（标签优化页为新增模块）
# 0035：0034 打包后从 app.log 捡到 QTimer 已析构崩溃（v1.24.1 起就存在），修复后重打
# 0036：v1.26.0 四条反馈（开关轨道不跟高亮色 / 底部开源声明 / 副标题裁字 + 性能基准）
BUILD_DATE = "260921"
BUILD_SEQ = "0036\""""),
]
bad = []
for old, new in pairs:
    if s.count(old) != 1:
        bad.append(old.splitlines()[0])
        continue
    s = s.replace(old, new, 1)
if bad:
    print("[FAIL] 锚点未命中：", bad)
    sys.exit(1)
with io.open(P, "w", encoding="utf-8", newline="") as f:
    f.write(s)
with io.open(P, encoding="utf-8", newline="") as f:
    back = f.read()
for need in ("v1.26.0", "MAJOR_ITER = 26", 'BUILD_SEQ = "0036"', "# 0036："):
    assert need in back, need
sys.path.insert(0, r"Z:/【01】自研软件/【26-19】本地影视中心/src")
print("[OK] version.py ->", end=" ")
print(back.split("FULL_VERSION = ")[1].strip())
