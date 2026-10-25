# -*- coding: utf-8 -*-
"""v1.41.3 冒烟：方案B 回退门永不打开的**真因**修复 —— browser_session host 归一 _norm_host。

复现过的 bug：`http_get` 用 `urlparse(完整URL).netloc` 得到裸 host（www.minnano-av.com），
再把它传给 `alive(host)`；而 `alive()` 内部又 `urlparse(裸host).netloc` —— 无 scheme 的裸
host 被 urlparse 当成 path，netloc 返回 '' → `_procs['']` 查不到 → alive() 恒 False →
is_enabled() 已是 True、会话也托管了，浏览器 fetch 却从未被调用（复测一直红）。

验证点：
  1) _norm_host：完整 URL 与裸 host 都归一到同一 netloc；
  2) attach 后 alive(裸host) 与 alive(完整URL) 均为 True（修复前 alive(裸host)=False）；
  3) get_html 用的 host 键与 alive/attach 一致（都用 _norm_host）；
  4) detach 后 alive 归 False。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import browser_session as bs

ok = 0
fail = 0


def check(name, cond):
    global ok, fail
    print(("[OK] " if cond else "[FAIL] ") + name)
    if cond:
        ok += 1
    else:
        fail += 1


class FakeProc:
    def poll(self):
        return None


URL = "https://www.minnano-av.com/search_result.php?search_word=x"
BARE = "www.minnano-av.com"

# 1) _norm_host 归一一致
check("_norm_host(完整URL) == _norm_host(裸host)",
      bs._norm_host(URL) == bs._norm_host(BARE) == "www.minnano-av.com")

# 2) attach 后两种写法都 alive（修复前 alive(裸host)=False）
bs.SESSION.detach()
bs.SESSION.attach(FakeProc(), "https://www.minnano-av.com/")
check("attach 后 alive(裸host) == True", bs.SESSION.alive(BARE) is True)
check("attach 后 alive(完整URL) == True", bs.SESSION.alive(URL) is True)
check("attach 后 hosts() 含该 host", "www.minnano-av.com" in bs.SESSION.hosts())

# 3) http_get 里那行 host 计算与 alive 键一致（都用 _norm_host 归一到同一值）
import urllib.parse as up
host_in_http_get = up.urlparse(URL).netloc
check("http_get 传出的裸 host 经 alive() 能命中（_norm_host 兜底）",
      bs.SESSION.alive(host_in_http_get) is True)

# 4) detach 后归 False
bs.SESSION.detach()
check("detach 后 alive == False", bs.SESSION.alive(BARE) is False)

print(f"\n=== 冒烟结果：{ok} 通过 / {fail} 失败 ===")
sys.exit(1 if fail else 0)
