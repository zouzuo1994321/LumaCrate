<div align="center">

# 🎬 LumaCrate (流明盒)

**Local movie & TV management · Emby-style poster wall + tinyMediaManager relation search · single-file exe**

**所有流明 · 尽收盒中** · *Every lumen, in one crate.*

![Version](https://img.shields.io/badge/version-v1.35.0%20(2609300052)-c0392b?style=flat-square)

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
  <img src="logo-3.png" width="200" alt="LumaCrate Logo">
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
| Guide vector | type an actor / tag / studio / series on the wall and this session's picks lean that way (**fuzzy match**: every containing tag / studio / series is boosted) |

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

1. Download `LumaCrate-v1.35.0-2609300052.exe` (~46 MB, single file) from [Releases](../../releases).
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
├── LumaCrate-v1.35.0-2609300052.exe   # single-file executable
├── logo-3.png                         # brand icon (golden film)
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

- Packaging params (`--onefile --windowed`, icon `logo.ico`, bundled `logo-3.png`) live in `build_exe.py`.
- Newest exe goes to root; older builds auto-archived to `history/`.

---

## 🧪 Dev checks

`dev/` holds offscreen (`QT_QPA_PLATFORM=offscreen`) smoke scripts — no real display needed:

| Script | Purpose |
| ------ | ------- |
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
