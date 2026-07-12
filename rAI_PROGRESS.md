# rAI_PROGRESS — Fatalities Editor

## Session Progress — 2026-07-10

- Added **"Maintenance" menu button** to MainMenu, positioned under the Update dataset buttons
  with its own separator.
- Created **`MaintenanceModal`** (tk.Toplevel) — red header, field selector dropdown,
  AU_Correct_Vietnamese / NZ_Correct_Vietnamese action buttons, and Close.
- Created **`correct_vietnamese_names.json`** lookup file — 9 ASCII→Vietnamese name mappings
  (phuoc tuy→Phước Tuy, long hai→Long Hải, vung tau→Vũng Tàu, etc.).
- Implemented **batch correction logic** in `_correct_vietnamese_names`:
  scans the selected field (AU or NZ JSON), previews 10 records at a time with
  service number + before/after text, saves after each batch.
  Three choices per batch: Update These / Skip Batch / Cancel All.
- Added optional **`width` parameter** to `StyledDialog` (default 50 → batch preview uses 90).
- Added **field selector dropdown** ("Field to update:") with 3 options:
  death_location | incident_location | circumstances_of_death.
  Defaults to death_location, **persisted in session.json** under key `"maintenance_field"`.
- Made correction logic **dynamic** via `FIELD_PATHS` class variable — maps field name to
  nested JSON path. No hardcoded field access remains.

## Session Progress — 2026-07-12 (Earlier)

- Increased **`BATCH_SIZE`** in `_correct_vietnamese_names` from **20 → 500** records per batch
  (`main.py` line 512). Also updated the docstring (line 508) to reflect the new size.

## Session Progress — 2026-07-12 (Current Session)

- **Firestore Migration**: Migrated the core data source from local JSON files to a live Firebase Firestore database (`djb-onthisday`). Added `firebase-admin` to dependencies.
- **Data Load Refactor**: Updated `coords._load_json` to stream from Firestore. Collections are mapped based on the filename: `AU` maps to `/countries/AU/wars/vietnam/honor_roll` and `NZ` maps to `/countries/NZ/wars/vietnam/honor_roll`. Data is sorted by `referenceID` before being returned to ensure a stable display in the UI.
- **Data Save Refactor**: Updated `coords._save_json` to utilize Firestore Batch Writes (chunked by 500). Write operations use `{ "merge": True }` to preserve unmapped fields.
- **Authentication**: Configured the app to use a Service Account Key (`firebase-key.json` located in the project root) since `gcloud` ADC was not available.
- **UI & Bug Fixes**:
  - Removed the legacy `os.path.exists()` check in `main.py` that was blocking the editor from opening.
  - Dynamically renamed the dataset labels in `main.py` to "Update AU_Fatalities (Honor_Roll)" and "Update NZ_Fatalities (Honor_Roll)".
  - Refactored `_backup_files` in `main.py` to pull the latest data directly from Firestore and dump it to JSON in the OneDrive sync directory, restoring backup functionality.

## Session Progress — 2026-07-12 (Late Session)

- **Removed Maintenance Menu**: Deleted `MaintenanceModal` class, Maintenance button + separators, and `_open_maintenance_modal` method from `main.py`. The batch Vietnamese correction UI is gone.
- **Auto Vietnamese Name Correction on Save**: Extracted the regex-based Vietnamese name correction from the old `MaintenanceModal._correct_vietnamese_names` into standalone module-level functions in `update_fatalities.py`:
  - `_apply_vietnamese_correction(text)` — lazy-loads `correct_vietnamese_names.json` once (cached), applies case-insensitive word-boundary regex substitution.
  - `_correct_record_vietnamese(record)` — traverses `derived_details.fatality_locations.death_location`, `derived_details.fatality_locations.incident_location`, and `derived_details.circumstances_of_death`, applying corrections silently.
  - Wired into `_update_record()` — runs after `_read_form()` succeeds, before user confirmation dialog. No UI, no preview, no dialogs.
- **Backup Button UX**:
  - Renamed: "Backup Fatalities.json to folder for OneDrive sync" → "Backup Firestore Fatalities to folder for OneDrive sync".
  - Disabled state: label grays to `TEXT_MUTED`, text changes to "Backing up...", click unbound.
  - Re-enabled via `try/finally` wrapping the backup body in a nested `_do_backup()` function — covers all exit paths (early returns, errors, success).
- **Window Titles**: Default title format changed from "Update AU_fatalities.json" → "Update AU_fatalities [Firestore]" (strips `.json` extension and appends `[Firestore]`). Applied in `update_fatalities._build_ui`.
- **Main Menu Labels**: "AU_Fatalities (Honor_Roll)" → "AU_Fatalities (Firestore->Honor_Roll)". Same for NZ.
- **README.md Updates**: App description, prerequisites (`firebase-admin`, `firebase-key.json`), env vars, architecture (`coords.py` Firestore role), and state management all now reflect Firestore as the live data source.

## Current System State

*(Preserved from previous sessions)*

- **Anti-hallucination rule (CRITICAL)**: Every factual claim MUST include a working URL
  from an authoritative source (AWM, DVA, VWMA, NAA, Trove).
- **Indian 1960 datum**: Tag MGRS with `I60:`, `INDIAN1960:`, or `INDIAN:` → EPSG:3148/3149.
- **Default MGRS**: Untagged uses legacy SVN60 shift (+205m E, +75m N).
- **Key files**: `update_fatalities.py`, `ai_derived_details_prompts.py`,
  `ai_master_prompts.py`, `coords.py`, `main.py`.
- **Dependencies**: `mgrs`, `pyproj`, `firebase-admin`.

*(Updated this session)*

- **Data Persistence Architecture**: 
  - **Source of Truth**: Firestore (`djb-onthisday` project).
  - **Auth**: Service Account Key (`firebase-key.json`).
  - **AU Path**: `/countries/AU/wars/vietnam/honor_roll`
  - **NZ Path**: `/countries/NZ/wars/vietnam/honor_roll`
  - **Batching Rule**: Writes are chunked into db.batch() max 500 size arrays.
  - **Merge Rule**: All sets must use `merge=True`.
- **Vietnamese Name Correction**: 
  - **Lookup**: `correct_vietnamese_names.json` in workspace root — 20 entries.
  - **Applied fields**: `death_location`, `incident_location`, `circumstances_of_death`.
  - **Execution**: Silent, on every record save, before Firestore write. No UI.
  - **Location**: Module-level in `update_fatalities.py` (`_apply_vietnamese_correction`, `_correct_record_vietnamese`).
  - **Field paths**: `derived_details.fatality_locations.death_location`, `derived_details.fatality_locations.incident_location`, `derived_details.circumstances_of_death`.
- **Backup button**: "Backup Firestore Fatalities to folder for OneDrive sync" — disabled (grayed, "Backing up...") during backup; re-enabled via try/finally.

## Next Steps

- Test the application to ensure data edits correctly merge back into the live Firestore.
- Add more entries to `correct_vietnamese_names.json` as additional incorrect names are discovered.
- (Optional) Remove the old local `.json` arrays (e.g. `AU_fatalities.json`) from the project if they are no longer required for other fallback systems.

## Incomplete Work

None.
