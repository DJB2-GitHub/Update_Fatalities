# AI Session Progress & Next Steps

## Session Summary
- **Confirmed `rank` editable change already pushed** (`85382aa`: "feat: make rank field editable in Update Fatalities modal").
- **Updated `rAI_PROGRESS.md` checklist** to reflect completed items; committed & pushed (`dcd6b07`).
- **Fixed backup-to-OneDrive bug**: `_backup_files` called `coords._load_json(filename)` which reads local disk files — these don't exist. Replaced with actual Firestore fetch via `db.collection("countries/{cc}/wars/vietnam/honor_roll").stream()`, deriving country code from filename prefix (`AU_fatalities` → `AU`). Also added `_init_firebase` + `firebase_admin.firestore` imports to `main.py`.

## Current System State
- **Firestore database**: Project `djb-onthisday`, database `onthisday` (never re-create). All Firestore client calls use `firestore.client(database_id='onthisday')`.
- **Backup flow** (`main.py`, `_backup_files`): `_init_firebase()` → `firestore.client(database_id='onthisday')` → for each file in `FILES_AVAILABLE_FOR_UPDATE`, derive country code → `db.collection("countries/{cc}/wars/vietnam/honor_roll").stream()` → JSON dump with timestamp → prune to 3 most recent.
- **Push flow**: `count_updates()` → `_ask_number()` dialog → threaded `push_updates(country_code, path, callback, limit=N)` → result dialog.
- **Editable fields in Update Fatalities modal**: `derived_details.*`, `service_status`, `unit`, `fatality_type`, `rank`.

## Absolute Next-Step Checklist
- [ ] Commit the backup-to-OneDrive fix and push to GitHub.
- [ ] Launch the app, run the backup, confirm AU/NZ data is fetched from Firestore and saved to OneDrive sync folder.

**Incomplete work**: None.
