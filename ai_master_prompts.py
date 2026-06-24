"""
AI Master Prompts
-----------------
This module contains the payload configurations for the 3 selectable AI Master Response architectures.
Each function returns a configuration dictionary that the execution engine in `update_fatalities.py` parses.
"""

def _get_json_schema():
    """Returns the strict OpenAPI 3.0 JSON schema required for structured data output."""
    return {
        "type": "OBJECT",
        "properties": {
            "full_name": {"type": "STRING"},
            "extra_unit_served_with": {
                "type": "OBJECT",
                "properties": {
                    "country": {"type": "STRING"},
                    "service": {"type": "STRING"},
                    "corps_or_branch": {"type": "STRING"},
                    "command_or_division": {"type": "STRING"},
                    "brigade_or_group": {"type": "STRING"},
                    "regiment_or_battalion": {"type": "STRING"},
                    "sub_unit": {"type": "STRING"},
                    "platoon_or_troop": {"type": "STRING"},
                    "section_or_squad": {"type": "STRING"},
                    "team_or_crew": {"type": "STRING"}
                }
            },
            "extra_derived_data": {
                "type": "OBJECT",
                "properties": {
                    "1_service_status": {"type": "STRING"},
                    "2_unit_served_with": {"type": "STRING"},
                    "3_operation_name": {"type": "STRING"},
                    "4_operational_tactical_setting": {"type": "STRING"},
                    "5_cause_of_death": {"type": "STRING"},
                    "6_grid_reference": {"type": "STRING"},
                    "7_map_sheet_or_utm_zone": {"type": "STRING"},
                    "8_location_description": {"type": "STRING"},
                    "9_unit_movements_prior_48hrs": {"type": "STRING"},
                    "10_associated_AARs_or_war_diaries": {"type": "STRING"},
                    "11_related_casualties": {"type": "STRING"},
                    "12_burial_and_repatriation": {"type": "STRING"},
                    "13_tank_APC_track_FSB_patrol_route_engineer_lane": {"type": "STRING"},
                    "14_probable_grid_and_archival_sources": {"type": "STRING"},
                    "15_notes_on_accuracy": {"type": "STRING"},
                    "references": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    },
                    "ai_respons": {"type": "STRING"}
                }
            }
        }
    }


def _get_archivist_prompt(params: dict) -> str:
    """Returns the detailed archivist prompt text."""
    country = params.get('country', '')
    svc = params.get('svc', '')
    sra = params.get('sra', {})
    name = params.get('name', '')
    dod = params.get('dod', '')
    dob = params.get('dob', '')
    rank = params.get('rank', '')
    unit = params.get('unit', '')
    ftype = params.get('ftype', '')

    return (
        f"As a military archivist / historian researching the detailed story behind the death of this soldier in the Vietnam War, "
        f"I require you to do deep research and complete as much as possible of the extra_derived_data output fields. It is imperative you approach this task to help paint a picture of all personal and tactical events surrounding his death.\\n"
        f"You will be provided the following input values to identify the soldier to be researched. If an input value is blank then ignore it in the research:\\n"
        f"country = {country}\\n"
        f"service number = {svc}\\n"
        f"service status = {sra.get('service_status', '')}\\n"
        f"full name = {name}\\n"
        f"sex = {sra.get('sex', '')}\\n"
        f"date of death = {dod}\\n"
        f"date of birth = {dob}\\n"
        f"rank = {rank}\\n"
        f"unit = {unit}\\n"
        f"fatality type = {ftype}\\n"
        f"Fill all fields using the provided values and best-effort military-archivist historical reconstruction.\\n"
        f"If a field cannot be determined, leave it empty.\\n"
        f"references must be historically credible and directly relevant.\\n"
        f"DERIVED FIELD \"2_unit_served_with\":\\n"
        f"Create a single-line summary by joining all NON-EMPTY hierarchy elements from \"extra_unit_served_with\" in the following order:\\n"
        f"country, service, corps_or_branch, command_or_division, brigade_or_group, regiment_or_battalion, sub_unit, platoon_or_troop, section_or_squad, team_or_crew\\n"
        f"Separate each element with \", \" and skip empty fields.\\n"
        f"Example:\\n"
        f"\"Australia, Australian Army, Royal Australian Infantry Corps, 1ATF, 4RAR, B Company, 5 Platoon\"\\n"
        f"DERIVED DATA REQUIREMENTS:\\n"
        f"2. Determine \"service_status\" as either \"Regular\" or \"Conscript\".\\n"
        f"3. Identify the military operation underway at the time of death.\\n"
        f"4. Provide a full operational and tactical setting including mission objectives, terrain, enemy situation, friendly force disposition, and a narrative summary.\\n"
        f"5. State the cause of death.\\n"
        f"6. Provide the exact or approximate grid reference.\\n"
        f"7. Identify the map sheet number and UTM zone.\\n"
        f"8. Provide a detailed location description.\\n"
        f"9. Reconstruct the unit's movements in the 48 hours prior.\\n"
        f"10. List any AARs, war diaries, contact reports, or casualty reports.\\n"
        f"11. Identify others killed or wounded in the same incident.\\n"
        f"12. Provide burial and repatriation details.\\n"
        f"13. Identify the tank/APC track, fire support base, patrol route, or engineer lane involved.\\n"
        f"14. If the exact grid is unavailable, provide the most probable grid and archival sources.\\n"
        f"15. Provide notes on accuracy and confidence level.\\n"
        f"16. Search for relevant references and return them as a list of strings."
    )


