# -*- coding: utf-8 -*-
"""内置浏览器取 cookie 的**隔离子进程**（v1.40.1 反馈 3）。

为什么要单开一个进程
--------------------
我们复刻微博bot小助手的做法：用 **pywebview** 开一个内嵌 **WebView2** 窗口让用户
在窗口里过 Cloudflare / AWS WAF 的人机校验，然后 `window.get_cookies()` 把
`cf_clearance` 之类的通行 cookie 取回来注入刮削器。

但 pywebview 有一条**硬约束**（源码断言）：

    if threading.current_thread().name != 'MainThread':
        raise WebViewException('pywebview must be run on a main thread.')

而本软件是 PySide6/Qt，`app.exec()` **独占主线程** —— 同进程里根本调不了
`webview.start()`。微博bot小助手能把 `webview.start()` 放在主线程，是因为它整个
GUI 就是 pywebview（没有 Qt）。所以这里把浏览器放进**独立子进程**：父进程只负责
spawn / 等结果 / 收 cookie，用户在内嵌窗口里的操作完全不阻塞主界面。

与父进程的约定（文件协议，零依赖、不需要 IPC 库）
--------------------------------------------------
调用：`python helper.py <url> <result_json_path> [<host_filter>]`

  · 用户在窗口里完成校验后，窗口内会有一个「✔ 我已完成验证，读取 Cookie」按钮
    （由 pywebview 的 `js_api` 注入），点它即写结果并关窗；
  · 用户若直接关闭窗口（右上角 ×），也算「完成」—— 关窗后同样写一次结果；
  · 若一切都没取到，写 `{"ok": false, "error": ...}`。

结果文件（UTF-8 JSON）：
```json
{"ok": true, "cookie": "cf_clearance=xxx; __cf_bm=yyy", "host": "www.minnano-av.com", "count": 2}
{"ok": false, "error": "用户取消"}
```

写盘用「先写 .tmp 再 os.replace」的原子替换，父进程只要看到文件存在就是完整的。

v1.40.2（反馈 2）：**持久快照 + 按需 dump**
--------------------------------------------------
用户反馈「cookie 读取有问题，单独安排一个按钮进行 cookie 读取」。为此：
  · 每次成功取到 cookie，除了写结果文件，还会额外写一份**持久快照**
    （`snapshot_path()`，默认 `%TEMP%/lmc_cf_snapshot.json`）——
    这样即使用户先关掉内置浏览器窗口、再回主对话框点「读取 Cookie」，也读得到；
  · 主对话框点「读取 Cookie」时若内置浏览器**还开着**，会写一个 `lmc_cf_request.json`
    请求文件；本进程的后台线程监听到它就立刻再 dump 一次（用户不必再去点窗口里的按钮）。
"""
import json
import os
import sys
import tempfile
import threading
import time
import traceback


SNAPSHOT_NAME = "lmc_cf_snapshot.json"
REQUEST_NAME = "lmc_cf_request.json"

# 方案B（v1.41.0）：常驻抓取会话的文件协议
BF_REQUEST = "lmc_bf_request.json"        # 抓取请求（父进程 browser_session → 子进程）
BF_RESULT_PREFIX = "lmc_bf_result_"       # 抓取结果（子进程 → 父进程），后缀 <id>.json
BF_TIMEOUT = 30

# 抓取请求用的浏览器 UA（与 scraper.UA 保持一致即可，不必 import）
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

# 方案B：常驻抓取会话开关与窗口引用（main() 从 argv 读 persist 标记）
_PERSIST = False
_STATE = {"win": None, "winref": None}


def snapshot_path():
    """持久 cookie 快照的固定路径（父进程 `ui_settings.cf_browser_snapshot_path` 同源）。"""
    return os.path.join(tempfile.gettempdir(), SNAPSHOT_NAME)


def request_path():
    """按需 dump 的请求文件路径。"""
    return os.path.join(tempfile.gettempdir(), REQUEST_NAME)


