"""
AI-Derived Detail Prompts
-------------------------
Prompt templates for hotlink-triggered AI field derivation.
Each function accepts a combined text (ai_response + authoritative_ai_override)
and returns a (system_instruction, user_prompt) tuple.

Override rule: authoritative_ai_override values take precedence over any
ambiguity or conflicting facts in ai_response data.
"""

# ── Shared footer rules appended to every system instruction ──
_SHARED_RULES = (
    "OVERRIDE RULE: If the key 'authoritative_ai_override' is present in the data, "
    "its values take absolute precedence over any conflicting facts. If it is missing, ignore this rule.\n"
    "NOISE FILTER: IGNORE any text marked as 'Unassigned', timestamps, or system logging metadata "
    "outside the core data. Output EXACTLY the requested format with no conversational filler, "
    "explanations, or markdown wrappers.\n"
    "Before producing the final output, internally summarize the provided text to ensure full context "
    "loading. Do not include this summary in the output."
)

_USER_PROMPT_TEMPLATE = (
    "The SOURCE TEXT to analyse is provided below between the <source> tags.\n"
    "This text is compiled from the record's ai_response and authoritative_ai_override fields.\n\n"
    "<source>\n"
    "{combined_text}\n"
    "</source>\n\n"
    "Extract the requested information based on your system instructions from the source text above."
)


def get_service_status_prompt(combined_text: str) -> tuple:
    """Return (system_instruction, user_prompt) to derive service_status."""
    system = (
        "Your task is to extract a single value called \"service_status\" from the provided text.\n\n"
        "Valid outputs:\n"
        "- Regular\n"
        "- National Service\n"
        "- Conscript\n"
        "- Other\n\n"
        "Extraction rules (in order of priority):\n\n"
        "1. If a field named \"authoritative_ai_override\" appears anywhere in the text:\n"
        "     - Treat its value as free-form notes.\n"
        "     - Search ONLY inside this field for the words \"Regular\", \"National Service\", \"Conscript\", or \"Other\".\n"
        "     - If one of these appears, return it exactly.\n"
        "     - If none appear, ignore this field completely.\n\n"
        "2. Else if the key \"1_service_status\" appears anywhere in the text and contains one of the valid values, return it exactly.\n\n"
        "3. Else search ALL provided text for evidence indicating service status:\n"
        "     - DO NOT infer service status from corps, regiment, unit, rank, trade, or branch.\n"
        "     - If the text describes voluntary enlistment, Regular Army, Regular soldier, or similar, return \"Regular\".\n"
        "     - If the text specifically mentions Australian National Service, National Serviceman, \"Nasho\", or the National Service Act, return \"National Service\".\n"
        "     - If the text describes other forms of conscription, call-up, ballot, or compulsory enlistment (not specifically National Service), return \"Conscript\".\n\n"
        "4. If no determination can be made, return \"Other\".\n\n"
        "Output format:\n"
        "Return ONLY the final value as a plain string with no JSON, no punctuation, and no explanation.\n"
        "Before producing the final output, internally summarize the provided text to ensure full context "
        "loading. Do not include this summary in the output."
    )
    return (system, _USER_PROMPT_TEMPLATE.format(combined_text=combined_text))


def get_place_of_death_prompt(combined_text: str) -> tuple:
    """Return (system_instruction, user_prompt) to derive place_of_death."""
    system = (
        "From the provided text, produce a concise \"place_of_death\" summary of no more than 40 words.\n\n"
        "Begin with country, then province/state, followed by broader geographic cues "
        "that help an informed reader visualise the area.\n"
        "Do not include grid references or the soldier's name.\n\n"
        "Provide a brief terrain-based description that aids memory and orientation.\n"
        "Write in a neutral, factual tone appropriate for an honour roll entry.\n\n"
        + _SHARED_RULES
    )
    return (system, _USER_PROMPT_TEMPLATE.format(combined_text=combined_text))


def get_circumstances_of_death_prompt(combined_text: str) -> tuple:
    """Return (system_instruction, user_prompt) to derive circumstances_of_death."""
    system = (
        "From the provided text, produce a concise \"circumstances_of_death\" summary "
        "of no more than 100 words.\n\n"
        "If an Operation name is present, begin with:\n"
        "\"During Operation [Operation Name], …\"\n\n"
        "Do not include the soldier's name or detailed location.\n\n"
        "Describe:\n"
        "- manner of death\n"
        "- type of enemy contact\n"
        "- operational environment\n"
        "- specific nature of the fatal wound (e.g., gunshot, RPG, mine, head or chest wound)\n\n"
        "Write in a neutral, factual tone appropriate for a military honour roll.\n\n"
        + _SHARED_RULES
    )
    return (system, _USER_PROMPT_TEMPLATE.format(combined_text=combined_text))


