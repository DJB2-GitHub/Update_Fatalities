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
    if valid_statuses is None:
        valid_statuses = ["Regular", "National Service", "Conscript", "Other"]
    _svc_list = ", ".join(valid_statuses)

    system = (
        f"Determine the service status. Valid values: {_svc_list}.\n"
        "Look for terms like Regular, National Service, Nasho, Conscript, volunteer, conscription.\n"
        "Return ONLY the value, nothing else.\n\n"
        + _SHARED_RULES
    )
    return (system, _USER_PROMPT_TEMPLATE.format(combined_text=combined_text))


def get_place_of_death_prompt(combined_text: str) -> tuple:
    system = (
        "Find WHERE the death occurred.\n"
        "Look for the death location / place of death — NOT burial, birth, memorial, or repatriation sites.\n"
        "Format: village/town/suburb, state/province, country.\n"
        "Example: Nui Dat, Phuoc Tuy Province, South Vietnam.\n"
        "If death occurred in Australia after return, output the Australian location.\n"
        "If not found, return empty string.\n\n"
        + _SHARED_RULES
    )
    return (system, _USER_PROMPT_TEMPLATE.format(combined_text=combined_text))


def get_circumstances_of_death_prompt(combined_text: str) -> tuple:
    system = (
        "Write a SHORT factual summary (max 100 words) of how the person died.\n"
        "If an Operation name is mentioned, start with: During Operation [Name], ...\n"
        "No soldier name or detailed location.\n\n"
        + _SHARED_RULES
    )
    return (system, _USER_PROMPT_TEMPLATE.format(combined_text=combined_text))


def get_unit_served_with_prompt(combined_text: str) -> tuple:
    system = (
        "Extract the unit hierarchy as written in the text.\n"
        "Preserve abbreviations (9RAR, 1RNZIR, 1st APC Sqn, HMAS, etc).\n"
        "Remove country/service prefix (Australian Army, RAN, US Army, etc).\n"
        "Output as comma-separated string. Example: B Sqn, 3 Cav Regt.\n\n"
        + _SHARED_RULES
    )
    return (system, _USER_PROMPT_TEMPLATE.format(combined_text=combined_text))


def get_grid_reference_prompt(combined_text: str) -> tuple:
    system = (
        "Find WHERE the death or incident took place.\n"
        "Look specifically for the death location / incident location in the text — "
        "NOT burial places, birth places, memorials, or repatriation locations.\n"
        "If GPS or MGRS coordinates exist for the death/incident site, output them first, "
        "then \" — \" and the place names (village, district, province, country).\n"
        "If only place names are found, output just the place names.\n"
        "Example: 10.512, 106.345 [YS478548] — Nui Dat, Phuoc Tuy Province, South Vietnam.\n"
        "If the death occurred in Australia after return, output the Australian location.\n"
        "If nothing is found, return empty string.\n\n"
        + _SHARED_RULES
    )
    return (system, _USER_PROMPT_TEMPLATE.format(combined_text=combined_text))


def get_all_hotlinks_prompt(combined_text: str, valid_statuses: list[str] | None = None) -> tuple:
    """Return (system_instruction, user_prompt) to derive all five hotlink fields at once.

    Simplified: reads the text directly, treats everything (including JSON-like content)
    as plain text, extracts facts without complex reasoning.
    """
    if valid_statuses is None:
        valid_statuses = ["Regular", "National Service", "Conscript", "Other"]
    _svc_list = ", ".join(valid_statuses)

    system = (
        "IMPORTANT: The source text may contain markdown, JSON, or mixed formatting. "
        "Treat it ALL as plain text — read it like a human reads a document. "
        "Do NOT get distracted by formatting. Just look for the facts.\n\n"
        "Extract these five fields and return them as a single JSON object:\n\n"
        f"1. \"service_status\" — one of: {_svc_list}. "
        "Look for terms like Regular, National Service, Nasho, Conscript.\n"
        "2. \"place_of_death\" — WHERE the death occurred (NOT burial/birth/memorial sites). town, state, country.\n"
        "3. \"circumstances_of_death\" — short factual summary (max 100 words) of how the person died.\n"
        "4. \"unit_served_with\" — unit hierarchy as written in the text. Preserve abbreviations.\n"
        "5. \"grid_reference\" — death/incident location coordinates or place names "
        "(NOT burial/birth/memorial sites). Include GPS/MGRS if present.\n\n"
        "If a field's information is not in the text, use an empty string.\n"
        "Output ONLY the JSON object. No markdown fences, no commentary, nothing else.\n\n"
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
