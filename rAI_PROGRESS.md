# rAI_PROGRESS.md

## Session Summary (2026-06-28)

### Progress This Session

1. **Clean pickup** — Session opened from prior commit `9a11600`; no code changes pending.
2. **Pushed all changes to GitHub** — Commit `437fc4b`: rAI_PROGRESS.md, OpenRouter plugin payload, README docs, session.json, openrouter.log.
3. **OneDrive backup menu item** — Added "Backup Fatalities.json to folder for OneDrive sync" button to Main Menu (`main.py`).
4. **Backup logic** — `_backup_files()` method copies `AU_fatalities.json` and `NZ_fatalities.json` (sourced from `FATALITY_FILE_DIRECTORY` + `FILES_AVAILABLE_FOR_UPDATE`) to the directory in `.env` `BACKUP_FATALITIES_TO_ONEDRIVE_SYNC`, appending `_yyyymmdd_hhmmss` to filenames. Keeps only the 3 most recent backups per base filename; deletes older ones.
5. **.env / .env.example** — Added `BACKUP_FATALITIES_TO_ONEDRIVE_SYNC` variable to both files.

### Prior Session Recap (2026-06-27)

1. **record_status** — Replaced `last_change_updated_to_firestore`; nested `{changed, update_to_firestore}`; read-only in UI.
2. **IDENTITY LOCK** — 7 rules in Master Response prompt; AI must accept identity fields as authoritative.
3. **incident_coordinates hotlink** — Manual `//...//` delimiters; no auto-conversion on Update; MGRS error reference table.
4. **Grid reference** — Now included in All Hotlinks batch; outputs `GPS [GRID] — place_names` format.
5. **Error dialogs** — Scrollable + markdown rendering when >10 lines.
6. **Prompt display** — Real newlines in side panel via `.replace("\\n", "\n")`.
7. **surname** — Computed from `full_name` (pre-comma); passed in `params["surname"]`.

### Current System State

| Area | Detail |
|---|---|
| **record_status** | `{changed, update_to_firestore}` per record; `changed` auto-set on save; read-only in UI |
| **surname** | Computed from `full_name` (pre-comma); passed to all Master Response options via `params` |
| **IDENTITY LOCK** | 7 rules in `_get_archivist_prompt` / Option B step 2 |
| **incident_coordinates** | Manual hotlink from `incident_location`; user types `//...//`; no auto-conversion |
| **grid_reference** | 5th field in All Hotlinks; mandatory place names in output |
| **Error dialogs** | Scrollable + markdown via `_render_markdown()` in `coords.py` |
| **Prompt newlines** | Real `\n` via `.replace("\\n", "\n")` at return |
| **OneDrive backup** | Menu button in `main.py` `MainMenu._build()` → `_backup_files()`; copies AU/NZ JSONs to `BACKUP_FATALITIES_TO_ONEDRIVE_SYNC` with `_yyyymmdd_hhmmss`; prunes to 3 most recent per file |
| **Files touched** | `main.py`, `.env`, `.env.example` |

### Absolute Next-Step Checklist

- [ ] **Test backup menu item** — Click "Backup Fatalities.json to folder for OneDrive sync" from Main Menu; verify both files copied to OneDrive path with timestamp
- [ ] **Test backup pruning** — Run backup 4+ times; verify only 3 most recent `AU_fatalities_*.json` and 3 most recent `NZ_fatalities_*.json` remain
- [ ] **Test backup with missing .env var** — Temporarily remove `BACKUP_FATALITIES_TO_ONEDRIVE_SYNC`; verify error dialog
- [ ] **Test backup with missing source files** — Verify error dialog if source paths don't exist
- [ ] **Test record_status** — Save a record and verify `changed` field is today; verify both fields are read-only in Update modal
- [ ] **Test IDENTITY LOCK** — Run Master Response Option B (Step 1+2); confirm AI never rejects/replaces identity fields
- [ ] **Test incident_coordinates hotlink** — Click hotlink on a record with `//XXXX YYYY//` in `incident_location`; verify conversion
- [ ] **Test MGRS error dialog** — Feed a malformed grid reference; confirm scrollable markdown dialog with reference table appears
- [ ] **Test All Hotlinks** — Run batch; confirm `grid_reference` is the 5th field and writes to `incident_location`
- [ ] **Run full smoke test** — Load app, navigate records, run a full Master Response cycle, verify no regressions

### Incomplete / Carry-Over Work
None. All session work completed. Last commit: `437fc4b`.
