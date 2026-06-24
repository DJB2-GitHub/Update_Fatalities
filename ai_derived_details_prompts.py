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
    "Extract the requested information based on your system instructions from the following text:\n\n"
    "```text\n"
    "{combined_text}\n"
    "```"
)


def get_service_status_prompt(combined_text: str) -> tuple:
    """Return (system_instruction, user_prompt) to derive service_status."""
    system = (
        "Your task is to extract a single value called \"service_status\" from the provided text.\n\n"
        "Valid outputs:\n"
        "- Regular\n"
        "- Conscript\n"
        "- Other\n\n"
        "Extraction rules (in order of priority):\n\n"
        "1. If a field named \"authoritative_ai_override\" appears anywhere in the text:\n"
        "     - Treat its value as free-form notes.\n"
        "     - Search ONLY inside this field for the words \"Regular\", \"Conscript\", or \"Other\".\n"
        "     - If one of these appears, return it exactly.\n"
        "     - If none appear, ignore this field completely.\n\n"
        "2. Else if the key \"1_service_status\" appears anywhere in the text and contains one of the valid values, return it exactly.\n\n"
        "3. Else search ALL provided text for evidence indicating Regular or Conscript status:\n"
        "     - DO NOT infer service status from corps, regiment, unit, rank, trade, or branch.\n"
        "     - If the text describes voluntary enlistment, Regular Army, Regular soldier, or similar, return \"Regular\".\n"
        "     - If the text describes conscription, national service, call-up, ballot, Nasho, or compulsory enlistment, return \"Conscript\".\n\n"
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
        "From the provided text, extract the soldier's \"unit_served_with\" hierarchy:\n"
        "country → service → corps/branch → regiment/battalion → sub-unit → "
        "platoon/troop → section/squad → team/crew.\n\n"
        "Deduce the country's military and automatically apply that nation's standard "
        "abbreviation conventions:\n"
        "- Australian Army: Coy, Pl, Sec\n"
        "- US Army: Co, Plt, Sq\n"
        "- British Army: Coy, Pl, Sect\n\n"
        "Preserve any abbreviations already present (e.g., \"9RAR\").\n\n"
        "Output a single comma-separated string in descending organisational order, e.g.:\n"
        "\"Australian Army, 9RAR, C Coy, 8 Pl\"\n\n"
        "Include only elements that appear in the text.\n\n"
        + _SHARED_RULES
    )
    return (system, _USER_PROMPT_TEMPLATE.format(combined_text=combined_text))


def get_all_hotlinks_prompt(combined_text: str) -> tuple:
    """Return (system_instruction, user_prompt) to derive all four hotlink fields at once."""
    system = (
        "From the provided text, extract four fields and return them as a single JSON object.\n\n"
        "Fields to extract:\n"
        "1. \"service_status\" — one of: Regular, Conscript, Other. "
        "Deduce from voluntary/compulsory enlistment evidence. "
        "DO NOT infer from corps, regiment, unit, rank, trade, or branch.\n"
        "2. \"place_of_death\" — concise summary (max 40 words). Start with country, then province/state, "
        "then geographic cues. No grid references or soldier's name.\n"
        "3. \"circumstances_of_death\" — concise summary (max 100 words). "
        "If an Operation name is present, begin with \"During Operation [Name], …\". "
        "Describe manner of death, enemy contact type, operational environment, fatal wound nature. "
        "No soldier's name or detailed location.\n"
        "4. \"unit_served_with\" — hierarchy string: country → service → corps/branch → "
        "regiment/battalion → sub-unit. Comma-separated, descending order.\n\n"
        "Return format:\n"
        "{\n"
        "  \"service_status\": \"<value>\",\n"
        "  \"place_of_death\": \"<value>\",\n"
        "  \"circumstances_of_death\": \"<value>\",\n"
        "  \"unit_served_with\": \"<value>\"\n"
        "}\n\n"
        + _SHARED_RULES
    )
    return (system, _USER_PROMPT_TEMPLATE.format(combined_text=combined_text))


# ── Field → prompt function mapping ──
FIELD_PROMPTS = {
    "service_status":          get_service_status_prompt,
    "place_of_death":          get_place_of_death_prompt,
    "circumstances_of_death":  get_circumstances_of_death_prompt,
    "unit_served_with":        get_unit_served_with_prompt,
}
