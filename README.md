# Fatalities Editor Application

A Python Tkinter-based GUI application designed to read, edit, and safely update complex JSON structures, specifically tailored for editing structured fatality records.

## 🛠 Development Environment

### Prerequisites
- **Python 3.10+**
- **Tkinter** (usually included with standard Python installations)

### Environment Configuration (`.env`)
The application relies on an environment configuration file for routing paths and managing API keys for integrated AI capabilities. To set up your local environment:
1. Copy the `.env.example` file and rename it to `.env`.
2. Configure the paths and API keys as needed.

**Key Environment Variables:**
- `FATALITY_FILE_DIRECTORY`: The absolute path pointing to your live JSON database files (e.g., your Firebase Hub `src/data` directory).
- `FILES_AVAILABLE_FOR_UPDATE`: A comma-separated list of JSON filenames the app is allowed to load.
- `ONEDRIVE_DIRECTORY`: Path used for maintaining structural backups.

---

## 🧠 AI Models & Features

The environment configuration specifically defines access to a variety of state-of-the-art AI models. Below is an overview of the features and intended use cases for each model tracked in the dev environment:

### Google Gemini Models
Configured under `GEMINI_TEXT_TO_TEXT_MODELS_TO_USE`. These models power the two-step AI pipeline in priority order.

1. **Gemini 2.5 Pro (`gemini-2.5-pro`)**
   - **Role:** Primary model for both research and structuring.
   - **Features:** The heavyweight flagship model. Highest accuracy, deepest reasoning, best JSON output. Tried first in both pipeline steps.

2. **Gemini 3.5 Flash (`gemini-3.5-flash`)**
   - **Role:** First fallback.
   - **Features:** Next-generation lightweight model. Fast and cost-efficient. Tried second if `-pro` is unavailable.

3. **Gemini 2.5 Flash (`gemini-2.5-flash`)**
   - **Role:** Final fallback.
   - **Features:** Predecessor to 3.5 Flash. Rapid, lightweight execution at very low token cost. Last resort if both higher-tier models fail.

### DeepSeek Models
Defined in `DEEPSEEK_TEXT_TO_TEXT_MODELS_TO_USE` and `AI_INTERNAL_ANALYSIS_MODEL`. These are configured in `.env` for future use but are not currently wired into the Master Response pipeline.

### AI Rates & Exchange Config
The `.env` actively tracks the token cost structure via the `AI_RATES` JSON mapping (tracking varying input/output costs per 1M tokens) and utilizes the `AUD_USD` exchange rate setting for accurate, localized cost calculations.

### AI Research & Data Population

The Fatalities Editor features a single AI entry point — the **"AI: Create Master Response"** button in the Update Fatalities modal. Clicking it triggers a two-step pipeline powered by the models defined in `GEMINI_TEXT_TO_TEXT_MODELS_TO_USE`.

---

#### The Two-Step Pipeline

Both steps iterate through the model list in order (`gemini-2.5-pro` → `gemini-3.5-flash` → `gemini-2.5-flash`), falling back to the next model if one fails.

**Step 1 — Live Research (with Google Search)**
- A prompt is sent asking the model to research the soldier's military history on the open web: *what operation was the unit engaged in, who was this person, and what were the circumstances of their death?*
- Google Search Grounding is **enabled** (`"tools": [{"google_search": {}}]`) so the model retrieves and synthesises live web data from the Australian War Memorial (AWM), Virtual War Memorial Australia (VWMA), and other official sources.
- The output is raw prose — no formatting, no markdown.
- Timeout: `AI_INTERNAL_RESPONSE_MODEL_CUTOFF_SECONDS` (defaults to 40s).
- If all models fail, Step 2 continues using only the model's internal knowledge.

**Step 2 — JSON Structuring (excl LIVE search data)**
- The research text from Step 1 (if available) is fed in as **the sole source material** — the model is explicitly instructed *"use ONLY this for your answers; do NOT search the web."*
- If Step 1 produced nothing, Step 2 works from the model's internal knowledge.
- The model outputs **valid JSON** (`responseMimeType: "application/json"`) matching the `derived_data` schema.
- Google Search is deliberately **disabled** to prevent contamination of the structured result.
- Timeout: `AI_MASTER_RESPONSE_MODEL_CUTOFF_SECONDS` (defaults to 150s).

---

#### Result: User Review → Master Record

The AI's final structured JSON response is displayed in the side panel for **user review and visual acceptance**. Once approved, the result is manually pasted into the `derived_data` → `ai_response` field, where it serves as an **internal master record for ad hoc quick info lookup** — a cached, authoritative AI-generated summary that can be referenced without re-running the pipeline.

