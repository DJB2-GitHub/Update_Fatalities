# rAI Progress Report

## Current System State

### Architecture
- **Master Response pipeline**: Bypassed — prompt generated & displayed in side panel for manual Gemini browser execution. No API call made.
- **Date format**: JSON storage is ISO 8601 (`yyyy-mm-dd`). Display and prompt insertion use `_format_date_display()` → `yyyy-Mmm-dd` (e.g., `1967-March-29`). Applied to `date_of_death`, `date_of_birth` in UI, and `dod` in Master Prompt.
- **Country-aware prompts**: `ai_master_prompts.py` gates primary sources, authoritative identification labels, citation abbreviations, and home-country text on `country_code` (`AU` vs `NZ`).
- **`is_live_search`**: Hardcoded `True`. Affects prompt text only (live-search instructions + source lists). Google Search grounding tool injection exists in the API path but is never reached in the current clipboard workflow.
- **COPY RESPONSE**: `_copy_response_to_ai_response()` checks `_record_dirty`. Clean → copies + auto-saves via `_update_record()`. Dirty → Yes/No/Cancel dialog.
- **Master Web Provider dropdown**: Combobox (Google/Microsoft/DeepSeek) + clickable provider-name hotlink. Persisted in session state. Visibility controlled by `_show_master_web_provider` flag — shown for "Show Master Prompt" and "Show + Op Prompt", hidden for "Enhanced operation details" hotlink.
- **JSON parsing**: `_robust_json_parse()` — two-strategy parser: strict `json.loads` then regex key-value extraction for malformed AI output (extra text after string values, missing braces, etc.).
- **GPS prompt rule**: `grid_reference` targets the **fatal incident location** (wounding/action site), NOT the hospital/aid station where death occurred. Applied in both individual hotlink and "All Hotlinks" prompts.
- **Hotlink API**: timeout 60s (was 15s); Gemini `maxOutputTokens` 8192 (was 1024); DeepSeek `max_tokens` 8192 (was unset). `_call_ai_for_field()` now accepts optional `max_tokens` param (default 8192) — Enhanced Circumstances passes 16384.
- **Side panel width**: 750px (was 500px).
- **Side panel visibility**: Always visible. Toggle checkbox, ✕ close button, and `_hide_side_panel`/`_toggle_side_panel` methods removed.

### Editable fields (non-derived_details)
- `service_status` — Combobox with country-specific valid statuses
- `unit` — text Entry
- `fatality_type` — text Entry

### Field label display
- `authoritative_ai_override` → displayed as "authoritative" (newline) "ai_override"
- `enhanced_operation_details` → displayed as "enhanced" (newline) "operation" (newline) "details"

### Enhanced operation details prompt — hallucination guardrails
- **`existing_data` anchor block**: Injects `circumstances_of_death`, `death_location`, and `place_of_burial` from the record as AUTHORITATIVE GROUND TRUTH. The AI must treat these as facts and never override or fabricate conflicting narratives.
- **Cross-contamination warning**: Prompt explicitly warns against conflating unit-level or cemetery-level web results with the individual soldier (e.g., Terendak, Singapore, Malaysia repatriation stories about other soldiers).
- **Fatality-type guardrail**: `fatality_type` gates combat vs non-combat research instructions. All fatality types starting with "accident" are forced non-combat regardless of embedded combat keywords.

### Hotlink source priority
- When `enhanced_operation_details` has > `SHOW_AI_MASTER_RESPONSE_COPY` chars (default 200), it replaces `ai_response` as the primary source for field hotlinks and All Hotlinks.
- `authoritative_ai_override` is always preserved and prepended to the combined text.
- Instance variables: `self._hotlink_source_label` (str), `self._hotlink_has_override` (bool) — set during `_hotlink_combined_text` build.

