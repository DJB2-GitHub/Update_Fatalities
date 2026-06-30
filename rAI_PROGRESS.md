# rAI Progress Report

## Current System State

### Architecture
- **Master Response pipeline**: Bypassed — prompt generated & displayed in side panel for manual browser execution. No API call made.
- **Master Web Provider dropdown**: Combobox (Google/Microsoft/DeepSeek) + clickable URL hotlink in side panel response header. Defined in `.env` as `AI_MASTER_WEB_PROMPT_URL`. Only visible when label is "RESPONSE: MASTER". Persisted in session state.
- **Hotlink derivations**: LOCAL extraction only — `_extract_hotlinks_locally()` reads `ai_response` text directly using actual labels (Service Status, Place of Death, Unit, Cause of Death, etc.). No external AI API calls. Instant, free.
- **Provider dropdown**: Top-row Combobox for internal provider (Google/DeepSeek/OpenRouter, from `.env` `AI_MODEL_PROVIDERS`). Persisted in session. Currently unused (hotlinks are local-only).
- **Session persistence**: `session.json` tracks last position, search text, on-this-day filters, side panel visibility, side panel content per-record, internal provider, and master web provider.
- **Label management**: `_set_response_label()` wrapper unifies all 10 label-change sites; auto-toggles master web provider controls visibility.

### Key env vars
| Variable | Purpose |
|---|---|
| `AI_MODEL_PROVIDERS` | Populates the provider dropdown |
| `AI_MASTER_WEB_PROMPT_URL` | JSON dict of provider names → URLs for Master Response web lookup |
| `AI_MASTER_MODEL_PROVIDER` | Master Response provider |
| `GEMINI_API_KEY` / `DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY` | Provider API keys |
| `SHOW_AI_MASTER_RESPONSE_COPY` | Char threshold for COPY RESPONSE button (default 200) |
| `AU_SERVICE_STATUSES` / `NZ_SERVICE_STATUSES` | Valid service statuses per country |

### Dead code (inert, kept for reference)
- `_call_ai_for_field()` — no longer called (hotlinks use local extraction)
- `_robust_json_parse()` — JSON parser with brace-balancing, markdown stripping, AI prefix removal
- `_fallback_parse_hotlinks()` — regex fallback for JSON parse failures
- Hotlink prompt functions in `ai_derived_details_prompts.py` — simplified but unused

---

## Completed This Session

1. **Main menu heading** → "OnThisDay in Vietnam webapp" (`main.py`)
2. **`AI_MASTER_WEB_PROMPT_URL`** added to `.env` — Google/Microsoft/DeepSeek with URLs
3. **Master Web Provider dropdown** — Combobox + clickable URL link in side panel, persisted in session (`update_fatalities.py`)
4. **`_set_response_label()` wrapper** — all 10 label-change sites unified; auto-shows/hides provider controls based on "RESPONSE: MASTER" text
5. **Provider controls visibility** — dropdown + URL hidden by default, shown ONLY for "RESPONSE: MASTER"
6. **Error dialog text selectable** — `StyledDialog` uses read-only `tk.Text` instead of `tk.Label` for copy/paste (`main.py`)
7. **Gemini HTTP 400 fixed** — removed `thinkingConfig` from both Gemini call sites; parts iteration already handles thought output
8. **`_robust_json_parse()`** — handles markdown fences, AI reasoning prefixes (`->`, `Sure!`, etc.), brace-balancing extraction
9. **Hotlinks: AI calls replaced with local extraction** — `_extract_hotlinks_locally()` reads `ai_response` directly by matching actual labels (Service Status, Place of Death, Location of Incident, Unit, Cause of Death, Circumstances). Zero API cost, instant.
10. **Regex fixed** — `[^\n.]` → `[^\n]` so unit names with periods ("No. 2 Squadron") are captured fully
11. **Prompts simplified** — `ai_derived_details_prompts.py` hotlink prompts shortened (now unused by local extraction; kept clean)
12. **All snake_case field names removed from extraction patterns** — only actual ai_response labels used

---

## Next Steps

- [ ] Test "All Hotlinks" with a record that has substantive `ai_response` text
- [ ] Test individual hotlink clicks (service_status, place_of_death, unit, etc.)
- [ ] Test Master Web Provider dropdown: select DeepSeek → URL updates → click link opens browser
- [ ] Test "AI: Create a Master Response" — verify clipboard copy and provider URL in insertion text
- [ ] Remove unused `_call_ai_for_field()` and AI hotlink prompt code if confirmed no longer needed
