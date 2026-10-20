# -*- coding: utf-8 -*-
"""v1.42.0 新数据源冒烟：注册/config 离线校验 + avbase 真机 search→fetch 全链路。

真机部分走系统代理 127.0.0.1:8899（实测 avbase 代理下可达、无挑战）。
只读 GET，不写任何索引 / 配置。
"""
import json
import os
import sys
import tempfile

SRC = r"E:/【01】自研软件/【26-19】本地影视中心/src"
sys.path.insert(0, SRC)

# 日志重定向到临时目录，避免污染真实 app.log
import applog
applog.log_dir = lambda: tempfile.mkdtemp(prefix="lmc_smoke1420_")

import scraper
import config as cfg

PROXY = "http://127.0.0.1:8899"
passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[OK] {name}" + (f"  {detail}" if detail else ""))
    else:
        failed += 1
        print(f"[FAIL] {name}  {detail}")


def main():
    print("== 离线：注册与 config ==")
    check("SEARCHERS 含 avbase", "avbase" in scraper.SEARCHERS)
    check("FETCHERS 含 avbase", "avbase" in scraper.FETCHERS)
    check("未注册 javdb（已弃，避免派错资料）", "javdb" not in scraper.SEARCHERS)
    keys = [x["key"] for x in cfg.SCRAPER_SOURCES]
    check("SCRAPER_SOURCES 含 avbase", "avbase" in keys, str(keys))
    check("SOURCE_NAMES 含 avbase", "avbase" in scraper.SOURCE_NAMES)
    check("test_source 认识 avbase", "avbase" in scraper.SOURCE_NAMES)

    # load() 合并：老配置应自动追加并启用 avbase
    tmp = tempfile.mkdtemp(prefix="lmc_cfg1420_")
    os.environ["LMC_CONFIG"] = os.path.join(tmp, "settings.json")
    with open(os.environ["LMC_CONFIG"], "w", encoding="utf-8") as fh:
        json.dump({"scraper": {"sources": ["minnano", "imdb"],
                               "sources_enabled": {"minnano": True, "imdb": True}}}, fh)
    s = cfg.Settings()
    s.load()
    order = s.scraper.get("sources", [])
    check("老配置 load 后自动追加 avbase", "avbase" in order, str(order))
    check("老配置 load 后 avbase 默认启用",
          s.scraper["sources_enabled"].get("avbase") is True)
    del os.environ["LMC_CONFIG"]

    print("\n== 真机：avbase search→fetch ==")
    try:
        hits = scraper.avbase_search("糸井瑠花", timeout=25, proxy=PROXY)
        check("avbase_search 命中", bool(hits), f"{len(hits)} 条；首条 {hits[0] if hits else None}")
        if hits:
            d = scraper.avbase_fetch(hits[0]["url"], timeout=25, proxy=PROXY)
            check("avbase_fetch 有姓名", bool(d.get("name")), repr(d.get("name")))
            check("avbase_fetch 有生日", bool(d.get("birthday")), repr(d.get("birthday")))
            check("avbase_fetch 有罗马音", bool(d.get("romaji")), repr(d.get("romaji")))
            check("avbase_fetch 有头图", bool(d.get("photo_url")), d.get("photo_url", "")[:70])
            check("avbase_fetch 有三围", "尺寸" in (d.get("meta") or {}), str(d.get("meta")))
            print("    meta:", d.get("meta"))
            print("    bio :", d.get("bio"))
    except Exception as e:
        check("avbase 真机链路", False, f"{type(e).__name__}: {e}")

    # test_source 自检（「测试」按钮走的正是这个）
    try:
        r = scraper.test_source("avbase", proxy=PROXY, timeout=25)
        check("test_source('avbase') ok", r.get("ok"), r.get("msg"))
    except Exception as e:
        check("test_source('avbase')", False, f"{type(e).__name__}: {e}")

    print(f"\n=== 冒烟结果：{passed} 通过 / {failed} 失败 ===")
    sys.exit(0 if failed == 0 else 1)


main()
