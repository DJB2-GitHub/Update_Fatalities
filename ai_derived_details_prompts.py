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
    "OVERRIDE RULE: If the source text contains an explicit, authoritatively marked service-status "
    "note (e.g. a line prefixed with 'Authoritative:', 'Override:', 'Service Status:', or similar), "
    "its value takes absolute precedence over any conflicting facts. If no such marker is present, ignore this rule.\n"
    "NOISE FILTER: IGNORE any text marked as 'Unassigned', timestamps, or system logging metadata "
    "outside the core data. Output EXACTLY the requested format with no conversational filler, "
    "explanations, or markdown wrappers.\n"
    "FATALITY_TYPE AUTHORITATIVE OVERRIDE: Before producing any output, FIRST identify the "
    "fatality_type from the source text (look for phrases like 'Fatality Type:', 'Cause of Death:', "
    "'Accidental', 'Killed in Action', 'Died of Illness', 'Died of Wounds', etc.). "
    "The fatality_type is AUTHORITATIVE — it determines the entire extraction approach:\n"
    "  - If fatality_type indicates NON-COMBAT (Accidental, Accident, Illness, Disease, Natural Causes, "
    "    Motor Vehicle Accident, Drowning, Homicide, Murder, Self-Inflicted, Heart Failure, Brain Tumour, "
    "    Carbon Monoxide, or any death NOT caused by enemy action): DO NOT fabricate combat scenarios, "
    "    enemy contact, booby traps, ambushes, operations, or battle narratives. "
    "    Describe the death factually as an accident/illness/non-combat event. "
    "    Do NOT use combat language (e.g. do not say 'type of enemy contact', 'operational environment', "
    "    'fatal wound', 'bunker systems', 'contact reports'). Use neutral language instead.\n"
    "  - If fatality_type indicates COMBAT (Killed in Action, KIA, Died of Wounds, DOW, "
    "    Enemy grenade, Booby trap, Land mine, GSW from enemy, Viet Cong ambush, "
    "    Helicopter shot down, etc.): research and describe the combat context normally.\n"
    "  - If uncertain, check whether 'Accident', 'Accidental', 'Illness', or 'Died of Illness' appear "
    "    — these are ALWAYS non-combat regardless of location or unit.\n"
    "Before producing the final output, internally summarize the provided text to ensure full context "
    "loading. Do not include this summary in the output."
)

_USER_PROMPT_TEMPLATE = (
    "The SOURCE TEXT to analyse is provided below between the <source> tags.\n"
    "This text is compiled from the record's AI-generated master response and any authoritative override notes.\n\n"
    "<source>\n"
    "{combined_text}\n"
    "</source>\n\n"
    "Extract the requested information based on your system instructions from the source text above."
)


