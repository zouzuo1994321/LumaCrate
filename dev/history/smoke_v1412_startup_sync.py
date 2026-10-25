# -*- coding: utf-8 -*-
"""v1.41.2 冒烟：方案B 重启后不生效的修复 —— 启动时把持久开关同步到 SESSION.set_enabled。

验证点：
  1) main.py 源码里确有「set_enabled( ... browser_scrape ... )」这行启动同步；
  2) config.get_settings().scraper.get("browser_scrape") 可读，且经 set_enabled 后
     SESSION.is_enabled() 与该值一致（回退门由此开闭）；
  3) set_enabled 真/假往返正确（关开关能真关回退门）。
不改动真实 settings.json。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import browser_session as bs
import config as cfg

ok = 0
fail = 0


def check(name, cond):
    global ok, fail
    print(("[OK] " if cond else "[FAIL] ") + name)
    if cond:
        ok += 1
    else:
        fail += 1


# 1) main.py 含启动同步行
main_src = open(os.path.join(ROOT, "src", "main.py"), encoding="utf-8").read()
sync_ok = ("SESSION.set_enabled" in main_src and "browser_scrape" in main_src)
check("main.py 含 SESSION.set_enabled(...browser_scrape...) 启动同步", sync_ok)

# 2) 读持久开关 → set_enabled → is_enabled 一致
bs_on = bool(cfg.get_settings().scraper.get("browser_scrape", False))
print("   当前持久 browser_scrape =", bs_on)
bs.SESSION.set_enabled(bs_on)
check("set_enabled(持久值) 后 is_enabled() 与之相等", bs.SESSION.is_enabled() == bs_on)

# 3) 往返：关能真关
bs.SESSION.set_enabled(not bs_on)
check("set_enabled(取反) 后 is_enabled() 跟随", bs.SESSION.is_enabled() == (not bs_on))

# 复位，避免影响同进程其它逻辑
bs.SESSION.set_enabled(False)

print(f"\n=== 冒烟结果：{ok} 通过 / {fail} 失败 ===")
sys.exit(1 if fail else 0)
