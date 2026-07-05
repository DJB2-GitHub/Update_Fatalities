# rAI_PROGRESS — Fatalities Editor

## Current System State

- **Indian 1960 datum**: Tag MGRS with `I60:`, `INDIAN1960:`, or `INDIAN:` inside `//...//` to route through pyproj EPSG:3148/3149 → EPSG:4326.
- **Default MGRS**: Untagged MGRS uses legacy SVN60 shift (+205m E, +75m N).
- **All Hotlinks**: AI-driven; infers coordinates from narrative text, not from a local converter.
- **Local conversion**: Click `incident_coordinates` label → reads `//...//` from `incident_location` → `coords.py` → writes to `incident_coordinates`.
- **Key files**: `coords.py` (parsers + datum transforms), `update_fatalities.py` (GUI modal), `ai_derived_details_prompts.py` (LLM prompts).
- **Dependencies**: `mgrs`, `pyproj` (both installed).

## Next Steps

1. [ ] For records with `YS 443 235` → verify source grid reference; may be `YS 386 619` or similar.
2. [ ] For records with `YS 785 650` mapped to Hoa Long area → verify; currently converts to 10.529°N, 107.545°E (~40 km east).
3. [ ] Consider adding Indian 1960 as default for all Vietnam-era MGRS (not just tagged) if the SVN60 shift proves insufficient across more records.
4. [ ] Test `//I60:...//` workflow end-to-end in the GUI (update modal → incident_coordinates click).