def get_service_status_prompt(combined_text: str, valid_statuses: list[str] | None = None) -> tuple:
    """Return (system_instruction, user_prompt) to derive service_status.

    If valid_statuses is provided, it overrides the default hardcoded list and
    the prompt will only accept those values.  The fallback (rule 4) uses the
    first value in valid_statuses.
    """
    if valid_statuses is None:
        valid_statuses = ["Regular", "National Service", "Conscript", "Other"]

    _valid_list = "\n".join(f"- {v}" for v in valid_statuses)
    _valid_quoted = ", ".join(f'"{v}"' for v in valid_statuses)
    _fallback = valid_statuses[0]

    system = (
        "Your task is to extract a single value called \"service_status\" from the provided text.\n\n" +
        "Valid outputs:\n" +
        f"{_valid_list}\n\n" +
        "Extraction rules (in order of priority):\n\n" +
        "1. If the text contains an explicitly labelled service-status marker (e.g. a line starting "
        "with 'Authoritative:', 'Override:', 'Service Status:', '1_service_status', or similar):\n" +
        "     - Treat the content following that marker as the primary evidence.\n" +
        f"     - Search ONLY inside that marked section for the words {_valid_quoted}.\n" +
        "     - If one of these appears, return it exactly.\n" +
        "     - If none appear, ignore the marker and continue to the next rule.\n\n" +
        "2. Else if the text anywhere contains an explicit service-status label followed by one of the valid values, return that value exactly.\n\n" +
        "3. Else search ALL provided text for evidence indicating service status:\n" +
        "     - DO NOT infer service status from corps, regiment, unit, rank, trade, or branch.\n" +
        (
            "     - If the text describes voluntary enlistment, Regular Army, Regular soldier, or similar, return \"Regular\".\n"
            if "Regular" in valid_statuses else ""
        ) +
        (
            "     - If the text specifically mentions Australian National Service, National Serviceman, \"Nasho\", or the National Service Act, return \"National Service\".\n"
            if "National Service" in valid_statuses else ""
        ) +
        (
            "     - If the text describes other forms of conscription, call-up, ballot, or compulsory enlistment (not specifically National Service), return \"Conscript\".\n"
            if "Conscript" in valid_statuses else ""
        ) +
        "\n" +
        f"4. If no determination can be made, return \"{_fallback}\".\n\n" +
        "Output format:\n" +
        "Return ONLY the final value as a plain string with no JSON, no punctuation, and no explanation.\n" +
        "Before producing the final output, internally summarize the provided text to ensure full context " +
        "loading. Do not include this summary in the output."
    )
    return (system, _USER_PROMPT_TEMPLATE.format(combined_text=combined_text))


def get_place_of_death_prompt(combined_text: str) -> tuple:
    """Return (system_instruction, user_prompt) to derive place_of_death."""
    system = (
        "From the provided text, extract the place of death as a concise location name "
        "that a geographer can locate on a map.\n\n"
        "Output ONLY the place name(s), ordered from smallest to largest:\n"
        "village/town/suburb, state/province, country.\n\n"
        "Examples:\n"
        "  Seymour, Victoria, Australia\n"
        "  Nui Dat, Phuoc Tuy Province, South Vietnam\n"
        "  Vung Tau, South Vietnam\n\n"
        "Do NOT include:\n"
        "- descriptive narrative, terrain notes, or historical context\n"
        "- grid references or coordinates\n"
        "- the soldier's name\n"
        "- conversational filler or markdown\n\n"
        "Return ONLY the place name string.\n\n"
        + _SHARED_RULES
    )
    return (system, _USER_PROMPT_TEMPLATE.format(combined_text=combined_text))


