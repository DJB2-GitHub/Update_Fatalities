# rAI_PROGRESS — Session Summary & Next Steps

> Auto-generated 2026-06-24 from the Kun agent session.
> Covers all file changes across `main.py`, `update_fatalities.py`, and new module `ai_derived_details_prompts.py`.

---

## Session Accomplishments

### 1. Window minimise / restore (both forms)
- **Main Menu** (`main.py`) — added `<Unmap>` / `<Map>` bindings so the title-bar minimise button iconifies the root `App` window to the taskbar and restores correctly.
- **Update modal** (`update_fatalities.py`) — same sync pattern; removed `transient()` call (which forced `WS_EX_TOOLWINDOW` on Windows, stripping the minimise & maximise buttons from the title bar); removed `event.widget is not self` guards that were silently dropping `<Unmap>` events; added `grab_release()` / `grab_set()` around minimise/restore so the title-bar button works while a local grab is active.

### 2. Button locking on Main Menu
- Replaced the old `state=tk.DISABLED` hack (Labels ignore `state` for click blocking) with a `_buttons_locked` boolean flag.
- All main-menu buttons (dataset buttons + Quit) are **truly disabled** (clicks ignored, dimmed visually, `watch` cursor) while the Update modal is open.  Only one modal at a time.

### 3. Bottom-bar layout restructure (Update modal)
- Option A/B/C dropdown now sits on its own row directly under the "AI: Create a Master Response" button.
- "Live Search" checkbox moved next to the right of the AI button.

### 4. AI-derived detail hotlinks (new feature)
#### New module: `ai_derived_details_prompts.py`
Four prompt templates with override-precedence rule:
| Field | Function |
|---|---|
| `service_status` | `get_service_status_prompt()` |
| `place_of_death` | `get_place_of_death_prompt()` |
| `circumstances_of_death` | `get_circumstances_of_death_prompt()` |
| `unit_served_with` | `get_unit_served_with_prompt()` |

#### Hotlink behaviour (`update_fatalities.py`)
- **Provider selection**: reads `AI_INTERNAL_MODEL_PROVIDER` (validated against `AI_MODEL_PROVIDERS`), routes to Gemini API or DeepSeek API accordingly.
- **Activation**: field label turns blue + underlined + hand cursor when `ai_response` OR `authoritative_ai_override` contains >50 words.
- **Click**: combines both texts (override first), sends prompt to selected provider, shows progress in side panel.
- **Result**: cost/time header (e.g. `AI: service_status [2s, $A 0.0003]`), Yes/No accept dialog, populates field on accept.
- **Error handling**: failures show a clear error dialog — never silently swallowed or fed into the accept/cancel flow.
- **Timeout**: 15 s (hardcoded — appropriate for single-field derivations).
- **Cost unknown**: `??s, $A ?.????` placeholders when rates are missing.
- **API routing**: DeepSeek uses `api.deepseek.com/v1/chat/completions` (OpenAI-compatible); Gemini uses `generativelanguage.googleapis.com` (generateContent). Usage metadata normalized to common format for cost calc.

---

## Current System State (architectural rules)

