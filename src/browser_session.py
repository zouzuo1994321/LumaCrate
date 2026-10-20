# -*- coding: utf-8 -*-
"""持久浏览器抓取会话（v1.41.0 · 方案B）。

为什么需要它
------------
演员刮削的 minnano-av / IMDB 两站，本机的 Python/curl 进程在 **TLS 握手层就被掐断**
（minnano 的 WinError 10054）或命中 **AWS WAF 挑战页**（IMDB），无头请求永远过不去；
而系统浏览器（WebView2）能正常打开 —— 因为它走的是真 Chromium 的 TLS/JA3 指纹，且能
执行挑战页 JS 换到放行 cookie。

`cf_browser.py` 已经能用 pywebview 开一个内嵌 WebView2 窗口让用户过一次校验，并把
`cf_clearance` 之类的通行 cookie 取回来。但原流程取完 cookie 就把窗口销毁了，而真正去
刮削的还是 `urllib` / `curl_cffi` —— 它的 TLS 栈照样被掐，cookie 跨不过去（minnano 甚至
连 HTTP 请求都发不出去，cookie 根本没机会用）。

⇒ 本模块把「验证后的 WebView2 窗口」**托管成常驻抓取会话**：窗口不销毁、会话与 cookie 罐
保留，刮削请求在 TLS/WAF 失败时改走这个浏览器会话用 `fetch()` 取回 HTML。浏览器取回的 HTML
与无头取回的完全一致，`minnano_search` / `minnano_fetch` / `imdb_*` 的解析逻辑一行都不用改。

与 cf_browser 的分工（文件协议，零 IPC 依赖，和既有 cookie 读取完全一致）
--------------------------------------------------------------------------
  · 父进程（本模块）写请求文件 `lmc_bf_request.json` = {url, referer, id}；
  · 子进程（cf_browser 在 persist 模式下）起一个后台线程监听该文件，用当前页面的
    `fetch(url, {credentials:'include'})` 取回 HTML，写结果文件
    `lmc_bf_result_<id>.json` = {ok, status, html, error}；
  · 父进程轮询结果文件，拿到 HTML 或异常。

会话是 **host 绑定**的：一个 WebView2 窗口 = 一个源站（验证时导航到哪个 host，就只能抓
那个 host 的页面，因为 `fetch` 受同源策略约束，且 cookie 按域生效）。因此按 host 维护
多个会话。

进程归属
--------
验证对话框（`ui_settings.CloudflareDialog`）spawn 子进程后，若「用内置浏览器抓取」开关打开，
就把存活的子进程 **移交** 给本模块的 `attach()`；本模块不负责 spawn（避免与对话框重复），
只负责持有引用、转发抓取请求、以及在窗口被用户关闭后自然失效。

默认行为
--------
开关 `config.scraper["browser_scrape"]` 默认 False → 本模块完全不参与，刮削走原无头路径，
与历史版本一致。只有用户显式打开开关、并对被拦的源点过一次「站点验证」后，才走浏览器会话。
"""
import json
import os
import threading
import time
import tempfile
import urllib.parse

REQUEST_NAME = "lmc_bf_request.json"
RESULT_PREFIX = "lmc_bf_result_"


def _req_path():
    return os.path.join(tempfile.gettempdir(), REQUEST_NAME)


def _result_path(rid):
    return os.path.join(tempfile.gettempdir(), RESULT_PREFIX + rid + ".json")


def _norm_host(x):
    """把「完整 URL」或「裸 host」都归一成 netloc（小写）。

    ⚠ `urlparse` 对没有 scheme 的裸 host（如 `www.minnano-av.com`）返回 `netloc=''`
    （它被当成 path）。所以 `alive()/detach()` 早先直接 `urlparse(host_url).netloc`，
    一旦调用方传进来的已是裸 netloc（`http_get` 就是这么调的），键就成空串 ——
    会话明明托管了却查不到，方案B 回退门因此永不开（「复测还是红」的真因之一）。
    """
    if not x:
        return ""
    h = urllib.parse.urlparse(x).netloc
    return (h or x).strip().lower()


