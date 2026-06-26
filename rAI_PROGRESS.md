# rAI_PROGRESS.md

## Session Summary (2026-06-26)

### Completed
1. **Location fields restructured** — `place_of_death`, `grid_reference`, `co-ordinates_decimal` migrated from flat `derived_details` keys to nested `derived_details.fatality_locations.{death_location, incident_location, incident_coordinates}`. Updated: display widgets, validation logic, info dialogs, clipboard copy, post-loop write, master `pod` param, All-Hotlinks dialog label. Backward-compat aliases preserved in `_populate_field_value`, `_render_fields`, and `_read_form`.
2. **OpenRouter cost key fix** — `usage.cost` added to extraction chain (`total_cost` → `totalCost` → `cost` → `0`). Cost was showing $0 because OpenRouter returns `cost` not `total_cost`.
3. **OpenRouter response logging** — `openrouter.log` appended at both call sites (internal + master) with timestamp and full JSON for cost/response verification.
4. **authoritative_ai_override not recognized** — combined hotlink text now label-prefixed (`authoritative_ai_override:\n{value}\n\nai_response:\n{value}`) so AI can identify the override section.

### Current System State
- **Storage paths**: `derived_details.fatality_locations.death_location`, `.incident_location`, `.incident_coordinates`
- **Backward compat**: `_populate_field_value`, `_render_fields`, `_read_form` accept both old (`place_of_death`, `grid_reference`, `co-ordinates_decimal`) and new leaf names
- **AI prompts**: still output legacy keys; mapping layer translates to new paths
- **Hotlinks**: work with both old and new display names via `FIELD_PROMPTS` aliases
- **OpenRouter cost**: extracted from `usage.cost` key (observed: `deepseek-r1` ~0.67¢ USD/call)
- **Override identification**: labeled sections in combined text enable AI to locate and apply `authoritative_ai_override`
- **Logging**: `openrouter.log` captures every OpenRouter response for debugging

### Incomplete Work
None.
