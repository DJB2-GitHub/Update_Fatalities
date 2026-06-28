# rAI_PROGRESS.md

## Session Summary (2026-06-28)

### Progress This Session
- No code changes were made in this session.
- Session opened as a clean pickup from the previous session (2026-06-27).
- Previous session's work (see below) was reviewed and confirmed stable.

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
| **Files touched** | `update_fatalities.py`, `ai_master_prompts.py`, `ai_derived_details_prompts.py`, `coords.py` |

### Absolute Next-Step Checklist

- [ ] **Test record_status** — Save a record and verify `changed` field is today; verify both fields are read-only in Update modal
- [ ] **Test IDENTITY LOCK** — Run Master Response Option B (Step 1+2); confirm AI never rejects/replaces identity fields
- [ ] **Test incident_coordinates hotlink** — Click hotlink on a record with `//XXXX YYYY//` in `incident_location`; verify conversion
- [ ] **Test MGRS error dialog** — Feed a malformed grid reference; confirm scrollable markdown dialog with reference table appears
- [ ] **Test All Hotlinks** — Run batch; confirm `grid_reference` is the 5th field and writes to `incident_location`
- [ ] **Test prompt display** — Expand side panel; confirm prompts show real newlines not literal `\n`
- [ ] **Run full smoke test** — Load app, navigate records, run a full Master Response cycle, verify no regressions

### Incomplete / Carry-Over Work
None. All previous-session work was completed and committed (`9a11600`).