| Rule | Detail |
|---|---|
| **Single modal** | `MainMenu._buttons_locked` flag + `grab_set()` enforce one Update modal at a time |
| **Window controls** | Never call `transient()` on Windows Toplevels — it forces `WS_EX_TOOLWINDOW` which removes minimise/maximise |
| **Minimise chain** | Update modal → MainMenu → App root (each `<Unmap>` iconifies its parent; `<Map>` on parent restores child) |
| **Grab + minimise** | Must `grab_release()` on `<Unmap>` / `grab_set()` on `<Map>` or Windows ignores the title-bar minimise click |
| **Hotlink provider** | Reads `AI_INTERNAL_MODEL_PROVIDER` from `.env`; validated against `AI_MODEL_PROVIDERS` (case-insensitive). Defaults to `"Google"`. |\n| **Hotlink models (Google)** | `AI_GEMINI_INTERNAL_ANALYSIS_MODELS` — Gemini models, API key `GEMINI_API_KEY` |\n| **Hotlink models (DeepSeek)** | `AI_DEEPSEEK_INTERNAL_ANALYSIS_MODELS` — DeepSeek models, API key `DEEPSEEK_API_KEY` |\n| **Master Response models** | Uses `AI_MASTER_MODEL_PROVIDER` / `GEMINI_TEXT_TO_TEXT_MODELS_TO_USE` or `DEEPSEEK_TEXT_TO_TEXT_MODELS_TO_USE` — entirely separate from hotlink config |
| **Hotlink activation** | >50 words in combined `ai_response` + `authoritative_ai_override` |
| **Override precedence** | `authoritative_ai_override` text placed first in combined prompt; all prompts include the override rule |
| **Click blocking** | Use boolean flags, not `state=DISABLED` on Labels (Labels don't block `<Button-1>`) |

---

## Files Changed

| File | Change |
|---|---|
| `main.py` | Minimise sync, button locking (`_buttons_locked`), grab release/restore |
| `update_fatalities.py` | Remove `transient()`, minimise sync, grab handling, bottom-bar layout, hotlink infrastructure (5 new methods) |
| `ai_derived_details_prompts.py` | **New** — 4 prompt templates + `FIELD_PROMPTS` dispatch dict |

---

## Carry-Over / Incomplete Work

**None.** All ticket items are implemented and compiling clean.

## AI Model Configuration: Master Response vs Hotlinks

These two pipelines use **completely independent** provider/model config.

### Master Response ("AI: Create a Master Response" button)
| Env Key | Purpose |
|---|---|
| `AI_MASTER_MODEL_PROVIDER` | Provider selector (`"Google"` or `"Deepseek"`) |
| `GEMINI_TEXT_TO_TEXT_MODELS_TO_USE` | Gemini models when provider is Google |
| `DEEPSEEK_TEXT_TO_TEXT_MODELS_TO_USE` | DeepSeek models when provider is DeepSeek |
| `AI_MASTER_RESPONSE_MODEL_CUTOFF_SECONDS` | Timeout for master response generation |

### Hotlinks (clickable blue field labels)
| Env Key | Purpose |
|---|---|
| `AI_INTERNAL_MODEL_PROVIDER` | Provider selector (`"Google"` or `"Deepseek"`) |
| `AI_MODEL_PROVIDERS` | Allowed provider list (case-insensitive, comma-separated) |
| `AI_GEMINI_INTERNAL_ANALYSIS_MODELS` | Gemini models for hotlinks |
| `AI_DEEPSEEK_INTERNAL_ANALYSIS_MODELS` | DeepSeek models for hotlinks |
| `AI_INTERNAL_RESPONSE_MODEL_CUTOFF_SECONDS` | Timeout for hotlink derivations (currently hardcoded to 15s in code) |
| `SHOW_AI_MASTER_RESPONSE_COPY` | Character threshold for showing "COPY RESPONSE" button on master response (default 200) |

### All Hotlinks (batch derivation)
- **Button**: "All Hotlinks" (orange, only visible when hotlinks are active — >50 words in `ai_response` + `authoritative_ai_override`).
- **Click**: sends a single combined prompt to derive all four hotlink fields at once (`service_status`, `place_of_death`, `circumstances_of_death`, `unit_served_with`).
- **Result dialog**: shows each field with:
  - A **checkbox** (checked by default) — only checked fields are updated.
  - An **editable text box** — edit the AI result before accepting.
  - **Update** / **Cancel** buttons.
- **Session persistence**: All Hotlinks prompt + response + labels saved per `referenceID`.
- **Prompt**: `ai_derived_details_prompts.get_all_hotlinks_prompt()` — returns JSON `{service_status, place_of_death, circumstances_of_death, unit_served_with}`.

---

## Next Steps (absolute)

1. [x] **Rename `.env` key**: `AI_INTERNAL_ANALYSIS_MODEL` → `AI_GEMINI_INTERNAL_ANALYSIS_MODELS` ✅ Done
2. [ ] **Launch the app** (`python main.py` or `python main.pyw`) and verify:
   - Main Menu minimise → taskbar → restore works
   - Update modal minimise → taskbar → restore works (both windows together)
   - Click a dataset button → modal opens → main-menu buttons locked → close modal → buttons unlocked
   - Navigate to a record with >50 words in `ai_response` → field labels turn blue/underlined
   - Click a hotlink → side panel shows progress → result displayed with cost/time → accept populates field
3. [ ] **Test all four hotlink fields**: `service_status`, `place_of_death`, `circumstances_of_death`, `unit_served_with`
4. [ ] **Test error path**: temporarily set `GEMINI_API_KEY` to a bad value in `.env` → verify clear error dialog appears