def get_circumstances_of_death_prompt(combined_text: str) -> tuple:
    """Return (system_instruction, user_prompt) to derive circumstances_of_death."""
    system = (
        "From the provided text, produce a concise \"circumstances_of_death\" summary "
        "of no more than 100 words.\n\n"
        "FIRST: identify the fatality_type from the source text. This determines approach.\n\n"
        "FOR COMBAT DEATHS (KIA, DOW, enemy action):\n"
        "  - If an Operation name is present, begin with:\n"
        "    \"During Operation [Operation Name], …\"\n"
        "  - Describe: manner of death, enemy contact type, operational environment, "
        "    and nature of the fatal wound.\n\n"
        "FOR NON-COMBAT DEATHS (Accidental, Illness, Disease, Natural Causes, Motor Vehicle, "
        "Drowning, Homicide, Self-Inflicted, etc.):\n"
        "  - Do NOT use the 'During Operation…' opening — there was no combat operation.\n"
        "  - Do NOT describe enemy contact, operational environment, or fatal wounds.\n"
        "  - Simply describe the non-combat circumstances factually, e.g.:\n"
        "    \"Died from [cause] at [location, if known].\"\n"
        "  - If the exact cause is not documented in the source, say so honestly:\n"
        "    e.g. \"Died from an accidental cause; specific details not documented.\"\n\n"
        "Do not include the soldier's name.\n\n"
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
        "If the text contains an authoritatively marked override section, its values override all other data.\n\n"
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
        "GPS coordinates for where the death-related location — and extract all "
        "physical location/place names from the text.\n\n"
        "FIRST: identify the fatality_type from the source text. This determines the location approach.\n\n"
        "FOR COMBAT DEATHS (KIA, DOW, enemy action):\n"
        "  - Identify where the fatal INCIDENT occurred — the place of wounding/action "
        "    (this is NOT necessarily where they died, which may be a hospital/aid station).\n\n"
        "FOR NON-COMBAT DEATHS (Accidental, Illness, Motor Vehicle, Drowning, etc.):\n"
        "  - Identify the location where the death or accident occurred (e.g. base camp, "
        "    training area, barracks, hospital, road, river, or civilian location).\n"
        "  - Do NOT search for war diary grid references, fire support bases, or combat incidents.\n"
        "  - There is no 'place of wounding' — use the death or incident location directly.\n"
        "  - If the death occurred at a base, camp, or hospital, that IS the location.\n"
        "  - If the location is merely a province or country-level (e.g. 'South Vietnam'), "
        "    that is sufficient — do NOT fabricate a specific grid reference or hamlet.\n\n"
        "PROCESS:\n"
        "  1. FIRST, check any authoritatively marked override section.  If it contains "
        "coordinates or a grid reference, use those as your starting point — but "
        "STILL search for and include location/place names.\n"
        "  2. Analyse all location-related information in the text, including:\n"
        "     - any location descriptions or geographic details\n"
        "     - any grid references, map sheet numbers, or UTM zones\n"
        "     - any military operation names (combat deaths only)\n"
        "     - any narrative or summary text\n"
        "     - any place names (village, hamlet, district, province)\n"
        "     - any fire support bases, rivers, roads, or landmarks\n"
        "     - any ARVN/US/Australian operational areas\n"
        "  3. Identify ALL location names in the text — villages, hamlets, districts,\n"
        "     provinces, FSB names, LZ names, rivers, rubber plantations, landmarks.\n"
        "  4. If a grid reference MGRS / UTM / partial coordinate appears anywhere "
        "in the text, extract it exactly as written.\n"
        "  5. Convert any full or partial grid reference into an approximate GPS "
        "coordinate when possible.\n"
        "  6. If no grid reference exists, use:\n"
        "     - Vietnam War 1:50,000 map sheets\n"
        "     - historical village/hamlet locations\n"
        "     - known AO boundaries\n"
        "     - documented operations to estimate the lowest-level location "
        "(village > hamlet > district > province).\n"
        "  7. Always output one single best-estimate GPS coordinate in decimal degrees.\n\n"
        "LOCATION NAME RULES (MANDATORY when location info exists):\n"
        "  - Extract ALL predominant physical place names found in the text.\n"
        "  - Include: villages, hamlets, districts, provinces, rivers, mountains, roads,\n"
        "    rubber plantations, landmarks, FSB names, LZ names.\n"
        "  - Do NOT omit location names just because you have GPS coordinates.\n"
        "  - Concatenate place names from smallest to largest (e.g. \"Ap Lo Gom, Phuoc Tuy\").\n"
        "  - Only omit location names if absolutely NO location info exists in the text.\n\n"
        "OUTPUT FORMAT (MANDATORY):\n"
        "Return a single line:\n"
        "  \"best_estimate_gps\": \"LAT, LON [GRID1, GRID2, ...] — location_names\"\n\n"
        "CRITICAL: The \" — location_names\" suffix is MANDATORY whenever any place\n"
        "name, landmark, FSB, LZ, village, hamlet, district, province, river, road,\n"
        "or rubber plantation is mentioned in the source text. DO NOT return bare\n"
        "GPS coordinates if location details exist.\n\n"
        "Rules:\n"
        "  - If grid fragments exist → include them in [brackets] before the location.\n"
        "  - If no grid fragments exist → output GPS then location names.\n"
        "  - If no estimate is possible → return an empty string.\n\n"
        "Examples:\n"
        "  \"best_estimate_gps\": \"16.533, 107.533 — Ap Lo Gom, Phuoc Tuy Province\"\n"
        "  \"best_estimate_gps\": \"10.512, 106.345 [YS478548] — Courtenay Rubber, FSB Flinders, Phuoc Tuy\"\n"
        "  \"best_estimate_gps\": \"11.221, 108.112 [48PYS1234] — near Song Rai River, Phuoc Tuy\"\n"
        "Return ONLY the output line — no commentary, no markdown, no explanation."
    )
    return (system, _USER_PROMPT_TEMPLATE.format(combined_text=combined_text))


