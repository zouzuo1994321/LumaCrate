# LumaCrate (流明盒)

> **Every lumen, in one crate.** —— *所有流明 · 尽收盒中*

[![Version](https://img.shields.io/badge/version-v1.33.2-blue.svg)](https://github.com/zouzuo1994321/LumaCrate/releases)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg)](https://github.com/zouzuo1994321/LumaCrate/releases)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/license-open--source·no--commercial-orange.svg)](./README_EN.md#license--disclaimer)
[![Build](https://img.shields.io/badge/build-2609240046-success.svg)](https://github.com/zouzuo1994321/LumaCrate/releases)

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

> All screenshots are **real UI** (rendered offscreen by an automated script), with **drive letters / directories / file paths irreversibly masked** for privacy, and a **肆月Aperture** watermark on every image. Files live in [`docs/screenshots/`](./docs/screenshots).

### Main UI

| Home (list + detail) | Movie wall (8 cards per row) |
| :---: | :---: |
| ![Home](./docs/screenshots/01_home.png) | ![Movie wall](./docs/screenshots/02_wall_all.png) |
| Columns are freely selectable and drag-reorderable; hovering a row pops up a thumbnail preview card. | Paged incremental loading — scroll down or click "Load more". Sorting + multi-facet filtering all happen in SQL. |

| Actors (6 per row · cup & measurements on card) | Directors |
| :---: | :---: |
| ![Actors](./docs/screenshots/03_actors.png) | ![Directors](./docs/screenshots/04_directors.png) |
| Cards show works, cup size, measurements, birthday and hometown; sort by works / initial / birthday, and favourite or pin. | Same card style as actors, minus birthday / hometown / height / measurements (rarely present for directors). |

| Folders (directory card grid) | Actor detail (reverse-lookup all works) |
| :---: | :---: |
| ![Folders](./docs/screenshots/05_folders.png) | ![Actor detail](./docs/screenshots/06_actor_detail.png) |
| Each card = one configured directory, cover collaged from its first two posters; right-click to scan that folder. | Measurements carry the cup size too; the grid below lists every work by that actor, paged. |

| Emby-style movie detail | Sidebar (brand · nav · stats · live status) |
| :---: | :---: |
| ![Movie detail](./docs/screenshots/07_media_detail.png) | ![Sidebar](./docs/screenshots/08_sidebar.png) |
| Full-width backdrop + quality badges + circular cast row + file info; action row has Play / Favourite / Rate / Refresh / More. | Live CPU / RAM / GPU bars plus network & local Ollama status; stats and live status can be turned off in Appearance. |

### Toolbox

| Preferences | Interface language (19 · applies instantly) |
| :---: | :---: |
| ![Preferences](./docs/screenshots/09_tools_personal.png) | ![English UI](./docs/screenshots/10_tools_personal_en.png) |
| Appearance / glass strength / accent colour / card fields / home modules — all instant. | The "Appearance → Interface language" dropdown switches among 19 languages, **instant, no restart** (shown in English). |

| Arabic UI (RTL: text only) | Language comparison |
| :---: | :---: |
| ![Arabic UI](./docs/screenshots/11_tools_personal_ar.png) | ![Language comparison](./docs/screenshots/23_lang_compare.png) |
| Arabic is right-to-left, but the app **translates the text only and keeps the LTR layout** (no full mirroring, to avoid misalignment). | Left: English　Right: العربية — nav and common actions are fully localised; algorithm details stay in Chinese. |

| Toolbox nav (4 groups) | Duplicate detection (normal / AI) |
| :---: | :---: |
| ![Toolbox nav](./docs/screenshots/12_tools_nav.png) | ![Duplicate detection](./docs/screenshots/13_tools_dedupe.png) |
| Basic tools / Data optimization / Smart detection / Data analysis — a dozen tabs found at a glance. | "Detection method" offers **normal algorithm** (instant) or **AI algorithm** (local Ollama review); "Turbo mode" only reviews uncertain items. |

| Image check (normal / AI) | Actor check (same person under different aliases) |
| :---: | :---: |
| ![Image check](./docs/screenshots/14_tools_imagedetect.png) | ![Actor check](./docs/screenshots/15_tools_actorcheck.png) |
| Finds missing and truncated images (JPEG without EOI / PNG without IEND) and lets you upload replacements; AI review supported. | Shows per-cluster evidence and doubtful flags, and lets you confirm a merge; AI review speeds it up. |

| Tag optimization (normal / AI) | Manual edit (fix without touching the nfo) |
| :---: | :---: |
| ![Tag optimization](./docs/screenshots/16_tools_tagopt.png) | ![Manual edit](./docs/screenshots/17_tools_manualedit.png) |
| Scan-and-preview is read-only; write only after you confirm. Japanese→Chinese tags supported, auto backup before changes. | 17 nfo fields + poster / thumbnail / fanart upload, written back to the nfo and synced to the index (paths masked below). |

| Smart recommendation (8-axis profile · vector edit) | Services (libraries / scraping) |
| :---: | :---: |
| ![Smart recommendation](./docs/screenshots/18_tools_smart.png) | ![Services](./docs/screenshots/19_tools_service.png) |
| Normal or AI algorithm, custom model, dedupe rounds, and manual keyword weighting. | Library CRUD, actor-scraper sources and strategy, data-source connectivity tests. |

| Insight overview (8-axis radar) | Data & logs (export / backup) |
| :---: | :---: |
| ![Insight overview](./docs/screenshots/20_tools_insight.png) | ![Data & logs](./docs/screenshots/21_tools_data.png) |
| 8-axis preference radar + one-line profile + top lists + distribution and co-occurrence analysis. | Export only the categories you tick, or back up the whole library as a zip; export logs as an archive when troubleshooting. |

| About (rewritten in v1.32.0) |
| :---: |
| ![About](./docs/screenshots/22_about.png) |
| The About dialog alone explains what each of the nine modules does, where data lives, whether it goes online — plus privacy and disclaimer notes. |

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
- **Director library** (v1.24.0; card slimmed in v1.28.1) — cards + filter/sort like the actor library, but without birth/body fields; cards carry only **work count / alias**, and double-click reverse-lookups all the director's works. **As of v1.28.1 the "bio" row is gone and the card height drops from 160px to 118px** — for 1,218 real-world directors the `bio` field is essentially always empty, so the row only ever printed a lone "—" while eating vertical space. (The **detail page still shows the full bio**; only the grid card was slimmed.)
- **6 cards per row in the actor & director libraries** (v1.28.1) — the person-card grid went from 5 to **6 cards per row**. Both libraries share the same grid kind, so one change covers both; at the default 1920-wide window six columns need 1476px and fit comfortably. The **poster wall stays at 8 per row** and folders at 6.
- **Actor cards show the work count** (v1.30.0) — the card's 5th fact is now **works** instead of bust size. Third row "三围" already reads `bust85·waist58·hip83`, so a separate bust column was pure duplication, whereas "how many titles" is the first thing you look at. Still **3 rows**, still `236×160px`. **Since v1.31.0 the "三围" row is prefixed with a bold cup size** (`L bust111·waist65·hip96`), taken from the `B111( Lカップ )` part of the measurement string or from a standalone `罩杯` key — if there's no cup data, nothing is shown rather than guessing a letter.
- **Tools → Actor Check** (v1.31.0) — finds people who are really the same actor under **different stage names**, then merges them once you confirm. Same **normal algorithm / AI algorithm** split as Tag Optimizer; the AI path uses local Ollama and **falls back automatically** to the normal algorithm when unavailable (fully offline either way).
  - The **normal algorithm** (`src/actorcheck.py`, pure computation, no Qt) only trusts **evidence-backed** sameness: identical `romaji`, identical normalized name (case / mid-dot width / trailing `//` junk), a stage name in parentheses, or aliases pointing at each other. It **never does transitive closure** — chaining "A≈B, B≈C ⇒ A≈C" collapses thirty people who happen to share one boilerplate birthday into a single cluster.
  - **Dirt-resistant by design**: in the real library (5,909 actors) the same scraped profile is often written into several rows (5–6 rows sharing a `romaji` have **byte-identical birthday / measurements / height / agency**, and the `alias` string is actually that actor's own list of former stage names). So the pass first counts **how often each value occurs library-wide**; boilerplate values (`height` has only **43** distinct values, `agency` 219, birthday `1997-11-30` on 27 rows, measurements `T / B / W / H / S` on 105) never count as evidence — they're only used to detect **contradiction**. Conflicting birthday / measurements or a height gap ≥5cm demotes the pair to **"suspect"** and never auto-merges.
  - Oversized `romaji` groups (e.g. the placeholder string `LIST` with 48 rows) are excluded, and **each person lands in at most one cluster**.
  - Results are split into **"suggested merges"** (N clusters, M redundant rows removable) and **"suspects"** (informational only). Each cluster shows a score / tier (certain · very high · high · medium · low) plus per-item reasons; pick which record to **keep** and confirm. `database.merge_people()` then moves the work links (the `PRIMARY KEY(media_id, person_id)` dedupes naturally), **fills only empty fields** (never overwrites), merges aliases and meta, and deletes the extra rows. **No video or nfo file is touched.**
  - The lower half of the page is a **manual actor editor**: search on the left; on the right edit name / aliases / romaji / birthday / status / bio plus scraped fields (height / measurements / cup / hometown / agency), and **upload an avatar** (copied into `cache/people` as `<id>_<name>.<ext>`, matching the scraper's naming). Renaming onto an existing name shows a plain-language warning instead of silently corrupting the index.
  - Real-library read-only run: **0.17s / 5,909 people / 1,351 pairs / 734 clusters** (672 certain, 49 very high, 13 high) / 48 suspects / 964 redundant person-rows. Three genuine "same romaji, different person" pairs (`千葉優花` vs `千葉ゆうか`, `神菜美まい` vs `奏海麻衣`) all landed correctly in **suspects** and were never auto-merged.
- **Tools navigation split into four groups** (v1.31.0) — the rail mirrors the main sidebar's "category + library" style: **Basic tools** (Personalization / Service Manager / Manual Edit), **Data optimization** (Actor Scraper / Smart Recommend / Tag Optimizer), **Smart detection** (Duplicate Detection / Actor Check / Image Check), **Data analysis** (Portrait Overview / Data & Logs). `ui_settings.ORDER` stays flat because `dev/` scripts iterate it.

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

- **Image check** (v1.30.0) — Tools → Image Check finds **missing** and **broken** artwork for `-poster.jpg` / `-thumb.jpg` / `-fanart.jpg`. Filter by library / slot / problem type, run in a background thread with progress, then upload a replacement per row (copied to the standard filename, source untouched, index synced).
  - **Qt can't detect truncated JPEGs** — chop 45% off a valid JPEG and `QImageReader.read()` still returns a non-null image, because libjpeg's error-tolerant decoding paints the missing part **grey** (exactly the "real strip on top, grey block below" symptom). So validity is decided by **pure-Python structure checks**: JPEG must end with `EOI(FF D9)`, PNG must contain an `IEND` chunk, **anything under 1KB is suspicious**. Qt is only a fallback for mid-stream PNG damage — **no Pillow, no extra dependency**.
  - Slots deliberately **don't cross-fall-back**: a broken `<id>-poster.jpg` isn't papered over by a healthy `-thumb.jpg`. Better to report it and let you decide.
- **Manual edit** (v1.30.0) — Tools → Manual Edit: **search on the left, edit on the right**. Look up any indexed title (optionally filtered by library), then edit its **17 nfo fields** (title / original title / sort title / year / premiered / runtime / rating / user rating / mpaa / studio / set / country / genre / director / tagline / plot / outline), its **cast block** (one per line, `Name` or `Name | Role`), and **upload the three artwork slots**. Saving writes the nfo **and** syncs the `media` index, keeps a `*.nfo.bak-<timestamp>`, **touches only the edited nodes** (unchanged fields, `<uniqueid>` and original indentation survive), and **reuses same-name `<actor>` nodes so `<thumb>` avatars are preserved**.

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

### Normal + AI algorithm in every check page (v1.32.0)
- Duplicate detection, image check and actor check each offer **normal algorithm** (pure computation / structural validation, on-device and instant) or **AI algorithm** (per-item review via a local Ollama), plus **turbo mode** (review only the items the normal algorithm is unsure about) and a **Check local AI engine** button. All four pages share one review base, `src/aireview.py`: probe → filter → ask per item → write back → count. When AI is unavailable the **reason is shown verbatim in the UI** (never a silent fallback), and review only records suggestions — **it never deletes or modifies files**.
- **What is sent to the model is redacted**: volume / duration / quality / slot / aspect only — **never drive letters, directory names, codes or file names** (directory names map to "Directory 1 / Directory 2"; codes become "item 1 (original ID: N chars)"). AI runs entirely on the local Ollama (`11434`) and never goes online.

### 19 interface languages (v1.32.0)
- Tools → Personalization → **Appearance → Interface language**: Simplified Chinese (base) / English / Japanese / Korean / Spanish / Hindi / Arabic / Portuguese / Russian / German / French / Italian / Turkish / Dutch / Polish / Swedish / Thai / Vietnamese / Indonesian, applying **instantly with no restart**.
- Implementation is a **dictionary + fallback** (no `QTranslator` / `.qm`): only strings that change the user's path (nav, groups, common actions, search placeholder, splash tips) are translated; unknown strings return the original Chinese — safer than machine-translating 1900+ business strings. Arabic translates text only, keeping the left-to-right layout.

### Rewritten About dialog (v1.32.0)
- Headline + English name/build + slogan, then Markdown body: **What this is / Feature list (one line per module) / Privacy & networking / Tech stack / Interface languages / Usage notes / Links** — the old dialog had only three lines.
- **Zero hard-coding**: name / slogan / version / copyright / links all come from `version.py`.

### Non-modal tools
- The **settings window (called "工具" since v1.24.0) is non-modal** (v1.14.0) — browse / search / page / play while it's open; re-clicking "工具" raises the open window; scan progress shows in-place (no modal "scan done" popup); closing the main window closes the tool window too.

## Download & Install

- Go to **[GitHub Releases](https://github.com/zouzuo1994321/LumaCrate/releases)** and download the latest `流明盒-v1.33.2-<build>.exe`;
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
15. Tools → **Duplicate / Image / Actor check** (v1.32.0): each page has a **Detection method** group — **normal algorithm** (instant, on-device) or **AI algorithm** (per-item review via a local Ollama; falls back with the reason shown in the UI if unavailable). Tick **Turbo mode** to review only the items the normal algorithm is unsure about, and click **Check local AI engine** to confirm the model is ready. Anything sent to the model is **redacted**: volume / duration / quality / slot only — never drive letters, directories, codes or file names. Review only writes suggestions into the result; it **never deletes or modifies files**.
16. Tools → **Personalization → Appearance → Interface language** (v1.32.0): switch among **19 languages** — Simplified Chinese (base), English, Japanese, Korean, Spanish, Hindi, Arabic, Portuguese, Russian, German, French, Italian, Turkish, Dutch, Polish, Swedish, Thai, Vietnamese, Indonesian. It takes effect **instantly, no restart**. Navigation and common actions are localised; algorithm explanations and similar business details stay in the original Chinese (a dictionary + fallback design — unknown strings return the original text, which is safer than machine-translating 1900+ strings). Arabic translates the text only and keeps the LTR layout.
17. **About** (v1.32.0, rewritten): explains each of the nine modules, what data is stored (and where), whether the app goes online, plus privacy and disclaimer notes — every string comes from `version.py`, nothing hard-coded.

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

- **v1.33.2** (2026-09-24) — One item: **smart recommendations kept surfacing the same four actors** (君島みお / さつき芽衣 / 森日向子 / 新井リマ), taking **62.5% of the top-24** on a real 49,668-title library. The profile had two defects. **(A) Normalisation order**: `build_profile` accumulated favourite works, normalised to `max=1`, *then* added `+1.2` per favourite person — so the actor dimension was compared against the *already-normalised* tag maximum of 1.0 and was **inherently 1.2× the tag dimension** before any real comparison. Favourite people are now folded into the profile **before** normalisation, putting both on the same scale. **(B) Constant favourite-person weight**: a flat `+1.2` per person ignored how many works that person has library-wide, so the biggest filmographies (357 / 305 / 273 / 232 works) won on *per-hit contribution × candidate-pool hits* and buried obscure favourites with single-digit counts. The weight is now discounted by library-wide work count, `fav_w = FAV_PEOPLE_BASE / (1 + ln(1 + works))` (`FAV_PEOPLE_BASE = 1.2`; 1 work → 0.709, median 37 → 0.259, 357 → 0.174), backed by a new `database.person_work_counts()`. Result: the four dropped from **62.5% → 10.9%** of recommendations, and the top of the profile went from "six actors leading" to "all tags". The remaining 10.9% is **genuine taste, not a bug**: with the actor dimension switched off entirely they still land 10.4% (versus 11.1% with it on), and they are in fact the closest matches to the collection's tag profile (similarity 0.8153 / 0.7773 / 0.7563 / 0.7270). Two further root causes were identified but **not adopted**: relaxing the `idf` `+1` floor made things *worse* (10.9% → 20.3%, because generic tags covering 47% of the pool sank below actor terms), and MMR never separated different works by the same actor (pairwise cosine 0.408–0.554).
- **v1.33.1** (2026-09-24) — Three items: (1) in **tag optimization**, the "**Export result file…**" / "**Import result file…**" buttons now sit **on the same horizontal row** as "Scan & preview / Apply to nfo / Clear preview" instead of occupying a second, misaligned row — a 1px vertical rule (`QFrame#VRule`) separates the per-run actions from the file actions; (2) **the duplicate-check page drops its "Export CSV" and "Export JSON" buttons** — they overlapped with v1.33.0's *Export result file…* (which can be re-imported, whereas raw CSV/JSON is view-only) and the format choice meant nothing to users, so only the re-importable entry point remains; the underlying `duplicates.export_csv / export_json` functions stay for scripts, and the post-import hint text was updated accordingly; (3) the **About dialog's GitHub / Bilibili / Weibo icons now use each platform's real logo** (Octocat, the TV with antennae, the eye-and-arc), embedded as **base64 inside `src/main_window.py`** (each resized to 96×96, ~2–3KB, ~12KB total) rather than shipped as `--add-data` image resources — single-file exe resource paths bit us in the v1.23.0 icon chain (blank icons once packaged), whereas an inline string runs through **exactly the same code path frozen and from source**. Because the source logos are near-white silhouettes with an alpha mask, they are recoloured at runtime via `QPainter.CompositionMode_SourceIn` (source alpha kept, colour replaced by the theme tint) so they stay visible on both dark and light surfaces; results are LRU-cached per kind/size/tint. The **e-mail icon keeps its hand-drawn envelope** (there is no "official" mail logo, and hand-drawing avoids trademark confusion), and a decode failure falls back to the hand-drawn glyph rather than a blank icon.
- **v1.33.0** (2026-09-24) — Four items: (1) **tag optimization / duplicate / actor / image check can now export and import their scan results** as a `.json` file — a full-library run takes 70+ seconds for duplicates, reads ~50k images for image check, and takes minutes when actor check uses the AI algorithm, so an unfinished run can now be resumed tomorrow instead of re-scanned; each file carries a **shared envelope** (`_kind` / `_format`) so picking the wrong file says *"this is not the «image check» result file"* rather than a raw `KeyError`, and the older v1.32.0 bare format is still accepted; (2) **fixed the pale "white bar"** at the right of the toolbar in **actor library / director library / recently played / collections** — the root cause was a lazy-grid guard clause: those four pages never registered that they took over the toolbar, so the head container (holding a progress bar whose maximum was never set) stayed at Qt's default visible state and painted an empty trough; it is now hidden by default and actively collapsed when unsupervised; (3) **removed the never-implemented "show trailer on hover (reserved)"** switch from both the config defaults and the Appearance → content-cards list; (4) the **About dialog gained four hand-drawn vector contact icons** (GitHub / Bilibili / Weibo / e-mail) that open the author's pages with the system default app, sourced from a single `CONTACTS` list in `src/version.py`.
- **v1.32.0** (2026-09-24) — Four items: (1) **duplicate / image / actor check all gain a "normal algorithm + AI algorithm" choice**, plus a shared review base `src/aireview.py` and a "turbo mode" that only reviews uncertain items — and everything sent to the model is **redacted** (volume / duration / quality / slot only, never drive letters, directory names, codes or file names); (2) **19 interface languages** in Appearance → Interface language (dictionary + fallback: unknown strings return the original Chinese; applies instantly, no restart; Arabic translates text only, no layout mirroring); (3) both READMEs now embed **screenshots of every screen**, with privacy info irreversibly masked and a 肆月Aperture watermark; (4) the **About dialog was rewritten** to explain each of the nine modules, where data lives, whether it goes online, plus privacy and disclaimer notes.
- **v1.31.0** (2026-09-24) — Four items: (1) **withdrew** the v1.30.0 A–Z rail (a jump to `Z` had to build ~4,800 cards; the benefit never justified the cost) — `letter_index.py` and `people_letter_index()` stay, and "letter" remains a valid sort key; (2) the card's "三围" row now carries a **bold cup size** prefix (`L bust111·waist65·hip96`), parsed from the measurement string or a standalone `罩杯` key with **no guessing**, and the actor detail page matches; (3) new **Tools → Actor Check** (between Duplicate Detection and Image Check) — the normal/AI algorithm pair, the boilerplate-value filtering, the no-transitive-closure rule, the suggested-merge vs suspect split, and the manual actor editor with avatar upload are all described in the feature list above; real-library run: **0.17s / 5,909 people / 734 clusters / 48 suspects**, with every "same romaji, different person" pair correctly demoted to suspect; (4) **Tools navigation split into four groups** (Basic tools / Data optimization / Smart detection / Data analysis). Offscreen smoke `dev/smoke_v1310.py`: **110 PASS / 0 FAIL**. Three real defects were caught only while producing the preview images: a `_clear_layout()` that `takeAt()`-ed widgets without detaching them (stale placeholder text stayed painted on top of the new panel), a horizontal splitter that starved the *actionable* right pane down to its `minimumWidth` (QSplitter stretch only applies while neither side has hit its minimum), and an action row that sat below the fold of a scrolling detail pane, hiding the primary button. Details in the Chinese [README.md](./README.md#迭代记录).
- **v1.30.0** (2026-09-23) — Four items: (1) actor cards swap the redundant **bust** fact for the **work count** (3 rows, 160px, unchanged); (2) new **Tools → Manual Edit** (between Personalization and Portrait Overview) — search any indexed title, edit all **17 nfo fields** + cast + the three artwork slots, save back to nfo (with `.bak-<timestamp>`, same-name `<actor>` nodes reused so `<thumb>` avatars survive) and sync the index; (3) new **Tools → Image Check** (between Duplicate Detection and Data & Logs) — scans `-poster/-thumb/-fanart.jpg` for **missing / broken** files using **pure-Python structure checks** (Qt happily "reads" a truncated JPEG and fills the missing part grey; <1KB is suspicious), then upload a replacement per row; (4) an **A–Z rail** beside the scrollbar in the actor & director libraries that jumps to the first person under a letter. `query_people` / `count_people` / `people_letter_index` now share one `_people_clauses()` builder so the three can't drift apart. Also fixed a 59-second freeze: jumping to `Z` (row 4805 of 5909) had to build 4800 cards, each reading its avatar from the NAS synchronously (~5.7 ms cold); avatars are now loaded **on first paint** (invisible cards never hit the disk), the jump batch went 240 → 600, and the header shows real progress — **59s → 26s**. Offscreen smoke `dev/smoke_v1300.py`: **77 PASS / 0 FAIL**. *(The A–Z rail was withdrawn in v1.31.0.)*
- **v1.28.1** (2026-09-21) — Director cards drop the (always empty) "bio" row and shrink from 160px to 118px; actor & director libraries go from 5 to 6 cards per row.
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