### Enhanced operation details hotlink
- The **DERIVED_DETAILS** heading is normal red text. Next to it is a **blue underlined label "Enhanced operation details"** with tooltip *"Click to research Enhanced Circumstances"*.
- Click is **unconditional** — always clickable when the DERIVED_DETAILS section exists.
- Prompt is built **dynamically per-record** from `serviceRecordAuthority` fields (rank, full_name, service_number, unit, date_of_death, fatality_type) plus `existing_data` dict.
- Result displays in the side panel RESPONSE with header `RESPONSE: Enhanced Operation Details`. Metadata `[model]  time  cost` prepended as first line of response text.
- **--> enhanced_operation_details** button (blue `#1565c0`) appears when header starts with "RESPONSE: Enhanced Operation Details" and text > `SHOW_AI_MASTER_RESPONSE_COPY`.
- `enhanced_operation_details` field renders as an 8-line text area with vertical scrollbar, selectable, editable.

### Show + Op Prompt button
- **"Show + Op Prompt"** button (blue `#1565c0`, multiline: "Show" / "+ Op Prompt") in top row.
- Click builds Enhanced operation details prompt, copies `SYSTEM:\n...\nMESSAGE:\n...` to clipboard, displays in prompt pane under `PROMPT: Enhanced Operation Details`, clears response pane with `// Prompt copied to clipboard — paste into https://copilot.microsoft.com, then paste the result here.`
- Sets response header to `RESPONSE: Enhanced Operation Details` with provider dropdown visible (`_show_master_web_provider = True`).

### COPY RESPONSE buttons (two)
- **--> ai_response** — green (`#2e7d32`). Shows when side panel label starts with "RESPONSE: Fatalities Master" and text > `SHOW_AI_MASTER_RESPONSE_COPY`.
- **--> enhanced_operation_details** — blue (`#1565c0`). Shows when side panel label starts with "RESPONSE: Enhanced Operation Details" and text > `SHOW_AI_MASTER_RESPONSE_COPY`.
- Both use `self._copy_threshold` (read from `.env` `SHOW_AI_MASTER_RESPONSE_COPY`, default 200).

### Response headers (clean)
- Field hotlinks: `RESPONSE: {field_name}` (e.g., `RESPONSE: death_location`)
- All Hotlinks: `RESPONSE: All Hotlinks`
- Enhanced operation details (hotlink): `RESPONSE: Enhanced Operation Details`
- Show + Op Prompt: `RESPONSE: Enhanced Operation Details`
- Show Master Prompt: `RESPONSE: Fatalities Master`
- Metadata (model, time, cost, source) is **prepended as first line** of the response text, never in the header label.
- Metadata is **stripped** from the Accept/Cancel dialog — only field value shown.

### Deriving status messages
- Single hotlink: `AI: {field_name} Deriving… From {source} data` + ` + override` if applicable
- All Hotlinks: `AI: All Hotlinks Deriving… From {source} data` + ` + override`
- Enhanced operation details: `Enhanced operation details Deriving…`
- Retry/progress: `Deriving … From {source} data (querying {model})`

### Provider selector behavior
- `_set_response_label()` uses `_show_master_web_provider` flag (not string matching).
- Set `True` in `_show_ops_prompt` and `_ai_lookup` → provider dropdown visible.
- Set `False` in `_on_enhanced_circumstances_click` → provider hidden.
- Combobox width reduced to 10 (was 12). Hotlink shows provider name (e.g., "Microsoft") instead of full URL.

### Fatality-Type Authority Rule
- `fatality_type` is **AUTHORITATIVE** across all hotlink prompts. It gates whether combat or non-combat research instructions are used.
- **Two-tier classification** in `_build_enhanced_circumstances_prompt()`:
  - Combat keywords checked first (KIA, DOW, Booby trap, Land mine, Enemy grenade, etc.)
  - Non-combat fallback (Accident, Illness, Motor Vehicle, Homicide, Drowning, etc.)
  - `accident*` prefix guard: any fatality_type starting with "accident" is forced non-combat regardless of embedded combat keywords