def get_unit_served_with_prompt(combined_text: str) -> tuple:
    """Return (system_instruction, user_prompt) to derive unit_served_with."""
    system = (
        "TASK:\n"
        "From the provided text, extract the soldier's *unit_served_with* hierarchy "
        "in the following order:\n"
        "country → service → corps/branch → regiment/battalion/squadron → sub-unit → "
        "platoon/troop/flight → section/squad/division → team/crew.\n\n"
        "SHORTHAND CONVERSION RULES (Mandatory):\n"
        "Convert all unit names into the correct shorthand for that nation and service.\n\n"
        "AUSTRALIA:\n"
        "  Australian Army: Regiment→Regt, Battalion→Bn, Squadron→Sqn, Troop→Tp, "
        "Company→Coy, Platoon→Pl, Section→Sec, Battery→Bty, Brigade→Bde\n"
        "  Royal Australian Navy (RAN): Ship prefix→HMAS, Division→Div, Department→Dept, "
        "Branch→Br, Squadron (Fleet Air Arm)→Sqn, Flight→Flt\n"
        "  Royal Australian Air Force (RAAF): Squadron→Sqn, Wing→Wg, Flight→Flt, "
        "Section→Sec, Unit→U, Group→Gp\n\n"
        "NEW ZEALAND:\n"
        "  New Zealand Army: Regiment→Regt, Battalion→Bn, Squadron→Sqn, Troop→Tp, "
        "Company→Coy, Platoon→Pl, Section→Sect, Battery→Bty, Brigade→Bde\n"
        "  Royal New Zealand Navy (RNZN): Ship prefix→HMNZS, Division→Div, "
        "Department→Dept, Branch→Br, Squadron (Air Component)→Sqn, Flight→Flt\n"
        "  Royal New Zealand Air Force (RNZAF): Squadron→Sqn, Wing→Wg, Flight→Flt, "
        "Section→Sect, Unit→U, Group→Gp\n\n"
        "UNITED STATES:\n"
        "  United States Army: Regiment→Regt, Battalion→Bn, Squadron (Cav)→Sqdn, "
        "Troop (Cav)→Trp, Company→Co, Platoon→Plt, Squad→Sq, Battery→Btry, Brigade→Bde\n"
        "  United States Navy (USN): Ship prefix→USS, Division→Div, Department→Dept, "
        "Branch→Br, Squadron (Aviation)→Sqdn, Flight→Flt\n"
        "  United States Air Force (USAF): Squadron→Sqdn, Wing→Wg, Group→Gp, "
        "Flight→Flt, Section→Sec\n\n"
        "UNIVERSAL STANDARD SHORTHAND OUTPUT ORDER (Mandatory):\n"
        "The final output must always follow: [Sub-unit], [Parent Unit]\n"
        "Examples: B Sqn, 3 Cav Regt | C Coy, 9RAR | A Co, 12 Inf Regt | "
        "3 Pl, B Coy, 1RNZIR | C Trp, 11 ACR | Flt 2, 75 Sqn RAAF | "
        "Div 1, USS Enterprise | A Flt, 40 Sqn RNZAF\n"
        "This ordering is mandatory whenever more than one unit level appears.\n\n"
        "PRESERVATION RULE:\n"
        "If a unit already appears in abbreviated form (e.g. 9RAR, 1RNZIR, 11 ACR, "
        "HMAS Perth, USS Nimitz), preserve it exactly.\n\n"
        "EXCLUSION RULE:\n"
        "Do NOT include country or service in the final output. "
        "(Exclude: Australian Army, Royal Australian Navy, US Army, etc.)\n\n"
        "OUTPUT FORMAT:\n"
        "Return one single comma-separated string, containing only unit elements "
        "that appear in the source text.\n"
        "No commentary, no markdown, no explanation.\n\n"
        "OVERRIDE RULE:\n"
        "If the key authoritative_ai_override exists, its values override all other data.\n\n"
        "NOISE FILTER:\n"
        "Ignore any text marked Unassigned, timestamps, system metadata, "
        "or anything outside the <source> block.\n\n"
        "PROCESSING RULE:\n"
        "Before producing the final output, internally summarise the source text "
        "to ensure full context loading. Do not include this summary in the output."
    )
    return (system, _USER_PROMPT_TEMPLATE.format(combined_text=combined_text))


