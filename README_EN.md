# LumaCrate (流明盒)

> **Every lumen, in one crate.** —— *所有流明 · 尽收盒中*

[![Version](https://img.shields.io/badge/version-v1.28.0-blue.svg)](https://github.com/zouzuo1994321/LumaCrate/releases)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg)](https://github.com/zouzuo1994321/LumaCrate/releases)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/license-open--source·no--commercial-orange.svg)](./README_EN.md#license--disclaimer)
[![Build](https://img.shields.io/badge/build-2609210038-success.svg)](https://github.com/zouzuo1994321/LumaCrate/releases)

A **local video-manager desktop app with no browser and no web service**. It borrows Emby's poster-wall + actor-management model and tinyMediaManager's local-management mindset, while putting extra weight on **joined search across title / genre / actor**. Movie scraping is intentionally stripped down: it only reads `.nfo` files already scraped by Emby / tinyMediaManager / Kodi; actor info is stored separately and can optionally be completed from `www.minnano-av.com` / `IMDB`.

> Formerly named "本地影视中心 / LocalMediaCenter". It was **rebranded to "流明盒 / LumaCrate" starting at v1.27.0** (same functionality, only the brand and UI copy changed).

## Contents

- [Screenshots](#screenshots)
- [Features](#features)
- [Download & Install](#download--install)
- [Usage](#usage)
- [Dependencies & Runtime](#dependencies--runtime)
- [Versioning Rules](#versioning-rules)
- [Directory Structure](#directory-structure)
- [Development / Build](#development--build)
- [Changelog](#changelog)
- [Related Project · NFO Profiler](#related-project--nfo-profiler)
- [License & Disclaimer](#license--disclaimer)

---

## Screenshots

> Screenshots ship with each release on [GitHub Releases](https://github.com/zouzuo1994321/LumaCrate/releases); you can also drop them under `docs/screenshots/` in the repo and reference them here.

- **Home**: list + detail side-by-side, with a thumbnail preview card popping up when you hover a row
- **Poster wall**: 8 cards per row, paged incremental loading, "Load more" at the bottom
- **Emby-style detail page**: full-width backdrop + quality badges + circular cast row + file info
- **Toolbox**: insight overview / smart recommendation / tag optimization / duplicate detection / actor scraper

## Features

### Pure desktop app
- **Native desktop program** — PySide6 UI, no web server, no browser dependency; double-click the exe to use it (default window 1920×1080).
- **Play with your own player** — clicking play invokes a local player (VLC / MPV / PotPlayer / system default), solving Emby's web-playback pain point.
- **Reads already-scraped `.nfo`** — supports `movie.nfo` / `tvshow.nfo` / episode `.nfo`, and recognizes tinyMediaManager-style single-item scraping (`id.nfo` + `id.mp4` + `id-poster.jpg`); extracts title, year, plot, rating, user rating, release date, genre, certification, quality, poster, fanart.

### Library & scanning
- **Fully custom libraries** — there is only one library list, **no built-in library**: you name it, pick a type and media folders when creating. Right-click a library in the sidebar to edit / rename / scan (3 modes: add+modify / fill-missing / overwrite) / delete (confirm dialog, **never touches disk files**); deleted libraries don't auto-restore.
- **Scan right inside a folder** (v1.13.0) — right-click a library on the "Folders" page to pick a scan mode; it **counts video files for confirmation first**, then shows scan progress (cancellable).
- **Poster wall, 8 per row** (v1.13.0) — the wall renders a fixed 8 cards per row.

### Browsing at scale
- **Paged read + progress** (v1.14.0) — the wall and actor library no longer load everything into memory at once: data is **paged at the DB layer** and cards are **rendered incrementally in batches of 60** (yielding to the event loop between batches); scroll near the bottom or click "Load more" to continue, then it shows "N items (all loaded)". **Since v1.18.0 the count/progress bar is hidden while loading** (stuck at 0% on tens of thousands of items looked like a freeze); the cards appearing incrementally *is* the progress feedback. **No more "not responding" on entry even at 50k items.**
- **Library name shows total count** (v1.14.0) — each sidebar library reads "Name (N)"; the page title reads "Name (N items)"; counts come from a single `GROUP BY` query.
- **Wall filter + sort** (v1.14.0) — a toolbar on top: sort menu (name / genre / added / release date / year / rating / user rating / favorite / duration / file size / plays / recently played + asc/desc, current item checked, Emby-style); filter dropdowns cover **favorite state, user rating (has/none, ≥3/5/7/9), year (after 2020·2010·2000 / 2000-and-before), genre, quality (4K/1080P/720P/HDR10/Dolby Vision/Atmos)**, stackable, one-click reset. **All filter/sort happens in SQL**; preferences persist to `settings.json`.
- **Actor-library filter + sort** (v1.14.0) — same toolbar: filter by favorite / pinned / status (active·retired·unknown) / has-avatar; sort by work count / latest work / name / birthday / favorite / pinned / join order (+ asc/desc, pinned always first).

### Actor & director libraries
- **Standalone actor library (Emby mode)** — actor info lives in its own `people` table, linkable to any work; an actor page can **reverse-lookup all their works**.
- **Joined search** (fixes tinyMediaManager's weak spot) — search by title / genre / actor together; actor ↔ work two-way jump.
- **Actor scraping** — Tools → Actor Scraper fills in alias / birthday / romaji / bio / avatar from `www.minnano-av.com` / `IMDB`, with priority, start/stop, rate-limit, proxy and resumable progress.
- **Director library** (v1.24.0) — cards + filter/sort like the actor library, but without birth/body fields; double-click reverse-lookups all the director's works.

### Detail page & playback
- **Home (list + detail)** — pick visible columns in settings, **drag the header to reorder** (including the "Actor" column); hovering a row pops a thumbnail preview card. Frosted backdrop follows the current work.
- **Emby-style detail page** (v1.20.0) — full-width fanart + plot + quality badges + circular cast row + file info; the action row above the title has **Play / Favorite / Rate / Refresh / More**. The "Refresh" button re-reads **only this item's** nfo and refreshes the page (`scanner.rescan_one`) — handy after an external tool edited the nfo; **favorite / play-count are untouched**, and series/episode structure isn't broken. Poster cards themselves carry two corner buttons: **bottom-right ▶ play** (no detail page) and **bottom-left ★ favorite** (gold filled = favorited, white outline = not), present on every page's cards.
- **Detail buttons clearly visible** (v1.20.0) — the action row sits on a bright still with a dedicated dark + gold-outline + bright-text style (`QPushButton#HeroAct`).
- **One-click favorite on card** (v1.21.0) — gold filled star when favorited, transparent white-outline star otherwise; toggles via the same `db.toggle_favorite` as the detail page and syncs sidebar counts.
- **Centered play icon** (v1.21.0) — the play triangle is geometrically drawn and centered on its centroid instead of the lopsided `▶` glyph.

### Smart features
- **Insight overview** (v1.24.0) — Tools → Insight computes a one-line taste profile, an **8-axis preference radar** (genre breadth / actor focus / studio loyalty / HD preference / long-film preference / rating activity / series collection / novelty), top charts (tag·actor·director·studio·series), distributions (quality / rating / duration / year / ingest month) and tag co-occurrence. Scope is switchable (all libraries / ★ my favorites / per library) and recomputes instantly. Ported from [NFO Profiler](https://github.com/zouzuo1994321/nfo_profiler).
- **Smart recommendation + vector editor** (v1.24.0) — a "Smart Recommend" nav entry builds a preference profile from **your favorited films** (tag / studio / series / actor / director weighted) and **favorited actors**, cosine-scores the candidate pool (IDF down-weight, co-occurrence expansion, MMR de-dup), writes a **reason** on each card, and offers "shuffle". The recommend wall uses the same cards as "All" (poster + ★ + ▶). Tools → Smart Recommend lets you pick **Normal** or **AI** algorithm (local offline Ollama; auto-falls-back if not detected, **no network, no upload**); "Detect local AI engine" gives a timestamped verdict (✅/⚠/❌) with troubleshooting. The **vector editor** adds/removes keyword weight per dimension (−5~+5).
- **Recommendations stop repeating** (v1.25.0) — "don't repeat within N rounds (0–50, default 3)"; each "shuffle" or page entry counts as 1 round. This also fixed a root-cause bug where the exclude set was computed but never applied, so "shuffle" had never actually worked.
- **Tag optimization** (v1.25.0) — Tools → Tag Optimization completes + translates JP→CN for `.nfo` `<genre>`. Scope: single file / folder / library; algorithm: normal (local rules — built-in JP→CN dictionary + title keywords + studio/series pseudo-tags + library-wide co-occurrence, zero deps) or AI (normal + local offline Ollama, auto-fallback). **Two-phase on purpose**: "scan & preview" lists each file's old → new / JP→CN (read-only), then "write" commits (confirm dialog, auto-backup `*.nfo.bak-<timestamp>`). Only the `<genre>` node is touched; a "overwrite source JP tag" toggle controls whether JP is replaced or kept alongside the CN addition.
- **Duplicate detection** (v1.23.0) — finds the same work stored in multiple directories: identity key prefers the normalized release id (`abc123`), falls back to "title + year"; same-directory copies are always treated as parts (CD1/CD2) and excluded; cross-directory only counts as duplicate. Estimates **recoverable space** by keeping the largest copy, with **very-high / high / medium / low** confidence. Filter by library and min confidence; export **CSV / JSON**. Algorithm ported from [NFO Profiler](https://github.com/zouzuo1994321/nfo_profiler)'s `dedupe`.

### Data & logs
- **Export / import + log export** (v1.13.0) — Tools → Data & Logs zips your index + actor data + library config for **database recovery** (auto-saves current data as `*.bak-<timestamp>` before import); all runtime logs go to `index_data/logs/app.log` and can be exported as a zip for debugging. **Since v1.24.0 you can export by category.**
- **Live log viewer** (v1.19.0) — the "Runtime log (live)" panel refreshes ~every 1.5s and scrolls the tail of `app.log` (max 200KB), telling you what the app is doing right now.

### Appearance & polish
- **12 highlight colors + selection glow** (v1.25.0) — Tools → Personalization → Appearance has a highlight palette (vermilion / pink / apricot / gold / bamboo-green / cyan / sky / indigo / purple / lotus / jade / graphite); selecting a card outlines it and the whole accent system (buttons / chips / sliders / checkboxes / progress) switches together (QSS token swap + `ACCENT_RGB` for custom-drawn widgets; light/dark shades derived via HLS). A selected card also gets a `QGraphicsDropShadowEffect` outer glow (blur 38, zero offset) that truly spills outside the card.
- **Frosted glass look** — the current work's still, heavily blurred, becomes the whole-window backdrop under semi-transparent glass panels, linked to what you browse; Tools can switch "frosted glass / classic dark" and low/mid/high intensity.
- **Sidebar "real-time status"** (v1.27.0) — bottom of the sidebar: a "**data stats**" block (movies / episodes / parts / actors, two rows) and a "**real-time status**" block with **CPU / memory / GPU bars** (≥60% amber, ≥85% warning-orange, color follows the highlight color), plus "**network · Ollama**" (one dot for both connectivity and Ollama running) and "**current model**" (the one from `ollama list`, with a hint if not installed). Collection runs on a **zero-hard-dependency fallback chain** (psutil → ctypes → `nvidia-smi`) in a background thread; set `LMC_NO_SYSMON=1` to disable.
- **Brand rename** (v1.27.0) — Chinese/English names live in one place (`src/version.py`: `APP_NAME` / `APP_NAME_EN` / `SLOGAN_CN` / `SLOGAN_EN`); sidebar, window title, splash, About, and the exe product name all follow.

### Performance at huge scale (v1.14.0)
- SQLite **WAL** + 16MB page cache + 256MB mmap + 15s busy timeout;
- **per-thread connection reuse** (no more connect/close per op);
- indexes added for filter / sort / join queries (`library / favorite / year / added_time / added_date / premiere / rating / user_rating / sort_title / file_path / collection / (library,kind) / media_people.media_id / media_people.person_id / people.role_type`);
- list queries use **column projection** (no `plot` etc. in lists; fetched by PK on demand);
- cast associations query **only the currently visible media_ids**;
- home list fills **in batches of 200** with a "loading list… x / y" footer;
- **poster / avatar caching** (was re-read + resize per card).

### Non-modal tools
- The **settings window (called "工具" since v1.24.0) is non-modal** (v1.14.0) — browse / search / page / play while it's open; re-clicking "工具" raises the open window; scan progress shows in-place (no modal "scan done" popup); closing the main window closes the tool window too.

## Download & Install

- Go to **[GitHub Releases](https://github.com/zouzuo1994321/LumaCrate/releases)** and download the latest `流明盒-v1.28.0-<build>.exe`;
- **It's a single-file Windows exe — double-click to run, no install, no Python needed**;
- If blocked by Windows / your antivirus, allow it to run or add an exception (single-file exes are occasionally false-flagged);
- Data lives in `index_data/` **next to the exe**; copy that folder along with the exe to migrate to another machine.

## Usage

1. Run `流明盒-<version>.exe`.
2. On the left "Libraries" group, click **＋ New Library** (or Tools → Service Management → Libraries) and create one: name, type, media folders.
3. **Right-click the library → Scan** (add/fill/overwrite modes; confirm count first, then progress), or click "Scan library" top-right to pick a directory; right-click "Delete" removes it (no disk changes). You can also right-click a library on the "Folders" page to scan.
4. Left nav: Home / Recently Played / My Favorites / Smart Recommend / Folders / Collections / Categories (All / Actors / Directors) / Libraries. A scanning library shows a **circular progress ring** next to its name.
5. Home is "list + detail": open "Column settings" to pick columns, **drag items or the header** to reorder; hovering a row pops a thumbnail preview.
6. Click a poster for the **Emby-style detail page**: full-width backdrop + plot + quality badges + circular cast row + file info; the action row has **Play / Favorite / Rate / Refresh / More** (Play calls your local player; Refresh re-reads only this item's nfo). Poster cards also have **bottom-right ▶ play** and **bottom-left ★ favorite**.
7. The top search box (`Ctrl+K`) searches title / genre / actor; `title@actor` scopes to an actor.
8. Tools → **Insight** ("Start analysis" to see your taste); Tools → **Smart Recommend** (pick Normal or AI — the latter needs a local Ollama, auto-falls back; set the model name in "Call model", or click "Read local models"; set "no repeat within N rounds" and use the vector editor to weight keywords).
9. Tools → **Actor Scraper** fills birthday / alias / bio / avatar; Tools → **Personalization → Appearance** switches frosted-glass / classic-dark and glass intensity.
10. Tools → **Duplicate Detection** (pick library + min confidence, then "Start"; results are sorted by recoverable space, expandable per copy with Explorer-locate on double-click, exportable to CSV / JSON). Clean up only after you verify in Explorer — this tool detects, never deletes.
11. Tools → **Data & Logs**: export **by category** (index / actor+director / favorites / user ratings / actor favorites…) or the whole DB as a zip (importable later; a package with `sections.json` **merges** into the current library); export logs for debugging.
12. Tools → **Tag Optimization** (v1.25.0): pick scope (file / folder / library) and method (normal / AI), click **Scan & Preview** (read-only), review the old → new / JP→CN table, then **Write** (confirm dialog, auto-backup; toggle "overwrite source JP tag" — off keeps JP and adds CN).
13. **Filter & sort** in any library (or All / Favorites / Collections): the top toolbar has a "Sort: …" button and filter dropdowns (favorite / user rating / year / genre / quality for actors/directors: favorite / pinned / status / avatar); "Reset" clears. Choices are remembered. At large scale a load progress shows at the top; scroll to the bottom or click "Load more" to continue.
14. The **tool window is non-modal** — keep it open while browsing; library scans run in the background with progress under the "Scan all libraries" button; a scanning library lights a circular ring in the sidebar.

## Dependencies & Runtime

- **Running the exe**: Windows 10 / 11 64-bit; the exe already bundles Python 3.13 + PySide6 6.x, no runtime needed.
- **Running / building from source**: Python 3.13 + `pip install -r requirements.txt` (PySide6, psutil).

## Versioning Rules

- **Internal build number**: `YYMMDDNNNN` — e.g. `2609170001` = 2026-09-17, the 0001st build. The last 4 digits increment on every packaging.
- **External version**: `v1.1.1`
  - 1st digit: product generation (only on a big rewrite)
  - 2nd digit: major iteration (functional additions)
  - 3rd digit: minor iteration (bug fix / small improvement)

## Directory Structure

```
LumaCrate/
├── src/                  # source code
│   ├── main.py           # entry point
│   ├── main_window.py    # main window (grouped sidebar + top nav + view router)
│   ├── ui_hero.py        # Emby-style detail page (banner / metadata / cast row / file info)
│   ├── ui_home.py        # home list + detail view
│   ├── ui_settings.py    # tool window (custom ToggleSwitch / libraries / insight / recommend / tag-opt / duplicates / background tasks)
│   ├── insight.py        # taste-profile computation (Qt-free: radar / top charts / distributions / co-occurrence)
│   ├── recommend.py      # smart recommendation (profile scoring + IDF / co-occurrence / MMR + multi-round dedup; local Ollama optional)
│   ├── splash.py         # blue splash screen (custom-drawn + real progress + fade + Slogan)
│   ├── sysmon.py         # sidebar "real-time status" (CPU/mem/GPU bars + net·Ollama + current model; psutil first, ctypes fallback)
│   ├── config.py         # global settings persistence (settings.json)
│   ├── database.py       # SQLite (media + standalone actor library + vector weights)
│   ├── nfo_parser.py     # nfo parsing (read-only, already-scraped)
│   ├── scanner.py        # library scan (bare videos / name dictionary / dedup)
│   ├── scraper.py        # actor scrape engine (minnano-av / IMDB, stdlib only)
│   ├── duplicates.py     # duplicate detection (id/title+year keys, CD-part toggle, dead-row pruning, CSV/JSON export)
│   ├── tagopt.py         # tag optimization (JP→CN dict aligned to your library + title/co-occurrence fill + AI assist; only edits <genre>)
│   ├── applog.py         # runtime log (rotating file, for debugging / export)
│   ├── backup.py         # data export / import (whole-db zip + category-sectioned export/merge)
│   ├── veil.py           # in-app frosted backdrop (heavy poster blur + darken + glass layers)
│   ├── backdrop.py       # Windows system-level blur (3-level fallback + capability detection)
│   ├── media_meta.py     # quality-badge inference / size / date
│   ├── player.py         # local player invocation + Explorer locate
│   ├── version.py        # version number
│   └── style.qss         # theme styles (with glass transparency tokens)
├── index_data/           # database + thumbnails (generated at runtime)
├── history/              # archived historical exes
├── dev/                  # dev test & preview scripts (not packaged)
├── build_exe.py          # packaging script
├── 性能基线.md            # performance baseline report (generated by dev/benchmark.py on a real index)
├── requirements.txt
└── README.md
```

## Development / Build

```bash
pip install -r requirements.txt     # PySide6 required; psutil for the sidebar "real-time status" (auto-falls back to ctypes if missing)
python build_exe.py                 # builds a standalone exe to the root dir; old versions auto-archived to history/
```

## Changelog

> Full per-version detail is in the Chinese [README.md](./README.md#迭代记录). Highlights below.

- **v1.28.0** (2026-09-21) — Appearance settings gain sidebar "stats / real-time status" show/hide toggles; sidebar logo opens the project homepage; status bar opens the author homepage.
- **v1.27.0** (2026-09-21) — Rebrand to 流明盒/LumaCrate + Slogan; new sidebar "real-time status" panel (CPU/mem/GPU/net/Ollama/current model).
- **v1.26.0** (2026-09-21) — 4 fixes: highlight color follows selection everywhere; bottom open-source notice; subtitle text crop fix; performance baseline.
- **v1.25.0** (2026-09-21) — Selectable AI model; recommendations stop repeating (root-cause fix); tag-optimization tool; 12 highlight colors + selection glow; home quick-filter selected state.
- **v1.24.1** (2026-09-21) — Recommendation card render fix; director-library jump-page fix; log-export fix.
- **v1.24.0** (2026-09-21) — Insight overview; Smart Recommend + vector editor; Director library; collections as poster wall; sidebar scan progress ring; category export/import; settings renamed to "工具" (non-modal).
- **v1.23.0** (2026-09-20) — Duplicate detection; actor-detail status buttons + favorite/pin; exe icon & sidebar brand.
- **v1.22.0** (2026-09-20) — Feedback iteration.
- **v1.21.2 / v1.21.1 / v1.21.0** (2026-09-20) — Card favorite star; centered play icon; floating-window fix for load-more/refresh.
- **v1.20.0** (2026-09-20) — Detail-page hero buttons visible; single-item refresh re-scan.
- **v1.19.1 / v1.19.0** (2026-09-19) — Live `app.log` viewer.
- **v1.18.0** (2026-09-19) — Hide loading progress bar on huge libraries.
- **v1.17.0 / v1.16.0** (2026-09-19) — Feature iterations.
- **v1.15.0** (2026-09-18) — Feature iteration.
- **v1.14.0** (2026-09-19) — Incremental rendering + 50k-scale performance overhaul; library count badge; wall filter/sort; actor filter/sort; non-modal settings.
- **v1.13.0** (2026-09-18) — Folder scan; poster wall 8/row; data export/import.
- **v1.12.0 … v1.1.1** (2026-09-17 ~ 09-18) — Early iterations: UI scaffolding, scanning, nfo parsing, library management, and actor-scraper foundations.

## Related Project · NFO Profiler

[NFO 画像矿工 (NFO Profiler)](https://github.com/zouzuo1994321/nfo_profiler) is a sister project. LumaCrate ports its `dedupe` (duplicate detection) and taste-profile algorithms, and shares the same `.nfo`-first philosophy.

## License & Disclaimer

- Copyright © 2026 肆月Aperture.
- This software is **open source; commercial use without a license is prohibited.**
- It only reads `.nfo` files already scraped by other tools; it does not provide any scraping/downloading of copyrighted material. Use it only on media you legally own.