- **~395 combat** / **~122 non-combat** / **~10 unknown** across 79 unique types in AU_fatalities.json
- **Rule**: If fatality_type indicates NON-COMBAT, the prompt says: "DO NOT fabricate combat scenarios, enemy contact, booby traps, ambushes, operations, or battle narratives."

### Title bar web links
1. `🔗` — key reference link from `.env` `KEY_REFERENCE_LINK` (country-specific, e.g., VWMA for AU)
2. `🔗 AWM-Commanders Diaries` — opens `https://www.awm.gov.au/collection/C1372714`
3. `🌐 Web query` — Google search updated per record

### Session restore
- `master_web_provider` persisted and restored on startup.
- Side panel response label restored via `_set_response_label` (not direct `.configure()`) so provider controls toggle correctly.
- Side panel always visible on launch (`_show_side_panel()` called at end of construction).

### Key env vars
| Variable | Purpose |
|---|---|
| `SHOW_AI_MASTER_RESPONSE_COPY` | Char threshold for COPY RESPONSE buttons and enhanced_operation_details source gating |
| `AI_MODEL_PROVIDERS` | Provider dropdown (hotlinks) |
| `AI_MASTER_WEB_PROMPT_URL` | JSON dict of provider → URL for Master Response web lookup |
| `AI_MASTER_MODEL_PROVIDER` | Master Response provider |
| `GEMINI_API_KEY` / `DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY` | Provider API keys |
| `AU_SERVICE_STATUSES` / `NZ_SERVICE_STATUSES` | Valid service statuses per country |
| `KEY_REFERENCE_LINK` | Country-specific quick reference links displayed in title bar |

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

## Completed — Prior Sessions (committed: `eec0e64`)

1. **Date display formatting** — `_format_date_display()` added. Converts `yyyy-mm-dd` → `yyyy-Mmm-dd` for display and Master Prompt.
2. **NZ country-aware Master Prompt** — Sources, auth label, cite refs, and home-country text all gated on `country_code`.
3. **COPY RESPONSE auto-save** — Clean record: copies + auto-saves. Dirty record: Yes/No/Cancel.
4. **All Hotlinks JSON parse fix** — `_robust_json_parse()` with two-strategy recovery.
5. **API hardening** — timeout 15→60s; DeepSeek `max_tokens` added (8192); Gemini `maxOutputTokens` 1024→8192.
6. **GPS prompt corrected** — `grid_reference` targets incident location (wounding/action site), not place of death.
7. **Prev/Next button UX** — Cursor and color state restored correctly after navigation.
8. **FATALITY_LOCATIONS heading → clickable hotlink** — Dynamic Enhanced Research Prompt from current record.
9. **Three new methods**: `_on_enhanced_circumstances_click`, `_build_enhanced_circumstances_prompt`, `_show_enhanced_circumstances_result`.
10. **fatality_type field now editable**.
11. **Response truncation fixed** — `max_tokens` param; Enhanced Circumstances passes 16384.
12. **Removed confirm/populate dialog for Enhanced Circumstances**.
13. **Fatality-type hallucination guardrails** — `_SHARED_RULES`, combat/non-combat keyword gates. Verified against 79 unique types.
14. **Hotlink moved to DERIVED_DETAILS** — Blue "Enhanced operation details" label next to red DERIVED_DETAILS heading.
15. **Side panel header renamed** — "AI: Enhanced circumstances" → "Enhanced operation details".
16. **COPY RESPONSE: to enhanced_operation_details** — Blue button, same dirty/clean handling.
17. **COPY RESPONSE button labels** — "COPY RESPONSE: to ai_response" / "COPY RESPONSE: to enhanced_operation_details".
18. **COPY RESPONSE threshold gating** — Both buttons gated on `SHOW_AI_MASTER_RESPONSE_COPY`.
19. **enhanced_operation_details field** — 8-line text area + scrollbar, editable.
20. **Side panel width** — 500px → 750px.
21. **Button rename** — "AI: Create a Master Response" → "Show Master Prompt".
22. **Side panel labels renamed** — "PROMPT: Master Response" → "PROMPT: Fatalities Master Prompt"; "RESPONSE: MASTER" → "RESPONSE: FATALITIES MASTER PROMPT". All `.startswith()` checks updated.
23. **enhanced_operation_details as primary hotlink source** — When > `SHOW_AI_MASTER_RESPONSE_COPY` chars, replaces `ai_response` for field hotlinks and All Hotlinks. `authoritative_ai_override` preserved.
24. **Response header metadata moved to response text** — Headers now clean. Metadata line prepended as first line in response text. Stripped from Accept/Cancel dialog.
25. **Deriving status includes source and override**.
26. **COPY RESPONSE button labels shortened** — "--> ai_response" / "--> enhanced_operation_details".