# ---------- 结果文件 ----------
class Result:
    def __init__(self, path):
        self.path = path
        self.written = False
        # v1.40.2：最后一次成功取到的结果（供快照复用，避免重复读浏览器）
        self.last = None

    def write(self, payload: dict):
        if self.written:
            return
        self.written = True
        self.last = payload
        try:
            d = os.path.dirname(os.path.abspath(self.path)) or "."
            fd, tmp = tempfile.mkstemp(prefix=".cfres_", dir=d)
            os.close(fd)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            os.replace(tmp, self.path)      # 原子：父进程不会读到半截文件
        except Exception:
            # 兜底：直接写（宁可让父进程解析失败，也不要静默丢结果）
            try:
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False)
            except Exception:
                pass
        # 成功结果再存一份**持久快照**（关窗后仍可被「读取 Cookie」读到）
        if payload.get("ok"):
            try:
                sp = snapshot_path()
                fd, tmp = tempfile.mkstemp(prefix=".cfsnp_", dir=os.path.dirname(sp) or ".")
                os.close(fd)
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False)
                os.replace(tmp, sp)
            except Exception:
                pass


# ---------- pywebview 的 Cookie 解析 ----------
# pywebview 的 window.get_cookies() 返回一个 list，每个元素是
# http.cookies.SimpleCookie（dict 子类，键是 cookie 名、值是 Morsel）。
# Morsel 要用 .key / .value 取值；老版本/其它后端可能直接给 dict。
# 这两种都要兼容（微博bot小助手 v1.4.x 踩过这个坑）。
def _extract_pairs(cookies, host_filter=""):
    """把 `window.get_cookies()` 的返回摊平成 {name: value}。

    pywebview 的返回形态**不稳定**，实测见过三种：
      · 每个元素是一个 `SimpleCookie`，且**里面可能装多条** cookie
        （`SimpleCookie` 是 dict 子类，值是 Morsel）→ 要迭代 `.values()` **全部**取，
        不能只取第一条（只取第一条会漏掉 __cf_bm 这类伴生 cookie）；
      · 每个元素是一个普通 dict（`{"name":…, "value":…}`）；
      · 每个元素是有 `.name` / `.value` 属性的对象。
    """
    pairs = {}

    def _put(name, value):
        if name and value is not None:
            pairs[str(name)] = str(value)

    for c in (cookies or []):
        got_morsel = False
        # ★ 判据是「值是不是 Morsel」（同时具备 .key 与 .value）—— 因为
        #   SimpleCookie 与普通 dict **都**有 .values()，只看方法名会误判。
        try:
            if hasattr(c, "values"):
                for v in c.values():
                    if hasattr(v, "key") and hasattr(v, "value"):
                        _put(getattr(v, "key", None), getattr(v, "value", None))
                        got_morsel = True
        except Exception:
            pass
        if got_morsel:
            continue
        if isinstance(c, dict):
            _put(c.get("name") or c.get("Name") or c.get("key"),
                 c.get("value") or c.get("Value"))
        else:
            _put(getattr(c, "name", None), getattr(c, "value", None))
    return pairs


def _to_header(pairs):
    return "; ".join(f"{k}={v}" for k, v in pairs.items())


# ---------- 方案B：常驻抓取会话（persist 模式） ----------
def _build_fetch_js(url: str, referer: str) -> str:
    """构造在页面内执行 `fetch()` 的 JS。用 JSON 字面量安全嵌入 URL（避免 % 格式化坑）。

    取回后 `JSON.stringify` 成字符串返回，父进程的 `browser_session` 再解析。
    同源约束：当前页面必须是目标 host（验证时已导航到该 host），否则浏览器会因 CORS 拒掉。
    """
    ref = json.dumps(referer or "")
    # 不拼格式化符，直接字符串拼接，URL 里的 % 不会被 Python % 操作符误读
    return (
        "(function(){return (async function(){"
        "try{"
        "var hd={'User-Agent':'" + UA + "'};"
        "if(" + ref + "){hd['Referer']=" + ref + ";}"
        "var r=await fetch(" + json.dumps(url) + ","
        "{credentials:'include',redirect:'follow',headers:hd});"
        "var t=await r.text();"
        "return JSON.stringify({ok:true,status:r.status,html:t});"
        "}catch(e){return JSON.stringify({ok:false,error:String(e)});}"
        "})();})()"
    )


