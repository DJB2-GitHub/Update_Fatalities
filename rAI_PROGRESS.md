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

### Hotlink source priority
- When `enhanced_operation_details` has > `SHOW_AI_MASTER_RESPONSE_COPY` chars (default 200), it replaces `ai_response` as the primary source for field hotlinks and All Hotlinks.
- `authoritative_ai_override` is always preserved and prepended to the combined text.
- Instance variables: `self._hotlink_source_label` (str), `self._hotlink_has_override` (bool) — set during `_hotlink_combined_text` build.

### Enhanced operation details hotlink
- The **DERIVED_DETAILS** heading is normal red text. Next to it is a **blue underlined label "Enhanced operation details"** with tooltip *"Click to research Enhanced Circumstances"*.
- Click is **unconditional** — always clickable when the DERIVED_DETAILS section exists.
- Prompt is built **dynamically per-record** from `serviceRecordAuthority` fields (rank, full_name, service_number, unit, date_of_death, fatality_type).
- Result displays in the side panel RESPONSE with clean header `Enhanced operation details`. Metadata `[model]  time  cost` prepended as first line of response text.
- **--> enhanced_operation_details** button (blue `#1565c0`) appears when header starts with "Enhanced operation details" AND text > `SHOW_AI_MASTER_RESPONSE_COPY`.
- `enhanced_operation_details` field renders as an 8-line text area with vertical scrollbar, selectable, editable.

### COPY RESPONSE buttons (two)
- **--> ai_response** — green (`#2e7d32`). Shows when side panel label starts with "RESPONSE: FATALITIES MASTER PROMPT" and text > `SHOW_AI_MASTER_RESPONSE_COPY`.
- **--> enhanced_operation_details** — blue (`#1565c0`). Shows when side panel label starts with "Enhanced operation details" and text > `SHOW_AI_MASTER_RESPONSE_COPY`.
- Both use `self._copy_threshold` (read from `.env` `SHOW_AI_MASTER_RESPONSE_COPY`, default 200).

### Response headers (clean)
- Field hotlinks: `RESPONSE: {field_name}` (e.g., `RESPONSE: death_location`)
- All Hotlinks: `RESPONSE: All Hotlinks`
- Enhanced operation details: `Enhanced operation details`
- Fatalities Master Prompt: `RESPONSE: FATALITIES MASTER PROMPT`
- Metadata (model, time, cost, source) is **prepended as first line** of the response text, never in the header label.
- Metadata is **stripped** from the Accept/Cancel dialog — only field value shown.

### Deriving status messages
- Single hotlink: `AI: {field_name} Deriving… From {source} data` + ` + override` if applicable
- All Hotlinks: `AI: All Hotlinks Deriving… From {source} data` + ` + override`
- Enhanced operation details: `Enhanced operation details Deriving…`
- Retry/progress: `Deriving … From {source} data (querying {model})`

### Fatality-Type Authority Rule (2026-07-03)
- `fatality_type` is **AUTHORITATIVE** across all hotlink prompts. It gates whether combat or non-combat research instructions are used.
- **Two-tier classification** in `_build_enhanced_circumstances_prompt()`:
  - Combat keywords checked first (KIA, DOW, Booby trap, Land mine, Enemy grenade, etc.)
  - Non-combat fallback (Accident, Illness, Motor Vehicle, Homicide, Drowning, etc.)
  - `accident*` prefix guard: any fatality_type starting with "accident" is forced non-combat regardless of embedded combat keywords
- **~395 combat** / **~122 non-combat** / **~10 unknown** across 79 unique types in AU_fatalities.json
- **Rule**: If fatality_type indicates NON-COMBAT, the prompt says: "DO NOT fabricate combat scenarios, enemy contact, booby traps, ambushes, operations, or battle narratives."

### Key env vars
| Variable | Purpose |
|---|---|
| `SHOW_AI_MASTER_RESPONSE_COPY` | Char threshold for COPY RESPONSE buttons and enhanced_operation_details source gating |
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

1. **Date display formatting** — `_format_date_display()` added. Converts `yyyy-mm-dd` → `yyyy-Mmm-dd` for display and Master Prompt.
2. **NZ country-aware Master Prompt** — Sources, auth label, cite refs, and home-country text all gated on `country_code`.
3. **COPY RESPONSE auto-save** — Clean record: copies + auto-saves. Dirty record: Yes/No/Cancel.
4. **All Hotlinks JSON parse fix** — `_robust_json_parse()` with two-strategy recovery.
5. **API hardening** — timeout 15→60s; DeepSeek `max_tokens` added (8192); Gemini `maxOutputTokens` 1024→8192.
6. **GPS prompt corrected** — `grid_reference` targets incident location (wounding/action site), not place of death.
7. **Prev/Next button UX** — Cursor and color state restored correctly after navigation.

---

## Completed — This Session (2026-07-01)

