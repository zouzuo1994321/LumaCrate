# -*- coding: utf-8 -*-
"""v2.0.0 升级前的回退准备：把 v1.46.15 的「样式 + 色板」原样留档。

产物（都在 docs/legacy/ 下，archive_version.py 会随 docs/ 一起收进源码 zip）：
  style_v1_46_15.qss      —— 墨金磨砂主题的完整 QSS 原文
  accent_v1_46_15.txt     —— 旧的 12 色高亮色板 + 默认值 + 派生规则说明
"""
import io
import os
import shutil

ROOT = r"E:\【01】自研软件\【26-19】本地影视中心"
SRC = os.path.join(ROOT, "src")
OUT = os.path.join(ROOT, "docs", "legacy")
os.makedirs(OUT, exist_ok=True)

shutil.copy2(os.path.join(SRC, "style.qss"), os.path.join(OUT, "style_v1_46_15.qss"))
print("已留档 QSS：", os.path.join(OUT, "style_v1_46_15.qss"),
      os.path.getsize(os.path.join(OUT, "style_v1_46_15.qss")), "字节")

TXT = """流明盒 v1.46.15（Build 2610290118）· 旧版配色留档
=====================================================
用途：v2.0.0 把 UI 组件套件整体切到 HeroUI 暗色语言，这里保留旧的「墨黑 / 朱红 / 鎏金」
      配色与派生规则，需要回退时按下面的三步操作即可（代码层不需要改逻辑）。

一、旧版高亮色板（12 色，config.ACCENT_COLORS 原文）
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
  旧默认值：ACCENT_DEFAULT = "#c0392b"（朱红）

二、旧版四个高亮色变体的派生规则（config.accent_shades）
   base  = 原色
   dark  = HLS 里明度 -0.135、饱和度 +0.05   （按下 / 列表选中底）
   deep  = HLS 里明度 -0.080、饱和度 +0.03   （主按钮底）
   light = HLS 里明度 +0.110、饱和度 +0.08   （亮描边 / 悬停边框）
   说明：只动明度与饱和度、保留色相；这是为了让任何基础色都能复现出
         「朱红 #c0392b → 描边 #df5444」这种层次关系。

三、回退步骤
   1) 把 docs/legacy/style_v1_46_15.qss 复制回 src/style.qss（覆盖）；
   2) 把上面 12 色与 ACCENT_DEFAULT 粘贴回 src/config.py 的 ACCENT_COLORS / ACCENT_DEFAULT；
   3) 把 config.accent_shades() 的四个系数改回 -0.135/+0.05、-0.080/+0.03、+0.110/+0.08。
   改完直接跑，无需重新打包（开发期）；交付版则重新 python build_exe.py。

四、更彻底的回退
   history/ 下保留了每一版的 exe 与源码 zip：
     history/流明盒-v1.46.15-2610290118.exe
     history/流明盒-v1.46.15-2610290118-源码.zip
     history/流明盒-v1.46.15-2610290118-封存说明.txt（含 SHA-256）
   直接换回 exe 即为完整的 v1.46.15 观感与功能。
"""
p = os.path.join(OUT, "accent_v1_46_15.txt")
io.open(p, "w", encoding="utf-8").write(TXT)
print("已留档色板：", p, os.path.getsize(p), "字节")