def _watch_fetch():
    """后台线程：监听父进程写的抓取请求文件，用当前页面 fetch 后回写结果。

    与既有 `_watch_request`（cookie dump）同构 —— 都用文件协议，零 IPC 依赖。
    """
    import time as _t
    while True:
        _t.sleep(0.3)
        try:
            if not os.path.exists(BF_REQUEST):
                continue
            try:
                with open(BF_REQUEST, "r", encoding="utf-8") as f:
                    req = json.load(f)
                os.remove(BF_REQUEST)
            except Exception:
                continue
            url = req.get("url") or ""
            referer = req.get("referer") or ""
            rid = req.get("id") or "x"
            if not url:
                continue
            payload = {"ok": False, "error": "空 URL"}
            try:
                ret = _STATE["winref"].evaluate_js(_build_fetch_js(url, referer))
                if isinstance(ret, str):
                    try:
                        payload = json.loads(ret)
                    except Exception:
                        payload = {"ok": False, "error": f"fetch 返回无法解析：{ret[:200]}"}
                elif isinstance(ret, dict):
                    payload = ret
                else:
                    payload = {"ok": False, "error": f"fetch 返回类型异常：{type(ret)}"}
            except Exception as e:
                payload = {"ok": False, "error": f"fetch 执行失败：{e}"}
            # 原子写结果文件（父进程按 id 轮询）
            res_path = os.path.join(tempfile.gettempdir(), BF_RESULT_PREFIX + rid + ".json")
            try:
                d = os.path.dirname(os.path.abspath(res_path)) or "."
                fd, tmp = tempfile.mkstemp(prefix=".bfres_", dir=d)
                os.close(fd)
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False)
                os.replace(tmp, res_path)
            except Exception:
                pass
        except Exception:
            continue


def _enter_fetch_server():
    """把当前 WebView2 窗口转为常驻抓取后端。

    窗口不销毁（否则 webview.start() 会返回、子进程退出）；尽量把它挪到屏幕外、
    失去焦点，免得挡用户，但保持渲染与会话（cookie 罐保留，父进程随后用同会话 fetch）。
    """
    try:
        _STATE["winref"].evaluate_js(
            "try{window.moveTo(-32000,-32000);window.blur();}catch(e){}")
    except Exception:
        pass
    # 后台线程监听抓取请求（daemon，子进程退出即随亡）
    threading.Thread(target=_watch_fetch, daemon=True).start()



# ---------- 注入到页面的「读 Cookie」按钮 ----------
_JS = r"""
(function () {
  if (document.getElementById('__lmc_cf_bar')) { return; }
  var mk = function (txt, bg, fg) {
    var d = document.createElement('div');
    d.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483647;' +
      'padding:10px 16px;border-radius:8px;font:14px/1.4 system-ui,sans-serif;' +
      'cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,.35);background:' + bg +
      ';color:' + fg + ';user-select:none;';
    d.textContent = txt;
    d.id = '__lmc_cf_bar';
    return d;
  };
  var bar = mk('\u2714 我已完成验证，读取 Cookie', '#1f6feb', '#ffffff');
  bar.onclick = function () {
    bar.textContent = '正在读取…';
    try { window.pywebview.api.done(); } catch (e) {
      bar.textContent = '读取失败，请直接关闭窗口';
    }
  };
  document.body.appendChild(bar);
})();
"""