---

#### Confirmation Dialog

Before the pipeline runs, a confirmation dialog appears explaining the AI's fixed knowledge cutoff and the role of Live Search:

> *Clear & Direct*
>
> *[The AI has a fixed cutoff date. Live Search fills the gap by finding the latest web results up to the present moment.]*
>
> *// Live Search is currently: ON | OFF*
>
> *[The AI's built-in knowledge stops at its last major update (roughly 1–2 years ago). Live Search fills that missing window with anything new or recently updated. Turn it on if you need modern information — just note it may increase overall response time by about 25%.]*

The **Live Search** checkbox in the bottom bar toggles search grounding on/off.

| Live Search | Effect on Master Response pipeline | Effect on non‑testing datasets |
|---|---|---|
| **ON** (default) | Step 1 always searches the web. Step 2 never searches (hardcoded per step). | Google Search tool injected — model can retrieve live web data. |
| **OFF** | Same as ON — Step 1/Step 2 search behaviour is hardcoded for the two‑step pipeline. | No search tool — model relies entirely on internal (cutoff‑dated) knowledge. |

> **Note:** In the Master Response pipeline, Step 1 always uses Google Search and Step 2 never does, regardless of the checkbox state. The toggle primarily affects the single‑step fallback path used for non‑testing datasets.

---

## 📝 Editable Fields & Validation

In the Update Fatalities modal, the application enforces strict data integrity by locking core identity information. Only specific fields are presented as editable.

### Editable Fields
Any field nested under the `derived_details` (or `derived_data`) object in the JSON record is fully editable. Commonly, this includes:
- `pre_service_occupation`
- `service_type`
- `unit_served_with`
- `circumstances_of_death`
- `ai_response`
- `authoritative_ai_override`
- `grid_reference` (or other GPS/coordinate fields)

*Note: `circumstances_of_death`, `ai_response`, and `authoritative_ai_override` are rendered as multi-line text boxes for easier narrative entry, with `ai_response` and `authoritative_ai_override` supporting taller heights (8 and 5 rows respectively) with scrollbars.*

### Edit Checking & Validation
When you click **Update Record**, the application runs the following safety checks before saving:
1. **Type Preservation:** The application strictly enforces the data type of the original JSON record. If the original value was a boolean, integer, or float, your new input must be successfully parsed into that exact type, otherwise an error dialog blocks the save.
2. **GPS Coordinate Validation:** If a field name implies a location reference (e.g., contains `gps`, `coordinate`, or `grid`), it is passed through a robust coordinate validator. The field must strictly match one of the following formats:
   - **Decimal Degrees:** e.g., `10.34694 N, 107.07263 E` or `10.34694, 107.07263`
   - **MGRS:** e.g., `48PYS458630` or `48P YS 458 630`
   - **DMS (Degrees, Minutes, Seconds):** e.g., `10° 20' N, 107° 04' E`

If the format is unrecognized, the application blocks the save and displays a tooltip detailing the exact acceptable formats.

---

## 🚀 Developer Quick Reference

### Architecture & File Structure
The application is built using a monolithic Tkinter architecture focused on direct DOM-like manipulation of widgets.
- **`main.py`**: Entry point. Parses `.env`, renders the main menu, and spawns the editor.
- **`update_fatalities.py`**: The core editor modal. Contains all UI bindings, coordinate parsing (`_try_parse_vietnam_mgrs`), session management (`session.json`), and the threaded AI Master Response pipeline (`_ai_lookup`).

### AI Pipeline Flow (`_ai_lookup`)
1. **Data Collection**: Extracts identity anchor values from `serviceRecordAuthority` (read-only truth).
2. **Step 1 (Research)**: Uses `GEMINI_TEXT_TO_TEXT_MODELS_TO_USE` with Google Search enabled to fetch raw historical prose.
3. **Step 2 (Structuring)**: Passes the raw prose into a JSON-mode Gemini request (Search disabled) to force output into the `derived_details` JSON schema.
4. **Resilience**: Automatically falls back to secondary models on 503/429 HTTP errors.

### State Management (`session.json`)
- Each JSON dataset has a corresponding `session.json` created in the same directory.
- It tracks the user's last viewed record index (`pos`) and active search filter (`search`), ensuring they return exactly where they left off.

## 🚀 Running the App
To run the application cleanly without an active terminal window, use the wrapper:
```bash
python main.pyw
```
For standard execution (useful for debugging or viewing console output):
```bash
python main.py
```
