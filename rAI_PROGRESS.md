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

### Editable fields (non-derived_details)
- `service_status` — Combobox with country-specific valid statuses
- `unit` — text Entry
- `fatality_type` — text Entry *(made editable this session)*

### Enhanced Circumstances hotlink
- The `FATALITY_LOCATIONS` heading in the update modal is a **blue underlined clickable hotlink** with tooltip *"Click to research Enhanced Circumstances"*.
- Click is **unconditional** — does not depend on `_hotlink_active` (>50 words in ai_response). Always clickable when the section exists.
- Prompt is built **dynamically per-record** from `serviceRecordAuthority` fields (rank, full_name, service_number, unit, date_of_death, fatality_type). Not hardcoded to any one soldier.
- Result displays **only in the side panel RESPONSE** with header `AI: Enhanced circumstances [model] time cost`.
- **No popup dialog, no field mapping** — Enhanced Circumstances results are read-only research and never write back to any JSON field.

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
| `AI_MODEL_PROVIDERS` | Provider dropdown (hotlinks) |
| `AI_MASTER_WEB_PROMPT_URL` | JSON dict of provider → URL for Master Response web lookup |
| `AI_MASTER_MODEL_PROVIDER` | Master Response provider |
| `GEMINI_API_KEY` / `DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY` | Provider API keys |
| `SHOW_AI_MASTER_RESPONSE_COPY` | Char threshold for COPY RESPONSE button |
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

1. **FATALITY_LOCATIONS heading → clickable hotlink** — Section heading in the update modal is now a blue underlined hotlink with tooltip. Click builds a dynamic Enhanced Research Prompt from the current record and runs it through the AI side panel. See Architectural rules above for full behaviour.

2. **Three new methods added to `UpdateFatalities`**:
   - `_on_enhanced_circumstances_click()` — orchestrates prompt build, side-panel display, background AI call, and result rendering.
   - `_build_enhanced_circumstances_prompt()` — dynamically fills the Enhanced Research Prompt template with current record data (rank, full_name, service_number, unit, date_of_death).
   - `_show_enhanced_circumstances_result()` — displays result in side panel with full cost/model/time header. No popup dialog.

3. **fatality_type field now editable** — Added `field_name == "fatality_type"` to both `is_editable` guards (render path line ~1837, save path line ~2060). Previously greyed-out readonly; now writable and persisted on save.

4. **Response truncation fixed** — `_call_ai_for_field()` signature extended: `max_tokens: int = 8192`. Backward-compatible; all existing callers unchanged. Enhanced Circumstances caller passes `max_tokens=16384` so long research reports aren't cut off mid-sentence.

5. **Removed confirm/populate dialog for Enhanced Circumstances** — Deleted `_confirm_with_edit` popup and `_populate_field_value("enhanced_circumstances", ...)` mapping. Results are read-only research displayed in the side panel only.

---

## Completed — This Session (2026-07-03)

6. **Fatality-type hallucination guardrails** — All hotlink prompts hardened against combat fabrication for non-combat deaths:
   - `_SHARED_RULES` in `ai_derived_details_prompts.py`: added FATALITY_TYPE AUTHORITATIVE OVERRIDE with explicit non-combat guard language covering 79 unique types
   - `get_circumstances_of_death_prompt`: split into COMBAT/NON-COMBAT branches — non-combat no longer asks for "enemy contact", "operational environment", or "fatal wound"
   - `get_grid_reference_prompt`: split into COMBAT/NON-COMBAT branches — non-combat uses death/accident location directly, forbids fabricating grid references
   - `get_all_hotlinks_prompt`: fatality-aware language added to circumstances and grid_reference fields
   - `_build_enhanced_circumstances_prompt`: now receives `fatality_type` parameter; two-tier keyword classification; prominent ⚠ FATALITY TYPE (AUTHORITATIVE) block; conditional research components
   - `_on_enhanced_circumstances_click`: extracts `fatality_type` from `sra` and passes it downstream
   - Classification verified against all 79 unique `fatality_type` values in AU_fatalities.json; zero false combat classifications for accident/illness types

7. **rAI_PROGRESS.md updated** — Full session summary, architecture rules, and next-step checklist.

---

## Incomplete Work — Carry-Over

*None.* All changes from this session are complete, syntax-verified, and import-tested.

---

## Next Steps

- [ ] Test FATALITY_LOCATIONS hotlink with an **Accidental** record (e.g., MITCHELL, David AU_1201249): verify prompt contains ⚠ FATALITY TYPE (AUTHORITATIVE): Accidental ⚠, non-combat research components, NO combat language (FSB, war diary, enemy contact, booby trap)
- [ ] Test FATALITY_LOCATIONS hotlink with a **KIA** record: verify prompt contains combat research components (FSB context, operation name, war diary extracts)
- [ ] Test individual hotlink clicks (circumstances_of_death, grid_reference) on an Accidental record — verify results describe the accident factually without fabricated combat narratives
- [ ] Test "All Hotlinks" on an Accidental record — verify all five fields respect fatality_type
- [ ] Test Enhanced Circumstances with a long response — verify no mid-sentence truncation (16384 tokens)
- [ ] Test fatality_type edit: change the value, navigate away and back, confirm it persisted
- [ ] Test date display: verify `date_of_death` and `date_of_birth` show as `yyyy-Mmm-dd` in update modal
- [ ] Test NZ Master Prompt: open NZ_fatalities.json record → "AI: Create a Master Response" → confirm NZ sources, Online Cenotaph label
- [ ] Test AU Master Prompt: confirm regression — AU still shows AWM sources
- [ ] Test COPY RESPONSE variations (clean/dirty/cancel)
- [ ] Add `openrouter.log` to `.gitignore` if not already present