1. **FATALITY_LOCATIONS heading → clickable hotlink** — Dynamic Enhanced Research Prompt from current record.
2. **Three new methods**: `_on_enhanced_circumstances_click`, `_build_enhanced_circumstances_prompt`, `_show_enhanced_circumstances_result`.
3. **fatality_type field now editable**.
4. **Response truncation fixed** — `max_tokens` param; Enhanced Circumstances passes 16384.
5. **Removed confirm/populate dialog for Enhanced Circumstances**.

---

## Completed — This Session (2026-07-03)

6. **Fatality-type hallucination guardrails** — `_SHARED_RULES`, `get_circumstances_of_death_prompt`, `get_grid_reference_prompt`, `get_all_hotlinks_prompt`, `_build_enhanced_circumstances_prompt`. Verified against 79 unique types.
7. **Hotlink moved to DERIVED_DETAILS** — Blue "Enhanced operation details" label next to red DERIVED_DETAILS heading.
8. **Side panel header renamed** — "AI: Enhanced circumstances" → "Enhanced operation details".
9. **COPY RESPONSE: to enhanced_operation_details** — Blue button, same dirty/clean handling.
10. **COPY RESPONSE button labels** — "COPY RESPONSE: to ai_response" / "COPY RESPONSE: to enhanced_operation_details".
11. **COPY RESPONSE threshold gating** — Both buttons gated on `SHOW_AI_MASTER_RESPONSE_COPY`.
12. **enhanced_operation_details field** — 8-line text area + scrollbar, editable.
13. **Side panel width** — 500px → 750px.
14. **rAI_PROGRESS.md updated**.

---

## Completed — This Session (2026-07-04)

15. **Button rename** — "AI: Create a Master Response" → "Show Master Prompt".

16. **Side panel labels renamed** — "PROMPT: Master Response" → "PROMPT: Fatalities Master Prompt"; "RESPONSE: MASTER" → "RESPONSE: FATALITIES MASTER PROMPT". All `.startswith()` checks updated.

17. **enhanced_operation_details as primary hotlink source** — When > `SHOW_AI_MASTER_RESPONSE_COPY` chars, replaces `ai_response` for field hotlinks and All Hotlinks. `authoritative_ai_override` preserved. Instance vars `_hotlink_source_label` + `_hotlink_has_override` track source.

18. **Response header metadata moved to response text** — Headers now clean (`RESPONSE: incident_location`, `RESPONSE: All Hotlinks`, `Enhanced operation details`). Metadata line `[model]  time  cost  | source: {source}` prepended as first line in response text. Stripped from Accept/Cancel dialog.

19. **Deriving status includes source and override** — Initial: `AI: death_location Deriving… From enhanced_operation_details data + override`. Progress: `Deriving … From {source} data (querying {model})`.

20. **COPY RESPONSE button labels shortened** — "COPY RESPONSE: to ai_response" → "--> ai_response"; "COPY RESPONSE: to enhanced_operation_details" → "--> enhanced_operation_details".

---

## Completed — This Session

21. **Fixed `NameError` in All Hotlinks dialog** — `_show_all_hotlinks_result` referenced undefined variable `header` at lines 1016 and 1023. Both changed to `prefix` (the correctly-scoped variable already defined in the method). Fixes crash when clicking "All Hotlinks".

---

## Incomplete Work — Carry-Over

*None.*

---

## Next Steps

- [ ] Test field hotlink with `enhanced_operation_details` > 200 chars → verify uses as primary source
- [ ] Test field hotlink with `enhanced_operation_details` < 200 chars → verify falls back to `ai_response`
- [ ] Test "+ override" suffix appears in Deriving status when `authoritative_ai_override` exists
- [ ] Test response header is clean (`RESPONSE: field_name`) with metadata as first line
- [ ] Test Accept/Cancel dialog does NOT contain metadata line
- [ ] Test "Show Master Prompt" button label
- [ ] Test side panel shows "PROMPT: Fatalities Master Prompt" / "RESPONSE: FATALITIES MASTER PROMPT"
- [ ] Test "Enhanced operation details" hotlink with Accidental record
- [ ] Test "Enhanced operation details" hotlink with KIA record
- [ ] Test COPY RESPONSE buttons: `--> ai_response` and `--> enhanced_operation_details`
- [ ] Test both COPY buttons only appear when response > `SHOW_AI_MASTER_RESPONSE_COPY`
- [ ] Test `enhanced_operation_details` field: 8-line text area, scrollbar, editable
- [ ] Test individual hotlink clicks on Accidental record
- [ ] Test "All Hotlinks" on Accidental record
- [ ] Test Enhanced Circumstances with long response — no truncation (16384 tokens)
- [ ] Test fatality_type edit: persist across navigation
- [ ] Test date display: `yyyy-Mmm-dd`
- [ ] Test NZ / AU Master Prompt regression
- [ ] Add `openrouter.log` to `.gitignore`
