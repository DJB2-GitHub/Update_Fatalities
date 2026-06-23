import os
import json

# Session state (last-viewed record per file)
# ---------------------------------------------------------------------------

def _session_path(file_path: str) -> str:
    """Return the session.json path in the root application directory."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "session.json")


def _load_session(file_path: str) -> dict | None:
    """Load session entry for *file_path*, or None if not found."""
    sp = _session_path(file_path)
    if not os.path.exists(sp):
        return None
    try:
        with open(sp, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    key = os.path.basename(file_path)
    return data.get(key)


def _save_session(file_path: str, pos: int, search_text: str = "", extra: dict | None = None):
    """Persist the current record position for *file_path*, merging *extra* if given."""
    sp = _session_path(file_path)
    data: dict = {}
    if os.path.exists(sp):
        try:
            with open(sp, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            data = {}
    if not isinstance(data, dict):
        data = {}
    key = os.path.basename(file_path)
    entry = data.get(key, {})
    if not isinstance(entry, dict):
        entry = {}
    entry["pos"] = pos
    entry["search"] = search_text
    if extra:
        entry.update(extra)
    data[key] = entry
    try:
        with open(sp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    except OSError:
        pass  # best-effort


def _apply_field(target: dict, key: str, value):
    """Set *target[key]* = *value* only if *value* is non-empty (non-blank string)."""
    if value and isinstance(value, str) and value.strip():
        target[key] = value