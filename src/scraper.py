# -*- coding: utf-8 -*-
"""
演员信息刮削引擎
================
数据源（可在设置中选择与排序）：
  - **www.minnano-av.com**：日本 AV 女优资料站。按日文名检索，可取 别名/爱称、生日、身高三围、
    出身地、所属事务所、趣味、罗马音 与 专属头图。
  - **IMDB**：国际影人库。按英文名检索，取 生日、出生地、简介、头图（走页面内嵌的 JSON-LD）。

设计原则：
  - **仅用标准库**（urllib / re / json / html），不引入第三方依赖，便于 PyInstaller 单文件打包。
  - v1.39.0（需求 1）补充：minnano-av.com 已移到 Cloudflare 后，按 TLS 指纹（JA3）
    拦截非浏览器客户端 —— urllib 补多少请求头都会被 403（换代理 IP 无效）。
    应对（办法 C）：标准库路径做 **cookie 会话复用 + 首页预热**；连续 403 达阈值且
    环境装有 `curl_cffi` 时**自动降级**到它的 Chrome TLS/HTTP2 指纹。curl_cffi 是
    **可选依赖**：缺失时一切照旧（纯标准库模式），不强制打包进 exe。
  - 页面解析采用「标签定位 + 邻近文本」的容错写法：找不到字段就返回 None，绝不因某个字段结构变化而整体失败。
  - 每个字段都记录来源，便于后续排查；失败原因回传上层用于统计与提示。
"""
import gzip
import html
import http.cookiejar
import json
import os
import re
try:                                    # Windows 才有 winreg；其它平台置空
    import winreg
except Exception:                       # pragma: no cover
    winreg = None
import ssl
import time
import zlib
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------- 反指纹（v1.39.0 需求 1）
try:                                    # 可选依赖：装了才能走 Chrome TLS 指纹降级
    from curl_cffi import requests as _cffi_requests
except Exception:                       # 未安装 / 打包未含 → 纯标准库模式
    _cffi_requests = None

_CF_403_COUNT = {}      # host -> 连续 403 次数
_CF_403_LIMIT = 3       # 连续这么多次 403 就降级到 curl_cffi
_JAR = http.cookiejar.CookieJar()       # 全局 cookie 罐（Cloudflare 认 cookie 不认头）
_OPENERS = {}           # (proxy, verify_ssl) -> opener（会话复用）
_WARMED = {}            # host -> 上次首页预热的时间戳
_WARM_EVERY = 600       # 秒；cookie 过期后重新预热

# v1.40.0（反馈 3）：用户显式关掉代理后置 True —— 让 `http_get` 不再拿系统代理兜底。
# 为什么不只看「proxy 参数是否为空」：空串在老调用点（`download_photo` 等）代表
# 「没传，帮我探一下系统代理」，而用户点「关闭代理」时他的意思是「我要纯直连」——
# 两者在参数上无法区分，必须有一个显式的进程级标志。
_PROXY_FORCED_OFF = False


def set_proxy_disabled(flag: bool):
    """由设置页在切换「使用代理」开关时调用（v1.40.0 反馈 3）。"""
    global _PROXY_FORCED_OFF
    _PROXY_FORCED_OFF = bool(flag)


# ---------------------------------------------------------------- v1.40.0（反馈 4）
# 人工过一次 Cloudflare / AWS WAF 挑战，把拿到的通行 cookie 灌进全局罐 —— 之后所有
# 请求（urllib 与 curl_cffi 两条路）都带着它，不必再被拦。
#
# 背景（用户原话）：「切换代理或者关闭代理后一样不可用，网页登录显示一切正常，
# 如果有 cloudflare 则弹窗输入验证码。」
# 本机实测代码层已无解（urllib / curl_cffi / 换代理 / 直连全被挡），但**系统浏览器
# 一切正常** —— 说明出口 IP 没被封死，被拒的是「非浏览器客户端」。所以唯一可行的
# 出路是：借浏览器过一次挑战，把 cf_clearance 这类 cookie 取回来复用。
#
# 通行 cookie 的通用名（Cloudflare 用 cf_clearance；AWS WAF 用 aws-waf-token）。
_PASS_COOKIE_NAMES = ("cf_clearance", "aws-waf-token", "__cf_bm", "cf_chl_2",
                      "cf_chl_prog", "cf_chl_rc_ni")


def parse_cookie_header(raw: str) -> dict:
    """把用户粘进来的 cookie 串解析成 {name: value}。

    容错三种常见粘贴形态：
      · 整行 Cookie 请求头：`cf_clearance=abc; __cf_bm=xyz`（浏览器 DevTools 复制）
      · 多行（网络面板逐行复制）：每行仍是 `name=value`
      · name / value 分两列的表格粘贴：`cf_clearance\\tabc`
    值里可能含 `=`，所以只按**第一个** `=` 切。
    """
    out = {}
    for line in str(raw or "").replace("\r", "\n").split("\n"):
        line = line.strip()
        if line.lower().startswith("cookie:"):     # 整行 Cookie 请求头
            line = line[len("cookie:"):].strip()
        if not line:
            continue
        # 网络面板里逐行复制时是「name<TAB>value」；先把它改写成 name=value
        if "=" not in line and "\t" in line:
            line = line.replace("\t", "=", 1)
        for seg in line.split(";"):
            seg = seg.strip()
            if not seg:
                continue
            if "=" not in seg and "\t" in seg:
                seg = seg.replace("\t", "=", 1)
            if "=" not in seg:
                continue
            k, v = seg.split("=", 1)
            k, v = k.strip(), v.strip().strip('"')
            if k and v:
                out[k] = v
    return out


def inject_cookies(host_url: str, pairs: dict) -> int:
    """把 {name: value} 灌进全局 cookie 罐（urllib 路径）并记进 curl_cffi 的 cookie 串。

    返回成功注入的条数。cookie 的 domain 取 `host_url` 的 host、path 给 `/`，
    这样 `actress*.html`、`search_result.php` 等**全部站内路径**都带得上。
    """
    host = urllib.parse.urlparse(host_url).netloc
    n = 0
    for k, v in (pairs or {}).items():
        try:
            _JAR.set_cookie(http.cookiejar.Cookie(
                version=0, name=k, value=v, port=None, port_specified=False,
                domain=host, domain_specified=True, domain_initial_dot=False,
                path="/", path_specified=True, secure=True, expires=None,
                discard=False, comment=None, comment_url=None, rest={}, rfc2109=False))
            n += 1
        except Exception:
            continue
    if n:
        # 会话已变 → 作废已缓存的 opener 与降级计数，下一次请求立刻用上新 cookie
        _OPENERS.clear()
        _CF_403_COUNT.clear()
        _WARMED.clear()
        _MANUAL_COOKIES[host] = dict(pairs)
        _MANUAL_COOKIE_TS[host] = time.strftime("%Y-%m-%d %H:%M:%S")
    return n


_MANUAL_COOKIES = {}    # host -> {name: value}（用户手工注入的，供 UI 显示）
_MANUAL_COOKIE_TS = {}  # host -> 注入时间


def _manual_cookie_header(host: str) -> str:
    """把该 host 手工注入的 cookie 拼成 Cookie 头；没有则返回空串。
    专给 curl_cffi 用 —— 它不走 urllib 的 cookie 罐。"""
    ck = _MANUAL_COOKIES.get(host)
    if not ck:
        return ""
    return "; ".join(f"{k}={v}" for k, v in ck.items())


def has_pass_cookie(host_url: str) -> bool:
    """该 host 是否已有「通行 cookie」（cf_clearance / aws-waf-token 等）。"""
    host = urllib.parse.urlparse(host_url).netloc
    ck = _MANUAL_COOKIES.get(host) or {}
    if any(k in ck for k in _PASS_COOKIE_NAMES):
        return True
    try:
        return any(c.name in _PASS_COOKIE_NAMES for c in _JAR)
    except Exception:
        return False


def cookie_state(host_url: str) -> dict:
    """给 UI 用：该 host 的手工 cookie 概要与注入时间。"""
    host = urllib.parse.urlparse(host_url).netloc
    ck = _MANUAL_COOKIES.get(host) or {}
    return {"host": host, "count": len(ck),
            "names": sorted(ck.keys()),
            "has_pass": has_pass_cookie(host_url),
            "at": _MANUAL_COOKIE_TS.get(host, "")}


