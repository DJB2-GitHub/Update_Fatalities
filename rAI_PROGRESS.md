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

## Current System State

*(Preserved from previous session)*

- **Anti-hallucination rule (CRITICAL)**: Every factual claim MUST include a working URL
  from an authoritative source (AWM, DVA, VWMA, NAA, Trove).
- **Indian 1960 datum**: Tag MGRS with `I60:`, `INDIAN1960:`, or `INDIAN:` → EPSG:3148/3149.
- **Default MGRS**: Untagged uses legacy SVN60 shift (+205m E, +75m N).
- **Key files**: `update_fatalities.py`, `ai_derived_details_prompts.py`,
  `ai_master_prompts.py`, `coords.py`, `main.py`.
- **Dependencies**: `mgrs`, `pyproj`.

*(New this session)*

- **Maintenance FIELD_PATHS**:
  `death_location` → `derived_details.fatality_locations.death_location`,
  `incident_location` → `derived_details.fatality_locations.incident_location`,
  `circumstances_of_death` → `derived_details.circumstances_of_death`.
- **Session persistence**: `maintenance_field` saved to `session.json` — loaded on modal
  open, written on every dropdown change.
- **Vietnamese name lookup**: `correct_vietnamese_names.json` in workspace root — shared
  by both AU and NZ correction routines.
- **Batch size**: 10 records per batch, hardcoded as `BATCH_SIZE` in `_correct_vietnamese_names`.

## Next Steps

- Add more entries to `correct_vietnamese_names.json` as additional incorrect names
  are discovered in the data.

## Incomplete Work

None — all stubs are implemented. Both AU_Correct_Vietnamese and NZ_Correct_Vietnamese
are fully functional with batch preview, session-persisted field selection,
and dynamic field-path resolution.
