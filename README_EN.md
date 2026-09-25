# LumaCrate — v1.34.2 Iteration Record (to be merged into the root README)

> **Note:** this repository lives on the Z: drive (a UGREEN NAS UNC share) which **allows
> creating new files but rejects any modification of existing ones**. The root `README.md`
> is therefore still frozen at v1.28.1. This file is the paragraph that v1.34.2 should add
> at the **top of the "## 迭代记录 / Iteration Record" section**; the format matches the
> existing entries, so it can be copy-pasted as-is. The changed sources, smoke script and
> build log are staged alongside in this `_staging_v1342/` folder.

---

### v1.34.2 (Build 2609250050) — 2026-09-25

> Theme: **2 pieces of feedback — too much whitespace under the "统计范围 / Scope" group box / raise the "Top N" cap from 200 to 999 and make 999 actually work.**

- **Feedback 1 · Tighten the "Scope" group box and remove the whitespace below it**
  - **Symptom** (user screenshot, circled in red): in Tools → Smart Recommend → Vector Edit →
    "Auto-fill from portrait…", the **Scope** group box was noticeably taller than its content,
    leaving a large empty band below it.
  - **Root cause (found only after measuring every widget's geometry):** the cause was **neither**
    the group-box sizing **nor** `_fit_height()` — it was the hint line under "Scope": the
    `lb_scope_tip` `QLabel` had **`setWordWrap(True)`**. Once word-wrap is on, `QLabel.sizeHint`
    estimates its height for **multiple lines**, so `QFormLayout` stretched it to roughly **3 lines**:
    measured at **60 px** in v1.34.1 and still **45 px** in the first v1.34.2 build, while the text
    inside is only **one line (~17 px)**. That extra ~40 px showed up as the blank band below the box.
  - **Fix:**
    - `lb_scope_tip.setWordWrap(False)` — turn off wrapping so `sizeHint` returns the true single line;
    - `lb_scope_tip.setFixedHeight(fontMetrics().lineSpacing() + 3)` — then **pin it to exactly one line**,
      so `QFormLayout` can no longer stretch it; the three scope texts were already condensed to a
      single line in `_refresh_est`, so nothing gets clipped;
    - **truncate with an ellipsis** when a library name exceeds 12 chars, so it can't widen the panel;
    - pin both group boxes `g1` / `g2` to `SizePolicy(Preferred, Fixed)` (so the outer layout can't
      stretch them), tighten the inner margins to 10/8/10/8 and spacing to 6, and drop the trailing
      `addStretch` in `_build()`.
  - **Measured** (same offscreen render, same font, per-widget geometry):

    | Metric | v1.34.1 | v1.34.2 |
    | --- | --- | --- |
    | `lb_scope_tip` height | 60 px | **19 px** |
    | "Scope" group-box height | 145 px | **102 px (−43 / −30%)** |
    | Whole dialog height | 613 px | **570 px** |

  - The first build (2609250049) tried to hand-sum the height in `_content_height()`, which
    **badly under-estimated** it (101 px) and would have clipped content — abandoned. Reverting to
    Qt's own `sizeHint` and fixing **the label itself** was the real fix.

- **Feedback 2 · Raise the "Top N" cap from 200 to 999 and make 999 actually work**
  - **Symptom:** the "Top N" field could only take **two digits (max 99)** in practice (the third
    digit wouldn't go in); and even with a larger number the high-frequency lists written to the
    database **stopped at 30**.
  - **Root cause had two ends — both had to be fixed:**
    - **End 1 (the panel):** the SpinBox used `setSuffix(" 个")`; with the suffix "999 个" is wider
      than "999", and under the `SPIN_MAX_W` width cap the **third digit was swallowed**, so only
      2 digits fit. **Fix:** drop the `" 个"` suffix so "999" displays and accepts fully.
    - **End 2 (the data):** each high-frequency list in `insight.Portrait.build()` was hard-coded to
      `most_common(30)` (20 for publishers), so even with 999 typed in, **only 30 entries could be
      written**. **Fix:** raise `config.Settings.AUTOFILL_TOP_RANGE` from `(1, 200)` to `(1, 999)`,
      add a module-level `insight.PORTRAIT_TOP = AUTOFILL_TOP_RANGE[1]`, and align all five
      user-visible lists (tags / studios / series / actors / directors) to it (tags use `MAX_TAGS`,
      raised from 600 to 1200 for headroom). **Both ends share one source**, so changing the cap
      propagates automatically.

- **Verification:** the offscreen smoke test `dev/smoke_v1342.py` passed **17/17 assertions** —
  covering `AUTOFILL_TOP_RANGE == (1, 999)`, `PORTRAIT_TOP == 999`, `most_common(999)` truly
  returning 999 rows, `items[:999]` length 999, SpinBox `maximum == 999` with `suffix == ""`,
  the three-digit value displaying fully, "999" reaching `_plan()`, the "Scope" group box being
  `SizePolicy == Fixed` and no longer over-tall (≤ 140 px), and `lb_scope_tip` neither wrapping
  nor exceeding one line.

---

## Sources changed in this version

| File | Change summary |
| --- | --- |
| `src/config.py` | `AUTOFILL_TOP_RANGE`: `(1, 200)` → `(1, 999)` |
| `src/insight.py` | add `PORTRAIT_TOP = 999`; `MAX_TAGS` 600 → 1200; align 5 visible lists' `most_common` to `PORTRAIT_TOP` |
| `src/ui_settings.py` | `AutoFillDialog`: `_fit_height` uses `sizeHint`; `g1`/`g2` pinned Fixed; drop `addStretch`; remove the `sp_top` suffix; **`lb_scope_tip` no-wrap + fixed one-line height** (the real root cause of feedback 1) |
| `src/version.py` | `MINOR_ITER 1 → 2`; `BUILD_SEQ 0048 → 0050`; add 0049/0050 build notes |

## Artifact

- `流明盒-v1.34.2-2609250050.exe` (~48 MB single-file, `--onefile --windowed`)
- Copied to the repository root and to `history/` (the UNC share forbids deleting existing files,
  so the root keeps several historical exes 0047 / 0048 / 0049 / 0050 — 0048 and 0049 can be
  removed by hand).
