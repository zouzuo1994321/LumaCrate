# -*- coding: utf-8 -*-
"""v1.41.0 方案B 离屏冒烟：验证 browser_session 文件协议与 scraper 兜底接线（不启 WebView2）。

验证点：
  1) browser_session / scraper / cf_browser 三个模块可正常导入（无 PySide6 依赖）；
  2) cf_browser._build_fetch_js 产出合法 JS（含 URL、referer，无 % 格式化坑）；
  3) 无会话时 SESSION.get_html 抛 RuntimeError（不崩）；
  4) 有存活会话时，父进程写请求文件 → 模拟子进程回写结果文件 → get_html 正确解析出 HTML；
  5) scraper.http_get 包装存在且签名可用（不实际联网）。
"""
import os
import sys
import json
import tempfile
import threading
import time
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import browser_session as bs
import cf_browser
import scraper as sc

ok = 0
fail = 0


def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
        print(f"[OK] {name}")
    else:
        fail += 1
        print(f"[FAIL] {name}")


# 1) 模块导入已在 import 时完成
check("browser_session / cf_browser / scraper 导入成功", True)

# 2) fetch JS 构造
js = cf_browser._build_fetch_js("https://www.minnano-av.com/search_result.php?search_word=%E5"
                                , "https://www.minnano-av.com/")
check("fetch JS 含目标 URL", "https://www.minnano-av.com/search_result.php" in js)
check("fetch JS 含 credentials:include", "credentials:'include'" in js)
check("fetch JS 含 referer", "Referer" in js)
check("fetch JS 不含 % 格式化符", "%" not in js.split("fetch(")[0][-3:])
# 合法 JS 不能出现裸的未闭合模板；简单判断首尾是 (function(){...})()
check("fetch JS 包裹为 IIFE", js.startswith("(function(){return (async function(){") and js.endswith("})();})()"))

# 3) 无会话时 get_html 抛 RuntimeError
bs.SESSION.detach()
raised = False
try:
    bs.SESSION.get_html("https://www.minnano-av.com/x", timeout=3)
except RuntimeError as e:
    raised = True
    print("   抛出:", e)
check("无会话时 get_html 抛 RuntimeError", raised)

# 4) 模拟子进程回写结果文件的完整协议
class FakeProc:
    def poll(self):
        return None

bs.SESSION.attach(FakeProc(), "https://www.minnano-av.com/")

# 后台线程：等请求文件出现 → 写结果文件（模拟 WebView2 fetch 成功）
def _fake_server():
    for _ in range(100):
        if os.path.exists(bs._req_path()):
            try:
                with open(bs._req_path(), "r", encoding="utf-8") as f:
                    req = json.load(f)
                os.remove(bs._req_path())
            except Exception:
                time.sleep(0.05)
                continue
            payload = {"ok": True, "status": 200,
                       "html": "<html><body>女優一覧</body></html>"}
            rid = req.get("id")
            rp = os.path.join(tempfile.gettempdir(), bs.RESULT_PREFIX + rid + ".json")
            with open(rp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            return
        time.sleep(0.05)

th = threading.Thread(target=_fake_server)
th.start()

html = None
err = None
try:
    html = bs.SESSION.get_html("https://www.minnano-av.com/search_result.php?search_word=test",
                               timeout=10)
except Exception as e:
    err = e
th.join(timeout=5)
check("get_html 经文件协议取回 HTML", html == "<html><body>女優一覧</body></html>")
if err:
    print("   异常:", err)

# 4b) 模拟子进程回写失败（ok:false）
bs.SESSION.detach()
bs.SESSION.attach(FakeProc(), "https://www.minnano-av.com/")

def _fake_server_fail():
    for _ in range(100):
        if os.path.exists(bs._req_path()):
            try:
                with open(bs._req_path(), "r", encoding="utf-8") as f:
                    req = json.load(f)
                os.remove(bs._req_path())
            except Exception:
                time.sleep(0.05)
                continue
            payload = {"ok": False, "error": "fetch failed: blocked"}
            rid = req.get("id")
            rp = os.path.join(tempfile.gettempdir(), bs.RESULT_PREFIX + rid + ".json")
            with open(rp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            return
        time.sleep(0.05)

threading.Thread(target=_fake_server_fail).start()
fail_err = None
try:
    bs.SESSION.get_html("https://www.minnano-av.com/x", timeout=10)
except Exception as e:
    fail_err = e
check("get_html 子进程报错时抛异常", fail_err is not None)
print("   异常:", fail_err)

# 5) scraper.http_get 包装存在
check("scraper.http_get 可调用", callable(getattr(sc, "http_get", None)))

# 清理
bs.SESSION.detach()
for fn in (bs._req_path(),):
    try:
        if os.path.exists(fn):
            os.remove(fn)
    except Exception:
        pass

print(f"\n=== 冒烟结果：{ok} 通过 / {fail} 失败 ===")
sys.exit(1 if fail else 0)
