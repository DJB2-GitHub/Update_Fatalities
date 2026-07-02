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
- **Hotlink API**: timeout 60s (was 15s); Gemini `maxOutputTokens` 8192 (was 1024); DeepSeek `max_tokens` 8192 (was unset).

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

## Completed — This Session

1. **Date display formatting** — `_format_date_display()` added to `update_fatalities.py` and `ai_master_prompts.py`. Converts `yyyy-mm-dd` → `yyyy-Mmm-dd` for display and Master Prompt. JSON storage stays ISO 8601.
2. **NZ country-aware Master Prompt** — Sources, auth label, cite refs, and home-country text all gated on `country_code`. Both `is_live_search` branches covered.
3. **COPY RESPONSE auto-save** — Clean record: copies response + executes `_update_record()` immediately. Dirty record: Yes/No/Cancel dialog.
4. **TEST_PROMPT.txt** — Full prompt template saved to workspace root for testing.
5. **All Hotlinks JSON parse fix** — `_robust_json_parse()` created with two-strategy recovery (strict `json.loads` → regex key-value extraction). Replaced naive 7-line block in `_all_hotlinks()`. Handles common AI mistakes like extra text after string values.
6. **API hardening** — timeout 15→60s; DeepSeek `max_tokens` added (8192); Gemini `maxOutputTokens` 1024→8192 (root cause of All Hotlinks truncation).
7. **GPS prompt corrected** — Individual and "All Hotlinks" `grid_reference` prompts now target *incident location* (wounding/action site), not place of death. Prevents AI from returning hospital coordinates when the soldier died at an aid station.
8. **Prev/Next button UX** — `_set_locked()` now sets `cursor="arrow"` + muted `fg` when locked, `cursor="hand2"` + dark `fg` when unlocked. Buttons restore correct state after navigation.

---

## Next Steps

- [ ] Test date display: verify `date_of_death` and `date_of_birth` show as `yyyy-Mmm-dd` in update modal
- [ ] Test NZ Master Prompt: open NZ_fatalities.json record → "AI: Create a Master Response" → confirm NZ sources, Online Cenotaph label, "in New Zealand"
- [ ] Test AU Master Prompt: confirm regression — AU still shows AWM sources and "in Australia"
- [ ] Test COPY RESPONSE clean: record not dirty → copy + auto-save
- [ ] Test COPY RESPONSE dirty: make an edit, click COPY RESPONSE → Yes/No/Cancel
- [ ] Test COPY RESPONSE dirty → Cancel: nothing happens
- [ ] Test COPY RESPONSE dirty → No: text copies, record stays dirty
- [ ] Test COPY RESPONSE dirty → Yes: text copies, record saves
- [ ] Test "All Hotlinks" with a record that has substantive `ai_response` text — verify all 5 fields populate correctly
- [ ] Test individual hotlink clicks (service_status, place_of_death, unit, grid_reference, circumstances)
- [ ] **Commit uncommitted working tree changes** (7 files dirty: `ai_derived_details_prompts.py`, `ai_master_prompts.py`, `main.py`, `rAI_PROGRESS.md`, `session.json`, `update_fatalities.py`, plus `openrouter.log` which should be gitignored)
