# rAI Progress Report

## Current System State

### Architecture
- **Master Response pipeline**: Bypassed — prompt generated & displayed in side panel for manual `gemini.google.com` execution. No API call made.
- **Hotlink derivations**: AI-powered field extraction for `service_status`, `place_of_death`, `circumstances_of_death`, `unit_served_with`, and `grid_reference`/`incident_location`.
- **Provider routing**: Hotlinks use the top-row dropdown (Google/DeepSeek/OpenRouter, populated from `.env` `AI_MODEL_PROVIDERS`). Master Response uses `AI_MASTER_MODEL_PROVIDER` from `.env`.
- **Session persistence**: `session.json` tracks last position, search text, on-this-day filters, side panel visibility, side panel content per-record, and internal provider selection.

### Key env vars
| Variable | Purpose |
|---|---|
| `AI_MODEL_PROVIDERS` | Populates the provider dropdown (hotlinks) |
| `AI_MASTER_MODEL_PROVIDER` | Master Response provider |
| `GEMINI_API_KEY` / `DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY` | Provider API keys |
| `SHOW_AI_MASTER_RESPONSE_COPY` | Char threshold for COPY RESPONSE button (default 200) |
| `AU_SERVICE_STATUSES` | Comma-separated valid service statuses for Australia |

### Removed
- `AI_INTERNAL_MODEL_PROVIDER` — replaced by dropdown selection persisted in session state

---

## Completed This Session

1. **Clipboard auto-copy** — "AI: Create a Master Response" copies full prompt to clipboard on click
2. **Copy button reactive** — "AI: COPY RESPONSE: to ai_response" now appears when user types/pastes into RESPONSE panel (bound to `<<Modified>>`)
3. **place_of_death concise** — Hotlink prompt now returns map-ready name (`Seymour, Victoria, Australia`) instead of terrain narrative
4. **Prompt restructure** (`ai_master_prompts.py`):
   - Removed unknown-at-click-time fields (Fatality Type, Place of Death, Armed Forces)
   - Added explicit "War: Vietnam War (1962–1972)" to Authoritative Identification
   - Restructured: Authoritative Identification → All Known Details → Research Requirements
   - Non-combat death warning added to both SYSTEM and USER prompts
   - Multi-match guidance: if Surname + DoD matches multiple soldiers, list each by Full Name + Service Number
5. **Provider dropdown** — `ttk.Combobox` in top row, before Side Panel checkbox, defaults to "Google"
6. **Provider in session** — dropdown selection persisted across all 5 session-save paths, restored on load
7. **`AI_INTERNAL_MODEL_PROVIDER`** — fully removed from codebase

---

## Next Steps

- [ ] Test full workflow: open editor → select OpenRouter in dropdown → click hotlink → verify it routes to OpenRouter
- [ ] Test session persistence: change provider dropdown → close editor → reopen → verify provider is restored
- [ ] Test place_of_death hotlink with new prompt — verify concise output
- [ ] Test "AI: Create a Master Response" — verify clipboard copy works, paste into gemini.google.com
- [ ] Remove `AI_INTERNAL_MODEL_PROVIDER` from `.env` file (no longer read by code)
- [ ] Update `.env.example` to remove `AI_INTERNAL_ANALYSIS_MODEL` if unused