def get_master_response_option_a_payload(params: dict, is_live_search: bool) -> dict:
    """
    Option A: 1-Step JSON Schema (Fast/JSON)
    ----------------------------------------
    Architecture: 1-Step
    Features: 
    - Uses `responseSchema` to strictly enforce output JSON structure.
    - Google Search tools are dynamically included if `is_live_search` is True.
    - Extremely fast, guarantees JSON parser safety without markdown pollution.
    """
    system_text = (
        "You are a military archivist and historian specializing in the Vietnam War. "
        "You produce structured JSON output from research material and soldier identity values. "
        "You always return valid, parseable JSON exactly matching the requested schema."
    )
    user_prompt = _get_archivist_prompt(params)
    
    payload = {
        "systemInstruction": {"parts": [{"text": system_text}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
            "thinkingConfig": {"thinkingBudget": 0},
        }
    }
    if is_live_search:
        payload["tools"] = [{"google_search": {}}]
    else:
        payload["generationConfig"]["responseMimeType"] = "application/json"
        payload["generationConfig"]["responseSchema"] = _get_json_schema()

    return {
        "is_two_step": False,
        "payloads": [payload],
        "user_prompt": user_prompt
    }


def get_master_response_option_b_payloads(params: dict, is_live_search: bool) -> dict:
    """
    Option B: 2-Step Legacy (Research -> Structure)
    -----------------------------------------------
    Architecture: 2-Step
    Features:
    - Step 1 performs raw prose research (optionally using Google Search).
    - Step 2 formats the research into JSON (with Google Search forced OFF to avoid JSON corruption).
    """
    name = params.get('name', '')
    dod = params.get('dod', '')
    svc = params.get('svc', '')
    rank = params.get('rank', '')
    unit = params.get('unit', '')

    research_prompt = (
        f"Research the military history: What operation was {unit} engaged in on {dod} "
        f"in Vietnam? Who was {name} (service number {svc}, rank {rank}) and what were "
        f"the circumstances of their death on {dod}? Provide raw operational details, "
        f"unit movements, battle narrative, casualties, terrain, and tactical context. "
        f"Be comprehensive and factual. Provide all details you can find."
    )
    
    step1_payload = {
        "systemInstruction": {
            "parts": [{
                "text": "You are a military researcher specializing in the Vietnam War. Provide raw, detailed factual text in prose. No formatting, no markdown."
            }]
        },
        "contents": [{"parts": [{"text": research_prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048}
    }
    if is_live_search:
        step1_payload["tools"] = [{"google_search": {}}]

    system_text_step2 = (
        "You are a military archivist and historian specializing in the Vietnam War. "
        "You produce structured JSON output from provided research material and soldier "
        "identity values. You always return valid, parseable JSON exactly matching "
        "the requested schema."
    )
    
    user_prompt = _get_archivist_prompt(params)
    legacy_json_schema = '''
OUTPUT FORMAT:
{
  "full_name": "",
  "extra_unit_served_with": {
    "country": "",
    "service": "",
    "corps_or_branch": "",
    "command_or_division": "",
    "brigade_or_group": "",
    "regiment_or_battalion": "",
    "sub_unit": "",
    "platoon_or_troop": "",
    "section_or_squad": "",
    "team_or_crew": ""
  },
  "extra_derived_data": {
    "1_service_status": "",
    "2_unit_served_with": "",
    "3_operation_name": "",
    "4_operational_tactical_setting": "",
    "5_cause_of_death": "",
    "6_grid_reference": "",
    "7_map_sheet_or_utm_zone": "",
    "8_location_description": "",
    "9_unit_movements_prior_48hrs": "",
    "10_associated_AARs_or_war_diaries": "",
    "11_related_casualties": "",
    "12_burial_and_repatriation": "",
    "13_tank_APC_track_FSB_patrol_route_engineer_lane": "",
    "14_probable_grid_and_archival_sources": "",
    "15_notes_on_accuracy": "",
    "references": [],
    "ai_respons": ""
  }
}
'''
    full_user_prompt = user_prompt + legacy_json_schema

    step2_payload = {
        "systemInstruction": {"parts": [{"text": system_text_step2}]},
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        }
    }

    return {
        "is_two_step": True,
        "payloads": [step1_payload, step2_payload],
        "user_prompt": full_user_prompt
    }


def get_master_response_option_c_payload(params: dict, is_live_search: bool) -> dict:
    """
    Option C: 1-Step Narrative (Raw Prose)
    --------------------------------------
    Architecture: 1-Step
    Features:
    - Generates a raw narrative response (no JSON schema enforcement).
    - Historically used for non-testing datasets to get a rich text blob.
    """
    name = params.get('name', '')
    dod = params.get('dod', '')
    svc = params.get('svc', '')
    dob = params.get('dob', '')
    rank = params.get('rank', '')
    unit = params.get('unit', '')
    af = params.get('af', '')
    pod = params.get('pod', '')

    user_prompt = (
        "Using the values I provide in the placeholders below, generate a detailed narrative focused only on:\\n\\n"
        "1. The circumstances of death, clearly separated into:\\n"
        "   - confirmed facts\\n"
        "   - details supported by official or semi-official sources\\n"
        "   - reasonable inference based on context\\n"
        "   - what remains unknown\\n\\n"
        "2. The best available approximation of the place of death, using one of the following (whichever is most appropriate or best supported by sources):\\n"
        "   - GPS latitude/longitude\\n"
        "   - UTM coordinates\\n"
        "   - MGRS grid reference\\n\\n"
        "If the exact location is not documented, provide the closest verifiable location (such as a base, town, road, or landmark) and explain why this is the most accurate approximation.\\n\\n"
        "3. The individual's pre-service occupation, as recorded in official enlistment or memorial records.\\n\\n"
        "4. The enlistment type: whether they were a Regular soldier or a Conscript (e.g., National Service, Draft, or similar).\\n\\n"
        "Use only the values I supply.\\n"
        "Do not invent or alter identity details.\\n"
        "Present the answer in normal text, not structured data.\\n\\n"
        "Identity anchor values:\\n\\n"
        f"- Service Number: {svc}\\n"
        f"- Full Name: {name}\\n"
        f"- Date of Birth: {dob}\\n"
        f"- Date of Death: {dod}\\n"
        f"- Armed Forces: {af}\\n"
        f"- Rank: {rank}\\n"
        f"- Unit: {unit}\\n"
        f"- Place of Death: {pod}\\n"
        "- Fatality Type: *[leave blank for the model to determine from records]*"
    )

    payload = {
        "systemInstruction": {"parts": [{"text": "I am a highly skilled historian."}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048,
        }
    }
    if is_live_search:
        payload["tools"] = [{"google_search": {}}]

    return {
        "is_two_step": False,
        "payloads": [payload],
        "user_prompt": user_prompt
    }