def clear_cookies(host_url: str = ""):
    """清掉（某个 host 的 / 全部的）手工 cookie。

    ⚠ 必须**同时**从 `_JAR` 里摘掉同名 cookie —— 光清 `_MANUAL_COOKIES` 是不够的：
    `has_pass_cookie()` 会回退到扫 `_JAR`，于是「清除」之后界面仍显示 ✅（探针实测踩到）。
    """
    global _MANUAL_COOKIES, _MANUAL_COOKIE_TS
    if host_url:
        host = urllib.parse.urlparse(host_url).netloc
        names = set(_MANUAL_COOKIES.get(host) or {})
        _MANUAL_COOKIES.pop(host, None)
        _MANUAL_COOKIE_TS.pop(host, None)
    else:
        names = set()
        for d in _MANUAL_COOKIES.values():
            names |= set(d)
        _MANUAL_COOKIES, _MANUAL_COOKIE_TS = {}, {}
    try:
        for c in list(_JAR):
            if c.name in names or not host_url:
                _JAR.clear(c.domain, c.path, c.name)
    except Exception:
        pass
    _OPENERS.clear()
    _CF_403_COUNT.clear()
    _WARMED.clear()

# ---------------------------------------------------------------- WAF 挑战页识别
# v1.39.4（反馈 1）：IMDB 检索「可访问但检索无结果」的**真因**不是解析写错了，
# 而是 AWS WAF 的 JS 挑战页 —— 它**回HTTP 200**，正文里一个 `/name/nm` 都没有，
# 只有 `awsWafCookieDomainList` 与 `challenge.js`。原来只按 403 计数触发降级，
# WAF 回 200 就永远降级不到 curl_cffi → 检索永远空。
# 同一类还有 Cloudflare 的「Just a moment...」/ cf-mitigated 挑战页。
_WAF_MARKS = (
    "awsWafCookieDomainList",   # AWS WAF
    "challenge.js",             # AWS WAF 挑战脚本
    "/cdn-cgi/challenge-platform",   # Cloudflare
    "Just a moment...",         # Cloudflare  interstitial标题
    "cf-mitigated",             # Cloudflare 响应头
    "Checking your browser",    # 通用前置校验
    "Enable JavaScript and cookies to continue",
)


def is_waf_challenge(text: str) -> bool:
    """判断正文是不是 WAF/反爬的**挑战页**（而不是真正的内容页）。

    v1.39.4（反馈 1）。必须放在 `http_get` 返回**之前**判断：这些页面 HTTP 码是
    200，走了「成功」分支，会一路流到解析器手里表现为「检索无结果」，
    让人误以为是选择器/正则失效。识别出来才能正确地切curl_cffi 指纹重试。
    """
    head = (text or "")[:4000]
    return any(m in head for m in _WAF_MARKS)


def _unwrap_reason(e: BaseException) -> BaseException:
    """把 `URLError` 剥到真正的原因。

    v1.39.4（反馈 1）：`urllib` 会把 `ssl.SSLError` **包进** `URLError`，
    所以 `except ssl.SSLError` **接不住** minnano 报的
    `[SSL: UNEXPECTED_EOF_WHILE_READING]` —— 实测
    `isinstance(e, ssl.SSLError)` 为 False、`type(e).__name__` 是 `URLError`，
    于是直接掉进兜底分支，证书降级重试**根本没被触发**。
    这里把 `.reason` 一路剥出来，让 SSL 类错误能被正确识别。
    """
    cur = e
    for _ in range(4):
        nxt = getattr(cur, "reason", None)
        if nxt is None or nxt is cur:
            break
        cur = nxt
    return cur

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

SOURCE_NAMES = {"minnano": "www.minnano-av.com", "imdb": "IMDB"}

MINNANO_BASE = "https://www.minnano-av.com/"
IMDB_BASE = "https://www.imdb.com/"


class ScrapeError(Exception):
    pass


# ---------------------------------------------------------------- HTTP
def _ssl_ctx(verify=True):
    if verify:
        return ssl.create_default_context()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _decode(raw: bytes, content_type: str = "") -> str:
    """按 header/meta 声明解码，失败则依次尝试常见日文编码。"""
    charset = ""
    m = re.search(r"charset=([\w\-]+)", content_type or "", re.I)
    if m:
        charset = m.group(1)
    if not charset:
        head = raw[:3000].decode("ascii", "ignore")
        m = re.search(r'charset=["\']?([\w\-]+)', head, re.I)
        if m:
            charset = m.group(1)
    for enc in [charset, "utf-8", "cp932", "euc_jp", "latin-1"]:
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


def _normalize_proxy(p: str) -> str:
    """把注册表里常见的**裸 `host:port`** 补成带 scheme 的 URL。

    v1.39.5（反馈 1）：Windows 的 `ProxyServer` 注册表值常写成 `127.0.0.1:8866`
    （无 `http://` 前缀）。`urllib` 的 ProxyHandler 会自动补，但 **`curl_cffi` 的
    `proxies=` 不会** —— 裸值会让它按畸形 URL 处理。实测两个端口都活着却全部失败，
    排查时极易误判成「站点拦截」。这里统一归一化，两条路径都拿到合法 URL。
    """
    p = (p or "").strip()
    if not p:
        return ""
    if "://" in p:
        return p
    # 支持 "http=host:port;https=host:port" 里已经拆出来的单段
    return "http://" + p


def _system_proxy() -> str:
    """读取系统代理：环境变量优先，其次 Windows IE/WinHTTP 设置。无则返回空串。

    v1.21.1（反馈 1）：用户电脑浏览器能开 minnano-av，但应用测连返回 HTTP 500 —— 根因之一
    是应用从不读系统代理（浏览器靠它出网），企业网/代理环境下 urllib 直接被拦。
    这里把系统代理自动补上，未显式设置代理时生效。
    """
    for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = (os.environ.get(k) or "").strip()
        if v:
            return _normalize_proxy(v)
    if winreg is not None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            ) as key:
                enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
                if enable:
                    server, _ = winreg.QueryValueEx(key, "ProxyServer")
                    server = str(server or "").strip()
                    if server:
                        # 形如 "http=host:port;https=host:port" 或 "host:port"
                        for part in server.split(";"):
                            if part.lower().startswith("https="):
                                return _normalize_proxy(part.split("=", 1)[1])
                        return _normalize_proxy(server)
        except Exception:
            pass
    return ""


