# rAI_PROGRESS — Fatalities Editor

## Session Progress — 2026-07-06

- **Diagnosed AI hallucination in "Enhanced Operations Details"**: The hotlink triggered
  `_build_enhanced_circumstances_prompt` which actively instructed the AI to fabricate
  war diary entries, eyewitness accounts, chronological timelines, patrol movements,
  and Dustoff details — then cite them against non-existent AWM records and books.
- **Rewrote `_build_enhanced_circumstances_prompt`** (`update_fatalities.py`):
  - Added 9 anti-hallucination rules to the system prompt.
  - Replaced both combat and non-combat research components with URL-mandatory versions.
  - Removed fabrication-encouraging instructions (the "If direct diary text is not
    accessible, summarise secondary sources" line was the primary fabrication engine).
  - Replaced "chronological reconstruction" requirement with: every factual claim
    MUST include a URL in `[Source Name](https://...)` format. No URL → NOT_DOCUMENTED.
- **Tightened `ai_derived_details_prompts.py`**:
  - Added anti-hallucination rules to `_SHARED_RULES` (applies to all field hotlinks).
  - Tightened `get_circumstances_of_death_prompt`: no longer asks AI to invent
    "enemy contact type, operational environment, fatal wound nature."
  - Tightened `get_all_hotlinks_prompt`: same constraints for combined extraction.
- **All files compile cleanly** (`update_fatalities.py`, `ai_derived_details_prompts.py`,
  `ai_master_prompts.py`).

## Current System State

- **Anti-hallucination rule (CRITICAL)**: Every factual claim in AI-generated output
  MUST include a working URL from an authoritative source (AWM, DVA, VWMA, NAA, Trove).
  No URL → the claim MUST be NOT_DOCUMENTED. This applies to the Enhanced Operations
  Details prompt AND all derived-detail hotlink prompts.
- **Fabrication prohibitions**: AI must NEVER invent war diary entries, eyewitness
  accounts, chronological timelines, patrol movements, platoon positions, Dustoff
  times, book references, or combat narratives. These are NOT in the public record
  for individual soldiers.
- **Indian 1960 datum**: Tag MGRS with `I60:`, `INDIAN1960:`, or `INDIAN:` inside
  `//...//` to route through pyproj EPSG:3148/3149 → EPSG:4326.
- **Default MGRS**: Untagged MGRS uses legacy SVN60 shift (+205m E, +75m N).
- **Local conversion**: Click `incident_coordinates` label → reads `//...//` from
  `incident_location` → `coords.py` → writes to `incident_coordinates`.
- **Key files**: `update_fatalities.py` (GUI + Enhanced Circumstances prompt),
  `ai_derived_details_prompts.py` (hotlink field prompts),
  `ai_master_prompts.py` (master response prompt), `coords.py` (parsers + datum).
- **Dependencies**: `mgrs`, `pyproj` (both installed).

## Next Steps

1. [ ] Test "Enhanced Operations Details" hotlink with a known soldier record.
   Verify output contains only URL-backed claims and honest NOT_DOCUMENTED markers
   — no fabricated war diaries, timelines, or eyewitness accounts.
2. [ ] Test individual field hotlinks (service_status, circumstances_of_death, etc.)
   — confirm anti-hallucination rules suppress fabrication in derived fields.
3. [ ] For records with `YS 443 235` → verify source grid reference; may be
   `YS 386 619` or similar.
4. [ ] For records with `YS 785 650` mapped to Hoa Long area → verify; currently
   converts to 10.529°N, 107.545°E (~40 km east).
5. [ ] Consider adding Indian 1960 as default for all Vietnam-era MGRS if the SVN60
   shift proves insufficient across more records.
6. [ ] Test `//I60:...//` workflow end-to-end in the GUI.

## Incomplete Work

None. All changes are complete and verified (syntax check passed).
