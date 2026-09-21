# -*- coding: utf-8 -*-
"""v1.25.0 补丁 H —— 修「纯日语汉字标签永远译不出来」。

问题（写 smoke 时被 F6/F7/F11/F30/F39 一起钉出来的）：
    `to_zh()` 一进来就 `if not t or not has_kana(t): return ""` —— 先要求串里含假名，
    再查词典。可词典里有一大批**纯日语汉字**的条目，一个假名都没有：

        単体作品=单体作品   （真机上 27,899 次，是用户库里第二高频的标签）
        単体=单体作品   専属=专属   企画=企划   大乱交=滥交   総集编=总集篇
        美人=美女       美人妻=人妻  巨根物=巨根  姊=姐姐 …

    于是这些词**永远**翻译不出来，「日语转中文」对最高频的那一类标签完全失效，
    而且因为 `to_zh` 返回空串时调用方会「原样保留」，界面上看不出任何异常 ——
    静默失效，最难发现的那种。

修法：把「整串命中词典」提到 has_kana 判断**之前**。
    命中就返回（这本来就是人工录入的、最准的一档）；
    没命中再要求含假名，才走复合拆分 / 逐段翻译那两级（避免把纯中文标签误判成日语）。
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


patch("tagopt.py", "to_zh：整串命中优先于 has_kana",
      '''    t = clean_tag(tag)
    if not t or not has_kana(t):
        return ""
    hit = JA2ZH.get(t)
    if hit:
        return hit
    parts = [p.strip() for p in _COMPOUND_SEP.split(t) if p.strip()]''',
      '''    t = clean_tag(tag)
    if not t:
        return ""
    # ① 整串命中词典 → 直接返回。**这一步必须在 has_kana 之前**：
    #    词典里有大批「纯日语汉字」条目（単体作品 / 単体 / 専属 / 企画 / 大乱交 / 総集编…），
    #    它们一个假名都没有，可恰恰是用户库里最高频的一类
    #    （単体作品 真机上有 27,899 次）。先判 has_kana 会让这些词永远译不出来，
    #    而且返回空串时调用方会「原样保留」，界面上完全看不出异常。
    hit = JA2ZH.get(t)
    if hit:
        return hit
    # ② 没整串命中，才要求含假名 —— 免得把纯中文标签当成日语去拆/去译
    if not has_kana(t):
        return ""
    parts = [p.strip() for p in _COMPOUND_SEP.split(t) if p.strip()]''')

print("\n[ALL DONE]")
