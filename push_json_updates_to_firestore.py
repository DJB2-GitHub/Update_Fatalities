import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

def push_updates(country_code: str, json_filepath: str, progress_callback=None) -> int:
    """
    Scans the given JSON file for records where update_to_firestore == "false".
    Pushes these records to Firestore under /countries/{country_code}/wars/vietnam/honor_roll
    using referenceID as the document ID. Updates the JSON file and Firestore field to "true".
    """
    if not os.path.exists(json_filepath):
        raise FileNotFoundError(f"Cannot find JSON file: {json_filepath}")

    # Initialize firebase_admin if not already initialized
    if not firebase_admin._apps:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        key_path = os.path.join(base_dir, "firebase-key.json")
        if not os.path.exists(key_path):
            raise FileNotFoundError(f"Cannot find Firebase service account key: {key_path}")
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
    
    db = firestore.client()
    
    with open(json_filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    records_to_update = []
    for record in data:
        status = record.get("record_status", {})
        val = status.get("update_to_firestore", True)
        if str(val).lower() == "false":
            records_to_update.append(record)
            
    total_to_update = len(records_to_update)
    if total_to_update == 0:
        return 0

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
                
    # Save updated JSON back to disk
    with open(json_filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    return updated_count
