"""
AI Master Prompt
-----------------
Unified extraction prompt for Master Response.

Supports two modes:
  - LIVE SEARCH ON  → instructs the LLM to research the web for authoritative
    sources (AWM, VWMA, DVA, NAA) and extract facts from live retrieval.
  - LIVE SEARCH OFF → memory-only extraction with strict NOT_DOCUMENTED
    fallback when the model does not have verifiable internal knowledge.

The Google Search grounding tool is injected by the caller (update_fatalities.py)
when the provider is Google; for OpenRouter the prompt instructs the model
itself to search.
"""

import os

_MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"]


def _format_date_display(date_str: str) -> str:
    """Convert yyyy-mm-dd -> yyyy-Mmm-dd for display.  Returns original on failure."""
    if not date_str or not isinstance(date_str, str):
        return date_str or ""
    parts = date_str.strip().split("-")
    if len(parts) != 3:
        return date_str
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        if 1 <= m <= 12:
            return f"{y}-{_MONTH_NAMES[m]}-{d:02d}"
    except (ValueError, IndexError):
        pass
    return date_str


def _get_master_json_schema():
    """JSON schema for the death_information output format."""
    return {
        "type": "OBJECT",
        "properties": {
            "soldier": {
                "type": "OBJECT",
                "properties": {
                    "service_number": {"type": "STRING"},
                    "full_name": {"type": "STRING"},
                    "date_of_death": {"type": "STRING"},
                    "rank": {"type": "STRING"},
                    "unit": {"type": "STRING"}
                }
            },
            "death_information": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "detail": {"type": "STRING"},
                        "confidence": {"type": "STRING"}
                    }
                }
            },
            "summary": {"type": "STRING"}
        }
    }


