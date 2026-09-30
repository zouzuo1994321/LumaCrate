<div align="center">

# 🎬 LumaCrate (流明盒)

**Local movie & TV management · Emby-style poster wall + tinyMediaManager relation search · single-file exe**

**所有流明 · 尽收盒中** · *Every lumen, in one crate.*

![Version](https://img.shields.io/badge/version-v1.36.0%20(2609300054)-c0392b?style=flat-square)

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
| Actor detection | romaji merge / alias cross-link + AI review; catches same-person-different-alias |
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

1. Download `LumaCrate-v1.36.0-2609300054.exe` (~46 MB, single file) from [Releases](../../releases).
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
├── LumaCrate-v1.36.0-2609300054.exe   # single-file executable
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
| `smoke_v1360.py` | v1.36.0 offscreen smoke: CN→JP candidates (lexicon / char map / multi-term split) / preference persistence + dirty-value normalization / translated hits merged into guides / **double-click callback destroying its own card no longer raises** — **all pass / 0 fail** |
| `smoke_v1351.py` | v1.35.1 offscreen smoke: toolbar min-width **independent of chip count** / chips wrap + fold in their own row / zero horizontal overflow at 1920 / logo-4 wiring — **all pass / 0 fail** |
| `smoke_v1350.py` | v1.35.0 offscreen smoke: fuzzy resolve / AI Engine page / vector-edit auto-fill — **all pass / 0 fail** |
| `smoke_v1343.py` | module-attribute audit and detector-page widget assertions |
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
