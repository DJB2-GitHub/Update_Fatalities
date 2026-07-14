# AI Session Progress & Next Steps

## Session Summary
- **Firestore push confirmation dialog**: Replaced the simple yes/no `_ask_yes_no` confirmation in `_run_push` with a two-step flow:
  1. `count_updates(file_path)` scans the JSON and returns the count of flagged records — no Firestore call.
  2. `_ask_number()` dialog displays the count and asks the user to enter how many records to push (pre-filled with total, max shown). Cancel is the default action (red button, Enter cancels).
  3. `push_updates()` now accepts an optional `limit` parameter; only the first N flagged records are pushed and marked `"true"` in the JSON.
- **Refactored `push_json_updates_to_firestore.py`**: Extracted `_init_firebase()` and `_load_records_to_update()` as shared internals. New public function `count_updates()` for zero-cost counting.
- **Both AU and NZ push buttons** follow the same flow (both wired through `_run_push`).

## Current System State
- **Button-lock contract**: All main-menu buttons (including Push AU/NZ) are in `_all_buttons` via `_flat_button`, toggled uniformly by `_set_buttons_locked()`.
- **Push flow** (`_run_push` in `main.py`): count → number dialog → threaded push with progress window → result dialog.
- **Cancel default**: `_ask_number` dialog has Cancel as the primary (red) button. `<Return>` and `<Escape>` both cancel. User must deliberately click Push or type in the entry and click Push.
- **Firestore project**: `djb-onthisday` (from `firebase-key.json`). Firestore database must be provisioned in the Firebase Console before push will succeed (404 if not created).

## Absolute Next-Step Checklist
- [ ] Create the Firestore database in Firebase Console for project `djb-onthisday` (`https://console.firebase.google.com/project/djb-onthisday/firestore`).
- [ ] Launch the app (`python main.py`), click "Push AU Updates to Firestore", verify the count dialog appears with correct record count, test Cancel (Enter/Escape), test entering a number and pushing.
