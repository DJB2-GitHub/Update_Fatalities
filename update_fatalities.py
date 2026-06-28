"""update_fatalities.py — Modal editor for fatality JSON records.

Modern flat-design: custom colour palette, hover effects, custom dialogs.
One record at a time, vertical layout, dynamic search, record locking.
Side panel for AI results (revealed on demand).
"""

from __future__ import annotations

from datetime import date
import json
import os
import re
import threading
import time
import tkinter as tk
import urllib.request
import urllib.error
import urllib.parse
import webbrowser
from tkinter import ttk
import ai_master_prompts
import ai_derived_details_prompts
import session_manager

# ---------------------------------------------------------------------------

def _open_url(url: str):
    """Open URL in Chrome if available, otherwise the system default browser."""
    for candidate in ("chrome", "google-chrome", "chromium", "chromium-browser"):
        try:
            browser = webbrowser.get(candidate)
            browser.open(url)
            return
        except webbrowser.Error:
            continue
    webbrowser.open(url)

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

ACCENT      = "#c63f3f"
ACCENT_HOV  = "#a53434"
BG_GREY     = "#f5f5f5"
WHITE       = "#ffffff"
TEXT_DARK   = "#222222"
TEXT_MUTED  = "#888888"
BORDER      = "#dcdcdc"
FONT        = "Segoe UI"

