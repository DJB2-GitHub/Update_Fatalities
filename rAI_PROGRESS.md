# Session Progress & Next Steps

## Progress Summary
* **Configuration Externalization**: Extracted file paths and critical environment variables (`FATALITY_FILE_DIRECTORY`, `FILES_AVAILABLE_FOR_UPDATE`, and application metadata) into a `.env` file.
* **Windowless Entry Point**: Created `main.pyw` to launch the Tkinter application without a background console on Windows. Implemented a fallback GUI error dialog for fatal startup crashes.
* **Refactored Core Logic**: Updated `main.py` and `update_fatalities.py` to securely load configuration parameters from the `.env` file rather than relying on hardcoded variables.
* **Version Control Updates**: Updated `.gitignore` to ensure the `.env` file remains local and is never committed to the repository.
* **Dual-Mode Data Pipeline**: `load_config()` now returns live and testing dataset groups from `.env` via `FILES_AVAILABLE_FOR_UPDATE` and `TEST_FILES_AVAILABLE_FOR_UPDATE`.
* **Grouped Main Menu**: `MainMenu` presents datasets under "Live OnThis Day app" and "Testing OnThisDay app expanded dataset" headings with separators.
* **Custom Modal Titles**: `UpdateFatalities` accepts a `modal_title` parameter so testing windows display descriptive titles.
* **List Field Editing**: Fields containing list values (e.g. `youtube_links`) render as multi-line `tk.Text` widgets; values are serialized/deserialized with newline separators.
* **Extended Editable Fields**: `service_status` is now editable alongside `derived_details` fields. Coordinate GPS validation skips pure-alphabetic placeholder text.
* **Testing AI Mode**: When file path contains "testing", the AI side panel uses a structured archivist system prompt (8192 token budget) targeting an `extra_derived_data` JSON schema. Responses are stripped of markdown code fences and pretty-printed.
* **Schema-Aware Identity Read**: Testing mode reads identity fields from `serviceRecordAuthority` and derives Armed Forces from the `referenceID` prefix (AU → "Australian Armed Forces", NZ → "New Zealand Armed Forces"). Record confirmation uses `referenceID`.
* **Testing Datasets**: Added `testing_data/AU_fatalities_testing.json` and `testing_data/NZ_fatalities_testing.json` with the expanded JSON structure.
* **Repository Hygiene**: Added `.antigravityignore` for IDE, build, and environment file exclusions.

## Current System State
* **Architectural Rule – Configuration**: The application strictly adheres to an environment-driven model. No file paths or sensitive keys are hardcoded.
* **Architectural Rule – Execution**: `main.pyw` is the designated entry point for desktop use.
* **Architectural Rule – Dual Dataset**: `.env` must define both `FILES_AVAILABLE_FOR_UPDATE` (live) and optionally `TEST_FILES_AVAILABLE_FOR_UPDATE` / `TEST_FATALITY_FILE_DIRECTORY` (testing). The app gracefully handles missing testing config.
* **Architectural Rule – AI Mode Switching**: The editor selects prompt strategy based on the presence of "testing" in the file path. Testing datasets use a structured JSON archivist prompt; live datasets use the narrative historian prompt.
* **Critical Variables**: `FATALITY_FILE_DIRECTORY`, `FILES_AVAILABLE_FOR_UPDATE`, `TEST_FATALITY_FILE_DIRECTORY`, `TEST_FILES_AVAILABLE_FOR_UPDATE`, and `GEMINI_API_KEY` must be correctly defined in `.env`.

## Absolute Next-Step Checklist
* [ ] Verify `.env` includes `TEST_FATALITY_FILE_DIRECTORY` and `TEST_FILES_AVAILABLE_FOR_UPDATE` keys pointing to the `testing_data/` directory.
* [ ] Run `main.pyw` and confirm both "Live OnThis Day app" and "Testing OnThisDay app expanded dataset" sections appear in the Main Menu.
* [ ] Open a testing dataset record and confirm the AI side panel uses the structured JSON archivist prompt (8192 tokens, JSON output schema).
* [ ] Open a live dataset record and confirm the AI side panel uses the original narrative historian prompt (2048 tokens).
* [ ] Edit a `youtube_links` list field and verify multi-line text entry saves correctly as a JSON array.
* [ ] Edit a `service_status` field and verify the change persists on save.
* [ ] Enter a pure-alphabetic placeholder in a GPS/coordinate field and confirm no validation error dialog appears.
* [ ] Confirm the confirmation dialog displays `referenceID` rather than a positional index.