def get_master_response_payload(params: dict, is_live_search: bool, country_code: str = "") -> dict:
    """
    Returns the payload configuration for the extraction prompt.

    When `is_live_search` is True the prompt instructs the model to search
    the web for authoritative sources (AWM, VWMA, DVA, NAA, etc.) and
    extract facts from live retrieval — internal memory is only a fallback.
    Google Search grounding must be enabled separately by the caller for
    Gemini providers.

    When False the prompt falls back to memory-only with strict
    NOT_DOCUMENTED guardrails.

    `country_code` (e.g. "AU", "NZ") enables country-specific extraction
    hints sourced from the corresponding *_SERVICE_STATUSES env var.
    """
    svc = params.get('svc', '')
    surname = params.get('surname', '')
    dod = _format_date_display(params.get('dod', ''))
    name = params.get('name', '')
    rank = params.get('rank', '')
    unit = params.get('unit', '')

    # Country-specific labels
    _army_map = {"AU": "Australian Army", "NZ": "New Zealand Army"}
    _army = _army_map.get(country_code, "Australian Army")

    # Country-specific authoritative sources, labels, and localisation
    _srcs_au = (
        "- Australian War Memorial (awm.gov.au) — Roll of Honour\n"
        "- Virtual War Memorial Australia (vwma.org.au)\n"
        "- Department of Veterans' Affairs Nominal Rolls (dva.gov.au)\n"
        "- National Archives of Australia (naa.gov.au)\n"
        "- Contemporary newspaper archives (Trove, The Age, Sydney Morning Herald)\n"
        "- Published unit histories and AATTV records"
    )
    _srcs_nz = (
        "- Auckland War Memorial Museum — Online Cenotaph (aucklandmuseum.com)\n"
        "- New Zealand History (nzhistory.govt.nz)\n"
        "- Archives New Zealand (archives.govt.nz)\n"
        "- Vietnam War New Zealand (vietnamwar.govt.nz)\n"
        "- Contemporary newspaper archives (Papers Past, NZ Herald)\n"
        "- Published unit histories and RNZIR/NZ Artillery records"
    )
    if country_code == "NZ":
        _sources = _srcs_nz
        _auth_label = "Auckland War Memorial Museum — Online Cenotaph"
        _cite_sources = "Online Cenotaph, nzhistory.govt.nz, Archives NZ, etc."
        _home_country = "in New Zealand"
    else:
        _sources = _srcs_au
        _auth_label = "Australian War Memorial"
        _cite_sources = "AWM, VWMA, DVA, etc."
        _home_country = "in Australia"

    # Country-specific service_status hint (only when env var has >1 value)
    _svc_hint = ""
    if country_code:
        _svc_raw = os.environ.get(f"{country_code}_SERVICE_STATUSES", "").strip()
        if _svc_raw:
            _svc_vals = [v.strip() for v in _svc_raw.split(",") if v.strip()]
            if len(_svc_vals) > 1:
                # e.g. "Regular or National Service, else Unassigned"
                _svc_hint = (
                    f"Additionally extract:\\n"
                    f"- Service Status {{"
                    f"{' or '.join(_svc_vals[:-1])}"
                    f"{', else ' if len(_svc_vals) > 1 else ''}"
                    f"{_svc_vals[-1]}"
                    f"}}\\n\\n"
                )

    # Shared multiple-match guidance, injected after All Known Details
    _multi_match = (
        "IMPORTANT — Multiple Matches: If the authoritative identification "
        "(Surname + Date of Death) matches more than one soldier, "
        "return each soldier's findings as a separate response, "
        "labelled by Full Name and Service Number."
    )

    if is_live_search:
        system_text = (
            f"You are a military historian specialising in {_army} personnel records "
            "and Vietnam War (1962–1972) fatality analysis. "
            "Your task is to RESEARCH the web for authoritative, verifiable information "
            "about a specific soldier's death. "
            "You MUST search these primary sources:\n"
            f"{_sources}\n\n"
            "CRITICAL: You MUST retrieve the actual, documented facts. "
            "Do NOT fabricate or guess. "
            "If a fact is not found after thorough searching, mark it 'NOT_DOCUMENTED'. "
            "Distinguish clearly between facts found in sources and inferences. "
            "Internal memory may be used ONLY as a secondary cross-reference, "
            "never as the primary source.\n\n"
            "IMPORTANT: Not all Vietnam War fatalities died in combat or in Vietnam. "
            "Many died from illness (cancer, heart attack, disease), accidents "
            "(motor vehicle, training), or by natural causes — sometimes "
            f"{_home_country}, sometimes after returning from deployment. "
            "These ARE classified as Vietnam War fatalities if their death was "
            "attributable to service. "
            "Do NOT default to assuming a combat or in-theatre death — "
            "search broadly and follow the evidence wherever it leads."
        )

        user_prompt = (
            "Identify the soldier using these authoritative fields, "
            "then extract ALL details for that soldier. "
            "You MUST search the web using the sources listed in your "
            "system instructions.\\n\\n"
            f"Authoritative Identification ({_auth_label}):\\n"
            f"- Army Country: {params.get('country', 'Australia')}\\n"
            f"- War: Vietnam War (1962–1972)\\n"
            f"- Surname: {surname}\\n"
            f"- Date of Death: {dod}\\n\\n"
            f"All Known Details:\\n"
            f"- Service Number: {svc}\\n"
            f"- Full Name: {name}\\n"
            f"- Rank: {rank}\\n"
            f"- Unit: {unit}\\n\\n"
            f"{_multi_match}\\n\\n"
            f"Research Requirements:\\n"
            f"Search the web for all information relating to the soldier's death: "
            f"cause, location, circumstances, operation (if applicable), unit involvement, "
            f"eyewitness accounts, medical treatment, burial, repatriation, awards, "
            f"investigations, and historical analysis. "
            f"The soldier may have died from illness, accident, or natural causes "
            f"({_home_country} or elsewhere), not necessarily in combat. "
            f"Do NOT assume a combat or in-theatre death — search broadly and "
            f"follow the evidence wherever it leads.\\n\\n"
            f"{_svc_hint}"
            f"For every fact you report, cite the specific source ({_cite_sources}). "
            f"If a detail cannot be verified from authoritative sources, mark it NOT_DOCUMENTED. "
            f"Do not invent or assume facts."
        ).replace("\\n", "\n")
    else:
        system_text = (
            f"You are a military historian specialising in {_army} personnel records "
            "and Vietnam War (1962–1972) fatality analysis. Use only your internal "
            "memory (training data, historical records, encyclopedic knowledge) and "
            "the soldier data provided below. Do not rely on external web pages or "
            "any content not included in this prompt.\n\n"
            "CRITICAL: If you do NOT have verifiable knowledge of a specific fact, "
            "you MUST return 'NOT_DOCUMENTED' for that detail. Do NOT fabricate, "
            "guess, or construct plausible-sounding narratives. "
            "A missing fact is better than a false fact.\n\n"
            "IMPORTANT: Not all Vietnam War fatalities died in combat or in Vietnam. "
            "Many died from illness (cancer, heart attack, disease), accidents "
            "(motor vehicle, training), or by natural causes — sometimes "
            f"{_home_country}. "
            "Do NOT default to assuming a combat or in-theatre death — "
            "search your memory broadly and follow the evidence wherever it leads."
        )

        user_prompt = (
            "Identify the soldier using these authoritative fields, "
            "then extract ALL details for that soldier from your memory.\\n\\n"
            f"Authoritative Identification ({_auth_label}):\\n"
            f"- Army Country: {params.get('country', 'Australia')}\\n"
            f"- War: Vietnam War (1962–1972)\\n"
            f"- Surname: {surname}\\n"
            f"- Date of Death: {dod}\\n\\n"
            f"All Known Details:\\n"
            f"- Service Number: {svc}\\n"
            f"- Full Name: {name}\\n"
            f"- Rank: {rank}\\n"
            f"- Unit: {unit}\\n\\n"
            f"{_multi_match}\\n\\n"
            f"Extraction Requirements:\\n"
            f"Search LLM memory only for all information relating to the soldier's death: "
            f"cause, location, circumstances, operation (if applicable), unit involvement, "
            f"eyewitness accounts, medical treatment, burial, repatriation, awards, "
            f"investigations, and historical analysis. "
            f"The soldier may have died from illness, accident, or natural causes "
            f"({_home_country} or elsewhere), not necessarily in combat. "
            f"Do NOT assume a combat or in-theatre death — search your memory "
            f"broadly and follow the evidence wherever it leads.\\n\\n"
            f"{_svc_hint}"
            f"Return every piece of information the model can retrieve from memory. "
            f"If you are not certain about any detail, return NOT_DOCUMENTED for that field."
        ).replace("\\n", "\n")

    payload = {
        "systemInstruction": {"parts": [{"text": system_text}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
            "responseSchema": _get_master_json_schema(),
            "thinkingConfig": {"thinkingBudget": 0},
        }
    }

    result: dict = {
        "is_two_step": False,
        "payloads": [payload],
        "system_text": system_text,
        "user_prompt": user_prompt,
    }

    # For Google Gemini: inject Google Search grounding tool when live search is on.
    # The caller (update_fatalities.py) reads this flag and adds tools to the
    # Gemini API request.  OpenRouter uses its own web_search plugin instead.
    if is_live_search:
        result["google_search_grounding"] = True

    return result