---

## Completed — This Session (2026-07-08)

27. **Enhanced operation details hallucination guardrails** — `existing_data` dict (circumstances_of_death, death_location, place_of_burial) injected as AUTHORITATIVE GROUND TRUTH. Cross-contamination warning against unit-level/cemetery-level web results.
28. **Field label display reformatting** — `authoritative_ai_override` and `enhanced_operation_details` display with line breaks in update panel.
29. **AWM-Commanders Diaries web link** — Third title-bar link (`🔗 AWM-Commanders Diaries`) opens collection C1372714.
30. **Side panel always visible** — Toggle checkbox removed, ✕ close button removed, `_hide_side_panel`/`_toggle_side_panel` methods removed. `_show_side_panel()` called at init.
31. **Show + Op Prompt button** — New button builds Enhanced operation details prompt, copies to clipboard, displays `PROMPT: Enhanced Operation Details` / `RESPONSE: Enhanced Operation Details`.
32. **Button text multiline** — "Show\nMaster Prompt" and "Show\n+ Op Prompt" with `pady=2`.
33. **Response header renames** — `RESPONSE: FATALITIES MASTER PROMPT` → `RESPONSE: Fatalities Master`; `RESPONSE: + Ops Prompt` → `RESPONSE: Enhanced Operation Details`.
34. **`_set_response_label` refactored** — Uses `_show_master_web_provider` flag instead of string matching. Provider dropdown visible for "Show Master Prompt" and "Show + Op Prompt", hidden for hotlink.
35. **Provider selector UX** — Combobox width 12→10. Hotlink shows provider name (e.g., "Microsoft") instead of full URL.
36. **Session restore fix** — Side panel response label restored via `_set_response_label` so provider controls toggle correctly.
37. **`_side_panel_chk` references removed** — Cleaned from `_set_locked` both disable and enable paths.
38. **AU_Nasho.json created** — 97 National Servicemen fatality records with service number keys.

---

## Incomplete Work — Carry-Over

*None.* All changes from this session are complete and syntax-verified.

---

## Next Steps

- [ ] Test "Show + Op Prompt" — verify prompt appears, response shows clipboard instruction, provider dropdown visible
- [ ] Test "Show Master Prompt" — verify provider dropdown visible
- [ ] Test "Enhanced operation details" hotlink — verify provider dropdown hidden, label shows RESPONSE: Enhanced Operation Details
- [ ] Test hallucination guardrail — Enhanced operation details with a record that has populated `circumstances_of_death`/`death_location`/`place_of_burial`; verify AI does not fabricate conflicting locations
- [ ] Test field label display — `authoritative_ai_override` and `enhanced_operation_details` line breaks
- [ ] Test AWM-Commanders Diaries link opens correct URL
- [ ] Test provider selector hotlink shows name not URL
- [ ] Test session restore — reopen app with a RESPONSE active; verify provider dropdown state preserved
- [ ] Test side panel always visible on launch
- [ ] Test COPY RESPONSE buttons with new header prefixes
- [ ] Add `openrouter.log` to `.gitignore`
