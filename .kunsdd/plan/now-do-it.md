
# Python Fatalities Editor — Implementation Plan

## What We're Building

A Python Tkinter desktop app that lets you select a JSON dataset from `config.ini`, edit its fields in a modal window, and save changes. Key fields (like `id`) are read-only. The app guards against quitting with unsaved changes.

## Files to Create (all in workspace root)

### 1. `config.ini` — Dataset Registry
```ini
[datasets]
AU_fatalities = AU_fatalities.json
NZ_fatalities = NZ_fatalities.json
```

### 2. `AU_fatalities.json` — Sample Data
5 fatality records with fields: `id` (protected), `date`, `region`, `incident_type`, `fatalities`, `notes`.

### 3. `NZ_fatalities.json` — Sample Data
Same structure as AU, 5 records for New Zealand.

### 4. `main.py` — Tkinter App

**Features:**
- Menu bar: Update AU_fatalities, Update NZ_fatalities, Quit
- Modal editor: scrollable form with Entry widgets for each field
- Key field `id` is read-only (grey background, `state='readonly'`)
- Only Update (save) button — no Delete or Create
- Dirty tracking: cannot quit with unsaved changes without prompt
- `askyesnocancel` dialog: Yes=save & quit, No=discard & quit, Cancel=stay
- Window close button also guarded via WM_DELETE_WINDOW protocol

**Edge cases handled:** missing config.ini, missing JSON file, invalid JSON, empty array.
