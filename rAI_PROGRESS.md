# rAI Progress Report

## Current System State

### Architecture
- **Master Response pipeline**: Bypassed — prompt generated & displayed in side panel for manual browser execution. No API call made. The insertion text uses the selected Master Web Provider's URL.
- **Master Web Provider dropdown**: Combobox (Google/Microsoft/DeepSeek) + clickable URL hotlink in side panel response header. Defined in `.env` as `AI_MASTER_WEB_PROMPT_URL` (JSON dict of provider → URL). Only visible when label is "RESPONSE: MASTER". Persisted in session state.
- **Hotlink derivations**: AI API calls via `_call_ai_for_field()`. Individual hotlinks use per-field prompts; "All Hotlinks" uses `get_all_hotlinks_prompt()` with JSON output. Prompts and `_SHARED_RULES` defined in `ai_derived_details_prompts.py`.
- **Provider routing**: Hotlinks use top-row dropdown (Google/DeepSeek/OpenRouter, from `.env` `AI_MODEL_PROVIDERS`). Master Response uses `AI_MASTER_MODEL_PROVIDER` from `.env`.
- **Session persistence**: `session.json` tracks last position, search text, on-this-day filters, side panel visibility, side panel content per-record, internal provider, and master web provider.
- **Label management**: `_set_response_label()` wrapper unifies all label-change sites; auto-toggles master web provider controls visibility.
- **Gemini API**: No `thinkingConfig` — removed after causing HTTP 400. Parts iteration handles any thought output. `maxOutputTokens` set to 8192 (was 1024, insufficient for combined "All Hotlinks" JSON output).
- **DeepSeek API**: `max_tokens` set to 8192 (was unset, causing truncated responses).
- **API timeout**: 60s (was 15s) — accommodates longer combined-prompt generations.
- **JSON parsing**: `_robust_json_parse()` — structural-only recovery: strips ``` fences, reasoning-prefix lines (`->`, `Sure!`, `GPS:`, `[GRID]:`, bullet points), brace-balanced extraction, `json.loads`. Returns `dict | None`. No field-name or schema awareness.

### Key env vars
| Variable | Purpose |
|---|---|
| `AI_MODEL_PROVIDERS` | Populates the provider dropdown (hotlinks) |
| `AI_MASTER_WEB_PROMPT_URL` | JSON dict of provider names → URLs for Master Response web lookup |
| `AI_MASTER_MODEL_PROVIDER` | Master Response provider |
| `GEMINI_API_KEY` / `DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY` | Provider API keys |
| `SHOW_AI_MASTER_RESPONSE_COPY` | Char threshold for COPY RESPONSE button (default 200) |
| `AU_SERVICE_STATUSES` / `NZ_SERVICE_STATUSES` | Valid service statuses per country |

### Hotlink prompt summary (from `ai_derived_details_prompts.py`)
| Field | Prompt function | Output |
|---|---|---|
| `service_status` | `get_service_status_prompt` | Plain string |
| `place_of_death` / `death_location` | `get_place_of_death_prompt` | Plain string |
| `circumstances_of_death` | `get_circumstances_of_death_prompt` | Plain string |
| `unit_served_with` | `get_unit_served_with_prompt` | Plain string |
| `grid_reference` / `incident_location` | `get_grid_reference_prompt` | Plain string |
| All Hotlinks (combined) | `get_all_hotlinks_prompt` | JSON object |

All prompts append `_SHARED_RULES` (override rule, noise filter, internal summarise) and wrap `ai_response` + `authoritative_ai_override` in `<source>...</source>` tags.

---

## Completed — Prior Session

1. **Main menu heading** → "OnThisDay in Vietnam webapp" (`main.py`)
2. **`AI_MASTER_WEB_PROMPT_URL`** added to `.env` — Google/Microsoft/DeepSeek with URLs
3. **Master Web Provider dropdown** — Combobox + clickable URL link in side panel response header, persisted in session state
4. **`_set_response_label()` wrapper** — unifies all label-change sites; auto-shows/hides provider controls
5. **Provider controls visibility** — dropdown + URL hidden by default, shown ONLY for "RESPONSE: MASTER"
6. **`_open_master_web_url()`** — opens selected provider's URL via `webbrowser.open()`
7. **Dynamic URL** — insertion text reads "paste into {selected_provider_url}" instead of hardcoded "gemini.google.com"
8. **Error dialog text selectable** — `StyledDialog` uses read-only `tk.Text` instead of `tk.Label` (`main.py`)
9. **Gemini HTTP 400 fixed** — removed `thinkingConfig` from both Gemini call sites in `update_fatalities.py`
10. **Session persistence** — `master_web_provider` saved to `session.json` in all 5 save paths
11. **Hotlink prompts reviewed** — confirmed all 5 individual prompts + combined "All Hotlinks" prompt structure

---

## Completed — This Session

1. **`_robust_json_parse()` created** (`update_fatalities.py` line ~2497) — structural JSON recovery: strips ``` fences, reasoning-prefix lines (`->`, `Sure!`, `Here`, `Let me`, `First,`, `GPS:`, `[GRID]:`, `* GPS:`, etc.), brace-balanced extraction, `json.loads`. Returns `dict | None`. Zero field-name awareness.
2. **`_all_hotlinks()` parsing fixed** — replaced 7-line naive `json.loads` block with `parsed = self._robust_json_parse(text)` (line 567)
3. **`get_all_hotlinks_prompt()` hardened** — prepended `"Return ONLY a valid JSON object. No reasoning, no commentary, no markdown before the JSON."` to system instruction (`ai_derived_details_prompts.py` line 256)
4. **API timeout increased** — `timeout_secs`: 15 → 60 for all providers (`_call_ai_for_field`, line 777)
5. **DeepSeek `max_tokens` added** — `"max_tokens": 8192` in DeepSeek request body (line 825)
6. **Gemini `maxOutputTokens` increased** — `"maxOutputTokens": 1024 → 8192` (line 912) — root cause of truncation

### Root Cause Summary
"All Hotlinks" failed because: (a) Gemini `maxOutputTokens` was 1024 — far too low for a 5-field JSON response including a 100-word circumstances summary — causing mid-response truncation; (b) no robust JSON parser existed to recover from noisy/partial AI output.

---

## Next Steps

- [ ] Test "All Hotlinks" with a record that has substantive `ai_response` text
- [ ] Test individual hotlink clicks (service_status, place_of_death, unit, grid_reference, circumstances)
- [ ] Test Master Web Provider dropdown: select DeepSeek → URL updates → click link opens browser
- [ ] Test "AI: Create a Master Response" — verify clipboard copy and dynamic provider URL in insertion text
- [ ] Verify session persistence: change master web provider → close/reopen → provider restored
- [ ] Consider adding `.env.example` entry for `AI_MASTER_WEB_PROMPT_URL`