def _browser_headers(referer: str = "") -> dict:
    """拟浏览器请求头。v1.21.1（反馈 1）：老 UA + 缺 Sec-Fetch/Sec-CH-UA 等头，
    容易被站点 WAF 判为爬虫而回 HTTP 500；补齐后通过率与浏览器一致。

    注意：Accept-Encoding 只声明 gzip/deflate（不上 br），因为标准库无法解 brotli，
    一旦声明 br 又收到 br 响应会解码失败 —— 编码差异不影响过 WAF。
    """
    h = {
        "User-Agent": UA,
        "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                   "image/avif,image/webp,*/*;q=0.8"),
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Sec-CH-UA": ('"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"'),
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
    }
    if referer:
        h["Referer"] = referer
    return h


def _opener(proxy: str, verify_ssl: bool):
    """按 (proxy, verify_ssl) 缓存 opener；cookie 罐全局共享 —— 会话复用。

    v1.39.0（需求 1）：老代码每次请求都 build_opener，Cloudflare 种下的 cookie
    用完即弃；复用同一个 opener（共享 _JAR）后续请求才带得上挑战 cookie。
    """
    key = (proxy, bool(verify_ssl))
    op = _OPENERS.get(key)
    if op is None:
        handlers = [urllib.request.HTTPCookieProcessor(_JAR)]
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        handlers.append(urllib.request.HTTPSHandler(context=_ssl_ctx(verify_ssl)))
        op = urllib.request.build_opener(*handlers)
        _OPENERS[key] = op
    return op


def _curl_get(url: str, timeout: int, proxy: str, referer: str) -> str:
    """curl_cffi 路径：完整 Chrome TLS/HTTP2 指纹（JA3 与浏览器一致）。
    curl_cffi 自动处理 gzip/br/deflate 解压，content 即原始字节。"""
    # v1.40.0（反馈 4）：把用户在「Cloudflare 验证」弹窗里手工注入的通行 cookie
    # 一并带上 —— curl_cffi **不走** urllib 的 cookie 罐（_JAR），必须单独拼头，
    # 否则「过一次挑战之后还是被拦」。
    hdrs = _browser_headers(referer)
    mc = _manual_cookie_header(urllib.parse.urlparse(url).netloc)
    if mc:
        hdrs["Cookie"] = mc
    try:
        r = _cffi_requests.get(
            url, impersonate="chrome124", headers=hdrs,
            timeout=timeout, verify=False,
            proxies=({"http": proxy, "https": proxy} if proxy else None),
        )
    except Exception as e:
        raise ScrapeError(f"{type(e).__name__}: {e}")
    # v1.39.4（反馈 1）：**AWS WAF 回 202** 表示「挑战已下发、但没通过」。
    # 它不是普通错误码，而是与 403 同类的拦截信号 —— 必须在**状态检查处**拦下，
    # 否则正文识别那一步根本轮不到，测连只显示一个莫名其妙的「HTTP 202」。
    if r.status_code in (202, 403):
        raise ScrapeError("命中反爬挑战页（WAF 回 %d）" % r.status_code)
    if r.status_code != 200:
        raise ScrapeError(f"HTTP {r.status_code}")
    ctype = ""
    try:
        ctype = r.headers.get("Content-Type") or ""
    except Exception:
        pass
    return _decode(r.content, ctype)


def _warmup(base: str, timeout: int, proxy: str):
    """首页预热：先访问一次主页，让 Cloudflare 种下挑战 cookie，再进检索/详情。

    v1.39.0（需求 1）。每 _WARM_EVERY 秒最多一次；失败静默（预热不了也照常发请求，
    预热本身也会走 403 计数，不会死循环）。
    """
    if not base:
        return
    host = urllib.parse.urlparse(base).netloc
    now = time.time()
    if now - _WARMED.get(host, 0) < _WARM_EVERY:
        return
    _WARMED[host] = now
    try:
        http_get(base, timeout=timeout, proxy=proxy)
    except Exception:
        pass


def http_get(url: str, timeout: int = 15, proxy: str = "", referer: str = "",
             verify_ssl: bool = True, _escalated: bool = False) -> str:
    """取回页面文本。自动处理 gzip/deflate 与日文编码。

    v1.21.1（反馈 1）：未显式给代理时自动套用系统代理；请求头补全浏览器字段，
    绕开把「缺头请求」判为爬虫的 WAF（原症状：浏览器能开、应用测连 HTTP 500）。
    v1.39.0（需求 1）：① cookie 罐 + opener 复用（会话保持）；② 连续 403 达阈值
    且装有 curl_cffi → 自动切 Chrome TLS 指纹（站点按 JA3 拦 urllib，换 IP 无效）。
    v1.39.4（反馈 1）：③ **命中 WAF 挑战页 / TLS 被对端断开时立即切指纹重试一次**
    （`_escalated` 保证只重试一次，不会死循环）——原先要攒够 3 次 403 才降级，
    而这类拦截**第一次就发生**，用户看到的就是「IMDB 可访问但检索无结果」。

    ⚠ v1.40.0（反馈 3）语义变更：本函数**不再**自己兜底套系统代理。
    代理由调用方（`config.Settings.scraper_proxy()`）按显式开关 `proxy_enabled` 解析 ——
    关掉时传进来就是空串，代表「用户要的就是纯直连」，此时**绝不能**用
    `_system_proxy()` 把它又补回去（那正是老版本「关代理关不掉」的根因）。
    下面保留的兜底只为**直接调用本函数、完全没传 proxy 参数**的老调用点服务，
    且仅在探测到确有系统代理时才生效（仍会被 `_PROXY_FORCED_OFF` 压住）。
    """
    global _PROXY_FORCED_OFF
    if proxy:
        _PROXY_FORCED_OFF = False
    elif not _PROXY_FORCED_OFF:
        proxy = _system_proxy()
    else:
        proxy = ""            # 用户显式选了直连 → 不套系统代理
    host = urllib.parse.urlparse(url).netloc
    # 已降级过一次就直接走 curl，不再回 urllib（避免来回弹）
    if _cffi_requests is not None and (_escalated
                                       or _CF_403_COUNT.get(host, 0) >= _CF_403_LIMIT):
        try:
            text = _curl_get(url, timeout, proxy, referer)
            if is_waf_challenge(text):
                raise ScrapeError("命中反爬挑战页（WAF）")
            _CF_403_COUNT[host] = 0
            return text
        except ScrapeError:
            if _escalated:
                raise           # 指纹也过不去 → 如实报错，别再试 urllib
            _CF_403_COUNT[host] = _CF_403_LIMIT   # 保持降级态，下次直接走 curl
            raise
    headers = _browser_headers(referer)
    req = urllib.request.Request(url, headers=headers)
    opener = _opener(proxy, verify_ssl)
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
            enc = (resp.headers.get("Content-Encoding") or "").lower()
            ctype = resp.headers.get("Content-Type") or ""
    except urllib.error.HTTPError as e:
        if e.code == 403:
            _CF_403_COUNT[host] = _CF_403_COUNT.get(host, 0) + 1
        raise ScrapeError(f"HTTP {e.code}")
    except urllib.error.URLError as e:
        # v1.39.4（反馈 1）：**必须先剥 `.reason`** —— urllib 把 ssl.SSLError 包在
        # URLError 里，原来的 `except ssl.SSLError` 永远接不到，
        # 于是 minnano 的 `[SSL: UNEXPECTED_EOF_WHILE_READING]` 直接落到兜底分支，
        # 既没触发证书降级、也没触发 curl_cffi 指纹降级。
        rsn = _unwrap_reason(e)
        if isinstance(rsn, ssl.SSLError):
            # UNEXPECTED_EOF_WHILE_READING 是**对端在握手后立刻断开**，
            # Cloudflare 用来挡非浏览器 TLS 指纹的经典手法 —— 证书不是问题，
            # 「关证书校验」重试毫无意义，**必须**换 curl_cffi 的 Chrome 指纹。
            if "UNEXPECTED_EOF_WHILE_READING" in str(rsn) or "EOF occurred" in str(rsn):
                _CF_403_COUNT[host] = _CF_403_COUNT.get(host, 0) + 1
                if not _escalated and _cffi_requests is not None:
                    return http_get(url, timeout, proxy, referer,
                                    verify_ssl, _escalated=True)
                raise ScrapeError(
                    "TLS 被对端断开（%s）：站点在按 TLS 指纹拦截，"
                    "需改用浏览器指纹访问" % type(rsn).__name__)
            if verify_ssl:
                # 其余 SSL 异常（证书/协议问题）→ 降级为不校验证书重试一次
                return http_get(url, timeout, proxy, referer, verify_ssl=False)
            raise ScrapeError(f"SSL 错误：{rsn}")
        raise ScrapeError(f"{type(rsn).__name__}: {rsn}")
    except ssl.SSLError as e:
        if verify_ssl:
            return http_get(url, timeout, proxy, referer, verify_ssl=False)
        raise ScrapeError(f"SSL 错误：{e}")
    except Exception as e:
        raise ScrapeError(f"{type(e).__name__}: {e}")
    _CF_403_COUNT[host] = 0

    if enc == "gzip":
        try:
            raw = gzip.decompress(raw)
        except Exception:
            pass
    elif enc == "deflate":
        try:
            raw = zlib.decompress(raw)
        except Exception:
            try:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            except Exception:
                pass
    text = _decode(raw, ctype)

    # v1.39.4（反馈 1）：WAF 挑战页回的是 **HTTP 200**，走的是「成功」分支。
    # 不拦住它，挑战页会一路流到解析器，表现为「检索无结果」，
    # 而真因是压根没拿到内容。这里识别出来、按 403 同等对待（触发指纹降级）。
    if is_waf_challenge(text):
        _CF_403_COUNT[host] = _CF_403_COUNT.get(host, 0) + 1
        if not _escalated and _cffi_requests is not None:
            return http_get(url, timeout, proxy, referer, verify_ssl,
                            _escalated=True)
        raise ScrapeError("命中反爬挑战页（WAF），需改用浏览器指纹访问")
    return text


# ---------------------------------------------------------------- 解析工具
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)


def strip_tags(s: str) -> str:
    return html.unescape(_TAG_RE.sub(" ", s or "")).strip()


def squeeze(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


# 站内标题常见的尾巴词：标题里往往夹着这些，取人名时必须剥掉
_NAME_TAIL = ("みんなのAV女優", "みんなのAV", "AV女優プロフィール", "女優プロフィール",
              "のプロフィール", "プロフィール", "AV女優", "女優",
              "動画", "画像", "作品一覧", "まとめ")


def clean_name(s: str) -> str:
    """从标题/主标题里剥出干净人名：去括号罗马音、去站点后缀、去分隔符右侧、去假名注音。"""
    s = squeeze(strip_tags(s or ""))
    if not s:
        return ""
    # 页面主标题形如「音琴るい ねごとるい / Negoto Rui」——假名注音与罗马音都在分隔符右侧
    s = re.split(r"[-|｜—–・、,，/／]", s)[0].strip()
    s = re.sub(r"（[^）]*）|\([^)]*\)", "", s).strip()
    # 去掉尾部的**纯假名**注音（『音琴るい ねごとるい』→『音琴るい』；纯假名名字如『さくら』不受影响）
    m = re.match(r"^(.+?)\s+[ぁ-んァ-ヶｦ-ﾟー\s]+$", s)
    if m:
        s = m.group(1).strip()
    changed = True
    while changed:
        changed = False
        for tail in _NAME_TAIL:
            if s.endswith(tail) and len(s) > len(tail):
                s = s[: -len(tail)]
                changed = True
    s = s.strip(" 　·・-–—の")
    return s if len(s) >= 2 else ""


def _meta(html_text: str, prop: str) -> str:
    """取 <meta property="og:image" content="...">；<meta> 属性顺序两种写法都兼容。"""
    for pat in (
        rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]*?content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]*?(?:property|name)=["\']{re.escape(prop)}["\']',
    ):
        m = re.search(pat, html_text, re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""


def _images(html_text: str):
    """收集页面内所有图片地址（含懒加载属性与 srcset）。"""
    out = []
    for m in re.finditer(r"<img\b[^>]*>", html_text, re.I):
        tag = m.group(0)
        for attr in ("data-src", "data-original", "data-lazy", "src", "srcset"):
            mm = re.search(rf'{attr}=["\']([^"\']+)["\']', tag, re.I)
            if mm:
                val = html.unescape(mm.group(1)).split()[0]
                if val and val not in out:
                    out.append(val)
    return out


# 刮削残留的「站内样板文案」特征词：命中即判为无效值（见 v1.11.0 演员卡乱码修复）
# v1.11.1 追加页面上的**功能区文案**（「別名を追加 → データを編集」被当成别名取进来过）
_JUNK_TOKENS = ("掲載", "情報交換", "無料動画", "アダルトビデオ",
                "property=", "content=", "og:",
                "データを編集", "ログイン後", "別名を追加", "編集でき")


def _clean_value(s: str, limit: int = 60) -> str:
    """把候选值清洗成纯文本：剥标签、断开未闭合标签残片、丢属性碎片。"""
    if not s:
        return ""
    s = html.unescape(str(s))
    s = _TAG_RE.sub(" ", s)
    s = s.split("<", 1)[0]                        # 未闭合标签起的残片一律丢弃
    s = re.sub(r"\s*(?:property|content)\s*=.*$", "", s, flags=re.I)
    s = squeeze(s)
    return s.strip("、。，, ｜| ・：: 　")[:limit]


def _valid_value(s: str) -> bool:
    """过滤命中的站内样板文案 / HTML 残片，避免把乱码写进 people.meta。"""
    if not s or len(s) > 60:
        return False
    return not any(t in s for t in _JUNK_TOKENS)


def _label_value(html_text: str, label: str, span: int = 400) -> str:
    """在**正文**中取标签文字（如「生年月日」）后紧随其后的单元格文本。

    v1.11.0 修复（演员卡乱码根因）：原实现直接在整个 HTML 里 `find(label)`，
    会先命中 `<head>` 里 `<meta property="og:description">` 的站内样板文案
    （「…（生年月日、出身地、サイズ、所属事務所など）を掲載。現在30歳。…」），
    再把**未闭合的 `<meta …` 标签残片**当数据写进 `people.meta`，于是演员卡上
    出现 `出身地：…"> <meta property="og:description" content="…` 这类乱码。
    现在：① 只在 `</head>` 之后的正文里查找；② 每个候选值先清洗并校验，
    不合格就继续找下一处，找不到则返回空串（宁缺勿脏）。
    """
    mh = re.search(r"</head\s*>", html_text, re.I)
    body = html_text[mh.end():] if mh else html_text
    idx = 0
    while True:
        i = body.find(label, idx)
        if i < 0:
            return ""
        idx = i + len(label)
        tail = body[idx: idx + span]
        # 优先取紧随其后的 <td>/<dd>/<span> 文本
        m = re.search(r"<(?:td|dd|span|div|p)\b[^>]*>(.*?)</(?:td|dd|span|div|p)>",
                      tail, re.S | re.I)
        if m:
            cand = _clean_value(m.group(1))
            if cand and _valid_value(cand):
                return cand
        cand = _clean_value(tail.replace("<", " <"))
        if cand and _valid_value(cand):
            return cand


def _description_texts(html_text: str, limit: int = 6) -> list:
    """取页面 `<head>` 里 description / og:description 的 content 文本。

    为什么需要它（v1.11.1）：minnano 的女优页**正文里没有「出身地」这一行**
    （站点只在已知时才输出，实测整页 0 次），但站点的描述 meta 里会写
    「…（生年月日、出身地、サイズ、所属事務所など）を掲載。現在32歳。出身地：山梨県。…」。
    所以出身地只能从 description 里取 —— 注意别误命中括号里那个「出身地、」（逗号不是冒号）。
    """
    out = []
    for m in re.finditer(r"<meta\b[^>]*>", html_text, re.I | re.S):
        tag = m.group(0)
        if not re.search(r"(?:og:description|name\s*=\s*[\"']description[\"'])", tag, re.I):
            continue
        c = re.search(r"content\s*=\s*[\"'](.*?)[\"']", tag, re.I | re.S)
        if c:
            out.append(html.unescape(c.group(1)))
        if len(out) >= limit:
            break
    return out


def _absolute(url: str, base: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    return urllib.parse.urljoin(base, url)


# ---------------------------------------------------------------- minnano-av
def minnano_search(name: str, timeout=15, proxy="") -> list:
    """检索女优，返回 [{name, url}]。"""
    _warmup(MINNANO_BASE, timeout, proxy)     # v1.39.0（需求 1）：先预热拿 cookie
    q = urllib.parse.quote(name, encoding="utf-8")
    url = f"{MINNANO_BASE}search_result.php?search_scope=actress&search_word={q}"
    text = http_get(url, timeout, proxy, referer=MINNANO_BASE)
    hits, seen = [], set()
    for m in re.finditer(r'href=["\'](?:https?://www\.minnano-av\.com/)?actress(\d+)\.html["\'][^>]*>(.*?)</a>',
                         text, re.S | re.I):
        aid, inner = m.group(1), squeeze(strip_tags(m.group(2)))
        if aid in seen:
            continue
        seen.add(aid)
        hits.append({"name": inner or name, "url": f"{MINNANO_BASE}actress{aid}.html"})
    return hits


def minnano_fetch(url: str, timeout=15, proxy="") -> dict:
    """取女优详情：别名/生日/身高三围/出身地/事务所/罗马音/头图。"""
    _warmup(MINNANO_BASE, timeout, proxy)     # v1.39.0（需求 1）：先预热拿 cookie
    text = http_get(url, timeout, proxy, referer=MINNANO_BASE)
    aid = ""
    m = re.search(r"actress(\d+)\.html", url)
    if m:
        aid = m.group(1)

    data = {"source": "minnano", "source_url": url, "name": "", "photo_url": "",
            "alias": "", "birthday": "", "romaji": "", "bio": "", "meta": {}, "status": ""}

    # 姓名：优先页面主标题（h1/h2），其次 <title>，都要剥掉站内后缀与括号罗马音
    for pat in (r"<h1[^>]*>(.*?)</h1>", r"<h2[^>]*>(.*?)</h2>",
                r"<title[^>]*>(.*?)</title>"):
        t = re.search(pat, text, re.S | re.I)
        if not t:
            continue
        nm = clean_name(strip_tags(t.group(1)))
        if nm:
            data["name"] = nm
            break

    # 罗马音：标题或名字行里的「（にいむらあかり / Niimura Akari）」
    mr = re.search(r"[/／]\s*([A-Za-z][A-Za-z\-\s\.']{2,40})[）)]", text)
    if mr:
        data["romaji"] = squeeze(mr.group(1))

    # 头图：og:image 优先，其次按女优 id 命中的图片
    photo = _meta(text, "og:image")
    if not photo:
        for u in _images(text):
            uu = _absolute(u, MINNANO_BASE)
            low = uu.lower()
            if any(k in low for k in (".gif", "banner", "logo", "spacer", "icon", "btn")):
                continue
            if aid and aid in low:
                photo = uu
                break
            if any(k in low for k in ("actress", "picture", "photo", "image")):
                photo = photo or uu
    data["photo_url"] = _absolute(photo, MINNANO_BASE)

    alias = _label_value(text, "別名")
    if alias:
        alias = re.split(r"[（(]", alias)[0].strip()
        # 页面里写作「朝海 汐「AV女優」」——引号里的身份标注不是名字的一部分
        alias = re.sub(r"[「『][^」』]*[」』]", "", alias).strip()
    if not alias:
        alias = _label_value(text, "愛称")
    data["alias"] = alias[:120]

    raw_bday = _label_value(text, "生年月日")
    mb = re.search(r"(\d{4})\s*[年/\-]\s*(\d{1,2})\s*[月/\-]\s*(\d{1,2})", raw_bday or "")
    if mb:
        data["birthday"] = f"{mb.group(1)}-{int(mb.group(2)):02d}-{int(mb.group(3)):02d}"

    meta = {}
    mt = re.search(r"T(\d{2,3})", _label_value(text, "サイズ"))
    if mt:
        meta["身高"] = mt.group(1) + "cm"
    size = _label_value(text, "サイズ")
    if size:
        meta["尺寸"] = size[:80]
    for labels, key in ((("出身地",), "出身地"), (("所属事務所",), "事务所"),
                        (("趣味・特技", "趣味"), "趣味"),
                        (("AV出演期間",), "出演期間"), (("デビュー作品",), "出道作")):
        for label in labels:
            v = _label_value(text, label)
            if v:
                meta[key] = v[:120]
                break
    # 出身地：正文常整行缺席，改从站点描述 meta 取（形如「現在32歳。出身地：山梨県。」）
    if not meta.get("出身地"):
        for desc in _description_texts(text):
            md = re.search(r"出身地[：:]\s*([^\s。、，,｜|]{1,16})", desc)
            if md:
                meta["出身地"] = md.group(1)
                break
    # 罩杯（来自尺寸串里的「Jカップ」），卡片「胸围」显示时可用
    # 注意：不要写成 [A-HK-Z] —— 那会把 I 和 **J** 一起排除掉，J 罩杯是常见尺寸。
    mc = re.search(r"([A-Z])\s*カップ", size or "")
    if mc:
        meta["罩杯"] = mc.group(1)
    tags = [squeeze(strip_tags(x)) for x in
            re.findall(r"actress_list\.php\?tag_a_id=\d+[^>]*>(.*?)</a>", text, re.S | re.I)]
    tags = [x for x in tags if x]
    if tags:
        meta["标签"] = " / ".join(tags[:10])
    data["meta"] = meta

    # 由「出演期間」启发式推断现役/退役（仅作便利，用户可在详情页手动修正）
    # v1.11.0：兼容全角数字（真机库里出现过「２０２４～」）与开区间写法（「2023年 -」）
    period = _clean_value(meta.get("出演期間", "")) or (meta.get("出演期間") or "")
    period_a = period.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if period_a:
        if (re.search(r"現在|至今|現役|継続|activity|present|active", period_a, re.I)
                or re.search(r"[-–~〜～]\s*$", period_a)):
            data["status"] = "现役"
        elif re.search(r"(\d{4})\s*年?\s*[-–~/〜～]\s*(\d{4})", period_a):
            data["status"] = "退役"

    bits = []
    if data["birthday"]:
        bits.append("生日 " + data["birthday"])
    if meta.get("身高"):
        bits.append("身高 " + meta["身高"])
    if meta.get("尺寸"):
        bits.append(meta["尺寸"])
    if meta.get("出身地"):
        bits.append("出身地 " + meta["出身地"])
    if meta.get("事务所"):
        bits.append("事务所 " + meta["事务所"])
    if meta.get("出演期間"):
        bits.append("出演 " + meta["出演期間"])
    if meta.get("标签"):
        bits.append("标签 " + meta["标签"])
    data["bio"] = " ｜ ".join(bits)
    return data


# ---------------------------------------------------------------- IMDB
def imdb_search(name: str, timeout=15, proxy="") -> list:
    _warmup(IMDB_BASE, timeout, proxy)        # v1.39.0（需求 1）：先预热拿 cookie
    q = urllib.parse.quote(name, encoding="utf-8")
    url = f"{IMDB_BASE}find/?q={q}&s=nm"
    text = http_get(url, timeout, proxy, referer=IMDB_BASE)
    hits, seen = [], set()
    for m in re.finditer(r'href=["\'](?:https?://(?:www\.)?imdb\.com)?/name/(nm\d+)/?[^"\']*["\']',
                         text, re.I):
        nid = m.group(1)
        if nid in seen:
            continue
        seen.add(nid)
        hits.append({"name": name, "url": f"{IMDB_BASE}name/{nid}/"})
        if len(hits) >= 8:
            break
    return hits


def imdb_fetch(url: str, timeout=15, proxy="") -> dict:
    text = http_get(url, timeout, proxy, referer=IMDB_BASE)
    data = {"source": "imdb", "source_url": url, "name": "", "photo_url": "",
            "alias": "", "birthday": "", "romaji": "", "bio": "", "meta": {}}

    # 页面内嵌 JSON-LD（最稳）
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                         text, re.S | re.I):
        raw = m.group(1).strip()
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        items = obj if isinstance(obj, list) else [obj]
        for it in items:
            if not isinstance(it, dict):
                continue
            if str(it.get("@type", "")).lower() not in ("person", "movie", "tvseries"):
                continue
            data["name"] = data["name"] or squeeze(str(it.get("name") or ""))
            img = it.get("image")
            if isinstance(img, dict):
                img = img.get("url")
            data["photo_url"] = data["photo_url"] or (img or "")
            bd = str(it.get("birthDate") or "")
            if bd and not data["birthday"]:
                data["birthday"] = bd[:10]
            bp = it.get("birthPlace")
            if isinstance(bp, dict):
                bp = bp.get("name")
            if bp:
                data["meta"]["出生地"] = squeeze(str(bp))[:80]
            desc = it.get("description")
            if desc:
                data["bio"] = squeeze(strip_tags(str(desc)))[:600]
            alt = it.get("alternateName")
            if alt:
                data["alias"] = (", ".join(alt) if isinstance(alt, list) else str(alt))[:120]

    if not data["photo_url"]:
        data["photo_url"] = _absolute(_meta(text, "og:image"), IMDB_BASE)
    if not data["name"]:
        t = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
        if t:
            data["name"] = re.split(r"[-|]", squeeze(strip_tags(t.group(1))))[0].strip()
    if not data["bio"]:
        m = re.search(r'data-testid=["\']bio-text["\'][^>]*>(.*?)</div>', text, re.S | re.I)
        if m:
            data["bio"] = squeeze(strip_tags(m.group(1)))[:600]
    data["meta"].setdefault("简介来源", "IMDB")
    return data


# ---------------------------------------------------------------- 统一入口
SEARCHERS = {"minnano": minnano_search, "imdb": imdb_search}
FETCHERS = {"minnano": minnano_fetch, "imdb": imdb_fetch}


def _network_hint(proxy: str) -> str:
    """拦截类错误时补一句「这不是代码问题」的判定，并点出系统代理这个常见元凶。

    v1.39.4（反馈 1）。实测：minnano-av 的 TLS 被对端断开、IMDB 回 AWS WAF 挑战页，
    **换 curl_cffi 指纹、绕代理、直连都不通**，而 baidu / cloudflare.com 都正常
    —— 说明是本机到这两个站点的网络链路（或出口 IP）被挡，不是解析逻辑或指纹问题。
    这类情况下继续重试没有意义，必须让人知道「要换网络/代理」。

    ★★ v1.40.2（反馈 2）**重要更正** —— 老文案把根因说错了。
    用户实测（E 盘探针逐条对照，2026-10-13 15:xx）：
      · TCP 能连上（IPv4/IPv6 都通，都是 Cloudflare 的地址）；
      · **TLS 握手第一步就被对端 RST** —— `ConnectionResetError [WinError 10054]`；
      · urllib / curl_cffi（chrome110/120/124/131、safari17、firefox133、edge101 全试过）
        / 裸 `ssl` 模块，**无一例外都在 ClientHello 阶段被重置**；
      · 走系统代理、直连，结果完全一样；
      · 而 cloudflare.com / baidu.com 直连都 200。

    ⇒ **这是「连接在 TLS 层就被掐断」，HTTP 请求根本没发出去，cookie 更没有机会被发送。**
    也就是说：**取回 cf_clearance 也救不了这个 —— 拦的不是 cookie，是 TLS 握手本身。**
    旧文案「浏览器能打开说明出口 IP 没被拒，缺的只是通行 cookie」是**错误推断**，
    害得用户在「取 cookie」这条死路上反复试（日志里连试了 8 次）。
    真实分界是：**本机的 Python/curl 进程走的链路被中间设备（防火墙/安全软件/运营商）
    按进程或按 TLS 特征掐断，而浏览器进程不受影响。** 所以出路是「换网络 / 换代理 /
    让浏览器所在的进程去抓取」，不是「取 cookie」。
    """
    bits = []
    sp = proxy or ("" if _PROXY_FORCED_OFF else _system_proxy())
    if sp:
        bits.append(f"当前走系统代理 {sp}")
    else:
        bits.append("当前为直连（未启用代理）")
    bits.append("已尝试浏览器 TLS 指纹（curl_cffi）仍被挡")
    bits.append("连接在 TLS 握手阶段即被重置（HTTP 请求没发出，与 cookie 无关）")
    bits.append("请换网络 / 换代理再试；若浏览器能开而本软件不能，"
                "多为本机防火墙或安全软件按进程拦截")
    return "；".join(bits)


def _waf_outlet(source: str) -> str:
    """★ v1.40.4（反馈 2）：命中 WAF 挑战页时，按**数据源**给出真正可行动的出路。

    用户原话「握手成功了也不太行」。上一版只把「命中反爬挑战页」翻译一遍，
    没告诉他**这个站的挑战页到底靠什么放行**、以及**本软件能不能做到** ——
    于是他在「取 cookie」上反复试。实测（2026-10-13，直连，E 盘探针）：

      · **IMDB**：TCP 通 → TLSv1.3 握手成功 → HTTP 202 → 正文是 AWS WAF 挑战页
        （`window.awsWafCookieDomainList = ['imdb.com']` + `gokuProps`）。
        放行凭据是 `aws-waf-token`，**必须由浏览器执行 `challenge.js` 才能拿到**。
      · **minnano-av**：TCP 通 → **TLS 握手就被 RST**（`WinError 10054`），
        连 HTTP 请求都没发出去。同一台机、同样直连，**系统浏览器能开** ——
        说明是本机 Python / curl 进程被按进程（或按 TLS 特征）掐断，
        与 cookie、与出口 IP 都无关。

    ⇒ 两个站的出路**完全不同**，笼统说「换网络/换代理」是误导。这里按源分开给。
    """
    if source == "imdb":
        return ("IMDB 用的是 **AWS WAF**：放行凭据是 `aws-waf-token`，"
                "必须由浏览器执行 `challenge.js` 才能生成 —— "
                "本软件的无头请求拿不到它，**取 cookie 也拿不到**。"
                "可行出路：① 用「站点验证」里的内置浏览器过一次人机校验；"
                "② 或直接改用 minnano 作为该演员的数据源。")
    if source == "minnano":
        return ("minnano-av 是 **Cloudflare 指纹校验**：实测本机连 **TLS 握手都被 RST**"
                "（HTTP 请求根本没发出去），而同一台机的浏览器能正常打开 —— "
                "说明是本机 Python 进程的链路被中间设备按进程掐断，"
                "**与 cookie 无关**。可行出路：① 换网络（手机热点试一次可立即判定）；"
                "② 换一个能过 Cloudflare 的代理；③ 排查本机防火墙 / 安全软件 / VPN 的"
                "「按进程拦截」规则。")
    return ("该站启用了反爬挑战（Cloudflare / AWS WAF 一类）：放行凭据要由浏览器"
            "执行 JS 才能生成，本软件的无头请求拿不到。可行出路：换网络 / 换代理，"
            "或用「站点验证」的内置浏览器过一次校验。")


def _explain(msg: str, source: str) -> str:
    """把拦截类错误翻译成人话，并区分「代码问题」与「网络问题」。"""
    # v1.40.0（反馈 4）：curl_cffi 的报错文案与 urllib 完全不同 ——
    # 它走 BoringSSL，被对端断开时长这样：
    #   `SSLError: Failed to perform, curl: (35) BoringSSL SSL_connect:
    #    Connection closed abruptly (SSL_ERROR_SYSCALL; error queue empty)`
    # 老分支只认 "TLS 被对端断开" / "UNEXPECTED_EOF"，于是这条最关键的报错
    # 直接落到兜底原样透出，用户看到一串英文什么也做不了。
    if ("TLS 被对端断开" in msg or "UNEXPECTED_EOF" in msg
            or "BoringSSL" in msg or "SSL_connect" in msg
            or "Connection closed abruptly" in msg or "curl: (35)" in msg):
        return ("站点在 TLS 握手后立刻断开连接（按客户端指纹拦截）："
                + _network_hint(""))
    if "WAF" in msg or "挑战页" in msg:
        # ★ v1.40.4（反馈 2）：原来这里只有一句「命中反爬挑战页 + _network_hint()」，
        # 而 `_network_hint()` 讲的是 **TLS 被 RST** 的结论 —— 与「TLS 通了、
        # 只是正文是挑战页」**不是同一个病**。用户看到的就是一句自相矛盾的说明。
        # 改成按数据源给**针对该站挑战机制**的出路（见 `_waf_outlet`）。
        code = ""
        m = re.search(r"回\s*(\d{3})", msg)
        if m:
            code = f"（HTTP {m.group(1)}）"
        return (f"命中反爬挑战页{code}：站点用的是 JS 挑战，"
                "**回 HTTP 200/202 也是挑战页**，不等于拿到了正文。"
                + _waf_outlet(source))
    # v1.39.4：AWS WAF 在**放行挑战**时回的就是 202（不是 200 也不是 403），
    # curl_cffi 的状态检查先一步抛了「HTTP 202」，轮不到正文识别 ——
    # 所以这里把 202 也翻译成「被反爬拦截」，别让用户以为是普通错误码。
    if msg.strip() == "HTTP 202":
        return "命中反爬挑战页（WAF 回 202，即校验未通过、没拿到正文）：" \
               + _network_hint("")
    if "403" in msg and source == "minnano":
        # v1.39.5（反馈 1）：这段文案原来**只说了「已自动切换指纹重试」，没有出路** ——
        # 用户看到「站点 Cloudflare 指纹校验拦截了标准库客户端；已自动切换浏览器指纹重试」
        # 只能干瞪眼。而实测本机三种走法（走 8866 代理 → 403 / 走 4328 代理 → TLS 断开 /
        # 完全直连 → 连接重置）**全被挡**，说明是出口 IP / 站点级拦截，
        # 与其它分支保持一致，统一补上 `_network_hint()` 的「换网络/换代理可解」。
        try_extra = ("（已自动切换到浏览器 TLS 指纹重试，仍被挡）"
                     if _cffi_requests is not None
                     else "（装 curl_cffi 可启用浏览器指纹模式，但本机实测同样过不去）")
        return ("站点按客户端 TLS 指纹拦截（HTTP 403）：" + try_extra + "："
                + _network_hint(""))
    return msg


def diagnose_host(host_url: str, proxy: str = "", timeout: int = 8) -> dict:
    """★ v1.40.2（反馈 2）：把「到底为什么连不上」的分层探针做成可调用的诊断。

    用户原话：「查看运行日志，查明 cookie 失败原因」。日志能告诉他「失败了」，
    但不能告诉他「失败在哪一层」—— 于是他在「取 cookie」这条**死路**上反复试了 8 次。
    本函数按网络分层逐级探，给出**决定性判据**：

      ① TCP 能否建连（能 → 不是 DNS/IP 封死）；
      ② TLS 握手能否完成（不能且是被 RST → ★ 关键结论：拦在握手，
         HTTP 请求没发出去，**cookie 无关**）；
      ③ 对照站点（cloudflare.com）能否通（能 → 本机出网正常，是目标站针对）。

    返回 `{stage, ok, verdict, detail}`：`stage` 是失败所在层，
    `verdict` 是一句人话结论。

    ★ v1.40.4（反馈 2）**重要补层** —— 用户原话「**握手成功了也不太行**」。
    上一版探到 TLS 通就 `return` 了，verdict 写「网络链路正常（TCP + TLS 都通）
    —— 若仍被拦，才是 cookie / WAF 层的问题。」这是**把球踢回给用户**：
    他拿到的仍是「不可用 — 命中反爬挑战页」（实测 IMDB 就是这样：TLSv1.3 握手成功、
    HTTP 200/202、正文却是 AWS WAF 的挑战页），而这句话没告诉他**下一步做什么**，
    并且**同一站点在不同轮次被判成 tls / http 摇摆**（因为探针对 minnano 会随机
    落在「TLS 被 RST」与「侥幸握手成功但正文仍是挑战页」两种结果上）。

    ⇒ 现在**继续探第 ④ 层 HTTP**：真发一次请求、看拿回来的是正文还是挑战页。
      探测结果落进 `waf`（是否挑战页）/ `http_code` / `body_len` 三个字段，
      verdict 按**真实结果**分三种给结论 + 出路，不再有「若仍被拦…才是…」这种空话。
    """
    import socket
    import ssl as _ssl
    host = urllib.parse.urlparse(host_url).netloc or host_url
    host = host.split(":")[0]
    port = 443
    out = {"stage": "unknown", "ok": False, "verdict": "", "detail": [],
           "waf": False, "http_code": 0, "body_len": 0}

    # ① TCP
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        out["detail"].append(f"① TCP 连接 {host}:{port} 成功（DNS / 路由正常）")
    except Exception as e:
        out["stage"] = "tcp"
        out["verdict"] = (f"TCP 都连不上（{type(e).__name__}: {e}）—— DNS 或网络不通，"
                          "不是 cookie 问题。")
        out["detail"].append(f"① TCP 连接失败：{type(e).__name__}: {e}")
        return out

    # ② TLS
    try:
        ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        try:
            ctx.set_alpn_protocols(["h2", "http/1.1"])
        except Exception:
            pass
        ss = ctx.wrap_socket(sock, server_hostname=host)
        ver = ss.version()
        ss.close()
        out["detail"].append(f"② TLS 握手成功（{ver}）")
    except Exception as e:
        try:
            sock.close()
        except Exception:
            pass
        out["stage"] = "tls"
        out["ok"] = False
        out["verdict"] = (
            "★ 决定性判据：TCP 通、但 **TLS 握手就被对端重置**"
            f"（{type(e).__name__}）。HTTP 请求根本没发出去，"
            "**cookie 在这一步还没轮到被使用 —— 取多少 cookie 都没用。** "
            "请换网络 / 换代理，或排查本机防火墙、安全软件、VPN 是否按进程/按 TLS 特征拦截。")
        out["detail"].append(f"② TLS 握手失败：{type(e).__name__}: {e}")
        return out

    # ★ ③ v1.40.4 新增：HTTP 层实测 —— 拿回来的是正文还是挑战页？
    # 这是「握手成功也不太行」的正面回答：TLS 通只说明链路通，
    # **能不能拿到正文**要看这一层。
    #
    # ⚠ 这里**不能直接用 `http_get()` 的返回值判挑战页**：`http_get` 见到
    # AWS WAF 的 202 会在状态检查处就抛 `ScrapeError`（v1.39.4 的改动），
    # **正文根本没机会被拿到** → body 长度为 0 → 会被误判成「HTTP 层硬拦截」，
    # 而真相是「拿到了挑战页正文」（实测 IMDB：202 + 1997 字节挑战页）。
    # 所以这里**自己发一次请求、拿到正文看内容**，再用 `is_waf_challenge` 判定。
    body = ""
    try:
        hdrs = _browser_headers()
        req = urllib.request.Request(host_url, headers=hdrs)
        with _opener(proxy, False).open(req, timeout=timeout) as resp:
            raw = resp.read()
            enc = (resp.headers.get("Content-Encoding") or "").lower()
            ctype = resp.headers.get("Content-Type") or ""
            out["http_code"] = resp.status
        if enc == "gzip":
            try:
                raw = gzip.decompress(raw)
            except Exception:
                pass
        elif enc == "deflate":
            try:
                raw = zlib.decompress(raw)
            except Exception:
                pass
        body = _decode(raw, ctype)
    except urllib.error.HTTPError as e:
        out["http_code"] = e.code
        # 4xx/5xx 也可能**带着挑战页正文**（AWS WAF 有时回 403 + 挑战页）
        try:
            raw = e.read()
            if (e.headers.get("Content-Encoding") or "").lower() == "gzip":
                try:
                    raw = gzip.decompress(raw)
                except Exception:
                    pass
            body = _decode(raw, e.headers.get("Content-Type") or "")
        except Exception:
            body = ""
    except Exception as e:
        out["detail"].append(f"③ HTTP 请求失败：{type(e).__name__}: {e}")

    out["body_len"] = len(body or "")
    out["waf"] = bool(body) and is_waf_challenge(body)

    if out["waf"]:
        out["stage"] = "waf"
        out["ok"] = False
        out["verdict"] = (
            "★ 决定性判据：TCP + TLS **都通**，但拿回来的是**反爬挑战页**"
            f"（正文 {out['body_len']} 字节，HTTP {out['http_code'] or '?'}，"
            "只有挑战脚本、没有正文）。"
            "**这不是 cookie 能解的** —— 挑战页要靠浏览器**执行 JS** 换取放行凭据"
            "（Cloudflare 的 cf_clearance / AWS WAF 的 aws-waf-token），"
            "本软件的无头请求永远拿不到。")
        out["detail"].append(
            "③ 正文识别为反爬挑战页（HTTP 200/202 也会是挑战页，别被状态码骗了）")
        return out

    if out["body_len"] > 0:
        out["stage"] = "ok"
        out["ok"] = True
        out["verdict"] = (f"链路与正文都正常（TCP + TLS + HTTP {out['http_code']}，"
                          f"正文 {out['body_len']} 字节）—— 若仍失败，是站点结构变动，"
                          "不是网络或 cookie 问题。")
        out["detail"].append(f"③ 已拿到正文 {out['body_len']} 字节（非挑战页）")
        return out

    # TLS 通、HTTP 却什么都没拿到 → 拦在 HTTP 层（状态码 4xx/5xx 或空响应）
    out["stage"] = "http"
    out["ok"] = False
    code = out["http_code"]
    if code in (202, 403):
        out["verdict"] = (
            f"★ TCP + TLS 都通，HTTP 返回 {code} —— **反爬的硬拦截**（不是挑战页正文，"
            "是在状态码上直接拒了）。取 cookie 解决不了，需换网络 / 换代理 / 换出口 IP。")
    else:
        out["verdict"] = (
            f"TCP + TLS 都通，但 HTTP 层没拿到正文"
            f"（{'HTTP %s' % code if code else '无状态码'}）—— 拦在应用层，"
            "与 cookie / 指纹有关；可先试「用浏览器过一次验证」再复测。")
    out["detail"].append(f"③ HTTP 层未取到正文（HTTP {code or '?'}）")
    return out


def test_source(source: str, proxy="", timeout=12) -> dict:
    """连接自检：返回 {ok, msg, ms}。

    v1.39.4（反馈 1）：**「可访问，但检索无结果」是最误导的结论**——
    它其实一次正文都没拿到（WAF 挑战页回的是 HTTP 200，被当成成功）。
    现在把拦截原因如实报出来，并明确区分「站点结构变动」与「被反爬拦截」。

    v1.40.2（反馈 2）：失败时附上 `diag`（`diagnose_host` 的分层结果），
    让 UI / 日志能给出**可据以行动**的根因，而不是一句笼统的「被拦」。
    """
    t0 = time.time()

    def done(ok, msg, diag=None):
        r = {"ok": ok, "msg": msg, "ms": int((time.time() - t0) * 1000)}
        if diag is not None:
            r["diag"] = diag
        return r

    base = ("https://www.minnano-av.com/" if source == "minnano"
            else "https://www.imdb.com/")
    try:
        if source == "minnano":
            hits = minnano_search("新村あかり", timeout=timeout, proxy=proxy)
        elif source == "imdb":
            hits = imdb_search("Emma Stone", timeout=timeout, proxy=proxy)
        else:
            return done(False, f"未知数据源 {source}")
        if hits:
            return done(True, f"可访问，检索测试命中 {len(hits)} 条")
        # v1.39.4：走到这里说明 http_get 没抛异常，正文是真拿到了但没匹配到条目。
        # 那才是「结构变动」；若正文其实是挑战页，http_get 已经拦下抛错了。
        return done(False, "已取到页面但未匹配到条目（站点结构可能变动，"
                           "或该测试名在本站不存在）")
    except ScrapeError as e:
        msg = _explain(str(e), source)
        diag = None
        try:
            diag = diagnose_host(base, proxy, min(timeout, 8))
        except Exception:
            pass
        return done(False, msg, diag)
    except Exception as e:
        return done(False, f"{type(e).__name__}: {e}")


_EXT_BY_TYPE = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
                "image/webp": ".webp", "image/gif": ".gif"}


def safe_name(name: str, maxlen: int = 40) -> str:
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", (name or "").strip())
    s = re.sub(r"\s+", "_", s).strip("_.")
    return (s or "person")[:maxlen]


def download_photo(url: str, dest_dir: str, stem: str, timeout=20, proxy="") -> str:
    """下载头像到本地，返回保存路径（失败返回空串）。"""
    if not url:
        return ""
    if proxy:
        pass
    elif _PROXY_FORCED_OFF:
        proxy = ""            # v1.40.0（反馈 3）：显式直连
    else:
        proxy = _system_proxy()
    os.makedirs(dest_dir, exist_ok=True)
    headers = _browser_headers(url)
    req = urllib.request.Request(url, headers=headers)
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    handlers.append(urllib.request.HTTPSHandler(context=_ssl_ctx(True)))
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    except Exception:
        try:
            req2 = urllib.request.Request(url, headers=headers)
            op2 = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_ssl_ctx(False)))
            if proxy:
                op2 = urllib.request.build_opener(
                    urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
                    urllib.request.HTTPSHandler(context=_ssl_ctx(False)),
                )
            with op2.open(req2, timeout=timeout) as resp:
                raw = resp.read()
                ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        except Exception:
            return ""
    if not raw or len(raw) < 512:
        return ""
    ext = _EXT_BY_TYPE.get(ctype)
    if not ext:
        m = re.search(r"\.(jpe?g|png|webp|gif)(?:\?|$)", url, re.I)
        ext = "." + m.group(1).lower().replace("jpeg", "jpg") if m else ".jpg"
    path = os.path.join(dest_dir, f"{stem}{ext}")
    try:
        with open(path, "wb") as f:
            f.write(raw)
    except Exception:
        return ""
    return path


# ---------------------------------------------------------------- 批量刮削
def scrape_one(person: dict, opts: dict, log=None) -> dict:
    """刮削单个演员。opts 见 config.DEFAULT_SCRAPER。返回结果字典。"""
    sources = opts.get("sources") or []
    timeout = int(opts.get("timeout", 15) or 15)
    proxy = opts.get("proxy") or ""
    retry = int(opts.get("retry", 1) or 0)
    overwrite = bool(opts.get("overwrite"))
    only_missing = not overwrite
    res = {"id": person.get("id"), "name": person.get("name", ""), "status": "notfound",
           "source": "", "fields": [], "photo": "", "error": ""}

    need = {"alias": bool(opts.get("fill_alias", True)),
            "birthday": bool(opts.get("fill_birthday", True)),
            "bio": bool(opts.get("fill_bio", True))}
    collected = {}
    photo_url = ""
    last_err = ""

    queries = [person.get("name") or ""]
    if person.get("romaji"):
        queries.append(person["romaji"])
    if person.get("alias"):
        queries.append(str(person["alias"]).split(" / ")[0].split(",")[0].strip())

    for src in sources:
        searcher, fetcher = SEARCHERS.get(src), FETCHERS.get(src)
        if not searcher:
            continue
        for q in queries:
            if not q:
                continue
            # IMDB 只接受拉丁字母检索词，日文名直接跳过以省请求
            if src == "imdb" and not re.search(r"[A-Za-z]", q):
                continue
            cand = None
            for attempt in range(retry + 1):
                try:
                    hits = searcher(q, timeout=timeout, proxy=proxy)
                    cand = hits[0] if hits else None
                    last_err = ""
                    break
                except ScrapeError as e:
                    last_err = str(e)
                    if attempt < retry:
                        time.sleep(0.6)
            if not cand:
                continue
            try:
                d = fetcher(cand["url"], timeout=timeout, proxy=proxy)
            except ScrapeError as e:
                last_err = str(e)
                continue
            got = False
            for k in ("alias", "birthday", "bio"):
                if need.get(k) and d.get(k) and not (only_missing and person.get(k)):
                    collected.setdefault(k, d[k])
                    got = True
            if d.get("romaji") and not person.get("romaji"):
                collected.setdefault("romaji", d["romaji"])
                got = True
            if d.get("meta") and (overwrite or not person.get("meta")):
                # v1.11.1：原来只在「本地没有 meta」时才写。可本地那份可能是 v1.10.0 写坏的
                # 样板文案乱码（真机 72/108 条），于是修复重刮永远刷不掉它 —— 覆盖模式下必须重写。
                collected.setdefault("meta", json.dumps(d["meta"], ensure_ascii=False))
            if d.get("status") and not (only_missing and person.get("status")):
                collected.setdefault("status", d["status"])
            if d.get("photo_url") and not photo_url:
                photo_url = d["photo_url"]
                got = True
            if got:
                res["source"] = src
                res["source_url"] = d.get("source_url") or cand["url"]
                res["status"] = "ok"
            # 已经拿全了就不再请求下一个源
            if all(collected.get(k) or person.get(k) for k in ("alias", "birthday", "bio")) and photo_url:
                break
        if res["status"] == "ok" and photo_url and len(collected) >= 2:
            break

    if res["status"] != "ok":
        res["error"] = last_err
        return res

    if opts.get("download_photo", True) and photo_url:
        if overwrite or not person.get("photo_path"):
            p = download_photo(photo_url, opts.get("photo_dir") or "",
                               f"{person.get('id')}_{safe_name(person.get('name'))}",
                               timeout=timeout, proxy=proxy)
            if p:
                collected["photo_path"] = p
                collected["thumb"] = p
                res["photo"] = p

    collected["source"] = res["source"]
    collected["source_url"] = res.get("source_url", "")
    collected["scraped_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    res["fields"] = list(collected.keys())
    res["_write"] = collected
    return res


def scrape_many(people, opts: dict, progress=None, should_stop=None, writer=None) -> dict:
    """批量刮削。progress(i, total, name, status)；should_stop() -> bool；
    writer(person_id, fields, only_missing) 用于落库（缺省则只统计不写入）。"""
    stats = {"total": len(people), "ok": 0, "notfound": 0, "failed": 0,
             "photo": 0, "fields": 0, "errors": []}
    delay = max(0, int(opts.get("delay_ms", 800) or 0)) / 1000.0
    only_missing = not bool(opts.get("overwrite"))
    for i, p in enumerate(people, 1):
        if should_stop and should_stop():
            break
        try:
            r = scrape_one(p, opts)
        except Exception as e:
            r = {"status": "failed", "error": f"{type(e).__name__}: {e}", "name": p.get("name", "")}
        if r.get("status") == "ok":
            stats["ok"] += 1
            if r.get("photo"):
                stats["photo"] += 1
            stats["fields"] += len(r.get("fields") or [])
            if writer and p.get("id") is not None:
                try:
                    writer(p["id"], r.get("_write") or {}, only_missing)
                except Exception as e:
                    stats["errors"].append(f"{r.get('name')}: 写入失败 {e}")
            if progress:
                progress(i, stats["total"], r["name"],
                         f"已补齐（{SOURCE_NAMES.get(r.get('source'), r.get('source'))}）")
        elif r.get("status") == "failed":
            stats["failed"] += 1
            if r.get("error"):
                stats["errors"].append(f"{r.get('name')}: {r['error']}")
            if (not only_missing) and writer and p.get("id") is not None:
                # v1.21.2（反馈 2 加固）：覆盖模式（「修复历史资料」）重刮时即便源报错
                #（如数据源 HTTP 500 / WAF 截断，见 请求 1），仍把本地 v1.10.0 残留的
                # 样板/HTML 垃圾清空，使修复计数即便在数据源不可用的情况下也能真正下降。
                # 只清判定为 junk 的 meta/bio，干净资料原样保留。
                try:
                    writer(p["id"], {}, False)
                except Exception:
                    pass
            if progress:
                progress(i, stats["total"], p.get("name", ""), "失败：" + (r.get("error") or ""))
        else:
            stats["notfound"] += 1
            if (not only_missing) and writer and p.get("id") is not None:
                # v1.21.1（反馈 2）：覆盖模式（「修复历史资料」）重刮时源未匹配到，
                # 仍把本地 v1.10.0 残留的样板/HTML 垃圾清空，使修复数量能真正下降。
                # 仅清判定为 junk 的 meta/bio，干净资料原样保留；不覆盖 source 等。
                try:
                    writer(p["id"], {}, False)
                except Exception:
                    pass
            if progress:
                progress(i, stats["total"], p.get("name", ""), "未找到匹配条目")
        if delay and i < stats["total"]:
            slept = 0.0
            while slept < delay:
                if should_stop and should_stop():
                    break
                time.sleep(0.1)
                slept += 0.1
    return stats
