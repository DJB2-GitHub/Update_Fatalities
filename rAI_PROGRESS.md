# AI Session Progress & Next Steps

## Session Summary
- **Added menu buttons**: Two new placeholder buttons added under `Update NZ_Fatalities.json` in the `MainMenu` — **"Push AU Updates to Firestore"** and **"Push NZ Updates to Firestore"**. Both use `_flat_button` and are registered in `self._all_buttons`. Click callbacks are no-ops (`lambda _e: None`) — no backend wired.

## Current System State
- **MainMenu button layout** (`main.py`, `MainMenu.__init__`, lines 809–817): Order is `Update AU_Fatalities.json` → `Update NZ_Fatalities.json` → **Push AU Updates to Firestore** → **Push NZ Updates to Firestore** → Backup button → separator → Report button → Quit button.
- **Button-lock contract**: All main-menu buttons (including the two new ones) are added to `self._all_buttons` via `_flat_button` and toggled uniformly by `_set_buttons_locked()`.

## Absolute Next-Step Checklist
- [ ] Implement Firestore push callbacks for both buttons (replace `lambda _e: None`).
- [ ] Launch the app, verify the two buttons render and lock/unlock correctly during modal usage.

**Incomplete work**: Firestore push backend logic is unimplemented — button UI only.
