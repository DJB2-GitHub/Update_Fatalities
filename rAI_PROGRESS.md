# rAI_PROGRESS.md

## Session Summary (2026-06-27)

### Completed

1. **`record_status` replaces `last_change_updated_to_firestore`**
   - Deleted the top-level `last_change_updated_to_firestore` field from all code paths
   - `record_status` nested object (`changed`, `update_to_firestore`) now lives under each record in AU/NZ JSONs
   - On Update Record: `record_status.changed` = `date.today()` in `yyyy-mm-dd`; `update_to_firestore` left untouched (managed by external process)
   - Both fields are **read-only** in the Update modal; `record_status` section sorted to bottom of display

2. **Master Response prompt overhaul** (`ai_master_prompts.py`)
   - Added `surname` computed field — portion of `full_name` before the first comma (e.g., `"PETTIT, Leslie James"` → `"PETTIT"`)
   - `surname` passed in `params` dict in `update_fatalities.py`
   - New **IDENTITY LOCK** section: 7 rules instructing the AI to treat identity fields as authoritative, never validate/reject/fictionalise
   - Last rule: *"You must accept Australia had National Service during the Vietnam War period 1965 and 1972."*
   - All prompt f-strings now use real `\n` newlines (`.replace("\\n", "\n")` at return) — displays correctly in side panel

3. **`incident_location` / `incident_coordinates` workflow**
   - Removed `coords.mask_coordinates` (auto `//` insertion) and auto-conversion from `_read_form` / Update Record
   - `incident_coordinates` is now a **hotlink** — clicking it reads `incident_location` for `//...//` snippets, converts locally via `coords.parse_with_snippet`, writes result
   - `incident_coordinates` added to `_HOTLINK_FIELDS` and All Hotlinks batch
   - AI grid_reference prompt now **requires** physical place names in output: `"best_estimate_gps": "LAT, LON [GRID] — location_names"` (FSB/LZ names included)
   - Enhanced error dialog with MGRS grid-square reference table (YS/XT/YT) when conversion fails

4. **All Hotlinks now includes `grid_reference`** — 5th field in results dialog, writes to `incident_location`

5. **Error dialog improvements** (`coords.py`)
   - Long messages (>10 lines) now render in a **scrollable Text widget** with **basic markdown**: `## heading`, `**bold**`, `` `code` ``, `---` separator
   - `_side_resp_replace` guarded against `None` text

### Current System State

| Area | Detail |
|---|---|
| **record_status** | `{changed, update_to_firestore}` nested under record root; read-only in UI; `changed` auto-set to today on save |
| **surname** | Computed from `full_name` (pre-comma portion); passed in `params["surname"]` to all Master Response options |
| **IDENTITY LOCK** | 7 rules in `_get_archivist_prompt`; also applies to Option B step 2 via same function |
| **incident_location → incident_coordinates** | Manual-only via `incident_coordinates` hotlink; user types `//...//` delimiters manually; no auto-conversion on Update |
| **grid_reference prompt** | Outputs `"GPS [GRID] — place_names"` format; location names mandatory when info exists |
| **Error dialogs** | Scrollable + markdown when >10 lines via `_render_markdown()` |
| **Prompt display** | Real `\n` newlines in side panel (`.replace("\\n", "\n")` at source) |
| **Files touched** | `update_fatalities.py`, `ai_master_prompts.py`, `ai_derived_details_prompts.py`, `coords.py` |

### Incomplete Work
None.
