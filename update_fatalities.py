"""update_fatalities.py — Modal editor for fatality JSON records.

Modern flat-design: custom colour palette, hover effects, custom dialogs.
One record at a time, vertical layout, dynamic search, record locking.
Side panel for AI results (revealed on demand).
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import tkinter as tk
import urllib.request
import urllib.error
from tkinter import ttk

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


# ---------------------------------------------------------------------------
# _try_parse_vietnam_mgrs(coord_str: str) → (float, float) | None
# ---------------------------------------------------------------------------
#
# The core Vietnam-era MGRS normaliser.
#
# Accepts any of these input shapes (spaces are stripped, case-insensitive):
#
#     "48P YS 426 694"   — full, correct zone
#     "48Q YS 426 694"   — full, WRONG zone  → auto-corrected 48Q→48P
#     "YS 426 694"       — partial, no zone   → zone inferred from square
#     "48PYS426694"      — compact (no spaces)
#     "YS426694"         — compact partial
#     "48Q YS 42600 69400" — 10-digit fine precision
#
# Pipeline (each step is documented inline):
#
#   1. Clean & normalise whitespace / case
#   2. Match against a full-MGRS regex or a partial (no-GZD) regex
#   3. If partial, infer zone 48 + band P or Q from the square lookup table
#   4. Auto-correct 48Q → 48P for squares known to be in 48P
#   5. Split the numerical half into Easting / Northing components
#   6. Expand abbreviated digits to full-metre values
#      (e.g. "426" → 42600 m for 6-digit input)
#   7. Add the SVN60 → WGS84 datum shift to both Easting and Northing
#   8. Clamp shifted values to the 0–99999 m range of a 100 km square
#   9. Round back to the input's original precision
#  10. Reconstruct a corrected MGRS string
#  11. Convert MGRS → decimal lat/lon (WGS84) using the `mgrs` library
#
# Returns a (lat, lon) tuple rounded to 5 decimal places (~1 m precision),
# or None if the input does not match any Vietnam MGRS pattern.
# ---------------------------------------------------------------------------
def _try_parse_vietnam_mgrs(coord_str: str):
    # Deferred import so the file can be loaded even without `mgrs` installed,
    # and to avoid a heavy import on every coordinate-parse attempt.
    import mgrs as mgrs_lib

    # ---- step 1: normalise -------------------------------------------------
    # Strip all whitespace, convert to uppercase.  This collapses
    # "48P YS 426 694" → "48PYS426694" and "ys 426 694" → "YS426694".
    clean = re.sub(r"\s+", "", str(coord_str).strip()).upper()
    if not clean:
        return None

    # ---- step 2: regex matching --------------------------------------------
    #
    # full_pat    matches  "48PYS426694"  (GZD + square + digits)
    # partial_pat matches  "YS426694"     (square + digits, no GZD)
    #
    # Both patterns use the official MGRS character sets:
    #   Latitude band:  C–H, J–N, P–X   (I and O are omitted to avoid
    #                   confusion with digits 1 and 0)
    #   100 km square:  A–H, J–N, P–Z   (same rationale)
    #   Digits:         4–10 (even count, i.e. 2+2 to 5+5 per component)

    # Pattern 1 — full MGRS with Grid Zone Designator
    #   Group 1: \d{1,2}       zone number (1–60, but typically 1–2 digits)
    #   Group 2: [C-HJ-NP-X]   latitude band letter
    #   Group 3: [A-HJ-NP-Z]{2}  100 km square letter pair
    #   Group 4: \d{4,10}      numerical easting + northing (even-length)
    full_pat = re.compile(
        r"^(\d{1,2})"            # e.g. "48"
        r"([C-HJ-NP-X])"         # e.g. "P"
        r"([A-HJ-NP-Z]{2})"      # e.g. "YS"
        r"(\d{4,10})$"           # e.g. "426694" or "4260069400"
    )

    # Pattern 2 — partial MGRS (square + digits only, no GZD)
    #   Group 1: [A-HJ-NP-Z]{2}  100 km square letter pair (e.g. "YS")
    #   Group 2: \d{4,10}        numerical easting + northing
    #
    # This handles the common Vietnam War shorthand where soldiers
    # omitted the GZD because everyone in the unit knew they were in
    # "48P" or "48Q".
    partial_pat = re.compile(
        r"^([A-HJ-NP-Z]{2})"     # e.g. "YS"
        r"(\d{4,10})$"           # e.g. "426694"
    )

    m = full_pat.match(clean)
    if m:
        zone_str, lat_band, square, digits = (
            m.group(1), m.group(2), m.group(3), m.group(4)
        )
    else:
        m = partial_pat.match(clean)
        if not m:
            # Does not look like any MGRS form we handle — let the caller
            # try the generic MGRS parser or fall through to DMS / error.
            return None
        square, digits = m.group(1), m.group(2)

        # ---- step 3: zone inference from square ----------------------------
        # When the user hasn't supplied a GZD, we look up the 100 km square
        # in our known-Vietnam table.  Squares not explicitly listed as 48P
        # are assumed to be 48Q (northern Vietnam).
        #
        # This is a heuristic — if someone is working with coordinates from
        # a completely different part of the world that happen to share the
        # same square letters, they should supply the full GZD.
        zone_str = "48"
        lat_band = "P" if square in _VIETNAM_48P_SQUARES else "Q"

    # Cast zone to integer for the correction check below.
    zone = int(zone_str)

    # ---- step 4: zone correction -------------------------------------------
    # "48Q YS" is a well-known transcription error in Vietnam War records.
    # The YS square physically exists only in zone 48P (southern Vietnam).
    # We silently correct Q → P for any square in our 48P set.
    #
    # This also catches the case where a user typed "48Q" out of habit
    # (many maps of the period labelled everything as "48Q" in the margin).
    if zone == 48 and lat_band == "Q" and square in _VIETNAM_48P_SQUARES:
        lat_band = "P"

    # ---- step 5: split numerical digits into Easting / Northing ------------
    #
    # MGRS digits are always an even-length string where the first half is
    # the Easting offset and the second half is the Northing offset, both
    # relative to the south-west corner of the 100 km square.
    #
    #     "426694"  →  half=3  →  e_str="426"   n_str="694"
    #     "4260069400" → half=5 → e_str="42600" n_str="69400"
    half = len(digits) // 2
    e_str = digits[:half]    # Easting digits
    n_str = digits[half:]    # Northing digits
    precision = half          # digits per component (3 → 100 m, 5 → 1 m)

    # ---- step 6: expand abbreviated digits to full metres ------------------
    #
    # A 6-digit MGRS encodes 100 m precision: "426" means 42 600 metres
    # east of the square's western edge.  We multiply by 10^(5-precision)
    # to bring the value into the 0–99 999 m range:
    #
    #     precision=3 → scale=10²=100  →  426×100 = 42 600 m
    #     precision=5 → scale=10⁰=1    → 42600×1 = 42 600 m
    scale = 10 ** (5 - precision)
    easting = int(e_str) * scale
    northing = int(n_str) * scale

    # ---- step 7: apply SVN60 → WGS84 datum shift --------------------------
    #
    # The original coordinate was recorded on an SVN60 map.  To express the
    # same physical point in WGS84 (used by GPS, Google Maps, etc.) we must
    # shift the grid easting and northing by the datum offset.
    #
    #     SVN60 Easting + 205 m ≈ WGS84 Easting
    #     SVN60 Northing + 75 m ≈ WGS84 Northing
    easting += _DATUM_SHIFT_E
    northing += _DATUM_SHIFT_N

    # ---- step 8: clamp to 100 km square bounds (0–99 999 m) ----------------
    #
    # A 100 km MGRS square runs from 0 to 99 999 metres in both axes.
    # The datum shift is small enough that real coordinates will never clip
    # under normal circumstances, but we clamp defensively to keep the
    # reconstructed MGRS valid.
    easting = max(0, min(99999, easting))
    northing = max(0, min(99999, northing))

    # ---- step 9: round back to the original input precision ----------------
    #
    # We divide by the scale factor, round to the nearest integer, and
    # zero-pad to the original number of digits.  This preserves the
    # precision level the user typed.
    #
    #     input "426" (100 m) → shifted 42805 → round(42805/100)=428 → "428"
    #     input "42600" (1 m) → shifted 42805 → round(42805/1)=42805 → "42805"
    new_e = str(int(round(easting / scale))).zfill(precision)
    new_n = str(int(round(northing / scale))).zfill(precision)

    # ---- step 10: reconstruct the corrected MGRS string --------------------
    #
    # Assemble the pieces back into a standard MGRS string that the `mgrs`
    # library can consume.  Example:
    #     "48" + "P" + "YS" + "428" + "695"  →  "48PYS428695"
    corrected_mgrs = f"{zone_str}{lat_band}{square}{new_e}{new_n}"

    # ---- step 11: convert MGRS → decimal lat/lon (WGS84) -------------------
    #
    # The `mgrs` Python library (pip install mgrs) converts an MGRS string
    # directly to WGS84 decimal degrees.  Because we already shifted the
    # easting/northing to account for the SVN60 datum, the result is the
    # modern GPS coordinate of the physical location described by the
    # original Vietnam-era grid reference.
    #
    # We round to 5 decimal places (~1.1 m at the equator, ~1.0 m at 10° N)
    # which is well within the inherent precision limits of wartime MGRS.
    try:
        m = mgrs_lib.MGRS()
        lat, lon = m.toLatLon(corrected_mgrs)
        return round(lat, 5), round(lon, 5)
    except Exception:
        # The `mgrs` library may raise on malformed input that passed our
        # regex but is not a real MGRS location (e.g. an invalid square
        # letter pair for the given zone).  Return None so the caller falls
        # through to the generic MGRS parser or error message.
        return None


# ---------------------------------------------------------------------------
# validate_and_parse_coordinate(coord_str: str)
#     → (is_valid: bool, message: str, coordinates: (float, float) | None)
# ---------------------------------------------------------------------------
#
# The single entry-point for coordinate validation used by both the manual
# editor and the AI-result ingestion paths (see _read_form() and the AI
# side-panel response parsing in UpdateFatalities).
#
# Tries each parser in order of specificity.  The first parser that
# succeeds wins and short-circuits the rest:
#
#   Priority  Parser              Examples
#   ────────  ──────────────────  ──────────────────────────────────────
#    1 (hi)   Decimal Degrees      "10.6895, 107.3305"
#                                 "10.34694 N, 107.07263 E"
#    2        Vietnam-era MGRS     "48Q YS 426 694"
#                                 "YS 426 694"
#    3        Generic MGRS         "48PYS458630"
#                                 (any non-Vietnam MGRS worldwide)
#    4 (lo)   DMS                  "10° 20' N, 107° 04' E"
#
# Vietnam-era MGRS (priority 2) is placed BEFORE generic MGRS (priority 3)
# so that Vietnam-specific corrections (zone fix + datum shift) are
# applied before the generic converter gets a chance to misinterpret the
# coordinate as a raw WGS84 MGRS.
#
# Returns a 3-tuple:
#   is_valid    True if a parser accepted the input
#   message     Human-readable validation result
#   coordinates (lat, lon) if parseable, else None
# ---------------------------------------------------------------------------
def validate_and_parse_coordinate(coord_str: str):
    # Guard: reject empty or whitespace-only input immediately.
    if not coord_str or not str(coord_str).strip():
        return False, "Input is empty.", None

    # Normalise: strip leading/trailing whitespace (but preserve internal
    # spaces — the regex patterns handle those themselves).
    coord_str = str(coord_str).strip()

    # =========================================================================
    # PARSER 1 — Decimal Degrees
    # =========================================================================
    #
    # Matches two decimal numbers separated by a comma (and optionally
    # whitespace and N/S/E/W hemisphere letters).
    #
    # Accepted forms:
    #     "10.34694, 107.07263"
    #     "10.34694 N, 107.07263 E"
    #     "-33.8688, 151.2093"           (bare negatives for S/W)
    #
    # The regex captures:
    #   Group 1: latitude  (signed decimal or unsigned + optional N/S)
    #   Group 2: N or S    (optional)
    #   Group 3: longitude (signed decimal or unsigned + optional E/W)
    #   Group 4: E or W    (optional)
    dec_regex = re.compile(
        r"^(-?\d+\.\d+)\s*([NS]?)[,\s]+(-?\d+\.\d+)\s*([EW]?)$",
        re.IGNORECASE
    )
    match = dec_regex.match(coord_str)

    if match:
        lat = float(match.group(1))
        lat_dir = match.group(2).upper() if match.group(2) else ""
        lon = float(match.group(3))
        lon_dir = match.group(4).upper() if match.group(4) else ""

        # Apply hemisphere sign from letter suffix (S/W flip the sign).
        # If no suffix and value is already negative, it stays negative.
        if lat_dir == 'S':
            lat *= -1
        if lon_dir == 'W':
            lon *= -1

        # Reject coordinates that are physically impossible.
        if not (-90 <= lat <= 90):
            return False, (
                f"Invalid latitude ({lat}): Must be between -90 and 90."
            ), None
        if not (-180 <= lon <= 180):
            return False, (
                f"Invalid longitude ({lon}): Must be between -180 and 180."
            ), None

        # 5 decimal places ≈ 1.1 m resolution — more than enough.
        return True, "Valid Decimal Degrees", (round(lat, 5), round(lon, 5))

    # =========================================================================
    # PARSER 2 — Vietnam-era MGRS (with zone correction & datum shift)
    # =========================================================================
    #
    # Try the Vietnam-specific parser BEFORE the generic MGRS parser.
    # This ensures that "YS 426 694" gets the SVN60 → WGS84 treatment
    # rather than being rejected or interpreted as a generic WGS84 MGRS.
    #
    # _try_parse_vietnam_mgrs returns None if the input does not look
    # like a Vietnam-era MGRS, which causes this parser to yield and
    # let parser 3 attempt it instead.
    vietnam_result = _try_parse_vietnam_mgrs(coord_str)
    if vietnam_result is not None:
        return (
            True,
            "Valid Vietnam-era MGRS (zone-corrected, datum-shifted)",
            vietnam_result,
        )

    # =========================================================================
    # PARSER 3 — Generic MGRS (worldwide, WGS84 assumed)
    # =========================================================================
    #
    # Catches any MGRS that does not match the Vietnam patterns: NATO
    # exercises in Germany, modern hiking coordinates, etc.
    #
    # The regex requires:
    #   - 1- or 2-digit zone (1-60, but 1-6 catches the first digit for 1-2
    #     digit zones; the full zone check is done by the mgrs library)
    #   - latitude band letter (C-X, excluding I/O)
    #   - 2-letter 100 km square (A-Z, excluding I/O)
    #   - 4-10 numerical digits (even count)
    #
    # NOTE: this regex requires the full GZD prefix, so "YS426694" would
    # NOT match here — it was already handled by parser 2 (Vietnam MGRS).
    clean_mgrs = re.sub(r"\s+", "", coord_str).upper()
    mgrs_regex = re.compile(
        r"^[1-6][0-9][C-X][A-Z]{2}\d{4,10}$", re.IGNORECASE
    )

    if mgrs_regex.match(clean_mgrs):
        try:
            import mgrs
            m = mgrs.MGRS()
            lat, lon = m.toLatLon(clean_mgrs)
            # No datum shift applied here — we assume the MGRS is
            # already referenced to WGS84 (modern standard).
            return True, "Valid MGRS", (round(lat, 5), round(lon, 5))
        except ImportError:
            # The `mgrs` library is listed in requirements.txt but the
            # user might be running from source without `pip install -r`.
            return (
                True,
                "Valid MGRS format (Tip: install 'mgrs' python library "
                "to calculate lat/lon)",
                None,
            )
        except Exception as e:
            return (
                False,
                f"MGRS format looks valid but math decoding failed: {str(e)}",
                None,
            )

    # =========================================================================
    # PARSER 4 — Degrees/Minutes/Seconds (DMS)
    # =========================================================================
    #
    # Lightweight detection: looks for at least two degree-minute pairs
    # with optional hemisphere letters.  Full mathematical conversion is
    # not implemented (the `mgrs` library doesn't handle DMS); this parser
    # simply validates the *format* so the user doesn't get an "unrecognized"
    # error when pasting DMS coordinates.
    #
    # If you need DMS → decimal conversion, integrate `dms-to-decimal` or
    # write the arc-second arithmetic here.
    dms_regex = re.compile(
        r"(\d+)[^0-9A-Z]+(\d+)[^0-9A-Z]*([NSEW]?)", re.IGNORECASE
    )
    matches = list(dms_regex.finditer(coord_str))

    if len(matches) >= 2:
        return True, "Valid DMS (Degrees/Minutes)", None

    # =========================================================================
    # FALLBACK — nothing matched
    # =========================================================================
    #
    # Show the user which formats are accepted so they can retype or
    # reformat the coordinate.
    error_msg = (
        f"Unrecognized coordinate format: '{coord_str}'.\n"
        "Acceptable formats are:\n"
        "  1. Decimal Degrees: '10.34694 N, 107.07263 E'"
        " or '10.34694, 107.07263'\n"
        "  2. Vietnam-era MGRS: 'YS 426 694' or '48P YS 426 694'\n"
        "  3. Standard MGRS: '48PYS458630' or '48P YS 458 630'\n"
        "  4. DMS: '10° 20' N, 107° 04' E'"
    )
    return False, error_msg, None


def _load_json(path: str) -> list[dict] | None:
    if not os.path.exists(path):
        _error_dialog(None, "File Missing", f"'{path}' does not exist.")
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        _error_dialog(None, "Invalid JSON", f"'{path}' is not valid JSON.\n{exc}")
        return None
    if not isinstance(data, list):
        _error_dialog(None, "Bad Structure", f"'{path}' must contain a JSON array.")
        return None
    return data


def _save_json(path: str, data: list[dict]) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        return True
    except OSError as exc:
        _error_dialog(None, "Save Error", f"Could not write '{path}'.\n{exc}")
        return False


# ---------------------------------------------------------------------------
# Session state (last-viewed record per file)
# ---------------------------------------------------------------------------

def _session_path(file_path: str) -> str:
    """Return the session.json path in the same directory as *file_path*."""
    return os.path.join(os.path.dirname(os.path.abspath(file_path)), "session.json")


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


# ---------------------------------------------------------------------------
# Custom dialogs
# ---------------------------------------------------------------------------

def _error_dialog(parent: tk.Toplevel | None, title: str, message: str):
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.configure(bg=WHITE)
    if parent:
        dlg.transient(parent)
        _center_on_parent(dlg, parent)
    dlg.grab_set()
    pad = {"padx": 24, "pady": 16}
    icon_row = ttk.Frame(dlg)
    icon_row.pack(fill=tk.X, **pad)
    canvas = tk.Canvas(icon_row, width=28, height=28, bg=WHITE, highlightthickness=0)
    canvas.pack(side=tk.LEFT)
    canvas.create_oval(2, 2, 26, 26, fill=ACCENT, outline="")
    canvas.create_line(9, 9, 19, 19, fill=WHITE, width=2)
    canvas.create_line(19, 9, 9, 19, fill=WHITE, width=2)
    msg_lbl = tk.Label(icon_row, text=message, font=(FONT, 10), bg=WHITE,
                       fg=TEXT_DARK, justify=tk.LEFT, wraplength=380)
    msg_lbl.pack(side=tk.LEFT, padx=(12, 0))
    btn_frame = ttk.Frame(dlg)
    btn_frame.pack(fill=tk.X, padx=24, pady=(0, 16))
    ok = tk.Label(btn_frame, text="OK", font=(FONT, 10, "bold"),
                  bg=ACCENT, fg=WHITE, padx=28, pady=6, cursor="hand2")
    ok.pack(side=tk.RIGHT)
    _bind_hover(ok, ACCENT, ACCENT_HOV)
    ok.bind("<Button-1>", lambda e: dlg.destroy())
    dlg.wait_window()


def _confirm_yesnocancel(parent: tk.Toplevel, title: str, message: str,
                         yes_text="Yes", no_text="No", cancel_text="Cancel",
                         yes_bg=ACCENT, no_bg=BORDER, cancel_bg=BORDER) -> bool | None:
    result = [None]
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.configure(bg=WHITE)
    dlg.transient(parent)
    _center_on_parent(dlg, parent)
    dlg.grab_set()
    pad = {"padx": 24, "pady": 16}
    icon_row = ttk.Frame(dlg)
    icon_row.pack(fill=tk.X, **pad)
    canvas = tk.Canvas(icon_row, width=28, height=28, bg=WHITE, highlightthickness=0)
    canvas.pack(side=tk.LEFT)
    canvas.create_oval(2, 2, 26, 26, fill="#f0ad4e", outline="")
    canvas.create_text(14, 14, text="!", fill=WHITE, font=(FONT, 14, "bold"))
    msg_lbl = tk.Label(icon_row, text=message, font=(FONT, 10), bg=WHITE,
                       fg=TEXT_DARK, justify=tk.LEFT, wraplength=380)
    msg_lbl.pack(side=tk.LEFT, padx=(12, 0))
    btn_frame = ttk.Frame(dlg)
    btn_frame.pack(fill=tk.X, padx=24, pady=(0, 16))
    def _press(val):
        result[0] = val
        dlg.destroy()
    if cancel_text:
        cancel = tk.Label(btn_frame, text=cancel_text, font=(FONT, 10, "bold"),
                          bg=cancel_bg, fg=TEXT_DARK if cancel_bg != ACCENT else WHITE,
                          padx=20, pady=6, cursor="hand2")
        cancel.pack(side=tk.RIGHT, padx=(6, 0))
        _bind_hover(cancel, cancel_bg, "#c0c0c0")
        cancel.bind("<Button-1>", lambda e: _press(None))
    no = tk.Label(btn_frame, text=no_text, font=(FONT, 10, "bold"),
                  bg=no_bg, fg=TEXT_DARK if no_bg != ACCENT else WHITE,
                  padx=20, pady=6, cursor="hand2")
    no.pack(side=tk.RIGHT, padx=(6, 0))
    _bind_hover(no, no_bg, "#c0c0c0")
    no.bind("<Button-1>", lambda e: _press(False))
    yes = tk.Label(btn_frame, text=yes_text, font=(FONT, 10, "bold"),
                   bg=yes_bg, fg=WHITE, padx=20, pady=6, cursor="hand2")
    yes.pack(side=tk.RIGHT, padx=(6, 0))
    _bind_hover(yes, yes_bg, ACCENT_HOV)
    yes.bind("<Button-1>", lambda e: _press(True))
    dlg.wait_window()
    return result[0]


def _confirm_yesno(parent: tk.Toplevel, title: str, message: str) -> bool:
    return _confirm_yesnocancel(parent, title, message,
                                yes_text="Yes", no_text="No", cancel_text="") is True


# ---------------------------------------------------------------------------
# Interaction helpers
# ---------------------------------------------------------------------------

def _bind_hover(widget: tk.Label, normal_bg: str, hover_bg: str):
    widget.bind("<Enter>", lambda e: widget.configure(bg=hover_bg))
    widget.bind("<Leave>", lambda e: widget.configure(bg=normal_bg))


def _center_on_parent(dlg: tk.Toplevel, parent: tk.Toplevel | tk.Tk):
    dlg.update_idletasks()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    dw, dh = dlg.winfo_width(), dlg.winfo_height()
    x = px + (pw - dw) // 2
    y = py + (ph - dh) // 2
    dlg.geometry(f"+{x}+{y}")


# ---------------------------------------------------------------------------
# Styled entry
# ---------------------------------------------------------------------------

def _styled_entry(parent, **kw) -> tk.Entry:
    fnt = kw.pop("font", (FONT, 10))
    return tk.Entry(parent, font=fnt, bg=WHITE, fg=TEXT_DARK,
                    relief=tk.FLAT, highlightbackground=BORDER,
                    highlightcolor=ACCENT, highlightthickness=1,
                    insertbackground=TEXT_DARK, **kw)


# ---------------------------------------------------------------------------
# Update Fatalities modal
# ---------------------------------------------------------------------------

class UpdateFatalities(tk.Toplevel):
    """Modern flat-design modal for editing fatality records with AI side panel."""

    def __init__(self, parent: tk.Tk | tk.Toplevel, file_path: str, *, modal_title: str | None = None):
        super().__init__(parent)
        self.configure(bg=BG_GREY)
        self._loaded = False
        self._modal_title = modal_title

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
        self._filtered = list(range(len(self.working_data)))
        self._filtered_pos = 0
        self._entry_widgets: dict[str, tk.Entry] = {}

        self._build_ui()
        self._apply_search()

        # ── Restore last-viewed record from session ──
        session = _load_session(file_path)
        if session and isinstance(session, dict):
            saved_pos = session.get("pos", 0)
            saved_search = session.get("search", "")
            if saved_search:
                self._search_text = saved_search
                self._search_var.set(saved_search)
                self._apply_search()  # re-filter to match saved search
                # Re-check saved_pos against re-filtered list
                if 0 <= saved_pos < len(self._filtered):
                    self._filtered_pos = saved_pos
            else:
                if 0 <= saved_pos < len(self._filtered):
                    self._filtered_pos = saved_pos
            self._show_record()

            # ── Restore side-panel prompt/response for this reference ID ──
            last_ref_id = session.get("lastRefId", "")
            if last_ref_id and last_ref_id in session:
                ref_state = session[last_ref_id]
                if isinstance(ref_state, dict):
                    saved_prompt = ref_state.get("prompt", "")
                    saved_response = ref_state.get("response", "")
                    if saved_prompt:
                        self._side_prompt.configure(state=tk.NORMAL)
                        self._side_prompt.delete("1.0", tk.END)
                        self._side_prompt.insert("1.0", saved_prompt)
                        self._side_prompt_label.configure(text="PROMPT: All Derived Data")
                    if saved_response:
                        self._side_resp_label.configure(text="RESPONSE: All Derived Data")
                        self._side_resp_replace(saved_response)
                        self._show_side_panel()
                    # Restore field values into working_data for this record
                    fields = ref_state.get("fields", {})
                    if fields:
                        record = self.working_data[self._filtered[self._filtered_pos]]
                        sra = record.setdefault("serviceRecordAuthority", {})
                        dd = record.setdefault("derived_details", {})
                        if isinstance(sra, dict) and isinstance(dd, dict):
                            _apply_field(sra, "service_status", fields.get("serviceRecordAuthority.service_status"))
                            _apply_field(dd, "place_of_death", fields.get("derived_details.place_of_death"))
                            _apply_field(dd, "grid_reference", fields.get("derived_details.grid_reference"))
                            _apply_field(dd, "circumstances_of_death", fields.get("derived_details.circumstances_of_death"))
                            _apply_field(dd, "pre_service_occupation", fields.get("derived_details.pre_service_occupation"))
                            _apply_field(dd, "unit_served_with", fields.get("derived_details.unit_served_with"))
                            _apply_field(dd, "references", fields.get("derived_details.references"))
                            _apply_field(dd, "ai_response", fields.get("derived_details.ai_response"))
                            self._show_record()

        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

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

        # Title
        tk.Label(main, text=f"Update {filename}", font=(FONT, 16, "bold"),
                 bg=BG_GREY, fg=TEXT_DARK, anchor=tk.W).pack(fill=tk.X, pady=(0, 12))

        # Search
        sf = tk.Frame(main, bg=BG_GREY)
        sf.pack(fill=tk.X, pady=(0, 8))
        tk.Label(sf, text="\U0001F50D", font=(FONT, 12), bg=BG_GREY, fg=TEXT_MUTED).pack(side=tk.LEFT, padx=(0, 6))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search_changed())
        self._search_entry = _styled_entry(sf, width=24, textvariable=self._search_var)
        self._search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
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

        # Bottom buttons
        bf = tk.Frame(main, bg=BG_GREY)
        bf.pack(fill=tk.X)
        self._flat_btn(bf, "Close", self._cancel, bg="#e0e0e0", fg=TEXT_DARK, side=tk.RIGHT)
        self._flat_btn(bf, "AI: Create a Master Response", self._ai_lookup, bg="#4a90d9", fg=WHITE, side=tk.LEFT)
        
        self._live_search_var = tk.BooleanVar(value=True)
        self._live_search_chk = tk.Checkbutton(
            bf, text="Live Search", variable=self._live_search_var,
            bg=BG_GREY, fg=TEXT_DARK, activebackground=BG_GREY, font=(FONT, 9)
        )
        self._live_search_chk.pack(side=tk.LEFT, padx=(10, 0))

        self._copy_btn = self._flat_btn(
            bf, "COPY RESPONSE: to ai_response", self._copy_response_to_ai_response,
            bg="#2e7d32", fg=WHITE, side=tk.LEFT, right_pad=10
        )
        self._copy_btn.pack_forget()  # hidden until response exceeds 200 chars

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
        self._side_prompt = tk.Text(self._side_panel, font=(FONT, 8), wrap=tk.WORD,
                                    bg=WHITE, fg=TEXT_DARK, padx=8, pady=6, height=12,
                                    relief=tk.FLAT, highlightthickness=0)
        self._side_prompt.pack(fill=tk.X, padx=12, pady=(0, 6))

        self._side_resp_label = tk.Label(self._side_panel, text="RESPONSE", font=(FONT, 8, "bold"),
                                          bg="#f0f2f5", fg=TEXT_MUTED, anchor="w")
        self._side_resp_label.pack(fill=tk.X, padx=12, pady=(4, 2))
        self._side_resp = tk.Text(self._side_panel, font=(FONT, 9), wrap=tk.WORD,
                                  bg=WHITE, fg=TEXT_DARK, padx=8, pady=6,
                                  relief=tk.FLAT, highlightthickness=0)
        self._side_resp.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

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
        self._filtered_pos = 0
        total = len(self._filtered)
        self._search_count.configure(text=f"{total} match{'es' if total != 1 else ''}" if self._search_text else "")
        self._show_record()
        _save_session(self.file_path, self._filtered_pos, self._search_text)

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
        for child in self._fields_frame.winfo_children():
            child.destroy()
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
        self._record_snapshot = copy.deepcopy(record)
        # Copy grid_reference to clipboard on every record change
        # so the user can always paste back the last-seen original
        dd = record.get("derived_details", {}) if isinstance(
            record.get("derived_details"), dict
        ) else {}
        grid_val = str(dd.get("grid_reference", ""))
        if grid_val:
            self.clipboard_clear()
            self.clipboard_append(grid_val)
        self._entry_widgets = {}

        def _render_fields(parent_frame, data_dict, prefix_path=()):
            items = list(data_dict.items())
            items.sort(key=lambda x: 1 if x[0] == 'summary' else 0)
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
                    label_width = 24 if not prefix_path else 22
                    field_label = tk.Label(rf, text=f"{field_name}", font=(FONT, 10),
                                           bg=WHITE, fg=TEXT_DARK,
                                           width=label_width, anchor=tk.E)
                    field_label.pack(side=tk.LEFT, padx=(0, 10), anchor=tk.N)
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
                        if field_name in ("circumstances_of_death", "summary", "ai_response"):
                            text_height = 3 if field_name == "summary" else (8 if field_name == "ai_response" else 4)

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
                        elif field_name and any(kw in field_name.lower() for kw in ('gps', 'coordinate', 'grid')):
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
                                     "Replace current value with new reference "
                                     "to convert to decimal format")

                            def _update_link_style(*args, w=entry):
                                val_str = w.get().strip()
                                if val_str:
                                    # Strip {original} suffix before validating
                                    decimal_part, _ = _split_coord_display(val_str)
                                    is_valid, _, parsed = validate_and_parse_coordinate(decimal_part)
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
                                    is_valid, _, parsed = validate_and_parse_coordinate(decimal_part)
                                    if is_valid and parsed is not None:
                                        import webbrowser
                                        webbrowser.open(f"https://www.google.com/maps?q={parsed[0]},{parsed[1]}")
                                        
                            entry.bind("<Double-Button-1>", _open_map)
                            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                        elif field_name == "place_of_death":
                            entry = _styled_entry(rf, width=42, font=entry_font)
                            entry.insert(0, dv)
                            entry.bind("<KeyRelease>", lambda _e: self._on_field_edited())
                            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                        elif field_name == "service_status":
                            status_values = ["Regular", "Conscript", "Other", "Unassigned"]
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
        self._search_entry.configure(state=state)
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
                        
                        # Apply coordinate GPS validation (skip non-coordinate placeholders)
                        if field_name and any(kw in field_name.lower() for kw in ('gps', 'coordinate', 'grid')):
                            val_str = str(val).strip()
                            if val_str and not re.match(r'^[A-Za-z]+$', val_str):
                                # Copy original to clipboard so the user can
                                # revert immediately after the update if needed
                                self.clipboard_clear()
                                self.clipboard_append(val_str)
                                # Strip existing {original} suffix before validating
                                clean_val, existing = _split_coord_display(val_str)
                                is_valid, msg, parsed = validate_and_parse_coordinate(clean_val)
                                if not is_valid:
                                    _error_dialog(self, "Invalid Coordinate Format", msg)
                                    return None
                                if parsed is not None:
                                    formatted = f"{parsed[0]}, {parsed[1]}"
                                    # Preserve or create plain-text annotation
                                    if existing:
                                        val = f"{formatted} {{{existing}}}"
                                    elif clean_val != formatted:
                                        val = f"{formatted} {{{clean_val}}}"
                                    else:
                                        val = formatted
                                else:
                                    val = val_str

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
        actual_idx = self._filtered[self._filtered_pos]
        self.working_data[actual_idx] = updated
        if not _save_json(self.file_path, self.working_data):
            return
        self.original_data.clear()
        self.original_data.extend(self.working_data)
        self.dirty = False
        self._record_dirty = False
        self._set_locked(False)
        self._show_record()

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
            _save_session(self.file_path, self._filtered_pos, self._search_text)

    def _next(self):
        if self._record_dirty:
            return
        if self._filtered_pos < len(self._filtered) - 1:
            self._filtered_pos += 1
            self._show_record()
            _save_session(self.file_path, self._filtered_pos, self._search_text)

    # ------------------------------------------------------------------
    # Side panel
    # ------------------------------------------------------------------

    def _show_side_panel(self):
        self._side_panel.pack(side=tk.LEFT, fill=tk.Y, pady=16, after=self.winfo_children()[0].winfo_children()[0])

    def _hide_side_panel(self):
        self._side_panel.pack_forget()

    # ------------------------------------------------------------------
    # AI Lookup
    # ------------------------------------------------------------------

    def _ai_lookup(self):
        if not self._filtered:
            return

        is_live_search = self._live_search_var.get()
        confirm_msg = (
            f"Clear & Direct\n\n"
            f"[The AI has a fixed cutoff date. Live Search fills the gap by finding the latest web results up to the present moment.]\n\n"
            f"// Live Search is currently: {'ON' if is_live_search else 'OFF'}\n\n"
            f"[The AI\u2019s built-in knowledge stops at its last major update (roughly 1\u20132 years ago). \n"
            f"Live Search fills that missing window with anything new or recently updated. \n"
            f"Turn it on if you need modern information\u2014just note it may increase overall response time by about 25%.]"
        )
        if not _confirm_yesno(self, "Confirm AI", confirm_msg):
            return

        actual_idx = self._filtered[self._filtered_pos]
        record = self.working_data[actual_idx]

        # Read from serviceRecordAuthority (the authoritative source)
        sra = record.get("serviceRecordAuthority", {}) if isinstance(record.get("serviceRecordAuthority"), dict) else {}
        svc = sra.get("service_number", "")
        name = sra.get("full_name", "")
        dob = sra.get("date_of_birth", "")
        dod = sra.get("date_of_death", "")
        rank = sra.get("rank", "")
        unit = sra.get("unit", "")

        # Derive Armed Forces from referenceID prefix (AU / NZ)
        ref_id = record.get("referenceID", "")
        forces_map = {"AU": "Australian Armed Forces", "NZ": "New Zealand Armed Forces"}
        af = forces_map.get(ref_id[:2], ref_id[:2] if ref_id else "")

        # Read derived_details
        dd = record.get("derived_details", {}) if isinstance(record.get("derived_details"), dict) else {}
        pod = dd.get("place_of_death", "")
        ftype = sra.get("fatality_type", "")

        # Use the detailed archivist prompt for testing datasets,
        # and AU_fatalities.json
        is_testing = ("testing" in self.file_path.lower() or
                      os.path.basename(self.file_path) in ("AU_fatalities.json",))
        if is_testing:
            country_map = {"AU": "Australia", "NZ": "New Zealand"}
            country = country_map.get(ref_id[:2], "")
            user_prompt = (
                f"As a military archivist / historian researching the detailed story behind the death of this soldier in the Vietnam War, "
                f"I require you to do deep research and complete as much as possible of the extra_derived_data output fields. It is imperative you approach this task to help paint a picture of all personal and tactical events surrounding his death.\n"
                f"You will be provided the following input values to identify the soldier to be researched. If an input value is blank then ignore it in the research:\n"
                f"country = {country}\n"
                f"service number = {svc}\n"
                f"service status = {sra.get('service_status', '')}\n"
                f"full name = {name}\n"
                f"sex = {sra.get('sex', '')}\n"
                f"date of death = {dod}\n"
                f"date of birth = {dob}\n"
                f"rank = {rank}\n"
                f"unit = {unit}\n"
                f"fatality type = {ftype}\n"
                f"Using ONLY these values, produce the JSON structure below.\n"
                f"Fill all fields using the provided values and best-effort military-archivist historical reconstruction.\n"
                f"If a field cannot be determined, leave it empty.\n"
                f"references must be historically credible and directly relevant.\n"
                f"DERIVED FIELD \"2_unit_served_with\":\n"
                f"Create a single-line summary by joining all NON-EMPTY hierarchy elements from \"extra_unit_served_with\" in the following order:\n"
                f"country, service, corps_or_branch, command_or_division, brigade_or_group, regiment_or_battalion, sub_unit, platoon_or_troop, section_or_squad, team_or_crew\n"
                f"Separate each element with \", \" and skip empty fields.\n"
                f"Example:\n"
                f"\"Australia, Australian Army, Royal Australian Infantry Corps, 1ATF, 4RAR, B Company, 5 Platoon\"\n"
                f"DERIVED DATA REQUIREMENTS:\n"
                f"2. Determine \"service_status\" as either \"Regular\" or \"Conscript\".\n"
                f"3. Identify the military operation underway at the time of death.\n"
                f"4. Provide a full operational and tactical setting including mission objectives, terrain, enemy situation, friendly force disposition, and a narrative summary.\n"
                f"5. State the cause of death.\n"
                f"6. Provide the exact or approximate grid reference.\n"
                f"7. Identify the map sheet number and UTM zone.\n"
                f"8. Provide a detailed location description.\n"
                f"9. Reconstruct the unit's movements in the 48 hours prior.\n"
                f"10. List any AARs, war diaries, contact reports, or casualty reports.\n"
                f"11. Identify others killed or wounded in the same incident.\n"
                f"12. Provide burial and repatriation details.\n"
                f"13. Identify the tank/APC track, fire support base, patrol route, or engineer lane involved.\n"
                f"14. If the exact grid is unavailable, provide the most probable grid and archival sources.\n"
                f"15. Provide notes on accuracy and confidence level.\n"
                f"16. Search for relevant references and return them as a list of strings:\n\n"
                f"[\n"
                f"  \"url_or_reference_text\"\n"
                f"]\n"
                f"Only include historically credible and directly relevant references.\n"
                f"OUTPUT FORMAT:\n"
                f"{{\n"
                f"  \"full_name\": \"\",\n"
                f"  \"extra_unit_served_with\": {{\n"
                f"    \"country\": \"\",\n"
                f"    \"service\": \"\",\n"
                f"    \"corps_or_branch\": \"\",\n"
                f"    \"command_or_division\": \"\",\n"
                f"    \"brigade_or_group\": \"\",\n"
                f"    \"regiment_or_battalion\": \"\",\n"
                f"    \"sub_unit\": \"\",\n"
                f"    \"platoon_or_troop\": \"\",\n"
                f"    \"section_or_squad\": \"\",\n"
                f"    \"team_or_crew\": \"\"\n"
                f"  }},\n"
                f"  \"extra_derived_data\": {{\n"
                f"    \"1_service_status\": \"\",\n"
                f"    \"2_unit_served_with\": \"\",\n"
                f"    \"3_operation_name\": \"\",\n"
                f"    \"4_operational_tactical_setting\": \"\",\n"
                f"    \"5_cause_of_death\": \"\",\n"
                f"    \"6_grid_reference\": \"\",\n"
                f"    \"7_map_sheet_or_utm_zone\": \"\",\n"
                f"    \"8_location_description\": \"\",\n"
                f"    \"9_unit_movements_prior_48hrs\": \"\",\n"
                f"    \"10_associated_AARs_or_war_diaries\": \"\",\n"
                f"    \"11_related_casualties\": \"\",\n"
                f"    \"12_burial_and_repatriation\": \"\",\n"
                f"    \"13_tank_APC_track_FSB_patrol_route_engineer_lane\": \"\",\n"
                f"    \"14_probable_grid_and_archival_sources\": \"\",\n"
                f"    \"15_notes_on_accuracy\": \"\",\n"
                f"    \"references\": [],\n"
                f"    \"ai_respons\": \"\"\n"
                f"  }}\n"
                f"}}"
            )
        else:
            user_prompt = (
                "Using the values I provide in the placeholders below, generate a detailed narrative focused only on:\n\n"
                "1. The circumstances of death, clearly separated into:\n"
                "   - confirmed facts\n"
                "   - details supported by official or semi-official sources\n"
                "   - reasonable inference based on context\n"
                "   - what remains unknown\n\n"
                "2. The best available approximation of the place of death, using one of the following (whichever is most appropriate or best supported by sources):\n"
                "   - GPS latitude/longitude\n"
                "   - UTM coordinates\n"
                "   - MGRS grid reference\n\n"
                "If the exact location is not documented, provide the closest verifiable location (such as a base, town, road, or landmark) and explain why this is the most accurate approximation.\n\n"
                "3. The individual's pre-service occupation, as recorded in official enlistment or memorial records.\n\n"
                "4. The enlistment type: whether they were a Regular soldier or a Conscript (e.g., National Service, Draft, or similar).\n\n"
                "Use only the values I supply.\n"
                "Do not invent or alter identity details.\n"
                "Present the answer in normal text, not structured data.\n\n"
                "Identity anchor values:\n\n"
                f"- Service Number: {svc}\n"
                f"- Full Name: {name}\n"
                f"- Date of Birth: {dob}\n"
                f"- Date of Death: {dod}\n"
                f"- Armed Forces: {af}\n"
                f"- Rank: {rank}\n"
                f"- Unit: {unit}\n"
                f"- Place of Death: {pod}\n"
                "- Fatality Type: *[leave blank for the model to determine from records]*"
            )

        env = {}
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip().strip('"').strip("'")

        api_key = env.get("GEMINI_API_KEY", "")
        models_str = env.get("GEMINI_TEXT_TO_TEXT_MODELS_TO_USE", "gemini-2.5-flash")
        models = [m.strip() for m in models_str.split(",") if m.strip()]
        master_timeout = int(env.get("AI_MASTER_RESPONSE_MODEL_CUTOFF_SECONDS", "150"))
        internal_timeout = int(env.get("AI_INTERNAL_RESPONSE_MODEL_CUTOFF_SECONDS", "40"))

        # Parse AI rates and AUD exchange rate for cost calculation
        try:
            ai_rates = json.loads(env.get("AI_RATES", "{}"))
        except Exception:
            ai_rates = {}
        try:
            aud_usd = float(env.get("AUD_USD", "0.7"))
        except Exception:
            aud_usd = 0.7

        if not api_key:
            _error_dialog(self, "AI Error", "GEMINI_API_KEY not found in .env")
            return

        # Show side panel with prompt, loading response
        self._side_prompt_label.configure(text="PROMPT: All Derived Data")
        self._side_resp_label.configure(text="RESPONSE: All Derived Data")
        self._side_prompt.configure(state=tk.NORMAL)
        self._side_prompt.delete("1.0", tk.END)
        self._side_prompt.insert("1.0", user_prompt)
        self._side_resp.delete("1.0", tk.END)
        self._show_side_panel()

        def _task():
            last_error = ""
            start_time = time.time()
            step1_secs = 0.0
            step2_start = 0.0
            is_testing = ("testing" in self.file_path.lower() or
                          os.path.basename(self.file_path) in ("AU_fatalities.json",))

            def _make_header(model_name, usage_meta, research_model_name=None, research_usage_meta=None):
                """Build cost/attribution header showing Step 1 + Step 2 costs, times, and total."""
                from datetime import datetime
                now = datetime.now()
                ts = now.strftime("%d:%b:%Y %H:%M")
                step2_secs = time.time() - step2_start if step2_start else time.time() - start_time
                total_secs = time.time() - start_time

                def _calc_cost(mn, um):
                    if not um or mn not in ai_rates:
                        return 0.0
                    rate = ai_rates[mn]
                    pt = um.get("promptTokenCount", 0)
                    ct = um.get("candidatesTokenCount", 0)
                    return (pt * rate.get("in1", 0) / 1_000_000) * aud_usd + \
                           (ct * rate.get("out1", 0) / 1_000_000) * aud_usd

                step1_cost = _calc_cost(research_model_name, research_usage_meta) if research_model_name else 0.0
                step2_cost = _calc_cost(model_name, usage_meta)
                total_cost = step1_cost + step2_cost

                lines = [f"Created {ts} $A {total_cost:.4f} ({total_secs:.0f}s)"]
                if research_model_name:
                    lines.append(f"Step 1 ({research_model_name}): $A {step1_cost:.4f} ({step1_secs:.0f}s)")
                lines.append(f"Step 2 ({model_name}): $A {step2_cost:.4f} ({step2_secs:.0f}s)")
                return "\n".join(lines) + "\n\n"

            def _fmt_err(exc):
                """Return error string; for HTTP errors include the response body."""
                if isinstance(exc, urllib.error.HTTPError):
                    try:
                        body = exc.read().decode("utf-8", errors="replace")[:500]
                    except Exception:
                        body = "(could not read body)"
                    return f"{exc.code} {exc.reason} — {body}"
                return str(exc)

            # ── Testing datasets: two-step pipeline ──
            research_model_name = None
            research_usage = None
            if is_testing:
                # Step 1: Research with search-enabled model ──
                research_prompt = (
                    f"Research the military history: What operation was {unit} engaged in on {dod} "
                    f"in Vietnam? Who was {name} (service number {svc}, rank {rank}) and what were "
                    f"the circumstances of their death on {dod}? Provide raw operational details, "
                    f"unit movements, battle narrative, casualties, terrain, and tactical context. "
                    f"Be comprehensive and factual. Provide all details you can find."
                )
                research_text = ""
                research_model_name = None
                research_usage = None
                step1_start = time.time()
                for model in models:
                    self.after(0, lambda m=model: self._side_resp_replace(
                        f"Step 1/2 — Researching with {m} (search enabled)..."
                    ))
                    try:
                        research_payload = {
                            "systemInstruction": {
                                "parts": [{
                                    "text": (
                                        "You are a military researcher specializing in the Vietnam War. "
                                        "Provide raw, detailed factual text in prose. No formatting, no markdown."
                                    )
                                }]
                            },
                            "contents": [{"parts": [{"text": research_prompt}]}],
                            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 4096},
                            "tools": [{"google_search": {}}],
                        }
                        research_url = (
                            f"https://generativelanguage.googleapis.com/v1beta/models/"
                            f"{model}:generateContent?key={api_key}"
                        )
                        research_body = json.dumps(research_payload).encode("utf-8")
                        research_req = urllib.request.Request(
                            research_url, data=research_body,
                            headers={"Content-Type": "application/json"}
                        )
                        with urllib.request.urlopen(research_req, timeout=internal_timeout) as resp:
                            research_data = json.loads(resp.read().decode("utf-8"))
                            research_text = research_data["candidates"][0]["content"]["parts"][0]["text"]
                            research_model_name = model
                            research_usage = research_data.get("usageMetadata", {})
                        break
                    except Exception as exc:
                        err_msg = f"{model}: {_fmt_err(exc)}"
                        last_error = err_msg
                        self.after(0, lambda e=err_msg: self._side_resp_replace(
                            f"Step 1/2 — Research failed.\n\n{e}"
                        ))
                        continue

                step1_secs = time.time() - step1_start
                step2_start = time.time()
                # Step 2: Structure with search-disabled, JSON-mode, no thinking ──
                if research_text:
                    structured_prompt = (
                        f"RESEARCH MATERIAL (use ONLY this for your answers; do NOT search the web):\n\n"
                        f"{research_text}\n\n"
                        f"────────────────────────────────────────\n\n"
                        f"{user_prompt}"
                    )
                else:
                    structured_prompt = user_prompt

                for model in models:
                    self.after(0, lambda m=model: self._side_resp_replace(
                        f"Step 2/2 — Structuring with {m} (JSON mode, excl LIVE search data)..."
                    ))
                    try:
                        url = (
                            f"https://generativelanguage.googleapis.com/v1beta/models/"
                            f"{model}:generateContent?key={api_key}"
                        )
                        system_text = (
                            "You are a military archivist and historian specializing in the Vietnam War. "
                            "You produce structured JSON output from provided research material and soldier "
                            "identity values. You always return valid, parseable JSON exactly matching "
                            "the requested schema."
                        )
                        payload = {
                            "systemInstruction": {"parts": [{"text": system_text}]},
                            "contents": [{"parts": [{"text": structured_prompt}]}],
                            "generationConfig": {
                                "temperature": 0.2,
                                "maxOutputTokens": 8192,
                                "responseMimeType": "application/json",
                                "thinkingConfig": {"thinkingBudget": 0},
                            },
                        }
                        # Google Search tool deliberately NOT included — disabled for step 2

                        body = json.dumps(payload).encode("utf-8")
                        req = urllib.request.Request(
                            url, data=body, headers={"Content-Type": "application/json"}
                        )
                        with urllib.request.urlopen(req, timeout=master_timeout) as resp:
                            data = json.loads(resp.read().decode("utf-8"))
                            content = data["candidates"][0]["content"]["parts"][0]["text"]
                            usage_meta = data.get("usageMetadata", {})
                        content = self._extract_json(content)
                        header = _make_header(model, usage_meta, research_model_name, research_usage)
                        content = header + content
                        self.after(0, lambda c=content: self._side_resp_replace(c))
                        return
                    except Exception as exc:
                        last_error = f"{model}: {_fmt_err(exc)}"
                        continue
                self.after(0, lambda: self._side_resp_replace(
                    f"All models failed.\n\n{last_error}"
                ))

            # ── Non-testing datasets: original single-step flow ──
            else:
                step2_start = time.time()
                for model in models:
                    self.after(0, lambda m=model: self._side_resp_replace(
                        f"Using {m} to get additional details...."
                    ))
                    try:
                        url = (
                            f"https://generativelanguage.googleapis.com/v1beta/models/"
                            f"{model}:generateContent?key={api_key}"
                        )
                        system_text = "I am a highly skilled historian."
                        max_tokens = 2048
                        payload = {
                            "systemInstruction": {"parts": [{"text": system_text}]},
                            "contents": [{"parts": [{"text": user_prompt}]}],
                            "generationConfig": {
                                "temperature": 0.3,
                                "maxOutputTokens": max_tokens,
                            },
                        }
                        if is_live_search:
                            payload["tools"] = [{"google_search": {}}]

                        body = json.dumps(payload).encode("utf-8")
                        req = urllib.request.Request(
                            url, data=body, headers={"Content-Type": "application/json"}
                        )
                        with urllib.request.urlopen(req, timeout=master_timeout) as resp:
                            data = json.loads(resp.read().decode("utf-8"))
                            content = data["candidates"][0]["content"]["parts"][0]["text"]
                            usage_meta = data.get("usageMetadata", {})
                        header = _make_header(model, usage_meta, research_model_name, research_usage)
                        content = header + content
                        self.after(0, lambda c=content: self._side_resp_replace(c))
                        return
                    except Exception as exc:
                        last_error = f"{model}: {_fmt_err(exc)}"
                        continue
                self.after(0, lambda: self._side_resp_replace(
                    f"All models failed.\n\n{last_error}"
                ))

        threading.Thread(target=_task, daemon=True).start()

    # ------------------------------------------------------------------
    # AI Location Lookup (triggered by clicking the grid_reference label)
    # ------------------------------------------------------------------

    def _ai_location_lookup(self):
        """Fire a location-focused AI lookup for the current record.

        Called when the user clicks the 'grid_reference' field label.
        Builds a prompt that stresses obtaining the best available
        approximation of the place of death (GPS / UTM / MGRS) and
        displays the result in the side panel.

        No confirmation dialog — the click itself is the confirmation.
        """
        if not self._filtered:
            return

        actual_idx = self._filtered[self._filtered_pos]
        record = self.working_data[actual_idx]

        # ── gather soldier identity fields ──────────────────────────
        sra = (
            record.get("serviceRecordAuthority", {})
            if isinstance(record.get("serviceRecordAuthority"), dict)
            else {}
        )
        svc = sra.get("service_number", "")
        name = sra.get("full_name", "")
        dob = sra.get("date_of_birth", "")
        dod = sra.get("date_of_death", "")
        rank = sra.get("rank", "")
        unit = sra.get("unit", "")

        ref_id = record.get("referenceID", "")
        forces_map = {
            "AU": "Australian Armed Forces",
            "NZ": "New Zealand Armed Forces",
        }
        af = forces_map.get(ref_id[:2], ref_id[:2] if ref_id else "")

        dd = (
            record.get("derived_details", {})
            if isinstance(record.get("derived_details"), dict)
            else {}
        )
        pod = dd.get("place_of_death", "")
        grid_ref = dd.get("grid_reference", "")
        ftype = sra.get("fatality_type", "")

        # ── build a location-stressed prompt ─────────────────────────
        user_prompt = (
            f"Using the soldier identity values below, research and provide "
            f"the following in plain text:\n\n"
            f"PRIMARY TASK — THE BEST AVAILABLE APPROXIMATION OF THE PLACE "
            f"OF DEATH, using one of the following (whichever is most "
            f"appropriate or best supported by sources):\n"
            f"   - GPS latitude/longitude\n"
            f"   - UTM coordinates\n"
            f"   - MGRS grid reference\n\n"
            f"If the exact location is not documented, provide the closest "
            f"verifiable location (such as a base, town, road, or landmark) "
            f"and explain why this is the most accurate approximation.\n\n"
            f"SECONDARY DETAILS:\n"
            f"1. A detailed location description (terrain, nearby features, "
            f"   distance from known landmarks).\n"
            f"2. The map sheet number and UTM zone.\n"
            f"3. The military operation underway at the time of death.\n"
            f"4. Brief circumstances of death (confirmed facts only).\n\n"
            f"IDENTITY ANCHOR VALUES:\n\n"
            f"- Service Number: {svc}\n"
            f"- Full Name: {name}\n"
            f"- Date of Birth: {dob}\n"
            f"- Date of Death: {dod}\n"
            f"- Armed Forces: {af}\n"
            f"- Rank: {rank}\n"
            f"- Unit: {unit}\n"
            f"- Place of Death (if known): {pod}\n"
            f"- Current Grid Reference (if any): {grid_ref}\n"
            f"- Fatality Type: {ftype}\n\n"
            f"Use only the values supplied.  Do not invent or alter identity "
            f"details.  Present the answer in normal text."
        )

        # ── read API key & models from .env ──────────────────────────
        env = {}
        env_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".env"
        )
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip().strip('"').strip("'")

        api_key = env.get("GEMINI_API_KEY", "")
        models_str = env.get(
            "GEMINI_TEXT_TO_TEXT_MODELS_TO_USE", "gemini-2.5-flash"
        )
        models = [m.strip() for m in models_str.split(",") if m.strip()]

        master_timeout = int(env.get("AI_MASTER_RESPONSE_MODEL_CUTOFF_SECONDS", "150"))
        internal_timeout = int(env.get("AI_INTERNAL_RESPONSE_MODEL_CUTOFF_SECONDS", "40"))

        if not api_key:
            _error_dialog(self, "AI Error", "GEMINI_API_KEY not found in .env")
            return

        is_live_search = self._live_search_var.get()

        self._side_prompt_label.configure(text="PROMPT: Grid Reference Lookup")
        self._side_resp_label.configure(text="RESPONSE: Grid Reference Lookup")
        # ── show side panel with the prompt ──────────────────────────
        self._side_prompt.configure(state=tk.NORMAL)
        self._side_prompt.delete("1.0", tk.END)
        self._side_prompt.insert("1.0", user_prompt)
        self._side_resp.delete("1.0", tk.END)
        self._show_side_panel()

        # ── run AI call in background thread ─────────────────────────
        def _task():
            last_error = ""
            for model in models:
                self.after(
                    0,
                    lambda m=model: self._side_resp_replace(
                        f"Researching location for {name} using {m}…"
                    ),
                )
                try:
                    url = (
                        f"https://generativelanguage.googleapis.com/v1beta/"
                        f"models/{model}:generateContent?key={api_key}"
                    )
                    payload = {
                        "systemInstruction": {
                            "parts": [{
                                "text": (
                                    "You are a military historian specialising "
                                    "in Vietnam War locations and geography. "
                                    "You provide accurate, source-supported "
                                    "location information in plain text."
                                ),
                            }],
                        },
                        "contents": [{"parts": [{"text": user_prompt}]}],
                        "generationConfig": {
                            "temperature": 0.3,
                            "maxOutputTokens": 2048,
                        },
                    }
                    if is_live_search:
                        payload["tools"] = [{"google_search": {}}]

                    body = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(
                        url,
                        data=body,
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=master_timeout) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        content = (
                            data["candidates"][0]["content"]["parts"][0]["text"]
                        )
                    self.after(
                        0, lambda c=content: self._side_resp_replace(c)
                    )
                    return
                except Exception as exc:
                    last_error = f"{model}: {exc}"
                    continue
            self.after(
                0,
                lambda: self._side_resp_replace(
                    f"All models failed.\n\n{last_error}"
                ),
            )

        threading.Thread(target=_task, daemon=True).start()

    # ------------------------------------------------------------------
    # AI Place Lookup (triggered by clicking the place_of_death label)
    # ------------------------------------------------------------------

    def _ai_place_lookup(self):
        """Fire a place-name expansion AI lookup for the current record.

        Called when the user clicks the 'place_of_death' field label.
        Builds a prompt that asks the AI to expand a text description
        like "Phuoc Tuy Province, South Vietnam" into structured
        location detail with country / province / village / landmark /
        distance-from-reference-point.

        Also requests the best available GPS / UTM / MGRS coordinate.
        No confirmation dialog — the click itself is the confirmation.
        """
        if not self._filtered:
            return

        actual_idx = self._filtered[self._filtered_pos]
        record = self.working_data[actual_idx]

        # ── gather soldier identity fields ──────────────────────────
        sra = (
            record.get("serviceRecordAuthority", {})
            if isinstance(record.get("serviceRecordAuthority"), dict)
            else {}
        )
        svc = sra.get("service_number", "")
        name = sra.get("full_name", "")
        dob = sra.get("date_of_birth", "")
        dod = sra.get("date_of_death", "")
        rank = sra.get("rank", "")
        unit = sra.get("unit", "")

        ref_id = record.get("referenceID", "")
        forces_map = {
            "AU": "Australian Armed Forces",
            "NZ": "New Zealand Armed Forces",
        }
        af = forces_map.get(ref_id[:2], ref_id[:2] if ref_id else "")
        country_map = {"AU": "Australia", "NZ": "New Zealand"}
        country = country_map.get(ref_id[:2], ref_id[:2] if ref_id else "")

        dd = (
            record.get("derived_details", {})
            if isinstance(record.get("derived_details"), dict)
            else {}
        )
        pod = dd.get("place_of_death", "")
        grid_ref = dd.get("grid_reference", "")
        cod = dd.get("circumstances_of_death", "")
        usw = dd.get("unit_served_with", "")
        ftype = sra.get("fatality_type", "")

        # ── build a place-expansion prompt ──────────────────────────
        user_prompt = (
            f"Your sole task is to produce an enhanced place_of_death "
            f"description for this soldier.  Using the soldier identity "
            f"values and all provided details below, describe the "
            f"location in plain text using this structured format:\n\n"
            f"  {{country}} / {{region or province}} / "
            f"{{village, town, district, or city}} / "
            f"{{prominent nearby feature, landmark, or military "
            f"object}} / {{distance and direction from a known "
            f"reference point}}\n\n"
            f"ALSO PROVIDE:\n"
            f"1. Any alternative names, historical names, or local "
            f"names for this place.\n\n"
            f"IDENTITY ANCHOR VALUES:\n\n"
            f"- Country: {country}\n"
            f"- Service Number: {svc}\n"
            f"- Full Name: {name}\n"
            f"- Date of Birth: {dob}\n"
            f"- Date of Death: {dod}\n"
            f"- Armed Forces: {af}\n"
            f"- Rank: {rank}\n"
            f"- Unit: {unit}\n"
            f"- Unit Served With: {usw}\n"
            f"- Fatality Type: {ftype}\n"
            f"- Grid Reference (if known): {grid_ref}\n"
            f"- Circumstances of Death: {cod}\n\n"
            f"CURRENT place_of_death TEXT TO EXPAND:\n"
            f"  \"{pod}\"\n\n"
            f"Use only the values supplied.  Do not invent or alter "
            f"identity details.  Present the answer in normal text."
        )
        # ── read API key & models from .env ──────────────────────────
        env = {}
        env_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".env"
        )
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip().strip('"').strip("'")

        api_key = env.get("GEMINI_API_KEY", "")
        models_str = env.get(
            "GEMINI_TEXT_TO_TEXT_MODELS_TO_USE", "gemini-2.5-flash"
        )
        models = [m.strip() for m in models_str.split(",") if m.strip()]

        master_timeout = int(env.get("AI_MASTER_RESPONSE_MODEL_CUTOFF_SECONDS", "150"))
        internal_timeout = int(env.get("AI_INTERNAL_RESPONSE_MODEL_CUTOFF_SECONDS", "40"))

        if not api_key:
            _error_dialog(self, "AI Error", "GEMINI_API_KEY not found in .env")
            return

        is_live_search = self._live_search_var.get()
        self._side_prompt_label.configure(text="PROMPT: Place of Death")
        self._side_resp_label.configure(text="RESPONSE: Place of Death")

        # ── show side panel with the prompt ──────────────────────────
        self._side_prompt.configure(state=tk.NORMAL)
        self._side_prompt.delete("1.0", tk.END)
        self._side_prompt.insert("1.0", user_prompt)
        self._side_resp.delete("1.0", tk.END)
        self._show_side_panel()

        # ── run AI call in background thread ─────────────────────────
        def _task():
            last_error = ""
            for model in models:
                self.after(
                    0,
                    lambda m=model: self._side_resp_replace(
                        f"Researching location for {name} using {m}…"
                    ),
                )
                try:
                    url = (
                        f"https://generativelanguage.googleapis.com/v1beta/"
                        f"models/{model}:generateContent?key={api_key}"
                    )
                    payload = {
                        "systemInstruction": {
                            "parts": [{
                                "text": (
                                    "You are a military historian specialising "
                                    "in Vietnam War locations and geography. "
                                    "You break down place descriptions into "
                                    "structured location detail and provide "
                                    "coordinates where possible."
                                ),
                            }],
                        },
                        "contents": [{"parts": [{"text": user_prompt}]}],
                        "generationConfig": {
                            "temperature": 0.3,
                            "maxOutputTokens": 2048,
                        },
                    }
                    if is_live_search:
                        payload["tools"] = [{"google_search": {}}]

                    body = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(
                        url,
                        data=body,
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=master_timeout) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        content = (
                            data["candidates"][0]["content"]["parts"][0]["text"]
                        )
                    self.after(
                        0, lambda c=content: self._side_resp_replace(c)
                    )
                    return
                except Exception as exc:
                    last_error = f"{model}: {exc}"
                    continue
            self.after(
                0,
                lambda: self._side_resp_replace(
                    f"All models failed.\n\n{last_error}"
                ),
            )

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
        self._side_resp.delete("1.0", tk.END)
        self._side_resp.insert("1.0", text)
        # Show COPY button when response exceeds 200 characters
        if len(text) > 200:
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

    # ------------------------------------------------------------------
    # File-level actions
    # ------------------------------------------------------------------

    def _save(self):
        if not self.dirty and not self._record_dirty:
            self.destroy()
            return
        if self._record_dirty:
            updated = self._read_form()
            if updated is None:
                return
            self.working_data[self._filtered[self._filtered_pos]] = updated
            self._record_dirty = False
            self._set_locked(False)
        if not _save_json(self.file_path, self.working_data):
            return
        self.original_data.clear()
        self.original_data.extend(self.working_data)
        self.dirty = False
        self._show_record()

    def _gather_ref_state(self) -> dict | None:
        """Collect side-panel prompt/response and key field values for the current record."""
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

        # Field values: serviceRecordAuthority.service_status,
        # derived_details.place_of_death, grid_reference, circumstances_of_death,
        # pre_service_occupation, unit_served_with, references, ai_response
        sra = record.get("serviceRecordAuthority", {}) if isinstance(record.get("serviceRecordAuthority"), dict) else {}
        dd = record.get("derived_details", {}) if isinstance(record.get("derived_details"), dict) else {}

        fields = {
            "serviceRecordAuthority.service_status": sra.get("service_status", ""),
            "derived_details.place_of_death": dd.get("place_of_death", ""),
            "derived_details.grid_reference": dd.get("grid_reference", ""),
            "derived_details.circumstances_of_death": dd.get("circumstances_of_death", ""),
            "derived_details.pre_service_occupation": dd.get("pre_service_occupation", ""),
            "derived_details.unit_served_with": dd.get("unit_served_with", ""),
            "derived_details.references": dd.get("references", ""),
            "derived_details.ai_response": dd.get("ai_response", ""),
        }

        ref_state = {
            "prompt": prompt_text,
            "response": resp_text,
            "fields": fields,
        }
        return {"lastRefId": ref_id, ref_id: ref_state}

    def _cancel(self):
        if self._record_dirty:
            ok = _confirm_yesno(self, "Discard Changes?",
                                "You have unsaved changes.\nClose and discard all changes?")
            if not ok:
                return
        extra = self._gather_ref_state()
        _save_session(self.file_path, self._filtered_pos, self._search_text, extra=extra)
        self.destroy()