def get_grid_reference_prompt(combined_text: str) -> tuple:
    """Return (system_instruction, user_prompt) to derive grid_reference."""
    system = (
        "TASK: From the provided soldier fatality record, identify the best-estimate "
        "GPS coordinates for the place of death.\n\n"
        "PROCESS:\n"
        "  1. FIRST, check the authoritative_ai_override field.  If it contains "
        "coordinates or a grid reference, use those immediately and stop searching — "
        "return that result.\n"
        "  2. Analyse all location-related fields, including:\n"
        "     - detailed_location_description\n"
        "     - grid_reference\n"
        "     - map_sheet_number_utm_zone\n"
        "     - military_operation\n"
        "     - narrative summary\n"
        "     - any place names (village, hamlet, district, province)\n"
        "     - any fire support bases, rivers, roads, or landmarks\n"
        "     - any ARVN/US/Australian operational areas\n"
        "  3. If a grid reference MGRS / UTM / partial coordinate appears anywhere "
        "in the text, extract it exactly as written.\n"
        "  4. Convert any full or partial grid reference into an approximate GPS "
        "coordinate when possible.\n"
        "  5. If no grid reference exists, use:\n"
        "     - Vietnam War 1:50,000 map sheets\n"
        "     - historical village/hamlet locations\n"
        "     - known AO boundaries\n"
        "     - documented operations to estimate the lowest-level location "
        "(village > hamlet > district > province).\n"
        "  6. Always output one single best-estimate GPS coordinate in decimal degrees.\n\n"
        "OUTPUT FORMAT (MANDATORY):\n"
        "Return a single line:\n"
        "  \"best_estimate_gps\": \"LAT, LON [GRID1, GRID2, ...]\"\n\n"
        "Rules:\n"
        "  - If no grid fragments exist → output only the GPS coordinate.\n"
        "  - If one or more grid fragments exist, even if incomplete → include them "
        "in square brackets, comma-separated.\n"
        "  - If no estimate is possible → return an empty string.\n\n"
        "Examples:\n"
        "  Case 1 — No grid reference in text:\n"
        "    \"best_estimate_gps\": \"16.533, 107.533\"\n"
        "  Case 2 — One grid reference found:\n"
        "    \"best_estimate_gps\": \"10.512, 106.345 [YS478548]\"\n"
        "  Case 3 — Multiple fragments found:\n"
        "    \"best_estimate_gps\": \"11.221, 108.112 [48PYS1234, 48PYS125678]\"\n\n"
        "Return ONLY the output line — no commentary, no markdown, no explanation."
    )
    return (system, _USER_PROMPT_TEMPLATE.format(combined_text=combined_text))


def get_all_hotlinks_prompt(combined_text: str) -> tuple:
    """Return (system_instruction, user_prompt) to derive all five hotlink fields at once."""
    system = (
        "From the provided text, extract five fields and return them as a single JSON object.\n\n"
        "Fields to extract:\n"
        "1. \"service_status\" — one of: Regular, National Service, Conscript, Other. "
        "Deduce from voluntary/compulsory enlistment evidence. "
        "DO NOT infer from corps, regiment, unit, rank, trade, or branch.\n"
        "2. \"place_of_death\" — concise summary (max 40 words). Start with country, then province/state, "
        "then geographic cues. No grid references or soldier's name.\n"
        "3. \"circumstances_of_death\" — concise summary (max 100 words). "
        "If an Operation name is present, begin with \"During Operation [Name], …\". "
        "Describe manner of death, enemy contact type, operational environment, fatal wound nature. "
        "No soldier's name or detailed location.\n"
        "4. \"unit_served_with\" — hierarchy string, comma-separated, [Sub-unit], [Parent Unit] order.\n"
        "  Apply nation/service shorthands (AU Army: Coy/Pl/Sec/Regt/Bn/Sqn/Tp/Bty/Bde; "
        "RAN: HMAS/Div/Dept/Br/Sqn/Flt; RAAF: Sqn/Wg/Flt/Sec/U/Gp. "
        "NZ Army: Coy/Pl/Sect/Regt/Bn/Sqn/Tp/Bty/Bde; RNZN: HMNZS; RNZAF: Sqn/Wg/Flt/Sect. "
        "US Army: Co/Plt/Sq/Regt/Bn/Sqdn/Trp/Btry/Bde; USN: USS; USAF: Sqdn/Wg/Gp/Flt/Sec).\n"
        "  Exclude country/service name from output. Preserve existing abbreviations (9RAR, 1RNZIR, 11 ACR).\n"
        "5. \"grid_reference\" — best-estimate GPS for place of death.\n"
        "  FIRST check authoritative_ai_override; if coordinates found there, use them.\n"
        "  Otherwise analyse all location fields, extract any MGRS/UTM/partial grid refs,\n"
        "  convert to decimal GPS, and output as:\n"
        "    \"best_estimate_gps\": \"LAT, LON [GRID1, GRID2, ...]\"\n"
        "  Include grid fragments in brackets when present; empty string if no estimate.\n\n"
        "Return format:\n"
        "{\n"
        "  \"service_status\": \"<value>\",\n"
        "  \"place_of_death\": \"<value>\",\n"
        "  \"circumstances_of_death\": \"<value>\",\n"
        "  \"unit_served_with\": \"<value>\",\n"
        "  \"grid_reference\": \"<value>\"\n"
        "}\n\n"
        + _SHARED_RULES
    )
    return (system, _USER_PROMPT_TEMPLATE.format(combined_text=combined_text))


# ── Field → prompt function mapping ──
FIELD_PROMPTS = {
    "service_status":          get_service_status_prompt,
    "place_of_death":          get_place_of_death_prompt,
    "death_location":          get_place_of_death_prompt,
    "circumstances_of_death":  get_circumstances_of_death_prompt,
    "unit_served_with":        get_unit_served_with_prompt,
    "grid_reference":          get_grid_reference_prompt,
    "incident_location":       get_grid_reference_prompt,
}
