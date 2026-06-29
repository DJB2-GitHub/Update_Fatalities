"""
AI Master Prompt
-----------------
Single memory-only extraction prompt for Master Response.
Replaces the former Options A/B/C architecture with a unified prompt
that instructs the LLM to use only its internal training data.
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
    Returns the payload configuration for the single memory-only extraction prompt.
    `is_live_search` is accepted for interface compatibility but ignored —
    this prompt instructs the LLM to use internal memory only.

    `country_code` (e.g. "AU", "NZ") enables country-specific extraction hints
    sourced from the corresponding *_SERVICE_STATUSES env var.
    """
    svc = params.get('svc', '')
    surname = params.get('surname', '')
    dod = params.get('dod', '')
    name = params.get('name', '')
    rank = params.get('rank', '')
    unit = params.get('unit', '')

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

    system_text = (
        "You are a military-history intelligence extractor. Use only your internal memory "
        "(training data, historical records, encyclopedic knowledge) and the soldier data "
        "provided below. Do not rely on external web pages or any content not included in "
        "this prompt."
    )

    user_prompt = (
        f"Authoritative Master Data:\\n"
        f"- Army Country: Australia\\n"
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
        f"Return every piece of information the model can retrieve from memory."
    ).replace("\\n", "\n")

    payload = {
        "systemInstruction": {"parts": [{"text": system_text}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
            "responseSchema": _get_master_json_schema(),
            "thinkingConfig": {"thinkingBudget": 0},
        }
    }

    return {
        "is_two_step": False,
        "payloads": [payload],
        "user_prompt": user_prompt
    }