def get_all_hotlinks_prompt(combined_text: str, valid_statuses: list[str] | None = None) -> tuple:
    """Return (system_instruction, user_prompt) to derive all five hotlink fields at once.

    If valid_statuses is provided, it overrides the default hardcoded list for
    the service_status field.  The fallback uses the first value in valid_statuses.
    """
    if valid_statuses is None:
        valid_statuses = ["Regular", "National Service", "Conscript", "Other"]

    _svc_list = ", ".join(valid_statuses)
    _svc_fallback = valid_statuses[0]

    system = (
        "Return ONLY a valid JSON object. No reasoning, no commentary, no markdown before the JSON.\n"
        "From the provided text, extract five fields and return them as a single JSON object.\n\n"
        "Fields to extract:\n"
        f"1. \"service_status\" — one of: {_svc_list}. "
        "Deduce from voluntary/compulsory enlistment evidence. "
        "DO NOT infer from corps, regiment, unit, rank, trade, or branch.\n"
        "2. \"place_of_death\" — concise location name a geographer can locate on a map. "
        "Output village/town/suburb, state/province, country. No narrative, terrain notes, "
        "grid references, or soldier's name. Example: Seymour, Victoria, Australia.\n"
        "3. \"circumstances_of_death\" — concise summary (max 100 words). "
        "FIRST identify fatality_type from source text. "
        "If COMBAT (KIA, DOW, enemy action) and Operation name present: begin with \"During Operation [Name], …\". "
        "Describe manner of death, enemy contact type, operational environment, fatal wound nature. "
        "If NON-COMBAT (Accidental, Illness, Disease, Motor Vehicle, Drowning, etc.): "
        "do NOT use 'During Operation' — describe the non-combat circumstances factually. "
        "No soldier's name or detailed location.\n"
        "4. \"unit_served_with\" — hierarchy string, comma-separated, [Sub-unit], [Parent Unit] order.\n"
        "  Apply nation/service shorthands (AU Army: Coy/Pl/Sec/Regt/Bn/Sqn/Tp/Bty/Bde; "
        "RAN: HMAS/Div/Dept/Br/Sqn/Flt; RAAF: Sqn/Wg/Flt/Sec/U/Gp. "
        "NZ Army: Coy/Pl/Sect/Regt/Bn/Sqn/Tp/Bty/Bde; RNZN: HMNZS; RNZAF: Sqn/Wg/Flt/Sect. "
        "US Army: Co/Plt/Sq/Regt/Bn/Sqdn/Trp/Btry/Bde; USN: USS; USAF: Sqdn/Wg/Gp/Flt/Sec).\n"
        "  Exclude country/service name from output. Preserve existing abbreviations (9RAR, 1RNZIR, 11 ACR).\n"
        "5. \"grid_reference\" — FIRST identify fatality_type from source text.\n"
        "  COMBAT DEATHS: best-estimate GPS for where the fatal INCIDENT occurred (place of wounding/action — NOT hospital/aid station).\n"
        "  NON-COMBAT DEATHS: GPS for where the death or accident occurred (base, camp, hospital, road, etc). Do NOT fabricate combat grid references.\n"
        "  FIRST check any authoritatively marked override section; if coordinates found there, use them as starting point.\n"
        "  Analyse all location fields, extract any MGRS/UTM/partial grid refs, convert to decimal GPS.\n"
        "  YOU MUST also extract place names: villages, hamlets, districts, provinces, FSB/LZ names,\n"
        "  rivers, roads, rubber plantations, landmarks. Concatenate smallest-to-largest.\n"
        "  Output as: <GPS> [GRID] — location_names\n"
        "  The \" — location_names\" suffix is MANDATORY when location info exists.\n"
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
