# rAI Progress Report

## Current System State

### Architecture
- **Master Response pipeline**: Bypassed — prompt generated & displayed in side panel for manual Gemini browser execution. No API call made.
- **Date format**: JSON storage is ISO 8601 (`yyyy-mm-dd`). Display and prompt insertion use `_format_date_display()` → `yyyy-Mmm-dd` (e.g., `1967-March-29`). Applied to `date_of_death`, `date_of_birth` in UI, and `dod` in Master Prompt.
- **Country-aware prompts**: `ai_master_prompts.py` gates primary sources, authoritative identification labels, citation abbreviations, and home-country text on `country_code` (`AU` vs `NZ`).
- **`is_live_search`**: Hardcoded `True`. Affects prompt text only (live-search instructions + source lists). Google Search grounding tool injection exists in the API path but is never reached in the current clipboard workflow.
- **COPY RESPONSE**: `_copy_response_to_ai_response()` checks `_record_dirty`. Clean → copies + auto-saves via `_update_record()`. Dirty → Yes/No/Cancel dialog.
- **Master Web Provider dropdown**: Combobox (Google/Microsoft/DeepSeek) + clickable URL hotlink. Persisted in session state.
- **JSON parsing**: `_robust_json_parse()` — two-strategy parser: strict `json.loads` then regex key-value extraction for malformed AI output (extra text after string values, missing braces, etc.).
- **GPS prompt rule**: `grid_reference` targets the **fatal incident location** (wounding/action site), NOT the hospital/aid station where death occurred. Applied in both individual hotlink and "All Hotlinks" prompts.
- **Hotlink API**: timeout 60s (was 15s); Gemini `maxOutputTokens` 8192 (was 1024); DeepSeek `max_tokens` 8192 (was unset). `_call_ai_for_field()` now accepts optional `max_tokens` param (default 8192) — Enhanced Circumstances passes 16384.
- **Side panel width**: 750px (was 500px).

### Editable fields (non-derived_details)
- `service_status` — Combobox with country-specific valid statuses
- `unit` — text Entry
- `fatality_type` — text Entry

### Enhanced operation details hotlink
- The **DERIVED_DETAILS** heading is normal red text. Next to it is a **blue underlined label "Enhanced operation details"** with tooltip *"Click to research Enhanced Circumstances"*.
- Click is **unconditional** — always clickable when the DERIVED_DETAILS section exists.
- Prompt is built **dynamically per-record** from `serviceRecordAuthority` fields (rank, full_name, service_number, unit, date_of_death, fatality_type). Not hardcoded to any one soldier.
- Result displays in the side panel RESPONSE with header `Enhanced operation details [model] time cost`.
- **COPY RESPONSE: to enhanced_operation_details** button appears when the header starts with "Enhanced operation details" AND response text exceeds `SHOW_AI_MASTER_RESPONSE_COPY` threshold (default 200 chars from `.env`).
- Clicking COPY RESPONSE copies the side panel text into `derived_details → enhanced_operation_details`. Same dirty/clean record handling as the ai_response COPY RESPONSE button.
- `enhanced_operation_details` field renders as an 8-line text area with vertical scrollbar, selectable, and editable (same as `ai_response`).

### COPY RESPONSE buttons (two)
- **COPY RESPONSE: to ai_response** — green (`#2e7d32`). Shows when side panel label starts with "RESPONSE: MASTER" and text > `SHOW_AI_MASTER_RESPONSE_COPY`.
- **COPY RESPONSE: to enhanced_operation_details** — blue (`#1565c0`). Shows when side panel label starts with "Enhanced operation details" and text > `SHOW_AI_MASTER_RESPONSE_COPY`.
- Both use `self._copy_threshold` (read from `.env` `SHOW_AI_MASTER_RESPONSE_COPY`, default 200).

### Fatality-Type Authority Rule (2026-07-03)
- `fatality_type` is **AUTHORITATIVE** across all hotlink prompts. It gates whether combat or non-combat research instructions are used.
- **Two-tier classification** in `_build_enhanced_circumstances_prompt()`:
  - Combat keywords checked first (KIA, DOW, Booby trap, Land mine, Enemy grenade, etc.)
  - Non-combat fallback (Accident, Illness, Motor Vehicle, Homicide, Drowning, etc.)
  - `accident*` prefix guard: any fatality_type starting with "accident" is forced non-combat regardless of embedded combat keywords (e.g., "Accidental- shot by a sentry... He died of wounds..." is friendly fire, not enemy action)
