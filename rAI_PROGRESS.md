# rAI_PROGRESS.md

## Session Summary (Completed)
1. **AI Pipeline Consolidation**: Migrated the legacy 2-step AI generation pipeline into a robust, 1-Step Architecture using `responseSchema` and exponential backoff (retries for 503/429 errors).
2. **Payload Modularisation**: Extracted all AI prompt and schema logic out of the UI into a dedicated `ai_master_prompts.py` module. Created three dynamically selectable API payload options (A, B, and C).
3. **UI Integration**: Added a UI dropdown to select the payload option at runtime, alongside a "Live Search" checkbox.
4. **Coordinate Engine Extraction**: Physically extracted complex GPS conversion logic (Vietnam-era MGRS, DMS, WGS84) out of the Tkinter controller and into a dedicated `coords.py` module.
5. **Session State Isolation**: Moved the session-tracking code out of the dataset directory and safely encapsulated it in `session_manager.py`. It now saves `session.json` directly to the python application root, tracking `pos`, `search`, `ai_option`, and `live_search` state per-dataset.
6. **Code Cleanup**: Removed all orphaned/legacy networking code (`_ai_location_lookup`, `_ai_place_lookup`) and refactored bulky loops using Python dictionary/list comprehensions for cleaner syntax.

## Current System State
* **Main UI Controller**: `update_fatalities.py` is now strictly focused on DOM manipulation, Tkinter rendering, and callback routing.
* **Payload Generation**: Handled entirely by `ai_master_prompts.py`, exporting dynamic configuration dicts.
* **Coordinate Parsing**: Handled entirely by `coords.py`.
* **State Management**: Session states are handled globally by `session_manager.py` (saving to `session.json` in the root app directory).
* **Data Targeting**: Target files (`AU_fatalities.json`, `NZ_fatalities.json`) are pulled from `FATALITY_FILE_DIRECTORY` defined in `.env`.

## Next-Step Checklist
* [ ] **User Verification**: Test the full UI workflow, including navigating records, running the AI query with different payload options, and applying coordinates.
* [ ] **Review AI Outputs**: Validate the precision and response time of the 1-Step JSON schema vs the older 2-Step pipeline.
* [ ] **Firestore Sync**: Perform a test synchronization of the derived data back to the Firebase backend.
* [ ] **Production Run**: Resume normal operational curation.
