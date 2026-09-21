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
  - 页面解析采用「标签定位 + 邻近文本」的容错写法：找不到字段就返回 None，绝不因某个字段结构变化而整体失败。
  - 每个字段都记录来源，便于后续排查；失败原因回传上层用于统计与提示。
"""
import gzip
import html
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


def _system_proxy() -> str:
    """读取系统代理：环境变量优先，其次 Windows IE/WinHTTP 设置。无则返回空串。

    v1.21.1（反馈 1）：用户电脑浏览器能开 minnano-av，但应用测连返回 HTTP 500 —— 根因之一
    是应用从不读系统代理（浏览器靠它出网），企业网/代理环境下 urllib 直接被拦。
    这里把系统代理自动补上，未显式设置代理时生效。
    """
    for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = (os.environ.get(k) or "").strip()
        if v:
            return v
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
                                return part.split("=", 1)[1].strip()
                        return server
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


def http_get(url: str, timeout: int = 15, proxy: str = "", referer: str = "",
             verify_ssl: bool = True) -> str:
    """取回页面文本。自动处理 gzip/deflate 与日文编码。

    v1.21.1（反馈 1）：未显式给代理时自动套用系统代理；请求头补全浏览器字段，
    绕开把「缺头请求」判为爬虫的 WAF（原症状：浏览器能开、应用测连 HTTP 500）。
    """
    if not proxy:
        proxy = _system_proxy()
    headers = _browser_headers(referer)
    req = urllib.request.Request(url, headers=headers)
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    handlers.append(urllib.request.HTTPSHandler(context=_ssl_ctx(verify_ssl)))
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
            enc = (resp.headers.get("Content-Encoding") or "").lower()
            ctype = resp.headers.get("Content-Type") or ""
    except urllib.error.HTTPError as e:
        raise ScrapeError(f"HTTP {e.code}")
    except ssl.SSLError as e:
        if verify_ssl:
            # 部分老站点证书/协议异常 -> 降级为不校验证书重试一次
            return http_get(url, timeout, proxy, referer, verify_ssl=False)
        raise ScrapeError(f"SSL 错误：{e}")
    except Exception as e:
        raise ScrapeError(f"{type(e).__name__}: {e}")

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
    return _decode(raw, ctype)


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


def test_source(source: str, proxy="", timeout=12) -> dict:
    """连接自检：返回 {ok, msg, ms}。"""
    t0 = time.time()
    try:
        if source == "minnano":
            hits = minnano_search("新村あかり", timeout=timeout, proxy=proxy)
            ms = int((time.time() - t0) * 1000)
            if hits:
                return {"ok": True, "msg": f"可访问，检索测试命中 {len(hits)} 条", "ms": ms}
            return {"ok": True, "msg": "可访问，但检索无结果（可能被限流/结构变动）", "ms": ms}
        if source == "imdb":
            hits = imdb_search("Emma Stone", timeout=timeout, proxy=proxy)
            ms = int((time.time() - t0) * 1000)
            if hits:
                return {"ok": True, "msg": f"可访问，检索测试命中 {len(hits)} 条", "ms": ms}
            return {"ok": True, "msg": "可访问，但检索无结果", "ms": ms}
        return {"ok": False, "msg": f"未知数据源 {source}", "ms": 0}
    except ScrapeError as e:
        return {"ok": False, "msg": str(e), "ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "msg": f"{type(e).__name__}: {e}", "ms": int((time.time() - t0) * 1000)}


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
    if not proxy:
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