- **~395 combat** / **~122 non-combat** / **~10 unknown** (GSW, Gunshot wound, Injuries, Wounds — genuinely ambiguous) across 79 unique types in AU_fatalities.json
- **Enhanced Circumstances prompt** now receives `fatality_type` explicitly. Non-combat deaths get accident/illness investigation instructions; combat deaths get full operational/military research instructions.
- **Field-level hotlinks** (`get_circumstances_of_death_prompt`, `get_grid_reference_prompt`, `get_all_hotlinks_prompt`) now include fatality-aware conditional instructions. `_SHARED_RULES` includes a FATALITY_TYPE AUTHORITATIVE OVERRIDE that applies to all field extractions.
- **Rule**: If fatality_type indicates NON-COMBAT, the prompt explicitly says: "DO NOT fabricate combat scenarios, enemy contact, booby traps, ambushes, operations, or battle narratives."

### Key env vars
| Variable | Purpose |
|---|---|
| `SHOW_AI_MASTER_RESPONSE_COPY` | Char threshold for COPY RESPONSE buttons (both ai_response and enhanced_operation_details) |
| `AI_MODEL_PROVIDERS` | Provider dropdown (hotlinks) |
| `AI_MASTER_WEB_PROMPT_URL` | JSON dict of provider → URL for Master Response web lookup |
| `AI_MASTER_MODEL_PROVIDER` | Master Response provider |
| `GEMINI_API_KEY` / `DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY` | Provider API keys |
| `AU_SERVICE_STATUSES` / `NZ_SERVICE_STATUSES` | Valid service statuses per country |

### NZ-specific sources (Live Search prompt)
- Auckland War Memorial Museum — Online Cenotaph (aucklandmuseum.com)
- New Zealand History (nzhistory.govt.nz)
- Archives New Zealand (archives.govt.nz)
- Vietnam War New Zealand (vietnamwar.govt.nz)
- Papers Past, NZ Herald
- Published unit histories and RNZIR/NZ Artillery records

### AU-specific sources (unchanged)
- AWM, VWMA, DVA, NAA, Trove, The Age, Sydney Morning Herald, unit histories, AATTV

---

## Completed — Prior Session (committed: `eec0e64`)

1. **Date display formatting** — `_format_date_display()` added to `update_fatalities.py` and `ai_master_prompts.py`. Converts `yyyy-mm-dd` → `yyyy-Mmm-dd` for display and Master Prompt. JSON storage stays ISO 8601.
2. **NZ country-aware Master Prompt** — Sources, auth label, cite refs, and home-country text all gated on `country_code`. Both `is_live_search` branches covered.
3. **COPY RESPONSE auto-save** — Clean record: copies response + executes `_update_record()` immediately. Dirty record: Yes/No/Cancel dialog.
4. **TEST_PROMPT.txt** — Full prompt template saved to workspace root for testing.
5. **All Hotlinks JSON parse fix** — `_robust_json_parse()` created with two-strategy recovery (strict `json.loads` → regex key-value extraction). Replaced naive 7-line block in `_all_hotlinks()`. Handles common AI mistakes like extra text after string values.
6. **API hardening** — timeout 15→60s; DeepSeek `max_tokens` added (8192); Gemini `maxOutputTokens` 1024→8192 (root cause of All Hotlinks truncation).
7. **GPS prompt corrected** — Individual and "All Hotlinks" `grid_reference` prompts now target *incident location* (wounding/action site), not place of death. Prevents AI from returning hospital coordinates when the soldier died at an aid station.
8. **Prev/Next button UX** — `_set_locked()` now sets `cursor="arrow"` + muted `fg` when locked, `cursor="hand2"` + dark `fg` when unlocked. Buttons restore correct state after navigation.

---

## Completed — This Session (2026-07-01)

1. **FATALITY_LOCATIONS heading → clickable hotlink** — Section heading in the update modal is now a blue underlined hotlink with tooltip. Click builds a dynamic Enhanced Research Prompt from the current record and runs it through the AI side panel.

2. **Three new methods added to `UpdateFatalities`**:
   - `_on_enhanced_circumstances_click()` — orchestrates prompt build, side-panel display, background AI call, and result rendering.
   - `_build_enhanced_circumstances_prompt()` — dynamically fills the Enhanced Research Prompt template with current record data.
   - `_show_enhanced_circumstances_result()` — displays result in side panel with full cost/model/time header. No popup dialog.