def main():
    if len(sys.argv) < 3:
        print("usage: cf_browser.py <url> <result_json> [host_filter]")
        return 2
    url = sys.argv[1]
    result_path = sys.argv[2]
    host_filter = sys.argv[3] if len(sys.argv) > 3 else ""
    res = Result(result_path)

    try:
        import webview
    except Exception as e:
        res.write({"ok": False, "error": f"内置浏览器不可用（pywebview 未安装）：{e}"})
        return 1

    # ★ 微博bot小助手 v1.4.4 的根因修复：Cloudflare / SSO 跳转会触发 WebView2 的
    #   NewWindowRequested，pywebview 默认会 webbrowser.open 把它交给**系统浏览器** ——
    #   表现为「点内置浏览器却跳出了 Edge」，登录/校验全程跑在窗口外，get_cookies()
    #   自然取不到。置 False 后新窗口请求一律在当前内嵌窗口内导航。
    try:
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
    except Exception:
        pass
    # 允许在页面里注入「读取 Cookie」按钮（pywebview 的 evaluate_js 需要它）
    try:
        webview.settings["ALLOW_DOWNLOADS"] = False
    except Exception:
        pass

    global _PERSIST
    _PERSIST = (len(sys.argv) > 4 and sys.argv[4] in ("1", "true", "persist"))
    # _STATE 已在模块级初始化（方案B 常驻抓取会话复用同一个窗口引用）

    class Api:
        def done(self):
            """页面按钮回调：读 cookie、写结果。
    
            v1.41.0（方案B）：若以 persist 模式启动（argv 第 5 位 = 1），取完 cookie **不销毁
            窗口**，而是把当前 WebView2 会话转为常驻抓取后端（`_enter_fetch_server`），让父进程
            的 `browser_session` 之后能用同一个浏览器会话去抓被 TLS/WAF 拦的页面。否则保持原行为
            （销毁窗口、会话结束）。
            """
            try:
                self._capture()
            finally:
                if _PERSIST:
                    try:
                        _enter_fetch_server()
                    except Exception:
                        pass
                else:
                    try:
                        _STATE["winref"].destroy()
                    except Exception:
                        pass
    
        def _capture(self, close_if_empty=True):
            """读一次 cookie。

            v1.40.2：`close_if_empty=False` 用于「按需 dump」—— 此时若没读到，
            不该写一个 ok:false 把结果文件钉死（用户可能只是还没过验证就点了按钮）。
            """
            pairs = {}
            try:
                pairs = _extract_pairs(_STATE["winref"].get_cookies(), host_filter)
            except Exception:
                pairs = {}
            if not pairs:
                if close_if_empty:
                    res.write({"ok": False, "error": "未读取到 Cookie，请确认已完成验证"})
                return False
            payload = {"ok": True, "cookie": _to_header(pairs),
                       "host": host_filter, "count": len(pairs)}
            if close_if_empty:
                res.write(payload)
            else:
                # 按需 dump：结果文件已写过就覆盖写一份新的（父进程轮询会拿到）
                try:
                    with open(result_path, "w", encoding="utf-8") as f:
                        json.dump(payload, f, ensure_ascii=False)
                    # 同时刷新持久快照
                    sp = snapshot_path()
                    with open(sp, "w", encoding="utf-8") as f:
                        json.dump(payload, f, ensure_ascii=False)
                except Exception:
                    pass
            return True

    api = Api()

    def on_loaded():
        # 每次导航后都补一次按钮（挑战页会自动刷新）
        try:
            _STATE["winref"].evaluate_js(_JS)
        except Exception:
            pass

    def _watch_request():
        """后台线程：父对话框点「读取 Cookie」会写请求文件，这里监听到就 dump 一次。

        v1.40.2（反馈 2）。用户不必再回到内置浏览器窗口去点那个按钮 ——
        主对话框上一个按钮就能把 cookie 拿回来。
        """
        req = request_path()
        while True:
            time.sleep(0.4)
            try:
                if not os.path.exists(req):
                    continue
                try:
                    os.remove(req)
                except Exception:
                    pass
                api._capture(close_if_empty=False)
            except Exception:
                pass

    try:
        win = webview.create_window(
            "站点验证 - 请在内置浏览器中完成验证",
            url=url,
            width=1000,
            height=740,
            js_api=api,
            # ★ v1.40.3（本轮反馈 2「点击没反应」）：**置顶**。
            #   真机复现（dev/_scratch/repro_builtin_click.py）证明窗口确实被创建了
            #   （vis=True / 1000×740 / (182,182)），但它和主程序（工具窗 + 「站点验证」
            #   对话框）**层层叠在一起、又不是置顶** → 用户点完按钮看不到任何新窗口，
            #   主观感受就是「点了没反应」，于是反复点。
            on_top=True,
            # focus=True（默认）：创建后立刻抢焦点、弹到最前 —— 保证用户第一眼就看得到。
            focus=True,
        )
        _STATE["win"] = win
        _STATE["winref"] = win
        win.events.loaded += on_loaded
        # 清掉可能残留的旧请求文件，免得一启动就误触发
        try:
            if os.path.exists(request_path()):
                os.remove(request_path())
        except Exception:
            pass
        threading.Thread(target=_watch_request, daemon=True).start()
        # private_mode=False：挑战 cookie 要留在会话里，避免每次导航都重新挑战
        webview.start(private_mode=False)
    except Exception as e:
        res.write({"ok": False, "error": f"内置浏览器启动失败：{e}"})
        return 1

    # webview.start() 返回 = 窗口被关闭。若按钮没点过（用户直接叉掉窗口），
    # 这里补一次读取 —— 只要窗口里已经过验证，cookie 通常在。
    if not res.written:
        api._capture()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        try:
            Result(sys.argv[2] if len(sys.argv) > 2 else
                   os.path.join(tempfile.gettempdir(), "lmc_cf_result.json")).write(
                {"ok": False, "error": traceback.format_exc(limit=3)})
        except Exception:
            pass
        sys.exit(1)
