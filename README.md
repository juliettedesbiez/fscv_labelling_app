# Labelling_App.py

Interactive tool for labelling FSCV voltammetry colour plots. Click-drag to select a time region on the colour plot, then
press a number key to assign a label to that region. Saves to CSV after
every action.

This is the same tool used for both the **binary** and **3-class**
pipelines — which labels you use depends on which pipeline you're feeding.

---

## 1. What needs changing before you run it

Paths are hardcoded at the top of the file — no command-line arguments.

```python
PLOT_DIR   = r"...\bettina and juj organoid data for cohens"           # folder of raw recording files to label
OUTPUT_CSV = r"...\bettina and juj organoid output for cohens\FSCV_labels_organoid_bettina.csv"   # where labels get saved
BACKUP_DIR = r"...\bettina and juj organoid output for cohens\label_backups"   # timestamped backup on each launch
FSCV_HZ    = 10                                                        # sampling rate, must match your recordings
```

`OUTPUT_CSV` is what `make_windows_XXX.py` (or `make_windows_3class.py`,
if labelling for 3-class) reads as `LABELS_CSV` downstream — make sure the
two paths point at the same file.

---

## 2. Labels — which ones to use for which pipeline

| Key | Label | Colour | Use for binary? | Use for 3-class? |
|---|---|---|---|---|
| `0` | No Event (baseline) | blue | ✅ | ✅ |
| `1` | Spontaneous | green | ✅ | ✅ |
| `2` | Stimulated | red | ❌ never | ✅ |
| `3` | Uncertain | orange | ✅ (excluded downstream) | ✅ (excluded downstream) |

- **Binary pipeline:** only ever use `0`, `1`, and `3`. Never press
  `2` — the "Spontaneous" class will be read as "Serotonin/Event"; `make_windows_XXX.py` will silently drop any
  window labelled `2` if it does slip in.
- **`3` (Uncertain) is always excluded** from window generation in both
  pipelines — it's there so you can flag ambiguous regions without forcing
  a decision, and both `make_windows_XXX.py` and `make_windows_3class.py`
  filter it out before building `windows_metadata.csv`.

---

## 3. Controls

| Key/action | Effect |
|---|---|
| Click + drag | Select a time region |
| `0` / `1` / `2` / `3` | Label the current selection (or the whole file, if nothing selected) |
| `←` / `→` | Previous / next file |
| `X` | Enter delete mode, then press `1`–`9` to delete that specific label |
| `D` | Delete **all** labels for the current file |
| `B` | Toggle background subtraction on the colour plot |
| `J` | Jump to a specific file (by number, name search, or `m:` for master index) |
| `Q` / `Esc` | Quit |

Labelling (or deleting) autosaves to `OUTPUT_CSV` immediately — no separate save step.

---

## 4. Running it

```bash
python Labelling_App.py
```

On launch you'll see a status line and a mode menu:

```
FSCV Labeler | 143 files | 87 labeled | 56 unlabeled

[Enter]=All [0/1/2/3]=Review label [u]=Unlabeled [m]=Multiple
Mode:
```

- **Enter** — go through every file, in order.
- **`0`/`1`/`2`/`3`** — review mode: only show files that already contain at
  least one label of that type. Useful for double-checking a specific class.
- **`u`** — only show files with no labels yet.
- **`m`** — only show files that have more than one label entry (multi-event
  recordings).

You'll then be asked where to start (defaults to the first unlabelled file
in the current view).

---

## 5. Output format

`OUTPUT_CSV` has one row per labelled region:

```
index, plot_file, start_time, end_time, label, comment
```

- `index` — 1-based position of that file in the **full** file list (not the filtered view).
- `start_time` / `end_time` — in seconds.
- `label` — 0/1/2/3 per the table above.
- `comment` — currently unused by the UI (always blank), but the column exists for manual annotation if needed.

A file with no labelled regions simply has no rows in the CSV — it's what
`unlabeled` mode checks for.

---

## 6. Backups

Every time you launch the app, if `OUTPUT_CSV` already exists, it's copied
to `BACKUP_DIR` with a timestamp (`backup_YYYYMMDD_HHMMSS.csv`) before
anything else happens. Nothing is ever overwritten without a backup first —
safe to experiment with delete/re-label without worrying about losing prior
work.
