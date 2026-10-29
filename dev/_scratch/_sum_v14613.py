# -*- coding: utf-8 -*-
"""汇总 v1.46.13 两个探针的结论行（只打印关键结论，避免翻长日志）。"""
import re

KEYS_PROBE = ("FAIL", "ALL_OK", "共 ")
KEYS_GUI = ("order:", "modals:", "end_", "mid_scan", "bar_values", "grid_total': ")

for path, keys, head in (
    (r"C:\Users\zouzu\AppData\Local\Temp\probe14613.log", KEYS_PROBE, "离屏探针"),
    (r"C:\Users\zouzu\AppData\Local\Temp\gui14613.log", KEYS_GUI, "真机走查"),
):
    print("=" * 20, head, path)
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    for l in lines:
        if any(k in l for k in keys):
            print(l)
    print()
