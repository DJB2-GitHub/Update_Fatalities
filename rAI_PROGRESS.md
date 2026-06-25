# rAI_PROGRESS.md

## Session Summary (2025-06-25) — prior session
*(see below for latest session)*

### Completed (prior)
1. **grid_reference / co-ordinates_decimal architecture** — raw input stays in `grid_reference`; decimal output auto-populates `co-ordinates_decimal` on Update. Only overwrites when grid_reference changed.
2. **Coordinate hotlink** — moved from grid_reference to co-ordinates_decimal (blue link, double-click → Google Maps).
3. **grid_reference info icon** — ℹ️ dialog explaining input/output flow between the two fields.
4. **co-ordinates_decimal validation** — rejects invalid format with clear message; blank or valid decimal only.
5. **Unable-to-convert warning** — dialog when grid_reference format is recognised but can't produce decimal (points to co-ordinates_decimal info button).
6. **coords.py parser fixes** — strips `°` symbols and trailing MGRS/UTM/DMS tags; DMS-to-decimal conversion implemented; `_VIETNAM_48P_SQUARES` table added (was missing, causing NameError).
7. **All Hotlinks button** — fixed to re-appear when hotlinks become active after AI response is copied.
8. **grid_reference hotlink** — added as 5th hotlink field (single-click + All Hotlinks) with best-estimate GPS prompt.
9. **unit_served_with prompt** — replaced with comprehensive AU/NZ/US Army/Navy/Air Force abbreviation rules.
10. **User prompt template** — changed from ```text fences to `<source>` tags with source labelling.
11. **Side panel scrollbars** — vertical scrollbars added to both PROMPT and RESPONSE text widgets.
12. **Side panel visibility** — saved/restored across sessions via `sidePanelVisible` flag.
13. **Parent window focus** — main menu lifted/focused when update modal closes.
14. **ai_response overwrite warning** — suppressed for placeholders ("Unassigned", <10 chars).
15. **COPY RESPONSE spacing** — increased header-to-JSON gap for readability.
16. **_set_buttons_locked crash** — guarded with try/except TclError for destroyed Tk instances.

---

## Session Summary (2025-06-25) — latest

### Completed
1. **OpenRouter API provider** — full integration as third AI provider alongside Google & Deepseek. Both `AI_MASTER_MODEL_PROVIDER` and `AI_INTERNAL_MODEL_PROVIDER` accept `"OpenRouter"`. Provider validated against `AI_MODEL_PROVIDERS` allowlist; unrecognized providers show error dialog.
2. **OpenRouter API call** — endpoint `https://openrouter.ai/api/v1/chat/completions`, OpenAI-compatible payload. Headers include `HTTP-Referer` and `X-Title` per OpenRouter requirements. Applied to both internal analysis (hotlinks) and master response flows.
3. **Master response provider switching** — `_run_request` now branches on `master_provider` (google/deepseek/openrouter). Gemini-format payloads (`systemInstruction`/`contents`/`parts`) auto-converted to OpenAI `messages` format for Deepseek & OpenRouter.
4. **OpenRouter `/auto` response parsing** — extracts actual routed model from `response.model` (e.g., `deepseek-v4-flash`). Reads full cost breakdown from `usage.total_cost`, `input_cost`, `output_cost` (body), with `x-openrouter-cost` header fallback. Token counts read from `usage.input_tokens`/`output_tokens`/`total_tokens`, with OpenAI `prompt_tokens`/`completion_tokens` fallback.
5. **Provider prefix in model display** — OpenRouter models shown as `OpenRouter-{routed_model}` (e.g., `OpenRouter-deepseek-v4-flash`) so provider is always visible next to the model name.
6. **Cost precision** — all `$A` cost displays changed from `.4f` → `.6f` for micro-cost visibility (OpenRouter costs typically sub-cent).
7. **Hotlink & All-Hotlinks dialog headers** — now show `[{model}]  {time}s  $A {cost}` in side-panel label, dialog title bar, and header label. Previously missing model name.
8. **All-Hotlinks cost display** — `_show_all_hotlinks_result` now has full OpenRouter `totalCost` support (was duplicated legacy code missing the check).
9. **`.env` fix** — `OPENROUTER_API_KEY` corrected (was mislabeled as duplicate `DEEPSEEK_API_KEY`). New `.env` keys recognized: `OPENROUTER_API_KEY`, `OPENROUTER_TEXT_TO_TEXT_MODELS_TO_USE`, `AI_OPENROUTER_INTERNAL_ANALYSIS_MODELS`.

### Current System State
- **OpenRouter API**: cost auto-returned in `usage.total_cost` (USD). Converted to AUD via `AUD_USD` env var. No `AI_RATES` entry needed for OpenRouter models — cost comes straight from response.
- **Cost display paths** (3 locations, all consistent): `_show_derivation_result` (single hotlink), `_show_all_hotlinks_result` (all hotlinks), `_make_header` (master response). All check `"totalCost" in usage_meta` first → use it directly × `AUD_USD`. Fall back to `AI_RATES` calculation for Google/Deepseek.
- **Provider/model flow**: internal analysis → `AI_INTERNAL_MODEL_PROVIDER` env var; master response → `AI_MASTER_MODEL_PROVIDER` env var. Model list per provider loaded from respective `*_TEXT_TO_TEXT_MODELS_TO_USE` or `*_INTERNAL_ANALYSIS_MODELS` env keys.
- **`.env` required for OpenRouter**: `AI_MODEL_PROVIDERS="Google,Deepseek,OpenRouter"`, `OPENROUTER_API_KEY`, `OPENROUTER_TEXT_TO_TEXT_MODELS_TO_USE`, `AI_OPENROUTER_INTERNAL_ANALYSIS_MODELS`. Also set `AI_MASTER_MODEL_PROVIDER="OpenRouter"` and/or `AI_INTERNAL_MODEL_PROVIDER="OpenRouter"`.
- **Display format**: `AI: {field}  [OpenRouter-{routed_model}]  {elapsed}s  $A {cost}` — provider prefix always prepended for OpenRouter models. Google/Deepseek models self-identify by model name prefix.

### Incomplete Work
None. All tasks completed.
