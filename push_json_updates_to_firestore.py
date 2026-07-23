import os
import json
import firebase_admin
from firebase_admin import credentials, firestore


def _init_firebase():
    """Lazy-init Firebase. Call once before any Firestore operation."""
    if not firebase_admin._apps:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        key_path = os.path.join(base_dir, "onthisdayinvn-firebase-key.json")
        if not os.path.exists(key_path):
            raise FileNotFoundError(f"Cannot find Firebase service account key: {key_path}")
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)


def _load_records_to_update(json_filepath: str) -> list[dict]:
    """Return records with update_to_firestore == 'false'."""
    if not os.path.exists(json_filepath):
        raise FileNotFoundError(f"Cannot find JSON file: {json_filepath}")
    with open(json_filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return [r for r in data if str(r.get("record_status", {}).get("update_to_firestore", True)).lower() == "false"]


def count_updates(json_filepath: str) -> int:
    """Return the number of records flagged to update. Does NOT touch Firestore."""
    return len(_load_records_to_update(json_filepath))


def push_updates(country_code: str, json_filepath: str, progress_callback=None, limit: int = None) -> int:
    """
    Scans the given JSON file for records where update_to_firestore == "false".
    Pushes these records to Firestore under /countries/{country_code}/wars/vietnam/honor_roll
    using referenceID as the document ID. Updates the JSON file and Firestore field to "true".

    If *limit* is given, only the first *limit* records are pushed.
    """
    _init_firebase()
    db = firestore.client(database_id='onthisdayinvn')

    records_to_update = _load_records_to_update(json_filepath)
    if limit is not None and limit > 0:
        records_to_update = records_to_update[:limit]

    total_to_update = len(records_to_update)
    if total_to_update == 0:
        return 0

    # Reload the full file so we can mark the pushed records in-place
    with open(json_filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Build a lookup of records to push by referenceID for marking
    push_ids = {r["referenceID"] for r in records_to_update if r.get("referenceID")}

    collection_path = f"countries/{country_code}/wars/vietnam/honor_roll"
    updated_count = 0

    for i, record in enumerate(records_to_update, 1):
        ref_id = record.get("referenceID")
        if not ref_id:
            continue

        # Update the local dictionary to true before pushing
        if "record_status" not in record:
            record["record_status"] = {}
        record["record_status"]["update_to_firestore"] = "true"

        doc_ref = db.collection(collection_path).document(ref_id)
        doc_ref.set(record)

        updated_count += 1
        if progress_callback:
            progress_callback(updated_count, total_to_update)

    # Mark pushed records in the full dataset before saving
    for r in data:
        if r.get("referenceID") in push_ids:
            if "record_status" not in r:
                r["record_status"] = {}
            r["record_status"]["update_to_firestore"] = "true"

    # Save updated JSON back to disk
    with open(json_filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return updated_count