class BrowserSession:
    """host -> 子进程 的常驻抓取会话表（模块级单例 `SESSION`）。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._procs = {}          # host -> subprocess.Popen
        self._enabled = False
        self._counter = 0

    # ---------- 开关 ----------
    def set_enabled(self, on):
        self._enabled = bool(on)

    def is_enabled(self):
        return self._enabled

    # ---------- 会话生命周期 ----------
    def attach(self, proc, host_url):
        """验证对话框把存活的子进程移交过来托管（不要 terminate）。"""
        host = _norm_host(host_url)
        with self._lock:
            # 同 host 已有旧会话 → 先回收
            old = self._procs.get(host)
            if old is not None:
                try:
                    if old.poll() is None:
                        old.terminate()
                except Exception:
                    pass
            self._procs[host] = proc
        return host

    def alive(self, host_url=None):
        """指定 host 的会话是否还活着（窗口没被关）。不传 host 则只要有任一会话活着即 True。"""
        with self._lock:
            if host_url:
                host = _norm_host(host_url)
                p = self._procs.get(host)
                return p is not None and p.poll() is None
            return any(p.poll() is None for p in self._procs.values())

    def hosts(self):
        with self._lock:
            return [h for h, p in self._procs.items() if p.poll() is None]

    def detach(self, host_url=None):
        """回收会话（用户关掉验证窗口、或切换开关时调用）。"""
        with self._lock:
            if host_url:
                host = _norm_host(host_url)
                p = self._procs.pop(host, None)
            else:
                p = None
                for h in list(self._procs.keys()):
                    self._procs.pop(h, None)
        if p is not None:
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception:
                pass

    # ---------- 抓取 ----------
    def get_html(self, url, referer="", timeout=25):
        """经由浏览器会话取回 `url` 的 HTML 文本。

        失败抛 `RuntimeError`（无会话）/ 或把子进程的 `error` 原样抛出。
        调用方应只在「无头路径已失败、且本会话对该 host 存活」时调用。
        """
        host = _norm_host(url)
        with self._lock:
            proc = self._procs.get(host)
        if proc is None or proc.poll() is not None:
            raise RuntimeError(f"没有 {host} 的浏览器会话（请先对该站做一次站点验证）")

        rid = f"{int(time.time()*1000)}_{os.getpid()}_{self._counter}"
        self._counter += 1
        req = {"url": url, "referer": referer or "", "id": rid}
        res_path = _result_path(rid)
        # 清掉可能残留的旧结果文件，避免读到上一轮的
        try:
            if os.path.exists(res_path):
                os.remove(res_path)
        except Exception:
            pass
        # 写请求（原子）
        try:
            d = os.path.dirname(os.path.abspath(_req_path())) or "."
            fd, tmp = tempfile.mkstemp(prefix=".bfreq_", dir=d)
            os.close(fd)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(req, f, ensure_ascii=False)
            os.replace(tmp, _req_path())
        except Exception as e:
            raise RuntimeError(f"写抓取请求失败：{e}")

        deadline = time.time() + max(5, timeout)
        while time.time() < deadline:
            if os.path.exists(res_path):
                try:
                    with open(res_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    try:
                        os.remove(res_path)
                    except Exception:
                        pass
                except Exception:
                    data = None
                if data and data.get("ok"):
                    html = data.get("html") or ""
                    if not html:
                        raise RuntimeError(f"{host} 浏览器会话取到空正文（HTTP {data.get('status')}）")
                    return html
                elif data:
                    raise RuntimeError(f"{host} 浏览器会话抓取失败：{data.get('error')}")
                # data 为空 → 文件还没写完，继续等
            time.sleep(0.2)
        raise RuntimeError(f"{host} 浏览器会话抓取超时（{timeout}s 无响应）")


# 模块级单例
SESSION = BrowserSession()
