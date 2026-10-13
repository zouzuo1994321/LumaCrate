<div align="center">

# 🎬 LumaCrate (流明盒)

**Local movie & TV management · Emby-style poster wall + tinyMediaManager relation search · single-file exe**

**所有流明 · 尽收盒中** · *Every lumen, in one crate.*

![Version](https://img.shields.io/badge/version-v1.39.5%20(2610130062)-c0392b?style=flat-square)

![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078d6?style=flat-square\&logo=windows)

![Python](https://img.shields.io/badge/python-3.13-3776ab?style=flat-square\&logo=python)

![Qt](https://img.shields.io/badge/UI-PySide6%20(Qt%206\)-41cd52?style=flat-square\&logo=qt)

![Offline](https://img.shields.io/badge/network-nfo%20only%20%2F%20offline-2c3e50?style=flat-square)

![License](https://img.shields.io/badge/license-open%20source%20%2F%20non--commercial-orange?style=flat-square)

</div>

---

## ✨ What it is

A **local-first** Windows desktop app for managing your movie & TV library: inspired by Emby's poster wall / cast / detail pages and tinyMediaManager's local management with strengthened relation search. Everything is built with PySide6 and packaged as a **single exe** with PyInstaller — double-click to run.

- **Local-only, no online scraping**: it only reads the already-scraped `.nfo` files beside your videos and never touches any online metadata service; your library, IDs and cast info stay on your own machine.
- **People as first-class entities (Emby mode)**: a standalone `people` table lets you reverse-lookup every work of any actor / director.
- **Single-file exe**: `--onefile --windowed`, no install and no Python required.

> Copyright 2026 肆月Aperture · This software is open source; commercial use without a license is prohibited.

---

## 📸 Preview

<p align="center">
  <img src="logo-4.png" width="200" alt="LumaCrate Logo">
</p>

> The UI presents an Emby-style poster wall, actor library and detail pages. Full screenshots ship with the GitHub Release assets.

---

## 🎯 Features

<details>

<summary><b>Browse & Libraries</b></summary>

| Module | Description |
| ------ | ----------- |
| Poster wall / Libraries | multi-library management, poster-wall browsing; favorites (★) and collections |
| Actor / Director libraries | standalone profiles (`people` table) with reverse work lookup; favorites and name / romaji search |
| Detail page | Emby-style work detail: cast, tags, studio, series |
| Favorites / Collections | one-click favorite (★); collections group titles across libraries |

</details>

<details>

<summary><b>Smart Recommend</b></summary>

| Module | Description |
| ------ | ----------- |
| Duplicate detection | normal + local AI engine (Ollama) dual modes; catches dupes |
| Actor detection | romaji merge / alias cross-link + AI review; catches same-person-different-alias; **multi-select batch confirm** (Shift / Ctrl multi-select, one-click merge of the selected clusters with their default keep-names) |
| Image detection | pure-Python structural check; catches missing / truncated images and replaces them |
| Tag optimization | high-frequency tag / studio / series / actor / director charts from your favorite profile |
| Vector edit | hand-tune per-dimension weights; "auto-fill from profile" and **"auto-fill from favorited actors"** |
| Guide vector | type an actor / tag / studio / series on the wall and this session's picks lean that way (**fuzzy match**: every containing tag / studio / series is boosted; optional **auto Chinese→Japanese translation** before matching — `轮奸 → 輪姦`, `三上悠亚 → 三上悠亜`) |

</details>

<details>

<summary><b>Tools & AI Engine</b></summary>

| Module | Description |
| ------ | ----------- |
| Library management | create / edit / delete libraries, set scan paths |
| Manual edit | 17 nfo fields + 3-slot upload, written back to the index |
| Appearance | 19 UI languages (instant switch, no restart), accent color, sidebar-panel toggles |
| **AI Engine** (v1.35.0) | unified model config, local-model picker, auto-launch Ollama (on startup + "Launch now"), auto-fills the dropdown after launch |
| Tools-window nav (v1.39.0) | a spinning ring appears next to the nav button of any **running** task (scan / scrape / detect / merge …) |

</details>

<details>

<summary><b>Sidebar & About</b></summary>

| Module | Description |
| ------ | ----------- |
| Data stats | sidebar "data stats" panel, toggleable in Appearance |
| Live status | CPU / RAM / network / GPU / Ollama collector (process-level singleton, toggleable) |
| About | what the nine modules do, where data lives, whether it goes online, privacy & disclaimer — all sourced from `version.py` |

</details>

---

## 🚀 Download & Run

**No Python, no network, no browser required.**

1. Download `LumaCrate-v1.39.5-2610130062.exe` (~46 MB, single file) from [Releases](../../releases).
2. Double-click to run — on first launch it creates `index_data/` (index DB) and `settings.json` **next to the exe**.
3. Runtime data lives **next to the exe**, so you can move the exe together with its folder.

> ⚠️ PyInstaller single-file exes are sometimes false-flagged by antivirus. The source is fully open — audit it or build from source.

---

## 🖱️ How to use

- **Create a library**: Tools → Libraries → New library, add a local movie folder (ideally with `.nfo` files).
- **Scan & index**: on save the app reads the nfo to build a local index (actors / directors / tags).
- **Browse**: switch the poster wall by library / favorites / collections; actor & director libraries reverse-lookup works.
- **Smart Recommend**:
  - Vector edit → auto-fill from profile / **from favorited actors** to shape your taste;
  - on the wall, type an actor / tag in "guide vector" to bias this session.
- **AI Engine** (optional): Tools → AI Engine, enable "auto-launch Ollama" or press "Launch now", pick the model after detection.

---

## 📁 Project Layout

```
LumaCrate/
├── LumaCrate-v1.39.5-2610130062.exe   # single-file executable
├── logo-4.png                         # brand icon (golden film)
├── logo.ico                           # exe icon
├── README.md / README_EN.md
├── src/                               # source (PySide6)
│   ├── main.py  splash.py  main_window.py
│   ├── version.py  config.py  database.py
│   ├── recommend.py  ui_settings.py  ...
├── build_exe.py                       # packaging script
├── dev/                               # smoke / probe scripts
├── index_data/                        # runtime index DB + logs (settings.json / media_center.db / logs)
└── history/                           # archived older exes
```

---

## 🛠️ Build from source

```bash
# 1) deps (virtualenv recommended)
pip install PySide6 pyinstaller

# 2) run from source
python src/main.py

# 3) package as single-file exe
python build_exe.py        # produces LumaCrate-vX.Y.Z-YYMMDDNNNN.exe into root + history/
```

- Packaging params (`--onefile --windowed`, icon `logo.ico`, bundled `logo-4.png`) live in `build_exe.py`.
- Newest exe goes to root; older builds auto-archived to `history/`.

---

## 🧪 Dev checks

`dev/` holds offscreen (`QT_QPA_PLATFORM=offscreen`) smoke scripts — no real display needed:

| Script | Purpose |
| ------ | ------- |
| `smoke_v1395.py`                                | v1.39.5 smoke: **actor-check page ergonomics + 403 wording escape hatch** — ① measured column widths `[76, 186, 62, 78, 172]` (column 0 went 62 → 76: the 1–2 px gap between the indicator's right edge at 60 and the text starting at 61–62 is widened to 16 px; columns 2/3 went 44/52 → 62/78 so "2 人" and "94 铁证" are no longer clipped); ② `style.qss` gains a base `QTreeView::item { padding: 4px 2px; }` rule (previously only the `::indicator` **sub-control** rule existed, with **no base rule → no padding**, so row height was the bare text height ~20 px and the 15 px boxes nearly touched, forming a "fence"; padding lifts rows to ~28 px); ③ the two root nodes use `setFirstColumnSpanned(row, QModelIndex(), True)` to **span all columns** (their titles are ~200 px wide but lived only in column 0 at 76 px and were truncated to "建议..."); ④ the scraper-stats strip uses `setWordWrap(False)` + horizontal `Ignored` (measured label w=998 / button w=82, **always one line**); ⑤ `_normalize_proxy()` turns a bare `host:port` from the registry into `http://host:port` (`urllib`'s ProxyHandler adds the scheme, **`curl_cffi`'s `proxies=` does not**); ⑥ `_explain()`'s **403 branch now appends a `_network_hint()` escape hatch**; ⑦ assertion fixes: `_qss_block()` strips comments before `find(sel)` (the selector name appears inside the comment text, so the old order mis-matched), and "counts right-aligned" became a **structural guard** (`QWidget.fontMetrics()` **does not reflect the QSS `font-family`**). **206 assertions, 0 failures** (inherits v1.39.4's 183) |
| `smoke_v1394.py`                                | v1.39.4 smoke: **network-layer root-cause regressions** — ① `_unwrap_reason()` peels an `ssl.SSLError` wrapped inside `URLError` (measured: `isinstance(e, ssl.SSLError)` is `False`, which is exactly why the old `except ssl.SSLError` never fired) and handles multi-level `.reason` nesting; ② `is_waf_challenge()` detects AWS WAF / Cloudflare challenge pages **without false-positives on real content**, and `_curl_get` rejects 202/403 at the status check; ③ `http_get` escalates to a browser TLS fingerprint on the **first** interception (`_escalated`, single retry, no loop); ④ `test_source` no longer reports the misleading "reachable but no results" (verified with `ast` after stripping docstrings) and `_explain()` / `_network_hint()` point at network / proxy / egress-IP causes; ⑤ the smoke itself now pins `setStyle(Fusion)` so its verdict no longer depends on whether the caller exported `QT_QPA_PLATFORM` (measured checkbox area **279 px**, matching the assertion exactly). **183 assertions, 0 failures** (inherits v1.39.3's 145) |
| `smoke_v1393.py`                                | v1.39.3 smoke: **QStyle guard** — asserts `main.py` calls `setStyle(QStyleFactory.create("Fusion"))`, and measures the checkbox fill/border pixel count in a real **windows-back-end** subprocess (**0** under the `windows11` style, **615** under Fusion); also asserts Qt's raw default style really is `windows11`. **145 assertions, 0 failures** (inherits v1.39.2's 140) |
| `smoke_v1392.py` | v1.39.2 offscreen smoke: the checkbox in its **unchecked** state differs from an empty tree by > 0 pixels (columns 46/62/80; all three `::indicator` unchecked states must use a solid background) — **140 pass / 0 fail** (also inherits the 131 layout assertions from v1.39.1) |
| `smoke_v1391.py` | v1.39.1 offscreen smoke: all 10 Insight "top list" / "distribution" columns with long CJK names never wrap / never overflow / counts right-aligned + body labels carry `wordWrap=False` and a horizontal `Ignored` size policy + tooltip keeps full names + the 5 columns still split the width evenly instead of being widened by `minimumSizeHint` (also inherits every v1.39.0 assertion) — **131 pass / 0 fail** |
| `smoke_v1390.py` | v1.39.0 offscreen smoke: actor-detection checkbox column width 62 + Checked visible area 279px + ExtendedSelection driving batch merge / minnano cookie jar + homepage warm-up + 403-count fallback chain (curl_cffi optional) / tools-window nav ring covering 11 task kinds + both detection pages / standalone ScanRing module — **all pass / 0 fail** |
| `smoke_v1380.py` | v1.38.0 offscreen smoke: all three scan entry points connect `live` for a live homepage count / actor-detection "Select" checkbox column + select-all / select-none / batch-merge toolbar / batch merge reusing `db.merge_people` — **all pass / 0 fail** |
| `smoke_v1370.py` | v1.37.0 offscreen smoke: cast/card favorite→gold & pinned→bold coloring / detail topbar only when on_back / DetailHost border / splash accent-derived colors — **all pass / 0 fail** |
| `smoke_v1360.py` | v1.36.0 offscreen smoke: CN→JP candidates (lexicon / char map / multi-term split) / preference persistence + dirty-value normalization / translated hits merged into guides / **double-click callback destroying its own card no longer raises** — **all pass / 0 fail** |
| `smoke_v1351.py` | v1.35.1 offscreen smoke: toolbar min-width **independent of chip count** / chips wrap + fold in their own row / zero horizontal overflow at 1920 / logo-4 wiring — **all pass / 0 fail** |
| `smoke_v1350.py` | v1.35.0 offscreen smoke: fuzzy resolve / AI Engine page / vector-edit auto-fill — **all pass / 0 fail** |
| `smoke_v1343.py` | module-attribute audit and detector-page widget assertions |
| `live_verify_v1395.py` | v1.39.5 **real-machine acceptance (slimmed)**: launches the newest exe, screenshots page by page, and checks `app.log` for uncaught exceptions. **Why slimmed**: during the v1.39.4 full run, after the modal confirm on the "Tag optimize" page every subsequent `PrintWindow` grab suddenly returned `0x0` (`IsWindow` still true, `GetWindowRect` normal) → this version **skips "Tag optimize" and "Duplicate detection"** (42944 → 32366 chars). ⚠ Rules unchanged: `SetWindowPos` the tools window back to `ui_coords`' 1000×900 client area before clicking coordinates, validate that any destructive-button click lands on the expected widget, and keep the "write minefield" log alarm |
| `live_verify_v1342.py` / `live_verify_v1343.py` | real-machine acceptance: run the frozen exe and check `app.log` for uncaught exceptions |

---

## 📄 License

```
Copyright 2026 肆月Aperture
This software is open source; commercial use without a license is prohibited.
```

Third-party components:

- [PySide6](https://doc.qt.io/qtforpython/) (Qt 6, LGPLv3) — UI
- [PyInstaller](https://pypi.org/project/pyinstaller) — single-file packaging
- [psutil](https://pypi.org/project/psutil) — local metrics collection (with ctypes fallback, safe inside a single-file exe)

---

## 📮 Contact

|        |                                    |
| ------ | ---------------------------------- |
| GitHub | <https://github.com/zouzuo1994321> |
| Bilibili | <https://space.bilibili.com/13715> |
| Weibo  | <https://weibo.com/u/5189652182>   |
| Email  | <921103025@qq.com>                 |

---

## 📚 Changelog

<details open>
<summary><b>v1.39.5 (Build 2610130062) — 2026-10-13</b></summary>

> Three reports: (1) the minnano-av and IMDB connection tests are **still unusable** — keep trying
> to fix; (2) the scraper-stats strip should sit on **its own line**; (3) the actor-detection UI
> "still looks wrong".

### ① Both sites unreachable — exhaustive probing confirms it is **environmental** (2 real bugs fixed along the way)

Every plausible route was measured this time; the conclusion matches v1.39.4 and is firmer:

| Route | minnano-av | IMDB |
| --- | --- | --- |
| Env-var proxy `http://127.0.0.1:4328` | `UNEXPECTED_EOF_WHILE_READING` (closed right after the TLS handshake) | WAF challenge **202** |
| Registry proxy `127.0.0.1:8866` | **HTTP 403** | WAF challenge **202** (zero-byte body) |
| Fully direct (cleared proxy / `NO_PROXY=*`) | connection reset / 403 | WAF challenge **202** |
| curl_cffi, 5 browser fingerprints × proxy/direct | all failed | all **202** |
| Control: `www.cloudflare.com` / `baidu` | **200 OK** | **200 OK** |

→ **Both sites block at the egress-IP / site level (JA3/TLS fingerprint + IP reputation). Changing
the network or the proxy fixes it; there is nothing further to optimise in code.** The investigation
still surfaced two **genuine code defects**, both fixed:

| Defect | Root cause | Fix |
| --- | --- | --- |
| **403 message had no escape hatch** | `_explain()`'s 403 branch was an old template that only said "the site's Cloudflare fingerprint check blocked the stdlib client; browser fingerprint retry engaged" — **no actionable advice at all**, inconsistent with the TLS/WAF branches | Append `_network_hint()`, yielding: `站点按客户端 TLS 指纹拦截（HTTP 403）：（已自动切换到浏览器 TLS 指纹重试，仍被挡）：当前走系统代理 http://…；已尝试浏览器 TLS 指纹（curl_cffi）仍被挡；多为出口 IP 被拒或本地代理未放行该站，换网络/换代理可解` |
| **Proxy value missing scheme** | Windows registry `ProxyServer` is often a **bare `127.0.0.1:8866`** (no `http://`). `urllib`'s ProxyHandler adds it, **`curl_cffi`'s `proxies=` does not** → it treats it as a malformed URL. Both ports were alive yet everything failed, which reads exactly like "site blocking" | New `_normalize_proxy()` normalises every return path of `_system_proxy()` |

### ② Scraper-stats strip "on its own line" (fixed)

The stats string has 6 segments (actors / with photo / with birthday / with alias / scraped /
to-fix). With `setWordWrap(True)` it wrapped into 2–3 lines in a narrow window, pushing the
"refresh stats" button into the middle so the whole strip looked misaligned. Now
**`setWordWrap(False)` + horizontal `SizePolicy.Ignored`**: the string stays on exactly one line and
elides itself, the button stays pinned right. Measured label `x=0, w=998`, button `x=1010, w=82`.

### ③ Three real defects on the actor-check page (fixed)

| Symptom | Root cause | Fix |
| --- | --- | --- |
| Checkbox and text **smeared together** | Column 0 was 62 wide → the indicator's right edge at 60 sat flush against the text starting at 61–62, a **1–2 px gap** | Column 0 **62 → 76** (right edge 60 + 16 px breathing room). ⚠ 82 was tried first: it pushed the total width out and squeezed "人数"/"匹配度", so 76 is the exact fit |
| The whole column of boxes **touched, forming a "fence"** | `style.qss` only had the `QTreeView::indicator` (**sub-control**) rule with **no base `QTreeView::item` rule** → no padding at all, so row height equalled the bare text height (~20 px) while the indicator is 15 px, leaving the boxes almost touching | Added `QTreeView::item { padding: 4px 2px; border: none; }`, lifting rows to ~28 px. **Padding only — the indicator's positioning properties are not touched** (the `subcontrol-position` / negative-margin family was fully disproved back in v1.39.0) |
| Root titles truncated to "建议…" / "存疑…" | The two root titles are long ("建议合并（5 簇，共可减少 5 条演员记录）" ≈ 200 px) but were written only into **column 0** (76 px) | `setFirstColumnSpanned(row, QModelIndex(), True)` makes root nodes **span all columns**. ⚠ PySide6 trap: calling it on a `QTreeWidget` resolves to **`QTreeView`'s three-argument signature**, so `(item, 0, True)` / `(item, True)` both raise `TypeError`; it must be `(indexOfTopLevelItem(item), QModelIndex(), True)` |
| "2 人" shown as "2 …", "94 铁证" reduced to "94 铁" | Columns 2/3 were 44/52, too narrow for content + QSS padding | Reset to **62 / 78** (measured via `sizeHintForColumn`) |

### ④ Two methodological defects fixed in the smoke itself

- **`_qss_block()` matched the selector name inside a comment**: this release added an explanatory
  comment *before* `QTreeView::indicator`, and the comment text itself contains
  "`QTreeView::indicator`". The old `_qss.find(sel)` therefore hit the **comment**, and the next
  `{` it found belonged to `QTreeView::item {` → it judged item's padding block as the indicator
  declaration (no `background` there → false FAIL). Fix: **replace each `/* … */` with equal-length
  blanks before `find`** (preserving offsets).
- **The "counts right-aligned" assertion was a false FAIL**: it measured **theoretical width** via
  `fm.horizontalAdvance(prefix)` and reported FAIL for directors/studios (spread 5 / 5–29), yet a 6×
  zoomed screenshot clearly showed the counts **are** right-aligned. The cause is a classic Qt trap —
  **`QWidget.fontMetrics()` does not reflect the QSS `font-family`**: `_bar_label()`'s QSS says
  `Consolas,'Courier New',monospace` but `fontMetrics()` measures the app-default
  `Microsoft YaHei UI` (proportional), whose `adv(" ")` jitters ±1 px and accumulates; rendering
  uses Consolas (monospace), so the real alignment is fine. → The check became a **structural
  guard**: assert `_bar_lines()` pads by pixels via `adv()`
  (`int(max(0, cnt_px - 10 - adv(ctext)) // sp)`) rather than by `{:>N}` character width.

</details>

<details>
<summary><b>v1.39.4 (Build 2610130061) — 2026-10-13</b></summary>

> Two reports: (1) the minnano-av and IMDB connection tests failed / IMDB said "reachable but no
> results" — root cause fully identified as **three stacked code bugs** that meant the v1.39.0
> fallback chain **had never actually triggered once**; (2) the actor-detection UI looked wrong —
> part of which turned out to be a **visual illusion**.

### ① Three code bugs (all fixed)

| bug | symptom | root cause | fix |
| --- | --- | --- | --- |
| **A: exception wrapping** | minnano reported `[SSL: UNEXPECTED_EOF_WHILE_READING]` yet neither the certificate fallback nor the fingerprint fallback fired | `urllib` wraps `ssl.SSLError` **inside** `URLError`. Measured `isinstance(e, ssl.SSLError)` = `False`, `type(e).__name__` = `URLError`, and only `e.reason` is the `SSLEOFError` → the old `except ssl.SSLError` **could never catch it** and fell straight through to the generic branch | added an `except urllib.error.URLError` branch plus `_unwrap_reason()`, which follows `.reason` to the end (multi-level nesting supported); and `UNEXPECTED_EOF_WHILE_READING` is now recognised as *the peer hanging up right after the TLS handshake* (Cloudflare blocking non-browser JA3 fingerprints) — so disabling certificate verification is pointless and a browser fingerprint is required |
| **B: WAF challenge pages answer 200/202, not 403** | IMDB reported "reachable but no results" | the AWS WAF JS challenge answers **HTTP 200** (urllib path, 1997 bytes, zero `/name/nm` links) or **202** (curl_cffi path), while the fallback chain only triggered on `_CF_403_COUNT >= 3` → the counter never reached 3 → the challenge page flowed straight into the parser | added `is_waf_challenge()` (7 markers: `awsWafCookieDomainList`, `challenge.js`, `/cdn-cgi/challenge-platform`, `Just a moment...`, `cf-mitigated`, `Checking your browser`, ...); 202/403 are now rejected at `_curl_get`'s **status check**, and challenge pages right after **decoding** in `http_get` |
| **C: the fallback came too late** | both interceptions above happen on the **first** request | but the fingerprint switch required 3 accumulated 403s | `http_get` gained an `_escalated` flag: the first interception immediately retries once with a browser fingerprint (no infinite loop) |

### ② Misleading reporting (fixed)

`test_source`'s old "reachable, but no results" was the most misleading outcome of all — it had in
fact **never retrieved a single byte of content**. It now reports the real interception reason and
uses `_explain()` / `_network_hint()` to separate "code problem" from "network problem", always
ending with an actionable hint. You will now see:

- **minnano**: *"The site closes the connection right after the TLS handshake (client-fingerprint
  blocking): currently using system proxy http://127.0.0.1:2336; browser TLS fingerprint
  (curl_cffi) already tried and still blocked; usually the egress IP is rejected or the local proxy
  does not allow this site — change network / proxy to fix."*
- **IMDB**: *"Hit an anti-bot challenge page (WAF check not passed — effectively no content):
  … change network / proxy to fix."*

### ③ Environment verdict (measured, **not solvable in code**)

| attempt | result |
| --- | --- |
| via the system proxy `http://127.0.0.1:2336` | `CONNECT www.minnano-av.com:443 → 200 Connection Established`, then still dropped |
| `--noproxy '*'` (bypassing the proxy entirely) | still fails |
| four curl_cffi fingerprints (chrome124 / 131 / 136 / safari17_0) | all fail (BoringSSL `Connection closed abruptly`) |
| TLS 1.2 / 1.3 / plain http | all fail |
| control: `www.cloudflare.com` / `www.dmm.co.jp` / `baidu` | **200 / 302 / 200 — fine** |

→ **The blocking happens at the egress-IP / site level** — not in the code, not in the proxy
configuration, not in leftover fingerprint state. Changing network (especially the egress IP) or
proxy resolves it; there is nothing further to optimise on the program side.

### ④ Actor-detection UI (one item was an illusion)

- **"Headers squeezed into a vertical column" is a false alarm**: the screenshot is only
  **544×57 px** (a wide flat strip) and was displayed scaled to 811×370, which produced the
  *appearance* of vertical header text. Opened at 3× with PIL, the headers (Select / Candidate /
  Count / Match / Reason) render perfectly. A full sweep of widths 500→1600 and heights 500→1000
  showed: minimum header width constant at 44, **zero** squashed columns, **zero** overlaps,
  overflow always `False`.
- **"Still no checkboxes" happened because v1.39.2 was still running**: `app.log` shows the last
  manual launch was v1.39.2 (Build 2610130059, 10:24:38), while v1.39.3 was only finished at 10:47.
  Same-region real-machine comparison is conclusive: **v1.39.2's select column is blank, v1.39.3
  shows a full column of rounded checkboxes** (**3181** non-background pixels). **Use v1.39.3 or
  later.**
- **"Already merged 543 clusters" is a leftover marker from an older accident**: it comes from the
  09:31 misclick (coordinates off by +318 px horizontally, hitting "Batch confirm"), and the last
  merge entry in `app.log` is timestamped 09:31:39 with nothing after it — **no new merge happened**.

### ⑤ A methodology flaw fixed inside the smoke itself

`smoke_v1393.py` only knew which back-end to use based on whether the **caller** exported
`QT_QPA_PLATFORM`, and it never called `setStyle(Fusion)` → under `offscreen` the style was still
`windows11` and the measured checkbox area was **0**, i.e. a straight FAIL. The smoke now pins
`setStyle(Fusion)` internally, so its verdict no longer drifts with the calling environment; this
run measured **279 px**, exactly matching the assertion.

</details>

<details>
<summary><b>v1.39.3 (Build 2610130061) — 2026-10-13</b></summary>

> One bug fix: the checkboxes in the actor-detection "Select" column were still not drawn at all
> on the real machine — this time we found the **actual** root cause.

- **Real root cause: on Windows 11, Qt 6's default QStyle is `windows11`, and it is the only
  available style that cannot draw `QTreeView::indicator`.**
  Running the same probe under `QT_QPA_PLATFORM=windows` (the real back end) across every style:

  | QStyle | checkbox rect | indicator fill/border pixels in column 0 |
  | --- | --- | --- |
  | `windows11` (Win11 default) | 16x19 | **0** |
  | `windowsvista` | 13x19 | 770 |
  | `Windows` | 13x17 | 820 |
  | `Fusion` | 14x17 | 820 |

  The `::indicator` painted by `QStyleSheetStyle` conflicts with `windows11`'s native checkbox
  path, so it skips drawing entirely — the rect is computed but no colour is emitted, leaving the
  whole "Select" column blank.
- **Fix**: right after creating `QApplication`, `main.py` now calls
  `app.setStyle(QStyleFactory.create("Fusion"))`. Fusion and windowsvista are visually
  indistinguishable for this app (dark glass theme + global QSS), and every control now behaves
  identically across all Windows versions.
- **Two previously mis-directed fixes are hereby corrected**: v1.39.0 and v1.39.2 both changed the
  **colour** of `::indicator` (half-transparent `rgba(255,255,255,0.05)` to solid `#2a241c`) —
  the colour was never the problem. The offscreen probes passed twice because the `offscreen`
  back end does not use `windows11`. New rule: **any probe that verifies "does this control
  actually paint" must run under `QT_QPA_PLATFORM=windows`** — offscreen and real-machine
  conclusions can differ by a whole QStyle.
- **A coordinate misjudgement in the acceptance script is also corrected**: v1.39.2 suspected the
  "Start detection" coordinate (227,170) missed the button. Measuring the accent-coloured cluster
  on a real screenshot disproves it — the button occupies x in [187,266], y in [154,190], centre
  (226,172); **the coordinate was always correct**. The nav spinner was missed purely because
  detection finishes in **0.3 s**; the script now grabs frames immediately after the click
  (new `grab_ring_burst()`, 16 frames at 120 ms). Real-machine result: **22 bright-blue pixels
  while running → 0 pixels in the same region after it finishes**.
- **Incident post-mortem (v1.39.0 wrongly merged 543 actors)**: on the real screenshot the
  destructive "Batch confirm links" button occupies x in [358,544], y in [480,501]. The window is
  1318 px wide on the real machine while the coordinates were measured for 1000 px, so everything
  shifted by **+318 px horizontally**: "Select all suggested merges" (218,486) actually landed on
  **(536,486)** — a precise hit on the destructive button. The root fix is the tool-window size
  correction (`SetWindowPos` to match the ui_coords client area), confirmed working.
- Verification: `smoke_v1393.py` — **145 assertions, 0 failures**, including a new
  "8. QStyle guard" section asserting `setStyle(Fusion)` exists in `main.py` and measuring the
  checkbox colour pixel count (615) in a real **windows-back-end** subprocess.
</details>
<details>
<details>

<summary><b>v1.39.2 (Build 2610130061) — 2026-10-13</b></summary>

> Two bug fixes: the actor-detection checkbox still drew nothing on the real machine (v1.39.0's fix had never actually worked) · long entry names blew out the rows in Insight's *Top lists* and *Distributions*

- **Fix: the checkboxes in the actor-detection "Select" column still drew nothing at all on the real machine** — this is the very issue v1.39.0 claimed to have fixed; it only came to light from a 5x-zoomed screenshot during v1.39.1's on-machine verification, i.e. the fix **had never taken effect**. Root cause: in `style.qss`, the unchecked state of `QTreeView::indicator` was given `background: rgba(255,255,255,0.05)`. As soon as a QSS rule sets `width`/`height` on `::indicator`, Qt stops using the default painting and switches to the QSS path, where it **re-fills the background** over the rectangle returned by `subElementRect` — and 5% white on a dark panel counts as "no background", so `QStyleSheetStyle` skips drawing entirely and the **unchecked state paints not a single pixel**; the checked state happened to work because it uses a solid `__ACCENT__`. Fix: give the unchecked state a **solid** background (`#2a241c`, hover `#362e23`), and fix the same latent problem in `QListWidget` / `QCheckBox` / `QRadioButton` indicators. ⚠ This also corrects v1.39.0's probing methodology: it measured the *difference* between the Checked and Unchecked renders (46→279px), but **a non-zero difference only proves the two states differ — it cannot prove a checkbox exists at all**. The correct criterion is a per-pixel diff against an **empty tree**, with the unchecked state required to be > 0 as well — after the fix the unchecked state measures 303/1002px instead of 0.
- **Fix: long entry names blew out the rows of the Insight page's "top lists" and "distribution" panels** (user screenshots: the series / studio / director columns were the worst, with counts and bar charts wrapped to the next line and colliding with the neighbouring entry). Root cause: the bar text was assembled with `str(name)[:18].ljust(18)`, i.e. **aligned by character count**, but the font is `Consolas` with CJK fallback where **one CJK glyph occupies two monospace cells**, so 18 Chinese characters actually need 36 cells; adding the count column and the bar, the row easily exceeded the column width by more than double. Fixed in three coordinated changes: ① the 10 bar labels are now built by a new `_bar_label()` factory, where `setWordWrap(False)` removes wrapping at the root, paired with a horizontal `QSizePolicy.Ignored` (**mandatory**: the `minimumSizeHint()` of a non-wrapping QLabel is the full text width, which would widen the 5-column grid and stretch the whole page horizontally); ② `_bar_lines` now budgets in **real pixels** via `QFontMetrics.horizontalAdvance` — trimming names character by character (with a trailing `…`), padding the name column with pixel-accurate spaces, and right-aligning the count column with pixel-accurate spaces (`{:>N}` character widths cannot work once CJK fallback is in play); ③ the hover tooltip still shows the full name and count.

</details>

<details>

<summary><b>v1.39.1 (Build 2610130058) — 2026-10-13</b></summary>

> One bug fix: long entry names blow up the rows in Insight's *Top lists* and *Distributions*

- **Fix: in the Insight page's "top lists" and "distribution" panels, long entry names blew out the row — the count and the bar chart were pushed to the next line and overlapped the neighbouring entry** (user screenshots: the series / studio / director columns were the worst). Root cause: the bar text was assembled with `str(name)[:18].ljust(18)`, i.e. **aligned by character count** — but the font is `Consolas` with CJK fallback, where **one CJK glyph occupies two monospace cells**, so 18 Chinese characters actually need 36 cells; on top of the `{:>7,}` count column and a 14-cell bar, the row easily exceeded the column width (~150px ≈ 22 cells) by more than double, and the `wordWrap=True` QLabel wrapped it — throwing the count and bar onto the next line where they collided with the next entry. Fixed in three coordinated changes: ① the 10 bar labels are now built by a new `_bar_label()` factory — `setWordWrap(False)` removes wrapping at the root, paired with a horizontal `QSizePolicy.Ignored` (**mandatory**: the `minimumSizeHint()` of a non-wrapping QLabel is the full text width, which would widen the 5-column grid and stretch the whole page horizontally); ② `_bar_lines` is now an instance method that budgets in **real pixels** via `QFontMetrics.horizontalAdvance` — trimming names character by character (with a trailing `…`), padding the name column with pixel-accurate spaces, and right-aligning the count column with pixel-accurate spaces (`{:>N}` character widths cannot work once CJK fallback is in play); ③ the hover tooltip still shows the full name and count, so a trimmed name can always be looked up. The regression probe feeds real-shaped long CJK data through all 10 columns and asserts "never wraps / never overflows (widest line ≤ column width) / counts right-aligned"; it also confirmed a second latent hazard: the window frame measured 1318px before the fix, yet after it the 5 columns still share the width evenly at about 201px each.

</details>

<details>

<summary><b>v1.39.0 (Build 2610130057) — 2026-10-13</b></summary>

> Three reports (two bug fixes + one new feature): actor-detection checkbox column fix (incl. Shift/Ctrl multi-select) · minnano-av Cloudflare fingerprint-wall fallback · spinning ring for running tasks in the tools-window nav

- **Fixed: actor detection's "Select" column checkboxes were invisible and Shift/Ctrl multi-select didn't work** (user screenshot: the header row "Select / Candidate / People / Match / Reason" was there but the Select column was empty). Root cause (offscreen probe, nailed): the QTreeView layout **gives the indicator no space** — after indentation the cluster row's text-area rect starts at viewport x=40 (only 6px wide), while the delegate paints the checkbox absolutely at x=43..60; column 0 was only 46px wide, so the checkbox's right 14px spilled into the "Candidate" column and was clipped by the column boundary, leaving a 3px sliver (top-level rows don't overflow — only indented child rows do). Fix: column width 46→62, measured visible area of the checkbox 46→279px (the full 17×17 square appears); also enabled `ExtendedSelection` for **Shift range / Ctrl individual multi-select**, with check ∪ selection driving "batch confirm (merge N clusters)".
- **Fixed: minnano-av.com actor-scrape test returned HTTP 403 (with or without proxy, while the browser worked fine)**. Root cause: that host resolves to Cloudflare, which blocks non-browser clients by **TLS fingerprint (JA3)** — unrelated to IP / proxy (IMDB sits on Amazon CloudFront with no such block). Fix (harden first, auto-degrade after repeated 403): a global cookie jar + cached opener for session reuse; a homepage warm-up every 600s so Cloudflare plants cookies; after 3 consecutive 403s, automatic fallback to **curl_cffi** (`impersonate="chrome124"`, full Chrome TLS/HTTP2 fingerprint — an optional dependency that falls back to the pure-stdlib path when unavailable); the "Test" button's 403 message now explains this in plain language.
- **New: a spinning ring next to running tasks in the tools-window's left nav** (matching the main window's library-scan ring). `ScanRing` moved out of `main_window.py` into the standalone `src/scan_ring.py`; each nav button is wrapped in a row container (button + ring, the ring hidden when idle and taking no layout space); a 400ms timer centrally polls `_running_tasks()` (covering 11 kinds of background tasks plus `is_busy()` on both detection pages).

</details>

<details>

<summary><b>v1.38.0 (Build 2610120056) — 2026-10-12</b></summary>

> One bug fix + one new feature: live homepage count during scans · actor detection multi-select batch confirm

- **Fixed: homepage counts didn't update while multi-directory sequential scans ran** (sidebar library count (N) / bottom-left stats / homepage list). Root cause: `ScanWorker`'s `live` signal (throttled 1.2s during scans) was only connected to `MainWindow._on_scan_live` from the first entry point (top-bar "scan library"); the other three entry points (library context-menu "scan", folder-scan dialog, background scheduled scan) never connected it. Fix: connected `live` at all three.
- **New: actor detection multi-select batch confirm.** A "Select" checkbox column was added to the result tree; below it a "select all suggested / select none / batch confirm (merge N clusters)" toolbar merges all checked "suggested-merge" clusters in one go (reusing `db.merge_people` — fills empty fields only, merges aliases and meta, never touches video/nfo), each cluster keeping its default name (most works / has poster).

</details>

<details>

<summary><b>v1.37.0 (Build 2610070055) — 2026-10-07</b></summary>

> Five reports: favorite/pin name coloring on the detail page · card sub-line coloring · detail-top whitespace fix · detail panel border · splash follows the accent color

- Detail-page cast/director names: favorite→gold, pinned→bold, both→gold bold (from markers already carried by `get_cast`, zero extra queries).
- Card sub-lines (actor / director) follow the same rules; new `database.cast_crew_map_ex()` carries per-person favorite/pinned markers (still batched per page).
- Fixed the whitespace band atop the homepage detail panel: `HeroView._build` built an empty topbar with 10px padding even when `on_back=None`; it is now skipped entirely.
- The homepage "Details" panel gained an accent-colored border (`detail_host` + `WA_StyledBackground` + `QWidget#DetailHost` in style.qss, background stays transparent).
- Splash animation now derives its background / progress bar / stroke from the accent color in HLS space, falling back to the classic blue.

</details>

<details>

<summary><b>v1.36.0 (Build 2609300054) — 2026-09-30</b></summary>

> One new feature + one real-machine defect fix: guide vectors now auto-translate Chinese → Japanese · fixed the "already deleted object" crash on double-clicking a poster

- **New: "guide vector" auto Chinese→Japanese translation before fuzzy matching** (toggle under
  **Tools → Smart Recommend → Recommendation scope & preferences**). Library tags / studios / series /
  actor names are almost all **original Japanese**, while users almost always type **Chinese** into the
  guide box — `轮奸` cannot match anything (`轮奸` vs `輪姦`). When enabled, the input is first translated
  into several Japanese candidates, each of which is run through the **same** fuzzy matcher, and the
  results are **merged** into the original hits (additive only; extra guides can be removed one by one).
  - **Fully offline, millisecond-level, no network**: new leaf module `src/guide_translate.py` with two
    layers — a **term lexicon** (`中出 → 中出し`, `护士 → ナース`, `捆绑 → 緊縛`, `时间停止 → 時間停止`)
    for terms whose glyphs differ entirely, plus a **541-entry simplified → Japanese shinjitai character
    map** covering the much larger group that only differs in orthography — which **also solves actor
    names** (`轮奸 → 輪姦`, `三上悠亚 → 三上悠亜`, `桥本有菜 → 橋本有菜`).
  - Multi-term input is **split**: `孕妇教师 → 妊婦教師 / 妊婦 / 教師` — otherwise the whole translated
    string matches nothing at all.
  - The status line reports "**of which N came from Chinese→Japanese translation**" and the log appends
    `[引导向量] 中文→日文扩展：…`, so it is obvious whether the toggle actually took effect.
- **Fixed a real-machine defect: double-clicking a poster raised `RuntimeError: libshiboken: Internal
  C++ object (PosterCard) already deleted`** (6 occurrences in the real `index_data/logs/app.log`, top
  frame `mouseDoubleClickEvent` in `main_window.py`). Root cause: the "check liveness on entry" guard
  added in v1.24.1 **cannot structurally catch this**, because the destruction happens **inside the
  callback**: `_on_open → _open_media → set_backdrop + go(HeroView)` replaces the current page, so the
  card is gone by then and the following `super()` call is the actual bomb. Fix: **run the base-class
  handling before the callback**, put the callback last and **never touch `self` after it** — applied
  uniformly to `mousePressEvent` + `mouseDoubleClickEvent` of `PosterCard` / `ActorCard` and to
  `mousePressEvent` of the collection card.

</details>

<details>

<summary><b>v1.35.1 (Build 2609300053) — 2026-09-30</b></summary>

> Two reports (both from user screenshots) + brand icon update: Smart Recommend layout fix · logo → v4

- **Fixed the "guide vector" chips wrecking the Smart Recommend layout**: v1.35.0's fuzzy match can hit
  dozens to hundreds of tags / studios / series at once, and every chip was crammed into the toolbar —
  a single-row HBox — so the row's minimum width ballooned far past the viewport, clipping the chips and
  buttons on the right and misaligning the whole page. Fix: chips + status text moved **out of the toolbar**
  into their own full-width row below it (`FlowLayout`, auto-wrapping); beyond 14 chips they collapse into
  "show all (N)" and can be expanded / collapsed.
- **Fixed the toolbar overflowing by itself**: the summary label's `setMinimumWidth(0)` is a **no-op in Qt**
  (0 is the default, so the call cannot distinguish "explicitly 0" from "never set"), leaving its minimum
  width equal to the full text (531px measured); together with the guide controls the toolbar's minimum
  reached 1081px > the 884px viewport and pushed controls off-screen. Fix: the summary now takes **its own
  row**, so both fit fully (zero horizontal overflow at the 1920 design width).
- **Brand icon switched from `logo-3.png` to `logo-4.png`** (3rd → 4th golden-film version):
  `build_exe.py` (`--icon` source and `--add-data`), `src/main.py`, `src/splash.py` all follow;
  `logo.ico` is regenerated automatically by mtime.

</details>

<details>

<summary><b>v1.35.0 (Build 2609300052) — 2026-09-30</b></summary>

> Three feature additions (Smart Recommend / AI Engine)

- Smart Recommend "algorithm" simplified to a "Normal / AI" detection-mode group; model settings moved to the new **AI Engine** page.
- AI Engine can **auto-launch Ollama** (on startup + "Launch now"), then auto-reads local models.
- Guide-vector **fuzzy match**: input no longer needs an exact tag — every containing tag / studio / series is boosted.
- Vector edit gains **auto-fill from favorited actors**.

</details>

<details>

<summary><b>v1.34.3 (Build 2609260051) — 2026-09-26</b></summary>

- Fixed runtime `AttributeError` in actor / image detection (7 stale modules restored to latest snapshots; 0 missing attrs across module audit).
- Tag-optim page got an explicit "detect local AI engine" button.
- Fixed actor-detection "min works" SpinBox overlapping its arrows (unified `SPIN_MIN_W`/`SPIN_MAX_W`).

</details>

<details>

<summary><b>v1.34.2 (Build 2609250050) — 2026-09-25</b></summary>

- Tightened the "scope" group box and removed the whitespace below it (root cause: `lb_scope_tip` wrongly word-wrapped to ~3 lines).
- Raised "Top N" cap 200 → 999 and made 999 actually work (panel swallowed the 3rd digit + `insight` list truncation, both fixed).

</details>

<details>

<summary><b>v1.34.1 (Build 2609250048) — 2026-09-25</b></summary>

- Three numeric SpinBoxes overlapped borders / arrows (style.qss padding ate the content area); unified `SPIN_MIN_W=131`/`SPIN_MAX_W=160`.
- "My favorites" scope jumped height (tips pinned to two lines + adaptive dialog height).
- Guide-vector weight box crowded the "boost" button (same root cause fixed).

</details>

<details>

<summary><b>v1.34.0 (Build 2609240047) — 2026-09-24</b></summary>

- Vector-edit "auto-fill from profile" became a dialog (scope / Top N / weight / per-dimension toggle) and remembers preferences.
- Recommendation wall gained **guide vector**: type an actor / tag / studio / series to bias this session.

</details>

<details>

<summary><b>v1.33.x — early 2026-09</b></summary>

- Four scan pages can export / import results to continue later.
- Fixed the white strip on the right of actor / director / recent / collection toolbars.
- Removed the never-implemented "show trailer on hover" toggle.
- Added 19 UI languages (instant switch, no restart).
- "About" rewritten with real GitHub / Bilibili / Weibo contact logos.

</details>

<details>

<summary><b>v1.32.0 — 2026-09</b></summary>

- Duplicate / image / actor detection unified on the "Normal + AI" `aireview.py` base, with a "fast mode" that only re-checks uncertain items.
- Prompts sent to the model are desensitized (no drive / folder / ID / filename).

</details>

<details>

<summary><b>v1.31.0 — 2026-09</b></summary>

- Tools nav grouped as "Basic / Data Optimize / Smart Detect / Data Analysis".
- Added "actor detection": normal (romaji merge / alias cross-link) + AI review to catch same-person-different-alias.
- Actor card shows cup size before measurements, bolded.

</details>

<details>

<summary><b>v1.30.0 — 2026-09</b></summary>

- Added "manual edit" (17 nfo fields + 3-slot upload back to index) and "image detection" (structural check for missing / truncated images).
- A-Z letter index on the right of actor / director libraries.

</details>

<details>

<summary><b>v1.28.x — 2026-09</b></summary>

- Sidebar "data stats / live status" toggle in Appearance; sidebar logo opens the project page, status bar opens the author page.
- Director card dropped "bio" and shrank 160 → 118; actor / director libraries 5 → 6 per row.

</details>

<details>

<summary><b>v1.27.0 — Rebrand</b></summary>

- Renamed **流明盒 / LumaCrate**; slogan "所有流明 · 尽收盒中" enters the splash and About.
- Sidebar gained a "live status" panel (process-level singleton collector thread to avoid rebuild crashes).

</details>