KEY_FIELDS  = {"id"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_coord_display(val_str: str) -> tuple[str, str]:
    """Split a coordinate display value into its decimal and original parts.

    When a non-decimal coordinate (MGRS, DMS, etc.) is parsed and converted,
    the stored value takes the form  "lat, lon {original input}"  so the
    user can see both the computed decimal and what they originally typed.

    This helper extracts the two parts:
        "10.57183, 107.21889 {YS 426 694}"  →  ("10.57183, 107.21889", "YS 426 694")
        "10.6895, 107.3305"                  →  ("10.6895, 107.3305", "")

    Returns (decimal_part, original_suffix).  original_suffix is "" when
    no {…} annotation is present.
    """
    m = re.match(r'^(.*?)\s*\{([^}]+)\}\s*$', str(val_str).strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return str(val_str).strip(), ""


class _ToolTip:
    """Lightweight hover tooltip for tkinter widgets.

    Usage:
        _ToolTip(widget, "help text")
    The tooltip appears on <Enter> and hides on <Leave>.
    """
    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text = text
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None):
        if self._tip is not None:
            return
        x = self.widget.winfo_rootx() + 6
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 2
        self._tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(
            tw, text=self.text, justify=tk.LEFT,
            background="#333333", foreground="#ffffff",
            font=(FONT, 9), padx=7, pady=4,
        )
        lbl.pack()

    def _hide(self, _event=None):
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


# =============================================================================
# Vietnam-era MGRS → Decimal Coordinate Conversion
# =============================================================================
#
# CONTEXT ────────────────────────────────────────────────────────────────────
#
# During the Vietnam War, U.S. and allied military maps used the MGRS
# (Military Grid Reference System) based on the **South Vietnam 1960 (SVN60)**
# datum.  Modern tools (Google Maps, GPS, GIS software) use **WGS84**.
#
# The two datums do not align — the same MGRS coordinate refers to slightly
# different physical locations depending on which datum underpins the grid.
#
# The SVN60 → WGS84 offset in southern Vietnam is roughly:
#     +205 m Easting
#      +75 m Northing
#
# At 10° N latitude this is ~0.0018° (≈ 6.5 arc-seconds), which matters for
# casualty-location accuracy when records were written on a 1970 map but
# viewed on Google Earth today.
#
#
# MGRS ANATOMY (using the README example) ────────────────────────────────────
#
#     Original:   48P YS 426 694
#
#     48   = UTM zone number (1–60)
#     P    = latitude band (C–X, skipping I and O)
#     YS   = 100 km × 100 km grid-square letter pair
#     426  = Easting  within that square (3 digits → 42600 m, i.e. 100 m prec.)
#     694  = Northing within that square (3 digits → 69400 m)
#
# Think of it like an address:
#     "48P"      → region  (UTM zone + latitude band)
#     "YS"       → city block  (100 km square)
#     "426 694"  → house number  (metre offset within the block)
#
#
# THE 48Q → 48P TRANSCRIPTION ERROR ──────────────────────────────────────────
#
# Many Vietnam War records contain "48Q YS …".  This is almost certainly a
# typographical error because the 100 km square **YS exists only in 48P**,
# not 48Q.  (48P covers southern Vietnam / III & IV Corps; 48Q covers
# northern Vietnam / I & II Corps.)
#
# Our parser detects this and auto-corrects 48Q → 48P for southern squares.
#
#
# PRECISION ──────────────────────────────────────────────────────────────────
#
# MGRS numerical digits come in even-length pairs (2, 4, 6, 8, 10 digits):
#
#     Digits  East/North digits    Precision       Example
#     ─────  ──────────────────    ─────────       ───────
#       2     1 + 1                10 000 m        (rarely used)
#       4     2 + 2                 1 000 m        48P YS 42 69
#       6     3 + 3                   100 m        48P YS 426 694  ← typical
#       8     4 + 4                    10 m        48P YS 4260 6940
#      10     5 + 5                     1 m        48P YS 42600 69400
#
# Our parser preserves the input precision: a 6-digit input produces a
# 6-digit shifted MGRS, rounded to the nearest 100 m grid intersection.
#
#
# LIMITATIONS ────────────────────────────────────────────────────────────────
#
# * The datum shift constants (+205 E, +75 N) are region-specific for
#   Bà Rịa–Vũng Tàu / Phước Tuy Province.  Other parts of Vietnam may need
#   slightly different values.
#
# * We do not handle 100 km square boundary crossing caused by the shift
#   (e.g. an easting of 99850 + 205 = 100055 would tick into the next
#   square).  In practice the shift is small and this is vanishingly
#   unlikely for real casualty coordinates.
#
# * The zone-inference table (_VIETNAM_48P_SQUARES) lists the common III &
#   IV Corps squares.  Edge cases near the 48P/48Q boundary may be wrong.
#   If you encounter one, add the square to the set or provide the full
#   GZD in the input.
#
# =============================================================================


# ---------------------------------------------------------------------------
# 100 km grid squares known to be in Vietnam zone 48P (southern: III & IV Corps)
# ---------------------------------------------------------------------------
#
# These are the two-letter 100 000 m square identifiers that fall inside
# UTM zone 48, latitude band P.  In the Vietnam War context, 48P covers
# the southern half of South Vietnam — roughly everything from Đà Nẵng
# southward, including III Corps (Saigon / Biên Hòa / Vũng Tàu) and
# IV Corps (Mekong Delta).
#
# Sourcing: US Army Map Service 1:250 000 series (Series L509 / L7014).
#
# Squares *not* in this set are assumed to be in 48Q (northern I & II Corps).
# ---------------------------------------------------------------------------
_VIETNAM_48P_SQUARES = {
    # Y-series squares (eastern side of zone 48, lat band P)
    "YS", "YT", "YU", "YV", "YW", "YX", "YY", "YZ",
    # X-series squares (western side of zone 48, lat band P)
    "XR", "XS", "XT", "XU", "XV", "XW", "XX", "XY", "XZ",
    # These straddle the P/Q boundary; listed in 48P because the majority
    # of their populated area lies in III Corps territory.
    "YQ", "YR",
    "XQ",
}


# ---------------------------------------------------------------------------
# SVN60 → WGS84 datum-shift parameters (metres)
# ---------------------------------------------------------------------------
#
# During the Vietnam War, U.S. military maps used the Indian 1960 datum
# (also called South Vietnam 1960, SVN60, or EPSG:4136 locally).
#
# Converting an SVN60 UTM coordinate to WGS84 UTM requires adding these
# offsets.  The values below are the **approximate average** for the
# Bà Rịa–Vũng Tàu / Phước Tuy Province area (the theatre of most
# Australian operations).
#
# For other regions of Vietnam the shift may differ by ±30 m; if you need
# higher accuracy, use a dedicated coordinate-transformation library
# (e.g. pyproj with the appropriate EPSG grid-shift file).
# ---------------------------------------------------------------------------
_DATUM_SHIFT_E = 205   # metres to add to Easting  (SVN60 → WGS84)
_DATUM_SHIFT_N = 75    # metres to add to Northing (SVN60 → WGS84)


from coords import (
    _load_json, _save_json, _error_dialog, _confirm_yesnocancel,
    _confirm_yesno, _bind_hover, _center_on_parent, _styled_entry
)
import coords

class UpdateFatalities(tk.Toplevel):
    """Modern flat-design modal for editing fatality records with AI side panel."""

    def __init__(self, parent: tk.Tk | tk.Toplevel, file_path: str, *, modal_title: str | None = None):
        super().__init__(parent)
        self.configure(bg=BG_GREY)

        # ── Window-level config (MUST be set before UI build, or Windows
        #    may ignore changes to extended styles like -toolwindow / resizable) ──
        # NOTE: do NOT call transient() — on Windows it forces WS_EX_TOOLWINDOW
        #       which strips the minimise / maximise buttons from the title bar.
        #       Use grab_set() alone for modal behaviour.
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.resizable(True, True)
        self.minsize(900, 600)

        # Minimize / restore parent together with this modal
        self.bind("<Unmap>", self._on_unmap)
        self.bind("<Map>", self._on_map)
        # When parent is restored from taskbar, restore this modal too
        self._on_parent_map_id = parent.bind("<Map>", self._on_parent_map, add=True)

        # ── Instance state & data loading ──
        self._loaded = False
        self._modal_title = modal_title
        self._hotlink_combined_text = ""  # cached for AI field-derivation hotlinks
        self._hotlink_active = False
        try:
            env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
            _env = {}
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as _f:
                    for _line in _f:
                        _line = _line.strip()
                        if _line and not _line.startswith("#") and "=" in _line:
                            _k, _, _v = _line.partition("=")
                            _env[_k.strip()] = _v.strip().strip('"').strip("'")
            self._copy_threshold = int(_env.get("SHOW_AI_MASTER_RESPONSE_COPY", "200"))
        except (ValueError, OSError):
            self._copy_threshold = 200

        data = _load_json(file_path)
        if data is None:
            self.destroy()
            return

        self._loaded = True
        self.file_path = file_path
        self.original_data = data
        self.working_data = [dict(r) for r in data]
        self.dirty = False
        self._record_dirty = False
        self._record_snapshot: dict | None = None

        self._search_text = ""
        today = date.today()
        self._on_this_day_month_var = tk.StringVar(value=str(today.month).zfill(2))
        self._on_this_day_day_var = tk.StringVar(value=str(today.day).zfill(2))
        self._on_this_day_chk_var = tk.BooleanVar(value=False)
        self._filtered = list(range(len(self.working_data)))
        self._filtered_pos = 0
        self._entry_widgets: dict[str, tk.Entry] = {}

        self._build_ui()

        # ── Restore last-viewed record from session ──
        session = session_manager._load_session(file_path)
        saved_pos = 0
        saved_search = ""
        if session and isinstance(session, dict):
            saved_pos = session.get("pos", 0)
            saved_search = session.get("search", "")
            
            saved_ai_option = session.get("ai_option")
            if saved_ai_option:
                self._payload_dropdown_var.set(saved_ai_option)
                
            saved_live_search = session.get("live_search")
            if saved_live_search is not None:
                self._live_search_var.set(saved_live_search)

            saved_on_this_day_month = session.get("on_this_day_month")
            if saved_on_this_day_month:
                self._on_this_day_month_var.set(saved_on_this_day_month)
            saved_on_this_day_day = session.get("on_this_day_day")
            if saved_on_this_day_day:
                self._on_this_day_day_var.set(saved_on_this_day_day)
            saved_on_this_day = session.get("on_this_day")
            if saved_on_this_day is not None:
                self._on_this_day_chk_var.set(saved_on_this_day)

            saved_side_panel = session.get("side_panel_visible")
            if saved_side_panel is not None:
                self._side_panel_visible_var.set(saved_side_panel)
                # Apply side panel visibility
                if saved_side_panel:
                    self._show_side_panel()
                else:
                    self._hide_side_panel()

        # Apply OnThisDay mutual-exclusivity state after session restore
        if self._on_this_day_chk_var.get():
            self._search_entry.configure(state=tk.DISABLED)
            self._on_this_day_month_entry.configure(state=tk.NORMAL)
            self._on_this_day_day_entry.configure(state=tk.NORMAL)
        else:
            self._on_this_day_month_entry.configure(state=tk.DISABLED)
            self._on_this_day_day_entry.configure(state=tk.DISABLED)

        if saved_search:
            self._search_text = saved_search
            self._search_var.set(saved_search)
        self._apply_search()
        if 0 <= saved_pos < len(self._filtered):
            self._filtered_pos = saved_pos
        self._show_record()

        # ── Restore side-panel prompt/response for this reference ID ──
        if session and isinstance(session, dict):
            last_ref_id = session.get("lastRefId", "")
            if last_ref_id and last_ref_id in session:
                ref_state = session[last_ref_id]
                if isinstance(ref_state, dict):
                    saved_prompt = ref_state.get("prompt", "")
                    saved_response = ref_state.get("response", "")
                    side_panel_visible = ref_state.get("sidePanelVisible", False)
                    if saved_prompt:
                        self._side_prompt.configure(state=tk.NORMAL)
                        self._side_prompt.delete("1.0", tk.END)
                        self._side_prompt.insert("1.0", saved_prompt)
                        self._side_prompt_label.configure(text=ref_state.get("promptLabel", "PROMPT: All Derived Data"))
                    if saved_response:
                        self._side_resp_label.configure(text=ref_state.get("responseLabel", "RESPONSE: All Derived Data"))
                        self._side_resp_replace(saved_response)
                    # Restore side-panel visibility independently of content
                    if side_panel_visible or saved_response:
                        self._show_side_panel()

        self.update_idletasks()
        w = 1250
        ph = self.winfo_screenheight()
        h = min(950, ph - 40)
        pw = self.winfo_screenwidth()
        x = (pw - w) // 2
        y = (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.grab_set()

        parent.wait_window(self)
        try:
            parent.unbind("<Map>", self._on_parent_map_id)
        except Exception:
            pass

    def _cancel(self):
        if self._record_dirty:
            ok = _confirm_yesno(self, "Discard Changes?",
                                "You have unsaved changes.\nClose and discard all changes?")
            if not ok:
                return
        extra = self._gather_ref_state()
        if extra is None:
            extra = {}
        extra["side_panel_visible"] = self._side_panel_visible_var.get()
        session_manager._save_session(self.file_path, self._filtered_pos, self._search_text, extra=extra)
        # Bring the parent (main menu) to the front before closing
        try:
            parent = self.master
            if parent and parent.winfo_exists():
                parent.deiconify()
                parent.lift()
                parent.focus_set()
        except Exception:
            pass
        self.destroy()

    def _on_unmap(self, event=None):
        """When this modal is minimised, minimise the parent too."""
        # Release grab so Windows allows the title-bar minimise to proceed
        try:
            self.grab_release()
        except Exception:
            pass
        self.after(100, self._sync_parent_iconify)

    def _sync_parent_iconify(self):
        try:
            if self.winfo_exists() and self.state() == 'iconic':
                parent = self.master
                if parent and parent.winfo_exists():
                    parent.iconify()
        except Exception:
            pass

    def _on_map(self, event=None):
        """When this modal is restored, restore the parent too."""
        # Re-establish grab that was released on minimise
        try:
            self.grab_set()
        except Exception:
            pass
        try:
            parent = self.master
            if parent and parent.winfo_exists() and parent.state() == 'iconic':
                parent.deiconify()
        except Exception:
            pass

    def _on_parent_map(self, event=None):
        """When the parent is restored (e.g. from taskbar), restore this modal too."""
        try:
            if self.winfo_exists() and self.state() == 'iconic':
                self.deiconify()
        except Exception:
            pass

    def _minimize_all(self):
        """Minimize this modal and the parent together (button-click handler)."""
        try:
            parent = self.master
            if parent and parent.winfo_exists():
                parent.iconify()
            self.iconify()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # AI field-derivation hotlinks
    # ------------------------------------------------------------------

    def _make_label_hotlink(self, label: tk.Label, field_name: str):
        """Restyle a field label as a clickable hotlink if activation
        condition is met (>50 words in ai_response or authoritative_ai_override)."""
        if not self._hotlink_active:
            return
        label.configure(
            fg="#4a90d9", cursor="hand2",
            font=(FONT, 10, "underline"),
        )
        _ToolTip(label, f"Click to AI-derive {field_name}")
        label.bind("<Button-1>", lambda e, fn=field_name: self._on_hotlink_click(fn))

    def _on_hotlink_click(self, field_name: str):
        """Handle a hotlink click: run AI derivation in background and show result."""
        # ── incident_coordinates: local conversion from incident_location, no AI ──
        if field_name == "incident_coordinates":
            self._convert_incident_coordinates()
            return

        combined = self._hotlink_combined_text
        if not combined.strip():
            _error_dialog(self, "No Data",
                          "No combined text available for AI derivation.")
            return

        prompt_fn = ai_derived_details_prompts.FIELD_PROMPTS.get(field_name)
        if not prompt_fn:
            return

        result_tuple = prompt_fn(combined)
        system_instruction, user_prompt = result_tuple

        # Show prompt in side panel and start progress
        self._side_resp_label.configure(text=f"AI: {field_name}")
        self._side_prompt.configure(state=tk.NORMAL)
        self._side_prompt.delete("1.0", tk.END)
        self._side_prompt.insert("1.0", system_instruction + "\n\n" + user_prompt)
        self._side_resp.delete("1.0", tk.END)
        self._side_resp_replace("Deriving…")
        self._show_side_panel()

        def _task():
            result = self._call_ai_for_field(system_instruction, user_prompt)
            if isinstance(result, tuple):
                text, model_name, usage_meta, elapsed = result
            else:
                text, model_name, usage_meta, elapsed = result, None, None, 0
            self.after(0, lambda: self._show_derivation_result(
                field_name, text, model_name, usage_meta, elapsed))

        threading.Thread(target=_task, daemon=True).start()

    def _all_hotlinks(self):
        """Run all four hotlink derivations in a single AI call."""
        combined = self._hotlink_combined_text
        if not combined.strip():
            _error_dialog(self, "No Data", "No combined text available for AI derivation.")
            return

        system_instruction, user_prompt = ai_derived_details_prompts.get_all_hotlinks_prompt(combined)

        self._side_resp_label.configure(text="AI: All Hotlinks")
        self._side_prompt.configure(state=tk.NORMAL)
        self._side_prompt.delete("1.0", tk.END)
        self._side_prompt.insert("1.0", system_instruction + "\n\n" + user_prompt)
        self._side_resp.delete("1.0", tk.END)
        self._side_resp_replace("Deriving all hotlinks…")
        self._show_side_panel()

        def _task():
            result = self._call_ai_for_field(system_instruction, user_prompt)
            if isinstance(result, tuple):
                text, model_name, usage_meta, elapsed = result
                try:
                    cleaned = (text or "").strip()
                    if cleaned.startswith("```"):
                        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
                    parsed = json.loads(cleaned)
                except (json.JSONDecodeError, ValueError):
                    parsed = None
                self.after(0, lambda: self._show_all_hotlinks_result(
                    parsed, text, model_name, usage_meta, elapsed))
            else:
                self.after(0, lambda: self._side_resp_replace(
                    f"All Hotlinks Failed.\n\n{result}"))

        threading.Thread(target=_task, daemon=True).start()

    def _convert_incident_coordinates(self):
        """Read incident_location, extract //...// snippet, convert, write to incident_coordinates."""
        loc_path = ("derived_details", "fatality_locations", "incident_location")
        coord_path = ("derived_details", "fatality_locations", "incident_coordinates")
        loc_entry = self._entry_widgets.get(loc_path)
        coord_entry = self._entry_widgets.get(coord_path)
        if loc_entry is None or coord_entry is None:
            return
        # Read current incident_location value from the widget
        if isinstance(loc_entry, tk.Text):
            loc_val = loc_entry.get("1.0", "end-1c").strip()
        else:
            loc_val = loc_entry.get().strip()
        if not loc_val or loc_val.lower() == "unassigned":
            _error_dialog(self, "No Location",
                          "The incident_location field is empty.\n\n"
                          "Enter a coordinate enclosed in //...// delimiters first.")
            return
        # Look for //...// delimiters
        if "//" not in loc_val:
            _error_dialog(self, "No Delimiters",
                          "No //...// delimiters found in incident_location.\n\n"
                          "Wrap your coordinate in // delimiters, e.g.\n"
                          "//-13.313, 107.370// or //48Q 328 456//")
            return
        is_valid, msg, parsed, snippet = coords.parse_with_snippet(loc_val)
        if not is_valid or parsed is None:
            attempted = snippet.strip() if snippet else loc_val
            _error_dialog(self, "Unable to calculate coordinates",
                          f"{msg}\n\n"
                          "---\n\n"
                          "## MGRS Grid-Square Reference (Vietnam War)\n\n"
                          "If using an MGRS coordinate, include the **100 km "
                          "grid-square letters** after the UTM zone.\n\n"
                          "**YS** — Phuoc Tuy, Long Khanh\n"
                          "`Nui Dat, Long Tan, Long Phuoc, Horseshoe`\n\n"
                          "**XT** — Tay Ninh, Binh Duong, Hau Nghia\n"
                          "`Tay Ninh, Nui Ba Den, War Zone C, Ho Bo Woods`\n\n"
                          "**YT** — Long Khanh, Bien Hoa, NW Phuoc Tuy\n"
                          "`Xuan Loc, Hat Dich, Courtenay Plantation`\n\n"
                          "Example: `//YS 328 456//` or `//48Q YS 328 456//`")
            return
        formatted = f"{parsed[0]}, {parsed[1]}"
        if isinstance(coord_entry, tk.Text):
            coord_entry.delete("1.0", tk.END)
            coord_entry.insert("1.0", formatted)
        else:
            coord_entry.delete(0, tk.END)
            coord_entry.insert(0, formatted)
        self._on_field_edited()

    def _show_all_hotlinks_result(self, parsed: dict | None, raw_text: str,
                                   model_name=None, usage_meta=None, elapsed=0.0):
        """Show a dialog with checkboxes and editable text fields for each hotlink."""
        if parsed is None:
            self._side_resp_label.configure(text="AI: All Hotlinks — FAILED")
            self._side_resp_replace(raw_text)
            _error_dialog(self, "Parse Failed",
                          "Could not parse JSON from AI response.\nRaw response shown in side panel.")
            return

        header = "AI: All Hotlinks"
        time_str = ""
        cost_str = ""
        if model_name and elapsed:
            if usage_meta:
                try:
                    # OpenRouter returns cost directly in response — use it
                    if "totalCost" in usage_meta:
                        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
                        env = {}
                        if os.path.exists(env_path):
                            with open(env_path, "r", encoding="utf-8") as f:
                                for line in f:
                                    line = line.strip()
                                    if line and not line.startswith("#") and "=" in line:
                                        k, _, v = line.partition("=")
                                        env[k.strip()] = v.strip().strip('"').strip("'")
                        aud_usd = float(env.get("AUD_USD", "0.7"))
                        cost = usage_meta["totalCost"] * aud_usd
                        cost_str = f"$A {cost:.6f}"
                    else:
                        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
                        env = {}
                        if os.path.exists(env_path):
                            with open(env_path, "r", encoding="utf-8") as f:
                                for line in f:
                                    line = line.strip()
                                    if line and not line.startswith("#") and "=" in line:
                                        k, _, v = line.partition("=")
                                        env[k.strip()] = v.strip().strip('"').strip("'")
                        ai_rates = json.loads(env.get("AI_RATES", "{}"))
                        aud_usd = float(env.get("AUD_USD", "0.7"))
                        if model_name in ai_rates:
                            rate = ai_rates[model_name]
                            pt = usage_meta.get("promptTokenCount", 0)
                            ct = usage_meta.get("candidatesTokenCount", 0)
                            cost = (pt * rate.get("in1", 0) / 1_000_000) * aud_usd + \
                                   (ct * rate.get("out1", 0) / 1_000_000) * aud_usd
                            cost_str = f"$A {cost:.6f}"
                except Exception:
                    pass
            time_str = f"{elapsed:.0f}s" if elapsed else "??s"
            cost_str = cost_str if cost_str else "$A ?.????"
            header = f"AI: All Hotlinks  [{model_name}]  {time_str}  {cost_str}"

        self._side_resp_label.configure(text=header)
        self._side_resp_replace(raw_text)
        self._copy_btn.pack_forget()  # only for master response, not hotlinks

        dlg = tk.Toplevel(self)
        dlg.title(f"All Hotlinks Results  [{model_name}]  {time_str}  {cost_str}")
        dlg.resizable(True, True)
        dlg.configure(bg=WHITE)
        dlg.transient(self)
        _center_on_parent(dlg, self)
        dlg.grab_set()

        hdr = tk.Label(dlg, text=f"Edit results and select fields to update:  [{model_name}]  {time_str}  {cost_str}",
                       font=(FONT, 10, "bold"), bg=WHITE, fg=TEXT_DARK, anchor="w")
        hdr.pack(fill=tk.X, padx=16, pady=(12, 8))

        fields = [
            ("service_status", "Service Status"),
            ("place_of_death", "Death Location"),
            ("circumstances_of_death", "Circumstances of Death"),
            ("unit_served_with", "Unit Served With"),
            ("grid_reference", "incident_location"),
        ]

        check_vars = {}
        text_widgets = {}

        for key, label in fields:
            row = tk.Frame(dlg, bg=WHITE)
            row.pack(fill=tk.X, padx=16, pady=4)

            var = tk.BooleanVar(value=True)
            check_vars[key] = var
            cb = tk.Checkbutton(row, text=label, variable=var,
                                font=(FONT, 10, "bold"), bg=WHITE,
                                activebackground=WHITE)
            cb.pack(anchor="w")

            tf = tk.Frame(dlg, bg=WHITE)
            tf.pack(fill=tk.X, padx=32, pady=(0, 8))

            value = str(parsed.get(key, ""))
            tw = tk.Text(tf, font=(FONT, 10), wrap=tk.WORD,
                         relief=tk.SOLID, borderwidth=1,
                         padx=8, pady=4, height=3, width=70)
            tw.pack(fill=tk.BOTH, expand=True)
            tw.insert("1.0", value)
            text_widgets[key] = tw

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill=tk.X, padx=16, pady=(8, 12))

        def _update():
            for key, var in check_vars.items():
                if var.get():
                    edited = text_widgets[key].get("1.0", "end-1c").strip()
                    if edited:
                        self._populate_field_value(key, edited)
            dlg.destroy()

        cancel_btn = tk.Label(btn_frame, text="Cancel", font=(FONT, 10, "bold"),
                              bg=BORDER, fg=TEXT_DARK, padx=20, pady=6, cursor="hand2")
        cancel_btn.pack(side=tk.RIGHT, padx=(6, 0))
        _bind_hover(cancel_btn, BORDER, "#c0c0c0")
        cancel_btn.bind("<Button-1>", lambda e: dlg.destroy())

        update_btn = tk.Label(btn_frame, text="Update", font=(FONT, 10, "bold"),
                              bg=ACCENT, fg=WHITE, padx=20, pady=6, cursor="hand2")
        update_btn.pack(side=tk.RIGHT, padx=(6, 0))
        _bind_hover(update_btn, ACCENT, ACCENT_HOV)
        update_btn.bind("<Button-1>", lambda e: _update())

        dlg.wait_window()

    def _call_ai_for_field(self, system_instruction: str, user_prompt: str):
        """Call the AI API with the field derivation prompt.
        Routes to Gemini or DeepSeek based on AI_INTERNAL_MODEL-PROVIDER.
        Returns (text, model_name, usage_meta, elapsed_seconds) on success,
        or an error string on failure."""
        import time as _time
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        env = {}
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        env[k.strip()] = v.strip().strip('"').strip("'")

        provider = env.get("AI_INTERNAL_MODEL_PROVIDER", "Google")
        allowed = [p.strip().lower() for p in env.get("AI_MODEL_PROVIDERS", "Google,Deepseek").split(",") if p.strip()]
        if provider.lower() not in allowed:
            return (f"In .env AI_INTERNAL_MODEL_PROVIDER constant \"{provider}\" is not a valid AI Provider\n"
                    f"Contact system admin to fix")
        timeout_secs = 15

        if provider.lower() == "deepseek":
            api_key = env.get("DEEPSEEK_API_KEY", "")
            models_str = env.get("AI_DEEPSEEK_INTERNAL_ANALYSIS_MODELS", "deepseek-v4-flash")
            if not api_key:
                return "ERROR: DEEPSEEK_API_KEY not found in .env"
        elif provider.lower() == "openrouter":
            api_key = env.get("OPENROUTER_API_KEY", "")
            if not api_key:
                return "ERROR: OPENROUTER_API_KEY not found in .env"
            # Parse allowed_models for the auto-router plugin
            _include_raw = env.get("OPENROUTER_INTERNAL_INCLUDE_MODELS", "")
            if not _include_raw:
                return "ERROR: OPENROUTER_INTERNAL_INCLUDE_MODELS not found in .env"
            try:
                import ast as _ast
                _allowed_models = list(_ast.literal_eval(_include_raw))
            except Exception as _e:
                return f"ERROR: OPENROUTER_INTERNAL_INCLUDE_MODELS parse failed: {_e}"
            models = ["openrouter/auto"]
            models_str = ""  # bypass the split below; models already set
        else:
            # Google (default)
            api_key = env.get("GEMINI_API_KEY", "")
            models_str = env.get("AI_GEMINI_INTERNAL_ANALYSIS_MODELS", "gemini-2.5-flash")
            if not api_key:
                return "ERROR: GEMINI_API_KEY not found in .env"

        if not models_str:
            pass  # models already set for openrouter
        else:
            models = [m.strip() for m in models_str.split(",") if m.strip()]
        last_error = ""

        for model in models:
            retry_count = 0
            max_retries = 2
            while retry_count <= max_retries:
                self.after(0, lambda m=model: self._side_resp_replace(
                    f"Deriving …  (querying {m})" + (f" (Retry {retry_count}/{max_retries})" if retry_count else "")))
                t0 = _time.time()
                try:
                    if provider.lower() == "deepseek":
                        url = "https://api.deepseek.com/v1/chat/completions"
                        body = json.dumps({
                            "model": model,
                            "temperature": 0,
                            "messages": [
                                {"role": "system", "content": system_instruction},
                                {"role": "user", "content": user_prompt},
                            ],
                        }).encode("utf-8")
                        req = urllib.request.Request(
                            url, data=body,
                            headers={
                                "Content-Type": "application/json",
                                "Authorization": f"Bearer {api_key}",
                            },
                        )
                        with urllib.request.urlopen(req, timeout=timeout_secs) as resp:
                            data = json.loads(resp.read().decode("utf-8"))
                            elapsed = _time.time() - t0
                            text = data["choices"][0]["message"]["content"]
                            ds_usage = data.get("usage", {})
                            usage_meta = {
                                "promptTokenCount": ds_usage.get("prompt_tokens", 0),
                                "candidatesTokenCount": ds_usage.get("completion_tokens", 0),
                            }
                            return (text, model, usage_meta, elapsed)
                    elif provider.lower() == "openrouter":
                        url = "https://openrouter.ai/api/v1/chat/completions"
                        body = json.dumps({
                            "model": "openrouter/auto",
                            "temperature": 0,
                            "messages": [
                                {"role": "system", "content": system_instruction},
                                {"role": "user", "content": user_prompt},
                            ],
                            "plugins": [
                                {
                                    "id": "auto-router",
                                    "allowed_models": _allowed_models,
                                    "cost_quality_tradeoff": 0
                                }
                            ],
                        }).encode("utf-8")
                        req = urllib.request.Request(
                            url, data=body,
                            headers={
                                "Content-Type": "application/json",
                                "Authorization": f"Bearer {api_key}",
                                "HTTP-Referer": "https://github.com/kun-app",
                                "X-Title": "Update Fatalities",
                            },
                        )
                        with urllib.request.urlopen(req, timeout=timeout_secs) as resp:
                            data = json.loads(resp.read().decode("utf-8"))
                            elapsed = _time.time() - t0
                            text = data["choices"][0]["message"]["content"]
                            or_usage = data.get("usage", {})
                            # OpenRouter returns full cost breakdown in response body
                            actual_model = f"OpenRouter-{data.get('model', model)}"
                            usage_meta = {
                                "promptTokenCount": int(or_usage.get("input_tokens") or or_usage.get("prompt_tokens", 0)),
                                "candidatesTokenCount": int(or_usage.get("output_tokens") or or_usage.get("completion_tokens", 0)),
                                "totalTokenCount": int(or_usage.get("total_tokens", 0)),
                                "totalCost": float(or_usage.get("total_cost") or or_usage.get("totalCost") or or_usage.get("cost") or 0),
                                "inputCost": float(or_usage.get("input_cost", 0)),
                                "outputCost": float(or_usage.get("output_cost", 0)),
                            }
                            # Fallback: try HTTP header if body cost is zero
                            if usage_meta["totalCost"] == 0:
                                try:
                                    usage_meta["totalCost"] = float(resp.info().get("x-openrouter-cost", "0"))
                                except (ValueError, TypeError):
                                    pass
                            # Log full OpenRouter response for cost verification
                            try:
                                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "openrouter.log"), "a", encoding="utf-8") as _log:
                                    _log.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} [internal] model={actual_model} ---\n")
                                    _log.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n\n")
                            except Exception:
                                pass
                            return (text, actual_model, usage_meta, elapsed)
                    else:
                        # Google Gemini
                        url = (
                            "https://generativelanguage.googleapis.com/v1beta/models/"
                            f"{model}:generateContent?key={api_key}"
                        )
                        body = json.dumps({
                            "systemInstruction": {"parts": [{"text": system_instruction}]},
                            "contents": [{"parts": [{"text": user_prompt}]}],
                            "generationConfig": {"temperature": 0, "maxOutputTokens": 1024},
                        }).encode("utf-8")
                        req = urllib.request.Request(
                            url, data=body,
                            headers={"Content-Type": "application/json"},
                        )
                        with urllib.request.urlopen(req, timeout=timeout_secs) as resp:
                            data = json.loads(resp.read().decode("utf-8"))
                            elapsed = _time.time() - t0
                            text = data["candidates"][0]["content"]["parts"][0]["text"]
                            usage_meta = data.get("usageMetadata", {})
                            return (text, model, usage_meta, elapsed)
                except urllib.error.HTTPError as exc:
                    if exc.code in (429, 503) and retry_count < max_retries:
                        retry_count += 1
                        import time as _stime
                        _stime.sleep(2.5)
                        continue
                    last_error = f"{model}: HTTP Error {exc.code}: {exc.reason}"
                    break
                except Exception as exc:
                    last_error = f"{model}: {exc}"
                    break

        return f"All models failed.\n\n{last_error}"

    def _confirm_with_edit(self, title: str, field_name: str, text: str) -> str | None:
        """Show a dialog with an editable text box containing the AI result.
        Returns the (possibly edited) text on Yes, or None on Cancel."""
        import tkinter.simpledialog as _sd
        result = [None]
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.resizable(True, True)
        dlg.configure(bg=WHITE)
        dlg.transient(self)
        _center_on_parent(dlg, self)
        dlg.grab_set()
        pad = {"padx": 16, "pady": 12}

        # Header
        hdr = tk.Label(dlg, text=f"AI-derived '{field_name}'. Edit if needed:",
                       font=(FONT, 10, "bold"), bg=WHITE, fg=TEXT_DARK, anchor="w")
        hdr.pack(fill=tk.X, **pad)

        # Editable text widget
        frame = tk.Frame(dlg, bg=WHITE)
        frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))
        text_widget = tk.Text(frame, font=(FONT, 10), wrap=tk.WORD,
                              relief=tk.SOLID, borderwidth=1,
                              padx=8, pady=6, height=6, width=60)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert("1.0", text)

        # Buttons
        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill=tk.X, padx=16, pady=(0, 16))

        def _accept():
            result[0] = text_widget.get("1.0", "end-1c").strip()
            dlg.destroy()

        def _cancel():
            dlg.destroy()

        cancel_btn = tk.Label(btn_frame, text="Cancel", font=(FONT, 10, "bold"),
                              bg=BORDER, fg=TEXT_DARK, padx=20, pady=6, cursor="hand2")
        cancel_btn.pack(side=tk.RIGHT, padx=(6, 0))
        _bind_hover(cancel_btn, BORDER, "#c0c0c0")
        cancel_btn.bind("<Button-1>", lambda e: _cancel())

        yes_btn = tk.Label(btn_frame, text="Accept", font=(FONT, 10, "bold"),
                           bg=ACCENT, fg=WHITE, padx=20, pady=6, cursor="hand2")
        yes_btn.pack(side=tk.RIGHT, padx=(6, 0))
        _bind_hover(yes_btn, ACCENT, ACCENT_HOV)
        yes_btn.bind("<Button-1>", lambda e: _accept())

        dlg.wait_window()
        return result[0]

    def _show_derivation_result(self, field_name: str, result_text: str,
                                 model_name=None, usage_meta=None, elapsed=0.0):
        """Show the AI-derived result and ask the user to accept or cancel."""
        result_text = (result_text or "").strip()

        # ── Build cost/time header ──
        header = f"AI: {field_name}"
        time_str = ""
        cost_str = ""
        if model_name and elapsed:
            # Calculate cost
            if usage_meta:
                try:
                    # OpenRouter returns cost directly in response — use it
                    if "totalCost" in usage_meta:
                        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
                        env = {}
                        if os.path.exists(env_path):
                            with open(env_path, "r", encoding="utf-8") as f:
                                for line in f:
                                    line = line.strip()
                                    if line and not line.startswith("#") and "=" in line:
                                        k, _, v = line.partition("=")
                                        env[k.strip()] = v.strip().strip('"').strip("'")
                        aud_usd = float(env.get("AUD_USD", "0.7"))
                        cost = usage_meta["totalCost"] * aud_usd
                        cost_str = f"$A {cost:.6f}"
                    else:
                        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
                        env = {}
                        if os.path.exists(env_path):
                            with open(env_path, "r", encoding="utf-8") as f:
                                for line in f:
                                    line = line.strip()
                                    if line and not line.startswith("#") and "=" in line:
                                        k, _, v = line.partition("=")
                                        env[k.strip()] = v.strip().strip('"').strip("'")
                        ai_rates = json.loads(env.get("AI_RATES", "{}"))
                        aud_usd = float(env.get("AUD_USD", "0.7"))
                        if model_name in ai_rates:
                            rate = ai_rates[model_name]
                            pt = usage_meta.get("promptTokenCount", 0)
                            ct = usage_meta.get("candidatesTokenCount", 0)
                            cost = (pt * rate.get("in1", 0) / 1_000_000) * aud_usd + \
                                   (ct * rate.get("out1", 0) / 1_000_000) * aud_usd
                            cost_str = f"$A {cost:.6f}"
                except Exception:
                    pass
            # Use ?? for unknown values
            time_str = f"{elapsed:.0f}s" if elapsed else "??s"
            cost_str = cost_str if cost_str else "$A ?.????"
            header = f"AI: {field_name}  [{model_name}]  {time_str}  {cost_str}"

        self._side_resp_label.configure(text=header)
        self._side_resp_replace(result_text)
        self._copy_btn.pack_forget()  # only for master response, not hotlinks

        # If the AI call failed, display the error clearly and stop —
        # never show an accept/cancel dialog for an error.
        if not model_name:
            self._side_resp_label.configure(text=f"AI: {field_name} \u2014 FAILED")
            _error_dialog(self, f"AI Derivation Failed",
                          f"Could not derive '{field_name}'.\n\n{result_text}")
            return

        # Confirm with user — editable text box
        title = f"AI Derived: {field_name}  [{model_name}]  {time_str}  {cost_str}"
        edited = self._confirm_with_edit(title, field_name, result_text)
        if edited is not None:
            self._populate_field_value(field_name, edited)

    def _populate_field_value(self, field_name: str, value: str):
        """Write the derived value into the corresponding form widget."""
        if field_name == "service_status":
            path = ("serviceRecordAuthority", "service_status")
        elif field_name in ("place_of_death", "death_location"):
            path = ("derived_details", "fatality_locations", "death_location")
        elif field_name in ("grid_reference", "incident_location"):
            path = ("derived_details", "fatality_locations", "incident_location")
        elif field_name in ("co-ordinates_decimal", "coordinates_decimal", "incident_coordinates"):
            path = ("derived_details", "fatality_locations", "incident_coordinates")
        else:
            path = ("derived_details", field_name)

        entry = self._entry_widgets.get(path)
        if entry is None:
            return

        cleaned = value.strip()
        # Strip AI "best_estimate_gps" wrapper if present — the grid_reference /
        # incident_location prompt returns '"best_estimate_gps": "LAT, LON [GRID]"'.
        # Extract just the inner coordinate value.
        if field_name in ("grid_reference", "incident_location"):
            m = re.match(r'^"best_estimate_gps":\s*"([^"]*)"$', cleaned)
            if m:
                cleaned = m.group(1)
        if isinstance(entry, tk.Text):
            entry.delete("1.0", tk.END)
            entry.insert("1.0", cleaned)
        elif isinstance(entry, ttk.Combobox):
            status_values = ["Regular", "National Service", "Conscript", "Other", "Unassigned"]
            if cleaned in status_values:
                entry.set(cleaned)
            else:
                for sv in status_values:
                    if sv.lower() in cleaned.lower():
                        entry.set(sv)
                        break
                else:
                    entry.set("Other")
        else:
            entry.delete(0, tk.END)
            entry.insert(0, cleaned)

        self._on_field_edited()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        filename = os.path.basename(self.file_path)
        if self._modal_title:
            self.title(self._modal_title)
        else:
            self.title(f"Update {filename}")

        outer = tk.Frame(self, bg=BG_GREY)
        outer.pack(fill=tk.BOTH, expand=True)

        # --- Main content (left) ---
        main = tk.Frame(outer, bg=BG_GREY, padx=20, pady=16)
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Title (with KEY_REFERENCE_LINK hotlink)
        title_frame = tk.Frame(main, bg=BG_GREY)
        title_frame.pack(fill=tk.X, pady=(0, 12))
        tk.Label(title_frame, text=f"Update {filename}", font=(FONT, 16, "bold"),
                 bg=BG_GREY, fg=TEXT_DARK).pack(side=tk.LEFT)
        # Parse KEY_REFERENCE_LINK from .env for country-specific quick link
        country_code = filename[:2] if len(filename) >= 2 else ""
        if country_code:
            env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as _env_f:
                    for line in _env_f:
                        line = line.strip()
                        if line.startswith("KEY_REFERENCE_LINK="):
                            raw = line.split("=", 1)[1].strip().strip('"').strip("'")
                            for m in re.finditer(
                                r'([A-Z]{2})_(https?://[^\s\]]+)\s*\[([^\]]*)\]', raw
                            ):
                                if m.group(1) == country_code:
                                    url, link_name = m.group(2), m.group(3)
                                    link_lbl = tk.Label(
                                        title_frame, text=f"\U0001F517 {link_name}",
                                        font=(FONT, 10, "underline"), bg=BG_GREY,
                                        fg="#4a90d9", cursor="hand2"
                                    )
                                    link_lbl.pack(side=tk.LEFT, padx=(12, 0))
                                    link_lbl.bind("<Button-1>", lambda e, u=url: _open_url(u))
                                    break
                            break

        # Web query link — updated per record in _show_record
        country_map_full = {"AU": "Australia", "NZ": "New Zealand"}
        country_name = country_map_full.get(country_code, country_code)
        self._web_query_link = tk.Label(
            title_frame, text="\U0001F310 Web query",
            font=(FONT, 10, "underline"), bg=BG_GREY,
            fg="#4a90d9", cursor="hand2"
        )
        self._web_query_link.pack(side=tk.LEFT, padx=(12, 0))
        self._web_query_country = country_name

        # Search
        sf = tk.Frame(main, bg=BG_GREY)
        sf.pack(fill=tk.X, pady=(0, 8))
        tk.Label(sf, text="\U0001F50D", font=(FONT, 12), bg=BG_GREY, fg=TEXT_MUTED).pack(side=tk.LEFT, padx=(0, 6))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search_changed())
        self._search_entry = _styled_entry(sf, width=24, textvariable=self._search_var)
        self._search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # OnThisDay date filter: month + day entries (defaults today) + checkbox
        tk.Label(sf, text="  Use OnThisDay", font=(FONT, 9), bg=BG_GREY, fg=TEXT_MUTED).pack(side=tk.LEFT, padx=(8, 2))
        self._on_this_day_month_entry = tk.Entry(sf, width=3, font=(FONT, 9), bg=WHITE, fg=TEXT_DARK,
                                                  textvariable=self._on_this_day_month_var,
                                                  justify=tk.CENTER)
        self._on_this_day_month_entry.pack(side=tk.LEFT)
        tk.Label(sf, text="-", font=(FONT, 9), bg=BG_GREY, fg=TEXT_MUTED).pack(side=tk.LEFT)
        self._on_this_day_day_entry = tk.Entry(sf, width=3, font=(FONT, 9), bg=WHITE, fg=TEXT_DARK,
                                                textvariable=self._on_this_day_day_var,
                                                justify=tk.CENTER)
        self._on_this_day_day_entry.pack(side=tk.LEFT)
        self._on_this_day_chk = tk.Checkbutton(
            sf, text="", variable=self._on_this_day_chk_var,
            bg=BG_GREY, activebackground=BG_GREY,
            command=self._on_this_day_toggled
        )
        self._on_this_day_chk.pack(side=tk.LEFT, padx=(2, 0))
        self._on_this_day_month_var.trace_add("write", lambda *_: self._on_this_day_changed())
        self._on_this_day_day_var.trace_add("write", lambda *_: self._on_this_day_changed())
        # Initial state: date picker disabled (OnThisDay unchecked by default)
        self._on_this_day_month_entry.configure(state=tk.DISABLED)
        self._on_this_day_day_entry.configure(state=tk.DISABLED)
        self._search_count = tk.Label(sf, text="", font=(FONT, 9), bg=BG_GREY, fg=TEXT_MUTED)
        self._search_count.pack(side=tk.RIGHT, padx=(8, 0))

        # Nav
        nf = tk.Frame(main, bg=BG_GREY)
        nf.pack(fill=tk.X, pady=(0, 8))
        self._prev_btn = self._flat_btn(nf, "\u25c0  Previous", self._prev, bg=BORDER, fg=TEXT_DARK, side=tk.LEFT)
        self._record_label = tk.Label(nf, text="", font=(FONT, 10, "bold"), bg=BG_GREY, fg=TEXT_DARK)
        self._record_label.pack(side=tk.LEFT, expand=True)
        self._next_btn = self._flat_btn(nf, "Next  \u25b6", self._next, bg=BORDER, fg=TEXT_DARK, side=tk.RIGHT)

        # Lock bar
        self._lock_frame = tk.Frame(main, bg="#fff3cd")
        tk.Label(self._lock_frame, text="\u26a0  Record locked — you have unsaved changes",
                 font=(FONT, 9, "bold"), bg="#fff3cd", fg="#856404").pack(side=tk.LEFT, padx=(10, 10), pady=6)
        self._discard_btn = tk.Label(self._lock_frame, text="Discard Changes", font=(FONT, 9, "bold"),
                                     bg="#e0e0e0", fg=TEXT_DARK, padx=14, pady=4, cursor="hand2")
        self._discard_btn.pack(side=tk.RIGHT, padx=(0, 5), pady=4)
        _bind_hover(self._discard_btn, "#e0e0e0", "#c0c0c0")
        self._discard_btn.bind("<Button-1>", lambda e: self._discard_record())
        self._update_record_btn = tk.Label(self._lock_frame, text="Update Record", font=(FONT, 9, "bold"),
                                           bg=ACCENT, fg=WHITE, padx=14, pady=4, cursor="hand2")
        self._update_record_btn.pack(side=tk.RIGHT, padx=(0, 5), pady=4)
        _bind_hover(self._update_record_btn, ACCENT, ACCENT_HOV)
        self._update_record_btn.bind("<Button-1>", lambda e: self._update_record())

        # Card
        self._card = tk.Frame(main, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        self._card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        cf = tk.Frame(self._card, bg=WHITE)
        cf.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self._canvas = tk.Canvas(cf, bg=WHITE, borderwidth=0, highlightthickness=0)
        sb = ttk.Scrollbar(cf, orient=tk.VERTICAL, command=self._canvas.yview)
        self._fields_frame = tk.Frame(self._canvas, bg=WHITE)
        self._fields_frame.bind("<Configure>", lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas_window = self._canvas.create_window((0, 0), window=self._fields_frame, anchor="nw")
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(self._canvas_window, width=e.width))
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        def _mw(event):
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._canvas.bind_all("<MouseWheel>", _mw)

        # Bottom buttons — pinned to the bottom of the main panel
        bf = tk.Frame(main, bg=BG_GREY)
        bf.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))

        # Top row: AI button + Live Search + Close
        top_row = tk.Frame(bf, bg=BG_GREY)
        top_row.pack(fill=tk.X)
        self._flat_btn(top_row, "Close", self._cancel, bg="#e0e0e0", fg=TEXT_DARK, side=tk.RIGHT)
        self._flat_btn(top_row, "AI: Create a Master Response", self._ai_lookup, bg="#4a90d9", fg=WHITE, side=tk.LEFT)
        self._all_hotlinks_btn = self._flat_btn(top_row, "All Hotlinks", self._all_hotlinks, bg="#e67e22", fg=WHITE, side=tk.LEFT, right_pad=10)

        self._live_search_var = tk.BooleanVar(value=True)
        self._live_search_chk = tk.Checkbutton(
            top_row, text="Live Search", variable=self._live_search_var,
            bg=BG_GREY, fg=TEXT_DARK, activebackground=BG_GREY, font=(FONT, 9)
        )
        self._live_search_chk.pack(side=tk.LEFT, padx=(10, 0))

        self._side_panel_visible_var = tk.BooleanVar(value=True)
        self._side_panel_chk = tk.Checkbutton(
            top_row, text="Side Panel", variable=self._side_panel_visible_var,
            bg=BG_GREY, fg=TEXT_DARK, activebackground=BG_GREY, font=(FONT, 9),
            command=self._toggle_side_panel
        )
        self._side_panel_chk.pack(side=tk.LEFT, padx=(10, 0))

        self._copy_btn = self._flat_btn(
            top_row, "AI: COPY RESPONSE: to ai_response", self._copy_response_to_ai_response,
            bg="#2e7d32", fg=WHITE, side=tk.LEFT, right_pad=10
        )
        self._copy_btn.pack_forget()  # hidden until response exceeds 200 chars

        # Dropdown row below the top row
        self._payload_dropdown_var = tk.StringVar(value="Option A: 1-Step (JSON Schema)")
        self._payload_dropdown = ttk.Combobox(
            bf,
            textvariable=self._payload_dropdown_var,
            values=[
                "Option A: 1-Step (JSON Schema)",
                "Option B: 2-Step Legacy (Search -> Structure)",
                "Option C: 1-Step Narrative (Raw Prose)"
            ],
            state="readonly",
            width=40
        )
        self._payload_dropdown.pack(fill=tk.X, pady=(4, 0))

        self.bind("<Escape>", lambda _e: self._cancel())

        # --- Side panel (right, hidden) ---
        self._side_panel = tk.Frame(outer, bg="#f0f2f5", width=500)
        self._side_panel.pack_propagate(False)

        sh = tk.Frame(self._side_panel, bg="#4a90d9", height=40)
        sh.pack(fill=tk.X)
        sh.pack_propagate(False)
        tk.Label(sh, text="AI RESULTS", font=(FONT, 10, "bold"), bg="#4a90d9", fg=WHITE).pack(side=tk.LEFT, padx=12, pady=8)
        hb = tk.Label(sh, text="\u2715", font=(FONT, 12, "bold"), bg="#4a90d9", fg=WHITE, padx=10, pady=4, cursor="hand2")
        hb.pack(side=tk.RIGHT)
        hb.bind("<Button-1>", lambda e: self._hide_side_panel())

        self._side_prompt_label = tk.Label(
            self._side_panel, text="PROMPT", font=(FONT, 8, "bold"),
            bg="#f0f2f5", fg=TEXT_MUTED, anchor="w",
        )
        self._side_prompt_label.pack(fill=tk.X, padx=12, pady=(10, 2))
        prompt_frame = tk.Frame(self._side_panel, bg=WHITE)
        prompt_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 6))
        self._side_prompt = tk.Text(prompt_frame, font=(FONT, 8), wrap=tk.WORD,
                                    bg=WHITE, fg=TEXT_DARK, padx=8, pady=6,
                                    relief=tk.FLAT, highlightthickness=0)
        prompt_scroll = tk.Scrollbar(prompt_frame, command=self._side_prompt.yview)
        self._side_prompt.configure(yscrollcommand=prompt_scroll.set)
        prompt_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._side_prompt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._side_resp_label = tk.Label(self._side_panel, text="RESPONSE", font=(FONT, 8, "bold"),
                                          bg="#f0f2f5", fg=TEXT_MUTED, anchor="w")
        self._side_resp_label.pack(fill=tk.X, padx=12, pady=(4, 2))
        resp_frame = tk.Frame(self._side_panel, bg=WHITE)
        resp_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))
        self._side_resp = tk.Text(resp_frame, font=(FONT, 9), wrap=tk.WORD,
                                  bg=WHITE, fg=TEXT_DARK, padx=8, pady=6,
                                  relief=tk.FLAT, highlightthickness=0)
        resp_scroll = tk.Scrollbar(resp_frame, command=self._side_resp.yview)
        self._side_resp.configure(yscrollcommand=resp_scroll.set)
        resp_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._side_resp.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # Flat button helper
    # ------------------------------------------------------------------

    def _flat_btn(self, parent, text, command, bg, fg, side, right_pad=0) -> tk.Label:
        btn = tk.Label(parent, text=text, font=(FONT, 10, "bold"),
                       bg=bg, fg=fg, padx=18, pady=6, cursor="hand2")
        btn.pack(side=side, padx=(0, right_pad))
        hover_bg = ACCENT_HOV if bg == ACCENT else ("#3a7bc8" if bg == "#4a90d9" else "#c0c0c0")
        _bind_hover(btn, bg, hover_bg)
        btn.bind("<Button-1>", lambda e: command())
        return btn

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search_changed(self):
        self._search_text = self._search_var.get().strip().lower()
        self._apply_search()

    def _on_this_day_changed(self):
        # Date entry changed while checkbox is checked — re-apply filter
        self._apply_search()

    def _on_this_day_toggled(self):
        """Mutually exclusive: text search OR OnThisDay filter, never both."""
        if self._on_this_day_chk_var.get():
            # OnThisDay ON → clear & disable text search
            self._search_var.set("")
            self._search_text = ""
            self._search_entry.configure(state=tk.DISABLED)
            self._on_this_day_month_entry.configure(state=tk.NORMAL)
            self._on_this_day_day_entry.configure(state=tk.NORMAL)
        else:
            # OnThisDay OFF → enable text search, disable date picker
            self._on_this_day_month_entry.configure(state=tk.DISABLED)
            self._on_this_day_day_entry.configure(state=tk.DISABLED)
            self._search_entry.configure(state=tk.NORMAL)
        self._apply_search()

    def _apply_search(self):
        if not self._search_text:
            self._filtered = list(range(len(self.working_data)))
        else:
            self._filtered = []
            for i, record in enumerate(self.working_data):
                def _search_dict(d):
                    for v in d.values():
                        if isinstance(v, dict):
                            if _search_dict(v):
                                return True
                        elif self._search_text in str(v).lower():
                            return True
                    return False
                if _search_dict(record):
                    self._filtered.append(i)
        # OnThisDay filter: restrict to records with date_of_death matching mm-dd
        if self._on_this_day_chk_var.get():
            m_str = self._on_this_day_month_var.get().strip()
            d_str = self._on_this_day_day_var.get().strip()
            if m_str and d_str:
                try:
                    m = int(m_str)
                    d = int(d_str)
                    if 1 <= m <= 12 and 1 <= d <= 31:
                        target_ddmm = f"{m:02d}-{d:02d}"
                        self._filtered = [
                            i for i in self._filtered
                            if (dod := (self.working_data[i]
                                        .get("serviceRecordAuthority", {})
                                        .get("date_of_death", "")))
                            and dod[-5:] == target_ddmm
                        ]
                except ValueError:
                    pass  # invalid input → no filter applied
        self._filtered_pos = 0
        total = len(self._filtered)
        self._search_count.configure(text=f"{total} match{'es' if total != 1 else ''}" if (self._search_text or self._on_this_day_chk_var.get()) else "")
        self._show_record()
        session_manager._save_session(self.file_path, self._filtered_pos, self._search_text, extra={
            "ai_option": self._payload_dropdown_var.get(),
            "live_search": self._live_search_var.get(),
            "on_this_day": self._on_this_day_chk_var.get(),
            "on_this_day_month": self._on_this_day_month_var.get(),
            "on_this_day_day": self._on_this_day_day_var.get(),
            "side_panel_visible": self._side_panel_visible_var.get(),
        })

    # ------------------------------------------------------------------
    # Record display
    # ------------------------------------------------------------------

    def _apply_hotlinks(self, text_widget: tk.Text):
        text_widget.tag_remove("link", "1.0", tk.END)
        content = text_widget.get("1.0", "end-1c")
        import re
        pattern = r'(https?://[^\s]+|www\.[^\s]+)'
        for match in re.finditer(pattern, content):
            start = match.start()
            end = match.end()
            text_widget.tag_add("link", f"1.0+{start}c", f"1.0+{end}c")
            
        text_widget.tag_config("link", foreground="#4a90d9", underline=1)
        
        def _on_click(event):
            idx = text_widget.index(f"@{event.x},{event.y}")
            tags = text_widget.tag_names(idx)
            if "link" in tags:
                ranges = text_widget.tag_ranges("link")
                for i in range(0, len(ranges), 2):
                    if text_widget.compare(ranges[i], "<=", idx) and text_widget.compare(idx, "<=", ranges[i+1]):
                        url = text_widget.get(ranges[i], ranges[i+1])
                        if url.startswith("www."):
                            url = "http://" + url
                        import webbrowser
                        webbrowser.open(url)
                        break

        def _on_enter(event):
            text_widget.config(cursor="hand2")
        def _on_leave(event):
            text_widget.config(cursor="xterm")
            
        text_widget.tag_bind("link", "<Button-1>", _on_click)
        text_widget.tag_bind("link", "<Enter>", _on_enter)
        text_widget.tag_bind("link", "<Leave>", _on_leave)

    def _show_record(self):
        # ── Save current side-panel state for the outgoing record ──
        self._save_side_panel_state()
        for child in self._fields_frame.winfo_children():
            child.destroy()
        # Clear side-panel for the incoming record
        self._side_prompt.configure(state=tk.NORMAL)
        self._side_prompt.delete("1.0", tk.END)
        self._side_prompt_label.configure(text="PROMPT")
        self._side_resp_label.configure(text="RESPONSE")
        self._side_resp_replace("")
        # Respect Side Panel checkbox
        if self._side_panel_visible_var.get():
            self._show_side_panel()
        total = len(self._filtered)
        full_total = len(self.working_data)
        if self._search_text:
            self._record_label.configure(text=f"Record {self._filtered_pos + 1} of {total}  (filtered from {full_total})")
        else:
            self._record_label.configure(text=f"Record {self._filtered_pos + 1} of {total}")
        self._prev_btn.configure(state=tk.NORMAL if self._filtered_pos > 0 else tk.DISABLED)
        self._next_btn.configure(state=tk.NORMAL if self._filtered_pos < total - 1 else tk.DISABLED)
        self._record_dirty = False
        self._record_snapshot = None
        self._set_locked(False)
        if total == 0:
            tk.Label(self._fields_frame, text="(No matching records)", font=(FONT, 11),
                     bg=WHITE, fg=TEXT_MUTED).pack(pady=30)
            self._entry_widgets = {}
            return
        import copy
        actual_idx = self._filtered[self._filtered_pos]
        record = self.working_data[actual_idx]
        # ── Update web query link for this record ──
        sra = record.get("serviceRecordAuthority", {}) if isinstance(
            record.get("serviceRecordAuthority"), dict
        ) else {}
        full_name = sra.get("full_name", "").strip()
        if hasattr(self, "_web_query_link") and full_name:
            query = urllib.parse.quote(f"{full_name} {self._web_query_country} Vietnam War")
            url = f"https://www.google.com/search?q={query}"
            self._web_query_link.unbind("<Button-1>")
            self._web_query_link.bind("<Button-1>", lambda e, u=url: _open_url(u))
        self._record_snapshot = copy.deepcopy(record)
        # Copy incident_coordinates (or incident_location as fallback) to
        # clipboard on every record change
        dd = record.get("derived_details", {}) if isinstance(
            record.get("derived_details"), dict
        ) else {}
        fl = dd.get("fatality_locations", {}) if isinstance(dd.get("fatality_locations"), dict) else {}
        coord_val = str(fl.get("incident_coordinates", "") or fl.get("incident_location", ""))
        if coord_val:
            self.clipboard_clear()
            self.clipboard_append(coord_val)

        # ── Compute hotlink activation state ──
        ai_resp = (dd.get("ai_response", "") or "").strip()
        override_raw = (dd.get("authoritative_ai_override", "") or "").strip()
        override = override_raw if override_raw and override_raw.lower() != "unassigned" else ""
        if override:
            self._hotlink_combined_text = f"authoritative_ai_override:\n{override}\n\nai_response:\n{ai_resp}".strip()
        else:
            self._hotlink_combined_text = ai_resp
        # Strip **[...]** metadata header produced by _make_header (see README
        # § Hotlink Metadata Filtering).  Tags must appear within the first 80
        # characters; if found the entire tagged block is removed so only the
        # payload reaches hotlink AI queries.
        if "**[" in self._hotlink_combined_text[:80]:
            end = self._hotlink_combined_text.find("]**")
            if end != -1:
                self._hotlink_combined_text = self._hotlink_combined_text[end + 3:]
        word_count = len(self._hotlink_combined_text.split())
        self._hotlink_active = word_count > 50
        if self._hotlink_active:
            self._all_hotlinks_btn.pack(side=tk.LEFT, padx=(0, 10), before=self._live_search_chk)
        else:
            self._all_hotlinks_btn.pack_forget()

        self._entry_widgets = {}

        def _render_fields(parent_frame, data_dict, prefix_path=()):
            items = list(data_dict.items())
            items.sort(key=lambda x: 1 if x[0] in ('summary', 'record_status') else 0)
            for field_name, raw_value in items:
                current_path = prefix_path + (field_name,)
                if isinstance(raw_value, dict):
                    hf = tk.Frame(parent_frame, bg=WHITE)
                    hf.pack(fill=tk.X, padx=16 if not prefix_path else 0, pady=(12, 4))
                    tk.Label(hf, text=field_name.upper(), font=(FONT, 10, "bold"), bg=WHITE, fg=ACCENT).pack(side=tk.LEFT, padx=(16 if not prefix_path else 0, 0))
                    sub_frame = tk.Frame(parent_frame, bg=WHITE)
                    sub_frame.pack(fill=tk.X, padx=(32, 0), pady=0)
                    _render_fields(sub_frame, raw_value, current_path)
                else:
                    rf = tk.Frame(parent_frame, bg=WHITE)
                    rf.pack(fill=tk.X, padx=16 if not prefix_path else 0, pady=4)
                    field_label = tk.Label(rf, text=f"{field_name}", font=(FONT, 10),
                                           bg=WHITE, fg=TEXT_DARK)
                    field_label.pack(side=tk.LEFT, padx=(0, 10), anchor=tk.N)
                    _HOTLINK_FIELDS = {"service_status", "death_location",
                                       "circumstances_of_death", "unit_served_with",
                                       "incident_location", "incident_coordinates"}
                    if field_name in _HOTLINK_FIELDS:
                        self._make_label_hotlink(field_label, field_name)
                    # Format list values (e.g. references) as newline-separated text
                    if isinstance(raw_value, list):
                        dv = "\n".join(str(item) for item in raw_value)
                    else:
                        dv = str(raw_value) if raw_value is not None else ""
                    is_editable = prefix_path and (prefix_path[0] == "derived_details" or field_name == "service_status" or field_name == "unit")
                    entry_font = (FONT, 12) if is_editable else (FONT, 10)
                    if not is_editable:
                        entry = _styled_entry(rf, width=42, font=entry_font)
                        entry.insert(0, dv)
                        entry.configure(state="readonly", readonlybackground="#f0f0f0", fg=TEXT_MUTED)
                        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    else:
                        if field_name in ("circumstances_of_death", "summary", "ai_response", "authoritative_ai_override"):
                            if field_name == "summary":
                                text_height = 3
                            elif field_name == "ai_response":
                                text_height = 8
                            elif field_name == "authoritative_ai_override":
                                text_height = 5
                            else:
                                text_height = 4

                            # Container frame for text + scrollbar
                            text_frame = tk.Frame(rf, bg=BG_GREY)
                            text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=4)

                            entry = tk.Text(text_frame, font=entry_font, height=text_height, width=42,
                                            wrap=tk.WORD, bg=WHITE, fg=TEXT_DARK, relief=tk.FLAT,
                                            highlightbackground=BORDER, highlightcolor=ACCENT,
                                            highlightthickness=1, insertbackground=TEXT_DARK)
                            entry.insert("1.0", dv)

                            scrollbar = tk.Scrollbar(text_frame, command=entry.yview)
                            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                            entry.configure(yscrollcommand=scrollbar.set)
                            entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

                            def _on_text_edited(_e, tw=entry):
                                self._on_field_edited()
                                self._apply_hotlinks(tw)

                            entry.bind("<KeyRelease>", _on_text_edited)
                            self._apply_hotlinks(entry)
                        elif isinstance(raw_value, list):
                            # references or other list fields: multi-line text, one item per line
                            text_height = 3
                            entry = tk.Text(rf, font=entry_font, height=text_height, width=42, wrap=tk.WORD,
                                            bg=WHITE, fg=TEXT_DARK, relief=tk.FLAT,
                                            highlightbackground=BORDER, highlightcolor=ACCENT,
                                            highlightthickness=1, insertbackground=TEXT_DARK)
                            entry.insert("1.0", dv)

                            def _on_list_edited(_e, tw=entry):
                                self._on_field_edited()
                                self._apply_hotlinks(tw)

                            entry.bind("<KeyRelease>", _on_list_edited)
                            self._apply_hotlinks(entry)
                            entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=4)
                        elif field_name == "incident_location":
                            # Info icon explaining the relationship to incident_coordinates
                            info_btn = tk.Label(
                                rf, text="\u2139", font=(FONT, 11),
                                bg=WHITE, fg="#4a90d9", cursor="hand2",
                            )
                            info_btn.pack(side=tk.LEFT, padx=(0, 6))
                            info_btn.bind(
                                "<Button-1>",
                                lambda e: _error_dialog(
                                    self, "About incident_location",
                                    "This field stores the raw grid reference as originally\n"
                                    "recorded — MGRS (e.g. YS 426 694), decimal degrees\n"
                                    "(e.g. 10.6895, 107.3305), or DMS notation.\n\n"
                                    "NOTE: GPS snippets must be enclosed in (bounded by)\n"
                                    "//....// within the text string.\n\n"
                                    "When you click Update Record, the editor inspects the\n"
                                    "FIRST //value// it finds.  It attempts to convert the\n"
                                    "value enclosed in \"//\" to a signed decimal degrees\n"
                                    "co-ordinate and if successful writes the result to the\n"
                                    "\"incident_coordinates\" field.\n\n"
                                    "Think of incident_location as the input and\n"
                                    "incident_coordinates as the calculated output.\n\n"
                                    "Accepted formats are listed in the Info button on the\n"
                                    "incident_coordinates field."
                                )
                            )
                            entry = _styled_entry(rf, width=42, font=entry_font)
                            entry.insert(0, dv)
                            entry.bind("<KeyRelease>", lambda _e: self._on_field_edited())
                            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                        elif field_name in ("co-ordinates_decimal", "coordinates_decimal", "incident_coordinates"):
                            # Small info button that opens the MGRS reference doc
                            info_btn = tk.Label(
                                rf, text="\u2139", font=(FONT, 11),
                                bg=WHITE, fg="#4a90d9", cursor="hand2",
                            )
                            info_btn.pack(side=tk.LEFT, padx=(0, 6))
                            info_btn.bind(
                                "<Button-1>", lambda e: self._show_mgrs_info()
                            )
                            entry = _styled_entry(rf, width=42, font=entry_font)
                            entry.insert(0, dv)
                            _ToolTip(entry,
                                     "Double-click to open this location in Google Maps")

                            def _update_link_style(*args, w=entry):
                                val_str = w.get().strip()
                                if val_str:
                                    # Strip {original} suffix before validating
                                    decimal_part, _ = _split_coord_display(val_str)
                                    is_valid, _, parsed = coords.validate_and_parse_coordinate(decimal_part)
                                    if is_valid and parsed is not None:
                                        fnt = list(entry_font)
                                        fnt.append("underline")
                                        w.configure(fg="#4a90d9", font=tuple(fnt), cursor="hand2")
                                        return
                                w.configure(fg=TEXT_DARK, font=entry_font, cursor="xterm")
                                
                            _update_link_style()
                            entry.bind("<KeyRelease>", lambda e, w=entry: (_update_link_style(), self._on_field_edited()))
                            
                            def _open_map(event, w=entry):
                                val_str = w.get().strip()
                                if val_str:
                                    # Strip {original} suffix before parsing
                                    decimal_part, _ = _split_coord_display(val_str)
                                    is_valid, _, parsed = coords.validate_and_parse_coordinate(decimal_part)
                                    if is_valid and parsed is not None:
                                        import webbrowser
                                        webbrowser.open(f"https://www.google.com/maps?q={parsed[0]},{parsed[1]}")
                                        
                            entry.bind("<Double-Button-1>", _open_map)
                            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                        elif field_name == "death_location":
                            entry = _styled_entry(rf, width=42, font=entry_font)
                            entry.insert(0, dv)
                            entry.bind("<KeyRelease>", lambda _e: self._on_field_edited())
                            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                        elif field_name == "service_status":
                            status_values = ["Regular", "National Service", "Conscript", "Other", "Unassigned"]
                            entry = ttk.Combobox(rf, values=status_values, state="readonly",
                                                 font=entry_font, width=40)
                            current_val = dv.strip()
                            if current_val in status_values:
                                entry.set(current_val)
                            else:
                                entry.set("Other")
                            entry.bind("<<ComboboxSelected>>", lambda _e: self._on_field_edited())
                            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                        else:
                            entry = _styled_entry(rf, width=42, font=entry_font)
                            entry.insert(0, dv)
                            entry.bind("<KeyRelease>", lambda _e: self._on_field_edited())
                            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    self._entry_widgets[current_path] = entry

        _render_fields(self._fields_frame, record)
        tk.Frame(self._fields_frame, bg=WHITE, height=8).pack()
        
        self.update_idletasks()
        self._canvas.yview_moveto(0)

    # ------------------------------------------------------------------
    # Record locking
    # ------------------------------------------------------------------

    def _on_field_edited(self):
        if not self._record_dirty:
            self._record_dirty = True
            self._set_locked(True)

    def _set_locked(self, locked: bool):
        state = tk.DISABLED if locked else tk.NORMAL
        self._prev_btn.configure(state=state)
        self._next_btn.configure(state=state)
        if locked:
            self._search_entry.configure(state=tk.DISABLED)
            self._on_this_day_month_entry.configure(state=tk.DISABLED)
            self._on_this_day_day_entry.configure(state=tk.DISABLED)
            self._on_this_day_chk.configure(state=tk.DISABLED)
            self._side_panel_chk.configure(state=tk.DISABLED)
        else:
            # Mutual exclusivity: enable only the active filter widget
            if self._on_this_day_chk_var.get():
                self._search_entry.configure(state=tk.DISABLED)
                self._on_this_day_month_entry.configure(state=tk.NORMAL)
                self._on_this_day_day_entry.configure(state=tk.NORMAL)
            else:
                self._search_entry.configure(state=tk.NORMAL)
                self._on_this_day_month_entry.configure(state=tk.DISABLED)
                self._on_this_day_day_entry.configure(state=tk.DISABLED)
            self._on_this_day_chk.configure(state=tk.NORMAL)
            self._side_panel_chk.configure(state=tk.NORMAL)
        if locked:
            self._lock_frame.pack(fill=tk.X, pady=(0, 6), before=self._card)
        else:
            self._lock_frame.pack_forget()

    # ------------------------------------------------------------------
    # Per-record actions
    # ------------------------------------------------------------------

    def _read_form(self) -> dict | None:
        if not self._entry_widgets:
            return {}
        actual_idx = self._filtered[self._filtered_pos]
        original = self.working_data[actual_idx]
        
        import copy
        result = copy.deepcopy(original)
        
        for path_tuple, entry in self._entry_widgets.items():
            if isinstance(entry, tk.Text):
                raw_value = entry.get("1.0", "end-1c")
            else:
                raw_value = entry.get()
            
            orig_val = original
            for key in path_tuple:
                if isinstance(orig_val, dict):
                    orig_val = orig_val.get(key, "")
                else:
                    orig_val = ""
                    
            field_name = path_tuple[-1]
            is_editable = len(path_tuple) > 0 and (path_tuple[0] == "derived_details" or field_name == "service_status" or field_name == "unit")
            
            if not is_editable:
                val = orig_val
            else:
                try:
                    if isinstance(orig_val, bool):
                        val_str = raw_value.strip().lower()
                        if val_str in ("true", "1", "yes"):
                            val = True
                        elif val_str in ("false", "0", "no", ""):
                            val = False
                        else:
                            raise ValueError(f"'{raw_value}' is not a valid boolean")
                    elif isinstance(orig_val, int):
                        val = int(raw_value.strip())
                    elif isinstance(orig_val, float):
                        val = float(raw_value.strip())
                    elif isinstance(orig_val, list):
                        # Parse newline-separated text back to list (e.g. references)
                        lines = raw_value.strip().split("\n")
                        val = [line.strip() for line in lines if line.strip()]
                    else:
                        val = raw_value
                        
                        # ── incident_location: copy to clipboard for reference ──
                        if field_name == "incident_location":
                            val_str = str(val).strip()
                            if val_str and val_str.lower() != "unassigned" and not re.match(r'^[A-Za-z]+$', val_str):
                                self.clipboard_clear()
                                self.clipboard_append(val_str)

                        # ── incident_coordinates: validate / normalise decimal format ──
                        elif field_name in ("co-ordinates_decimal", "coordinates_decimal", "incident_coordinates"):
                            val_str = str(val).strip()
                            if val_str and not re.match(r'^[A-Za-z]+$', val_str):
                                clean_val, _ = _split_coord_display(val_str)
                                is_valid, msg, parsed = coords.validate_and_parse_coordinate(clean_val)
                                if not is_valid:
                                    _error_dialog(
                                        self, "Invalid incident_coordinates",
                                        "\"incident_coordinates\" requires a valid decimal\n"
                                        "coordinate in \"latitude, longitude\" format.\n\n"
                                        "Examples:\n"
                                        "  10.6895, 107.3305\n"
                                        "  -33.8688, 151.2093\n\n"
                                        "The value you entered could not be parsed:\n"
                                        f"  \"{val_str}\"\n\n"
                                        "Leave the field blank or enter a correct decimal\n"
                                        "coordinate.  To convert a grid reference, enter it\n"
                                        "in the \"incident_location\" field and click Update Record."
                                    )
                                    return None
                                if parsed is not None:
                                    val = f"{parsed[0]}, {parsed[1]}"

                        # Prevent saving with an empty unit field
                        if field_name == "unit" and not str(val).strip():
                            _error_dialog(
                                self, "Missing Unit",
                                "The 'unit' field cannot be empty.\n"
                                "Please enter the soldier's unit before updating.",
                            )
                            return None

                except (ValueError, TypeError) as exc:
                    _error_dialog(self, "Type Error",
                                  f"Field '{'.'.join(path_tuple)}': '{raw_value}' does not match "
                                  f"expected type ({type(orig_val).__name__}).\n\n{exc}")
                    return None
                    
            target = result
            for key in path_tuple[:-1]:
                if key not in target or not isinstance(target[key], dict):
                    target[key] = {}
                target = target[key]
            target[path_tuple[-1]] = val
        
        return result

    def _update_record(self):
        updated = self._read_form()
        if updated is None:
            return
        record_id = updated.get("referenceID", str(self._filtered_pos + 1))
        ok = _confirm_yesno(self, "Confirm Update", f'Please confirm update for "{record_id}"')
        if not ok:
            return
        # Update record_status: mark as changed (today's date)
        # record_status.update_to_firestore is managed by a separate process — leave as-is
        if "record_status" not in updated:
            updated["record_status"] = {}
        updated["record_status"]["changed"] = date.today().strftime("%Y-%m-%d")
        actual_idx = self._filtered[self._filtered_pos]
        self.working_data[actual_idx] = updated
        if not _save_json(self.file_path, self.working_data):
            return
        self.original_data.clear()
        self.original_data.extend(self.working_data)
        self.dirty = False
        self._record_dirty = False
        self._set_locked(False)
        # ── Preserve side-panel content across the _show_record clear ──
        saved_prompt = self._side_prompt.get("1.0", "end-1c").strip()
        saved_prompt_label = self._side_prompt_label.cget("text")
        saved_resp = self._side_resp.get("1.0", "end-1c").strip()
        saved_resp_label = self._side_resp_label.cget("text")
        self._show_record()
        # Restore side-panel — same record, content should persist
        self._side_prompt.configure(state=tk.NORMAL)
        self._side_prompt.delete("1.0", tk.END)
        self._side_prompt.insert("1.0", saved_prompt)
        self._side_prompt_label.configure(text=saved_prompt_label)
        self._side_resp_label.configure(text=saved_resp_label)
        self._side_resp_replace(saved_resp)

    def _discard_record(self):
        if self._record_snapshot is not None:
            actual_idx = self._filtered[self._filtered_pos]
            self.working_data[actual_idx] = dict(self._record_snapshot)
        self._record_dirty = False
        self._set_locked(False)
        self._show_record()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _prev(self):
        if self._record_dirty:
            return
        if self._filtered_pos > 0:
            self._filtered_pos -= 1
            self._show_record()
            session_manager._save_session(self.file_path, self._filtered_pos, self._search_text, extra={
                "ai_option": self._payload_dropdown_var.get(),
                "live_search": self._live_search_var.get(),
                "on_this_day": self._on_this_day_chk_var.get(),
                "on_this_day_month": self._on_this_day_month_var.get(),
                "on_this_day_day": self._on_this_day_day_var.get(),
                "side_panel_visible": self._side_panel_visible_var.get(),
            })

    def _next(self):
        if self._record_dirty:
            return
        if self._filtered_pos < len(self._filtered) - 1:
            self._filtered_pos += 1
            self._show_record()
            session_manager._save_session(self.file_path, self._filtered_pos, self._search_text, extra={
                "ai_option": self._payload_dropdown_var.get(),
                "live_search": self._live_search_var.get(),
                "on_this_day": self._on_this_day_chk_var.get(),
                "on_this_day_month": self._on_this_day_month_var.get(),
                "on_this_day_day": self._on_this_day_day_var.get(),
                "side_panel_visible": self._side_panel_visible_var.get(),
            })

    # ------------------------------------------------------------------
    # Side panel
    # ------------------------------------------------------------------

    def _show_side_panel(self):
        self._side_panel.pack(side=tk.LEFT, fill=tk.Y, pady=16, after=self.winfo_children()[0].winfo_children()[0])

    def _hide_side_panel(self):
        self._side_panel.pack_forget()

    def _toggle_side_panel(self):
        """Toggle side panel visibility from the checkbox."""
        if self._side_panel_visible_var.get():
            self._show_side_panel()
        else:
            self._hide_side_panel()

    # ------------------------------------------------------------------
    # AI Lookup
    # ------------------------------------------------------------------

    def _ai_lookup(self):
        """
        Master AI Response Pipeline: Triggers the generative AI to populate 'derived_details'.
        Routes through the dynamic dropdown selector to choose the appropriate prompt architecture.
        """
        if not self._filtered:
            return

        is_live_search = self._live_search_var.get()
        selected_option = self._payload_dropdown_var.get()
        
        actual_idx = self._filtered[self._filtered_pos]
        record = self.working_data[actual_idx]

        dd = record.get("derived_details", {}) if isinstance(record.get("derived_details"), dict) else {}
        existing = dd.get("ai_response", "").strip()
        # Only warn if there is substantive content (ignore placeholders like "Unassigned")
        has_substantive = existing and existing.lower() != "unassigned" and len(existing) > 10
        warning = (
            "\n\nWarning: 'ai_response' data already exists in this record. "
            "Running this process will re-create it again for review, but not immediately overwrite it."
        ) if has_substantive else ""

        # Read provider for confirmation dialog
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        env = {
            line.partition("=")[0].strip(): line.partition("=")[2].strip().strip('"').strip("'")
            for line in (l.strip() for l in open(env_path, "r", encoding="utf-8"))
            if line and not line.startswith("#") and "=" in line
        } if os.path.exists(env_path) else {}

        confirm_msg = (
            f"Get a new dataset using "
            f"{env.get('AI_MASTER_MODEL_PROVIDER', 'Google')}\n"
            f"-----"
            f"This is a lengthy process (~2 minutes). Execute?\n\n"
            f"// Live Search is currently: {'ON' if is_live_search else 'OFF'}\n"
            f"[The AI has a fixed cutoff date. Live Search fills the gap by finding the latest web results up to the present moment.]\n\n"
            f"// AI processing Pipeline Selected : {selected_option}"
            f"{warning}"
        )
        result = _confirm_yesnocancel(self, "Confirm AI — Master Response", confirm_msg)
        if result is None or result is False:
            return

        sra = record.get("serviceRecordAuthority", {}) if isinstance(record.get("serviceRecordAuthority"), dict) else {}
        ref_id = record.get("referenceID", "")
        forces_map = {"AU": "Australian Armed Forces", "NZ": "New Zealand Armed Forces"}
        country_map = {"AU": "Australia", "NZ": "New Zealand"}
        
        full_name = sra.get("full_name", "")
        surname = full_name.split(",")[0].strip() if "," in full_name else full_name.strip()
        
        params = {
            "country": country_map.get(ref_id[:2], ""),
            "svc": sra.get("service_number", ""),
            "sra": sra,
            "name": full_name,
            "surname": surname,
            "dod": sra.get("date_of_death", ""),
            "dob": sra.get("date_of_birth", ""),
            "rank": sra.get("rank", ""),
            "unit": sra.get("unit", ""),
            "ftype": sra.get("fatality_type", ""),
            "af": forces_map.get(ref_id[:2], ref_id[:2] if ref_id else ""),
            "pod": (record.get("derived_details", {}).get("fatality_locations", {}).get("death_location", "") if isinstance(record.get("derived_details"), dict) else "")
        }

        if "Option A" in selected_option:
            config = ai_master_prompts.get_master_response_option_a_payload(params, is_live_search)
        elif "Option B" in selected_option:
            config = ai_master_prompts.get_master_response_option_b_payloads(params, is_live_search)
        else:
            config = ai_master_prompts.get_master_response_option_c_payload(params, is_live_search)

        master_provider = env.get("AI_MASTER_MODEL_PROVIDER", "Google").lower()
        allowed = [p.strip().lower() for p in env.get("AI_MODEL_PROVIDERS", "Google,Deepseek,OpenRouter").split(",") if p.strip()]
        if master_provider not in allowed:
            _error_dialog(self, "AI Error",
                          f"AI_MASTER_MODEL_PROVIDER \"{master_provider}\" is not a valid AI Provider.\n"
                          f"Allowed: {', '.join(allowed)}")
            return

        if master_provider == "deepseek":
            api_key = env.get("DEEPSEEK_API_KEY", "")
            models_str = env.get("DEEPSEEK_TEXT_TO_TEXT_MODELS_TO_USE", "deepseek-v4-pro,deepseek-v4-flash")
            if not api_key:
                _error_dialog(self, "AI Error", "DEEPSEEK_API_KEY not found in .env")
                return
        elif master_provider == "openrouter":
            api_key = env.get("OPENROUTER_API_KEY", "")
            if not api_key:
                _error_dialog(self, "AI Error", "OPENROUTER_API_KEY not found in .env")
                return
            # Parse allowed_models for the auto-router plugin
            _include_raw = env.get("OPENROUTER_MASTER_INCLUDE_MODELS", "")
            if not _include_raw:
                _error_dialog(self, "AI Error", "OPENROUTER_MASTER_INCLUDE_MODELS not found in .env")
                return
            try:
                import ast as _ast
                _allowed_models = list(_ast.literal_eval(_include_raw))
            except Exception as _e:
                _error_dialog(self, "AI Error", f"OPENROUTER_MASTER_INCLUDE_MODELS parse failed: {_e}")
                return
            models = ["openrouter/auto"]
            models_str = ""  # bypass the split below; models already set
        else:
            # Google (default)
            api_key = env.get("GEMINI_API_KEY", "")
            models_str = env.get("GEMINI_TEXT_TO_TEXT_MODELS_TO_USE", "gemini-2.5-pro,gemini-3.5-flash,gemini-2.5-flash")
            if not api_key:
                _error_dialog(self, "AI Error", "GEMINI_API_KEY not found in .env")
                return

        if not models_str:
            pass  # models already set for openrouter
        else:
            models = [m.strip() for m in models_str.split(",") if m.strip()]
        master_timeout = int(env.get("AI_MASTER_RESPONSE_MODEL_CUTOFF_SECONDS", "150"))

        try:
            ai_rates = json.loads(env.get("AI_RATES", "{}"))
        except Exception:
            ai_rates = {}
        try:
            aud_usd = float(env.get("AUD_USD", "0.7"))
        except Exception:
            aud_usd = 0.7

        if not api_key:
            _error_dialog(self, "AI Error", f"{master_provider.upper()}_API_KEY not found in .env")
            return

        self._side_prompt_label.configure(text=f"PROMPT: {selected_option}")
        self._side_resp_label.configure(text=f"RESPONSE: MASTER {selected_option}")
        self._side_prompt.configure(state=tk.NORMAL)
        self._side_prompt.delete("1.0", tk.END)
        self._side_prompt.insert("1.0", config["user_prompt"].replace("\\n", "\n"))
        self._side_resp.delete("1.0", tk.END)
        self._show_side_panel()

        def _task():
            last_error = ""
            start_time = time.time()
            step1_secs = 0.0
            step2_start = 0.0

            def _make_header(model_name, usage_meta, step1_model=None, step1_usage=None):
                from datetime import datetime
                now = datetime.now()
                ts = now.strftime("%d:%b:%Y %H:%M")
                
                def _calc_cost(mn, um):
                    if not um: return 0.0
                    # OpenRouter: cost auto-returned in usage_meta
                    if "totalCost" in um:
                        return um["totalCost"] * aud_usd
                    # Other providers: calculate from AI_RATES
                    if mn not in ai_rates: return 0.0
                    rate = ai_rates[mn]
                    pt = um.get("promptTokenCount", 0)
                    ct = um.get("candidatesTokenCount", 0)
                    return (pt * rate.get("in1", 0) / 1_000_000) * aud_usd + \
                           (ct * rate.get("out1", 0) / 1_000_000) * aud_usd

                c1 = _calc_cost(step1_model, step1_usage) if step1_model else 0.0
                c2 = _calc_cost(model_name, usage_meta)
                total = c1 + c2
                total_secs = time.time() - start_time
                
                provider_label = {"openrouter": "OpenRouter", "deepseek": "Deepseek", "google": "Google"}.get(master_provider, master_provider.capitalize())
                display_model = model_name if master_provider == "openrouter" else f"{provider_label} {model_name}"
                lines = [f"Created {ts} used {display_model} $A {total:.6f} ({total_secs:.0f}s) - {selected_option}"]
                if config["is_two_step"]:
                    lines.append(f"Step 1 ({step1_model}): $A {c1:.6f} ({step1_secs:.0f}s)")
                    lines.append(f"Step 2 ({model_name}): $A {c2:.6f} ({time.time()-step2_start:.0f}s)")
                # Metadata tagged with sentinel delimiters so _apply_hotlinks can
                # strip it before feeding data into AI field-derivation queries.
                # Display format: **[ Created {ts} used ... ]**\n{payload}
                return "**[" + "\n".join(lines) + "]**" + "\n"

            def _fmt_err(exc):
                if isinstance(exc, urllib.error.HTTPError):
                    try: return f"{exc.code} {exc.reason} - {exc.read().decode('utf-8', errors='replace')[:500]}"
                    except: return f"{exc.code} {exc.reason}"
                return str(exc)

            def _run_request(payload, log_msg, timeout):
                for model in models:
                    retry_count = 0
                    max_retries = 3
                    while retry_count <= max_retries:
                        msg = log_msg.replace("{m}", model)
                        if retry_count > 0: msg += f" (Retry {retry_count}/{max_retries})"
                        self.after(0, lambda m=msg: self._side_resp_replace(m))
                        
                        try:
                            if master_provider == "deepseek":
                                # Convert Gemini-format payload to OpenAI format
                                sys_text = payload.get("systemInstruction", {}).get("parts", [{}])[0].get("text", "")
                                user_text = payload.get("contents", [{}])[0].get("parts", [{}])[0].get("text", "")
                                gen_config = payload.get("generationConfig", {})
                                openai_payload = {
                                    "model": model,
                                    "temperature": gen_config.get("temperature", 0.3),
                                    "max_tokens": gen_config.get("maxOutputTokens", 2048),
                                    "messages": [
                                        {"role": "system", "content": sys_text},
                                        {"role": "user", "content": user_text},
                                    ],
                                }
                                url = "https://api.deepseek.com/v1/chat/completions"
                                body = json.dumps(openai_payload).encode("utf-8")
                                req = urllib.request.Request(url, data=body, headers={
                                    "Content-Type": "application/json",
                                    "Authorization": f"Bearer {api_key}",
                                })
                                with urllib.request.urlopen(req, timeout=timeout) as resp:
                                    data = json.loads(resp.read().decode("utf-8"))
                                    text = data["choices"][0]["message"]["content"]
                                    ds_usage = data.get("usage", {})
                                    um = {
                                        "promptTokenCount": ds_usage.get("prompt_tokens", 0),
                                        "candidatesTokenCount": ds_usage.get("completion_tokens", 0),
                                    }
                                    return model, text, um
                            elif master_provider == "openrouter":
                                # Convert Gemini-format payload to OpenAI format
                                sys_text = payload.get("systemInstruction", {}).get("parts", [{}])[0].get("text", "")
                                user_text = payload.get("contents", [{}])[0].get("parts", [{}])[0].get("text", "")
                                gen_config = payload.get("generationConfig", {})
                                openai_payload = {
                                    "model": "openrouter/auto",
                                    "temperature": gen_config.get("temperature", 0.3),
                                    "max_tokens": gen_config.get("maxOutputTokens", 2048),
                                    "messages": [
                                        {"role": "system", "content": sys_text},
                                        {"role": "user", "content": user_text},
                                    ],
                                    "plugins": [
                                        {
                                            "id": "auto-router",
                                            "allowed_models": _allowed_models,
                                            "cost_quality_tradeoff": 0
                                        }
                                    ],
                                }
                                url = "https://openrouter.ai/api/v1/chat/completions"
                                body = json.dumps(openai_payload).encode("utf-8")
                                req = urllib.request.Request(url, data=body, headers={
                                    "Content-Type": "application/json",
                                    "Authorization": f"Bearer {api_key}",
                                    "HTTP-Referer": "https://github.com/kun-app",
                                    "X-Title": "Update Fatalities",
                                })
                                with urllib.request.urlopen(req, timeout=timeout) as resp:
                                    data = json.loads(resp.read().decode("utf-8"))
                                    text = data["choices"][0]["message"]["content"]
                                    or_usage = data.get("usage", {})
                                    # OpenRouter returns full cost breakdown in response body
                                    actual_model = f"OpenRouter-{data.get('model', model)}"
                                    um = {
                                        "promptTokenCount": int(or_usage.get("input_tokens") or or_usage.get("prompt_tokens", 0)),
                                        "candidatesTokenCount": int(or_usage.get("output_tokens") or or_usage.get("completion_tokens", 0)),
                                        "totalTokenCount": int(or_usage.get("total_tokens", 0)),
                                        "totalCost": float(or_usage.get("total_cost") or or_usage.get("totalCost") or or_usage.get("cost") or 0),
                                        "inputCost": float(or_usage.get("input_cost", 0)),
                                        "outputCost": float(or_usage.get("output_cost", 0)),
                                    }
                                    # Fallback: try HTTP header if body cost is zero
                                    if um["totalCost"] == 0:
                                        try:
                                            um["totalCost"] = float(resp.info().get("x-openrouter-cost", "0"))
                                        except (ValueError, TypeError):
                                            pass
                                    # Log full OpenRouter response for cost verification
                                    try:
                                        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "openrouter.log"), "a", encoding="utf-8") as _log:
                                            _log.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} [master] model={actual_model} ---\n")
                                            _log.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n\n")
                                    except Exception:
                                        pass
                                    return actual_model, text, um
                            else:
                                # Google Gemini
                                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                                body = json.dumps(payload).encode("utf-8")
                                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
                                with urllib.request.urlopen(req, timeout=timeout) as resp:
                                    data = json.loads(resp.read().decode("utf-8"))
                                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                                    um = data.get("usageMetadata", {})
                                    return model, text, um
                        except Exception as exc:
                            if isinstance(exc, urllib.error.HTTPError) and exc.code in [429, 503] and retry_count < max_retries:
                                retry_count += 1
                                time.sleep(2.5)
                            else:
                                nonlocal last_error
                                last_error = f"{model}: {_fmt_err(exc)}"
                                break
                return None, None, None

            if not config["is_two_step"]:
                # Single step flow
                m, txt, um = _run_request(config["payloads"][0], "Querying {m}...", master_timeout)
                if not m:
                    self.after(0, lambda: self._side_resp_replace(f"All models failed.\n\n{last_error}"))
                    return
                if "Option A" in selected_option:
                    txt = self._extract_json(txt)
                final_text = _make_header(m, um) + txt
                self.after(0, lambda c=final_text: self._side_resp_replace(c))
            else:
                # Two step flow
                step1_start = time.time()
                m1, txt1, um1 = _run_request(config["payloads"][0], "Step 1/2: Researching with {m}...", 40)
                if not m1:
                    self.after(0, lambda: self._side_resp_replace(f"Step 1 Failed.\n\n{last_error}"))
                    return
                step1_secs = time.time() - step1_start
                step2_start = time.time()
                
                # Inject research text into step 2 contents
                step2_payload = config["payloads"][1]
                injected_prompt = f"RESEARCH MATERIAL (use ONLY this for your answers; do NOT search the web):\n\n{txt1}\n\n---\n\n{config['user_prompt']}"
                step2_payload["contents"] = [{"parts": [{"text": injected_prompt}]}]
                
                m2, txt2, um2 = _run_request(step2_payload, "Step 2/2: Structuring with {m}...", master_timeout)
                if not m2:
                    self.after(0, lambda: self._side_resp_replace(f"Step 2 Failed.\n\n{last_error}"))
                    return
                txt2 = self._extract_json(txt2)
                final_text = _make_header(m2, um2, m1, um1) + txt2
                self.after(0, lambda c=final_text: self._side_resp_replace(c))

        threading.Thread(target=_task, daemon=True).start()

    # ------------------------------------------------------------------
    # MGRS Reference Doc Viewer (triggered by the ℹ button on grid fields)
    # ------------------------------------------------------------------

    def _show_mgrs_info(self):
        """Open a modal viewer for MGRS_to_Decimal_Coordinates.md.

        Displays the reference document with heading formatting and a
        live search bar that highlights matching text in yellow.
        """
        doc_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "rConvert_to_Decimal_Coordinates.md",
        )
        # Fallback: try in the parent directory (workspace root)
        if not os.path.exists(doc_path):
            doc_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..",
                "rConvert_to_Decimal_Coordinates.md",
            )
            doc_path = os.path.normpath(doc_path)

        dlg = tk.Toplevel(self)
        dlg.title("MGRS → Decimal Coordinates Reference")
        dlg.geometry("780x620")
        dlg.configure(bg=WHITE)
        dlg.resizable(True, True)
        dlg.transient(self)
        dlg.grab_set()

        # ── centre on parent ──────────────────────────────────────
        dlg.update_idletasks()
        pw = self.winfo_screenwidth()
        ph = self.winfo_screenheight()
        x = (pw - 780) // 2
        y = max(0, (ph - 620) // 2)
        dlg.geometry(f"+{x}+{y}")

        # ── header with search bar ─────────────────────────────────
        header = tk.Frame(dlg, bg=ACCENT, height=52)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header, text="Search:", bg=ACCENT, fg=WHITE,
            font=(FONT, 11, "bold"),
        ).pack(side=tk.LEFT, padx=(20, 8), pady=13)

        search_var = tk.StringVar()
        search_entry = tk.Entry(
            header, textvariable=search_var,
            font=(FONT, 11), width=38,
            relief=tk.FLAT, bg="#ffffff", fg=TEXT_DARK,
        )
        search_entry.pack(side=tk.LEFT, pady=13)

        # ── text area with scrollbar ───────────────────────────────
        text_frame = tk.Frame(dlg, bg=WHITE)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(14, 20))

        text_w = tk.Text(
            text_frame, font=(FONT, 10), wrap=tk.WORD,
            relief=tk.FLAT, bg="#f9f9f9", fg=TEXT_DARK,
            padx=12, pady=12,
        )
        scrollbar = ttk.Scrollbar(text_frame, command=text_w.yview)
        text_w.configure(yscrollcommand=scrollbar.set)
        text_w.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ── tag styles ─────────────────────────────────────────────
        text_w.tag_configure(
            "search", background="#ffeb3b", foreground="black",
        )
        text_w.tag_configure(
            "h1", font=(FONT, 16, "bold"), foreground=ACCENT,
            spacing1=12, spacing3=8,
        )
        text_w.tag_configure(
            "h2", font=(FONT, 14, "bold"), foreground=ACCENT_HOV,
            spacing1=10, spacing3=6,
        )
        text_w.tag_configure(
            "h3", font=(FONT, 12, "bold"), spacing1=6, spacing3=4,
        )
        text_w.tag_configure(
            "code", font=("Consolas", 9), background="#e8e8e8",
            foreground="#333333",
        )

        # ── load the markdown file ─────────────────────────────────
        if not os.path.exists(doc_path):
            text_w.insert(tk.END, f"Document not found:\n{doc_path}")
            text_w.configure(state=tk.DISABLED)
            return

        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        text_w.insert(tk.END, content)

        # Apply heading tags (using Text widget "line.column" indices)
        for match in re.finditer(r'^#\s+(.+)$', content, re.MULTILINE):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            text_w.tag_add("h1", start, end)
        for match in re.finditer(r'^##\s+(.+)$', content, re.MULTILINE):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            text_w.tag_add("h2", start, end)
        for match in re.finditer(r'^###\s+(.+)$', content, re.MULTILINE):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            text_w.tag_add("h3", start, end)
        # Style inline code (backtick-wrapped spans)
        for match in re.finditer(r'`([^`]+)`', content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            text_w.tag_add("code", start, end)

        text_w.configure(state=tk.DISABLED)

        # ── live search callback ───────────────────────────────────
        def _on_search(*args):
            query = search_var.get().lower()
            # Remove previous highlights (must temporarily enable writes)
            text_w.configure(state=tk.NORMAL)
            text_w.tag_remove("search", "1.0", tk.END)
            if not query:
                text_w.configure(state=tk.DISABLED)
                return

            start_idx = "1.0"
            first_match = None
            while True:
                start_idx = text_w.search(
                    query, start_idx, nocase=True, stopindex=tk.END,
                )
                if not start_idx:
                    break
                if first_match is None:
                    first_match = start_idx
                end_idx = f"{start_idx} + {len(query)} chars"
                text_w.tag_add("search", start_idx, end_idx)
                start_idx = end_idx

            text_w.configure(state=tk.DISABLED)
            if first_match:
                text_w.see(first_match)

        search_var.trace_add("write", _on_search)

    def _extract_json(self, text: str) -> str:
        """Strip markdown code fences and pretty-print JSON if possible."""
        import re as _re
        # Remove ```json ... ``` or ``` ... ``` fences
        cleaned = _re.sub(r'```(?:json)?\s*\n?', '', text)
        cleaned = _re.sub(r'```\s*$', '', cleaned)
        cleaned = cleaned.strip()
        # Try to parse and pretty-print
        try:
            parsed = json.loads(cleaned)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            return text  # Return original if not valid JSON

    def _side_resp_replace(self, text: str):
        safe_text = text if text is not None else ""
        self._side_resp.delete("1.0", tk.END)
        self._side_resp.insert("1.0", safe_text)
        # Only show COPY RESPONSE button for master responses, never for hotlinks.
        # Identified by the side-panel label starting with "RESPONSE: MASTER".
        is_master = self._side_resp_label.cget("text").startswith("RESPONSE: MASTER")
        if len(safe_text) > self._copy_threshold and is_master:
            try:
                self._copy_btn.pack(side=tk.LEFT, padx=(10, 0), before=self._live_search_chk)
            except tk.TclError:
                pass  # already packed
        else:
            self._copy_btn.pack_forget()

    def _copy_response_to_ai_response(self):
        """Copy the current AI response text into the ai_response field in the Update modal."""
        response_text = self._side_resp.get("1.0", "end-1c").strip()
        if not response_text:
            return
        # Find the ai_response entry widget
        key = ("derived_details", "ai_response")
        entry = self._entry_widgets.get(key)
        if entry is None:
            return
        # Replace the displayed value (does NOT write to underlying JSON until Update)
        if isinstance(entry, tk.Text):
            entry.delete("1.0", tk.END)
            entry.insert("1.0", response_text)
        else:
            entry.delete(0, tk.END)
            entry.insert(0, response_text)
        # Mark record dirty so user is prompted on close
        self._record_dirty = True
        self._set_locked(True)

    def _gather_ref_state(self) -> dict | None:
        """Collect side-panel prompt/response text and labels for the current record."""
        if not self._filtered:
            return None
        actual_idx = self._filtered[self._filtered_pos]
        record = self.working_data[actual_idx]
        ref_id = record.get("referenceID", "")
        if not ref_id:
            return None

        # Side panel text
        prompt_text = self._side_prompt.get("1.0", "end-1c").strip()
        resp_text = self._side_resp.get("1.0", "end-1c").strip()

        ref_state = {
            "prompt": prompt_text,
            "response": resp_text,
            "promptLabel": self._side_prompt_label.cget("text"),
            "responseLabel": self._side_resp_label.cget("text"),
            "sidePanelVisible": self._side_panel.winfo_ismapped(),
        }
        return {"lastRefId": ref_id, ref_id: ref_state}

    def _save_side_panel_state(self):
        """Persist current side-panel content to session for the active record."""
        extra = self._gather_ref_state()
        if extra:
            session_manager._save_session(self.file_path, self._filtered_pos, self._search_text, extra=extra)