3. **fatality_type field now editable** — Added `field_name == "fatality_type"` to both `is_editable` guards. Previously greyed-out readonly; now writable and persisted on save.

4. **Response truncation fixed** — `_call_ai_for_field()` signature extended: `max_tokens: int = 8192`. Backward-compatible; Enhanced Circumstances passes `max_tokens=16384`.

5. **Removed confirm/populate dialog for Enhanced Circumstances** — Deleted `_confirm_with_edit` popup and field mapping. Results are read-only research in side panel only.

---

## Completed — This Session (2026-07-03)

6. **Fatality-type hallucination guardrails** — All hotlink prompts hardened against combat fabrication for non-combat deaths:
   - `_SHARED_RULES`: added FATALITY_TYPE AUTHORITATIVE OVERRIDE covering 79 unique types
   - `get_circumstances_of_death_prompt`: COMBAT/NON-COMBAT branches
   - `get_grid_reference_prompt`: COMBAT/NON-COMBAT branches
   - `get_all_hotlinks_prompt`: fatality-aware circumstances + grid_reference
   - `_build_enhanced_circumstances_prompt`: receives `fatality_type`; two-tier keyword classification; ⚠ FATALITY TYPE (AUTHORITATIVE) block; conditional research components
   - `_on_enhanced_circumstances_click`: extracts and passes `fatality_type`
   - Verified against all 79 unique `fatality_type` values in AU_fatalities.json

7. **Hotlink moved to DERIVED_DETAILS** — Enhanced Circumstances hotlink moved from `FATALITY_LOCATIONS` heading to `DERIVED_DETAILS`. Heading is now normal red text with a blue "Enhanced operation details" label next to it as the clickable hotlink.

8. **Side panel header renamed** — All "AI: Enhanced circumstances" headers changed to "Enhanced operation details".

9. **COPY RESPONSE: to enhanced_operation_details** — New blue button appears when Enhanced operation details result is shown. Copies side panel text to `derived_details → enhanced_operation_details` with same dirty/clean handling as the existing ai_response COPY RESPONSE.

10. **COPY RESPONSE button labels** — Both buttons renamed: "COPY RESPONSE: to ai_response" and "COPY RESPONSE: to enhanced_operation_details" (removed "AI: " prefix).

11. **COPY RESPONSE threshold gating** — Both buttons now only appear when response text exceeds `SHOW_AI_MASTER_RESPONSE_COPY` threshold (default 200 chars, from `.env`).

12. **enhanced_operation_details field** — Renders as 8-line text area with vertical scrollbar, selectable, editable — identical to `ai_response`. Added to the multi-line text widget condition tuple.

13. **Side panel width** — Increased from 500px to 750px (50% wider).

14. **rAI_PROGRESS.md updated** — This file.

---

## Incomplete Work — Carry-Over

*None.* All changes from this session are complete, syntax-verified, and import-tested.

---

## Next Steps

- [ ] Test "Enhanced operation details" hotlink with **Accidental** record (e.g., MITCHELL, David AU_1201249): verify ⚠ FATALITY TYPE (AUTHORITATIVE) block, non-combat components, NO combat language
- [ ] Test "Enhanced operation details" hotlink with **KIA** record: verify combat research components
- [ ] Test COPY RESPONSE: to enhanced_operation_details — click, verify text copies to field, verify dirty/clean dialog
- [ ] Test COPY RESPONSE: to ai_response — verify still works as before
- [ ] Test both COPY RESPONSE buttons only appear when response > SHOW_AI_MASTER_RESPONSE_COPY threshold
- [ ] Test enhanced_operation_details field: verify 8-line text area, scrollbar, editable
- [ ] Test individual hotlink clicks (circumstances_of_death, grid_reference) on Accidental record
- [ ] Test "All Hotlinks" on Accidental record
- [ ] Test Enhanced Circumstances with long response — verify no mid-sentence truncation (16384 tokens)
- [ ] Test fatality_type edit: change, navigate away and back, confirm persisted
- [ ] Test date display: `date_of_death` and `date_of_birth` as `yyyy-Mmm-dd`
- [ ] Test NZ Master Prompt: NZ_fatalities.json → confirm NZ sources
- [ ] Test AU Master Prompt: confirm regression
- [ ] Add `openrouter.log` to `.gitignore` if not already present
