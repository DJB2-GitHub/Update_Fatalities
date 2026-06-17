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
Configured under `GEMINI_TEXT_TO_TEXT_MODELS_TO_USE`, these models offer varying tiers of reasoning and speed.

1. **Gemini 2.5 Pro (`gemini-2.5-pro`)**
   - **Role:** Deep Analysis Model (`GEMINI_DEEP_ANALYSIS_MODEL`).
   - **Features:** The heavyweight flagship model. Highly capable of handling massive contexts, deep reasoning, and complex instructions. Offers the highest accuracy for difficult analytical tasks and complex data transformations.

2. **Gemini 3.5 Flash (`gemini-3.5-flash`)**
   - **Role:** Primary Fast Generation.
   - **Features:** Next-generation lightweight model. Extremely fast time-to-first-token and highly cost-efficient. Designed for high-volume, standard text-to-text tasks where speed and responsiveness are paramount.

3. **Gemini 2.5 Flash (`gemini-2.5-flash`)**
   - **Role:** Fallback Fast Generation.
   - **Features:** Predecessor to 3.5 Flash. Still highly capable for rapid, lightweight prompt execution with a very low token cost.

### DeepSeek Models
Configured under `DEEPSEEK_TEXT_TO_TEXT_MODELS_TO_USE`, known for highly optimized pricing and strong reasoning.

1. **DeepSeek v4 Pro (`deepseek-v4-pro`)**
   - **Role:** Advanced Generation/Coding.
   - **Features:** An extremely robust model that frequently rivals top-tier proprietary models in logic and reasoning tasks while maintaining highly competitive input/output token pricing.

2. **DeepSeek v4 Flash (`deepseek-v4-flash`)**
   - **Role:** Ultra-fast Generation.
   - **Features:** Built for raw speed and minimal cost. Excellent for simple classification, formatting, or parsing tasks where deep reasoning is not required.

### AI Rates & Exchange Config
The `.env` actively tracks the token cost structure via the `AI_RATES` JSON mapping (tracking varying input/output costs per 1M tokens) and utilizes the `AUD_USD` exchange rate setting for accurate, localized cost calculations.

---

## 🚀 Running the App
To run the application cleanly without an active terminal window, use the wrapper:
```bash
python main.pyw
```
For standard execution (useful for debugging or viewing console output):
```bash
python main.py
```
