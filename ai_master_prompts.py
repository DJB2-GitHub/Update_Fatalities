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
    dod = params.get('dod', '')
    name = params.get('name', '')
    rank = params.get('rank', '')
    unit = params.get('unit', '')

    # Country-specific labels
    _army_map = {"AU": "Australian Army", "NZ": "New Zealand Army"}
    _army = _army_map.get(country_code, "Australian Army")

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

    if is_live_search:
        system_text = (
            f"You are a military historian specialising in {_army} personnel records "
            "and Vietnam War (1962–1972) fatality analysis. "
            "Your task is to RESEARCH the web for authoritative, verifiable information "
            "about a specific soldier's death. "
            "You MUST search these primary sources:\n"
            "- Australian War Memorial (awm.gov.au) — Roll of Honour\n"
            "- Virtual War Memorial Australia (vwma.org.au)\n"
            "- Department of Veterans' Affairs Nominal Rolls (dva.gov.au)\n"
            "- National Archives of Australia (naa.gov.au)\n"
            "- Contemporary newspaper archives (Trove, The Age, Sydney Morning Herald)\n"
            "- Published unit histories and AATTV records\n\n"
            "CRITICAL: You MUST retrieve the actual, documented facts. "
            "Do NOT fabricate or guess. "
            "If a fact is not found after thorough searching, mark it 'NOT_DOCUMENTED'. "
            "Distinguish clearly between facts found in sources and inferences. "
            "Internal memory may be used ONLY as a secondary cross-reference, "
            "never as the primary source."
        )

        user_prompt = (
            "I request your expertise to research and extract comprehensive, "
            "verifiable information regarding the death of the following soldier. "
            "You MUST search the web using the authoritative sources listed in your "
            "system instructions.\\n\\n"
            f"Authoritative Master Data (from Australian War Memorial):\\n"
            f"- Army Country: {params.get('country', 'Australia')}\\n"
            f"- Service Number: {svc}\\n"
            f"- Surname: {surname}\\n"
            f"- Date of Death: {dod}\\n\\n"
            f"Supplementary High-Confidence Data:\\n"
            f"- Full Name: {name}\\n"
            f"- Rank: {rank}\\n"
            f"- Unit: {unit}\\n\\n"
            f"Research Requirements:\\n"
            f"Search the web for all information relating to the soldier's death: "
            f"cause, location, circumstances, operation, unit involvement, eyewitness accounts, "
            f"medical treatment, burial, repatriation, awards, investigations, and historical "
            f"analysis.\\n\\n"
            f"{_svc_hint}"
            f"For every fact you report, cite the specific source (AWM, VWMA, DVA, etc.). "
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
            "A missing fact is better than a false fact."
        )

        user_prompt = (
            "I request your expertise to extract comprehensive and precise information "
            f"regarding the death of the following soldier:\\n\\n"
            f"Authoritative Master Data:\\n"
            f"- Army Country: {params.get('country', 'Australia')}\\n"
            f"- Service Number: {svc}\\n"
            f"- Surname: {surname}\\n"
            f"- Date of Death: {dod}\\n\\n"
            f"Supplementary High-Confidence Data:\\n"
            f"- Full Name: {name}\\n"
            f"- Rank: {rank}\\n"
            f"- Unit: {unit}\\n\\n"
            f"Extraction Requirements:\\n"
            f"Search LLM memory only for all information relating to the soldier's death: "
            f"cause, location, circumstances, operation, unit involvement, eyewitness accounts, "
            f"medical treatment, burial, repatriation, awards, investigations, and historical "
            f"analysis.\\n\\n"
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
