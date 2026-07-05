import re
import math
import mgrs
import os
import json
import tkinter as tk
from tkinter import ttk

# Deferred import — pyproj is needed only for Indian-1960 datum transformation.
# The import is also tried inside _transform_indian1960_to_wgs84
# with a friendlier error message when the library is missing.
try:
    from pyproj import Transformer as _PyprojTransformer
except ImportError:
    _PyprojTransformer = None

# ---------------------------------------------------------------------------
# Update {incident_location} value by scanning the input text for any substring
# that resembles a coordinate and applying masking rules to protect location data.
#
# The function performs the following steps:
# 1. Identify coordinate‑like patterns using a broad fuzzy matcher. These include:
#    - decimal pairs (e.g., "12.34 56.78")
#    - grid references (e.g., "12345 2345")
#    - degrees/minutes/seconds fragments
#    - shorthand formats with N/S/E/W
#
# 2. For each detected snippet, apply masking rules:
#    - If the snippet is already fully masked (//text//), leave it unchanged.
#    - If the snippet begins with "//", do not prepend another "//".
#    - If the snippet ends with "//", do not append another "//".
#    - Only wrap clean, unmasked snippets in "//" on both sides.
#
# 3. Multiple coordinate‑like snippets in the same line are processed independently.
#
# This ensures {incident_location} is consistently masked while preventing
# double‑masking, malformed masks, or accidental extension of existing masks.
# The transformation is idempotent: running it multiple times will not alter
# already‑masked content.
# ---------------------------------------------------------------------------

COORD_FUZZY = re.compile(
    r"""
    ([-+]?\d{1,3}\.\d{1,8}\s*[,;/\-\s]\s*[-+]?\d{1,3}\.\d{1,8} |
     \b\d{1,3}\s*[-/,;: ]\s*\d{1,3}\b |
     \d{1,3}°\s*\d{1,3}'\s*\d{0,3}"? |
     \d{1,3}°\s*\d{1,3}' |
     \d{1,3}°\s*\d{1,3}\.\d+' |
     [NS]\s*\d{1,3}(\.\d+)? |
     [EW]\s*\d{1,3}(\.\d+)? |
     \d{1,3}(\.\d+)?\s*[NSEW] |
     \b\d{1,2}[A-Z]{2}\s*\d{3,5}\s*\d{3,5}\b |
     \b[A-Z]{2}\s*\d{3,5}\s*\d{3,5}\b |
     \b[A-Z]{2}\d{2,3}\s*\d{3,5}\b |
     \b[A-Z]{2}\d{4,6}\b |
     \b\d{3,6}\s*[-/ ]\s*\d{3,6}\b)
    """,
    re.VERBOSE | re.IGNORECASE
)


def mask_coordinates(line: str) -> str:
    """Mask coordinate-like substrings with // // unless already masked or inside // //."""

    # Locate all existing //...// spans so nested matches are not re-wrapped.
    existing_spans = [(m.start(), m.end()) for m in re.finditer(r'//.+?//', line)]

    def replacer(m):
        text = m.group(0)
        pos, end = m.start(), m.end()

        # If the match text itself is already fully masked
        if text.startswith("//") and text.endswith("//"):
            return text

        # If left side already masked, don't prepend
        if text.startswith("//"):
            return text

        # If right side already masked, don't append
        if text.endswith("//"):
            return text

        # If the match falls entirely inside an existing //...// span, skip it
        for sp_start, sp_end in existing_spans:
            if sp_start <= pos and end <= sp_end:
                return text

        # Otherwise wrap normally
        return f"//{text}//"

    return COORD_FUZZY.sub(replacer, line)

# ---------------------------------------------------------------------------
# Known 100 km MGRS squares in zone 48P (southern / III Corps Vietnam).
# Any square NOT in this set is assumed to be in 48Q (northern / I & II Corps).
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
# MGRS column / row letter mappings (I and O are omitted per MGRS spec)
# ---------------------------------------------------------------------------
_MGRS_COLS = "ABCDEFGHJKLMNPQRSTUVWXYZ"   # 24 letters (columns)
_MGRS_ROWS = "ABCDEFGHJKLMNPQRSTUV"        # 20 letters (rows, only A–V)


# ---------------------------------------------------------------------------
# _mgrs_square_to_utm(zone, lat_band, square, e_off, n_off, precision)
#   → (utm_e, utm_n, hemisphere)
# ---------------------------------------------------------------------------
# Pure grid math: converts an MGRS 100 km square + offsets to full UTM
# easting / northing in metres.  Datum-independent — this only computes
# where the grid lines fall, not how they relate to the geoid.
# ---------------------------------------------------------------------------
def _mgrs_square_to_utm(zone, lat_band, square, easting_offset, northing_offset,
                        precision):
    """Return (utm_easting, utm_northing, 'N'|'S') for an MGRS square + offsets."""
    col_letter = square[0].upper()
    row_letter = square[1].upper()

    col_idx = _MGRS_COLS.index(col_letter)   # 0–23
    row_idx = _MGRS_ROWS.index(row_letter)   # 0–19

    zone_in_set = (zone - 1) % 3
    first_col_for_zone = zone_in_set * 8
    col_in_zone = col_idx - first_col_for_zone

    if col_in_zone < 0:
        col_in_zone += 24
    elif col_in_zone >= 8:
        col_in_zone -= 24

    square_easting = col_in_zone * 100_000

    hemisphere = 'N' if lat_band.upper() >= 'N' else 'S'
    if hemisphere == 'N':
        square_northing = row_idx * 100_000
    else:
        square_northing = 10_000_000 - (row_idx + 1) * 100_000

    utm_e = square_easting + easting_offset
    utm_n = square_northing + northing_offset
    return utm_e, utm_n, hemisphere


# ---------------------------------------------------------------------------
# _transform_indian1960_to_wgs84(zone, utm_e, utm_n, hemisphere)
#   → (lat, lon) | None
# ---------------------------------------------------------------------------
def _transform_indian1960_to_wgs84(zone, utm_e, utm_n, hemisphere='N'):
    """Transform UTM coordinates from Indian 1960 datum to WGS84 lat/lon.

    Uses pyproj with EPSG:3148 (zone 48N) or EPSG:3149 (zone 49N).
    Returns (lat, lon) or None if the zone is unsupported / pyproj missing.
    """
    if _PyprojTransformer is None:
        return None

    _INDIAN1960_EPSG = {48: 3148, 49: 3149}
    epsg = _INDIAN1960_EPSG.get(zone)
    if epsg is None:
        return None

    transformer = _PyprojTransformer.from_crs(
        f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(utm_e, utm_n)
    return lat, lon


# ---------------------------------------------------------------------------
# _try_parse_vietnam_mgrs(coord_str: str) → (float, float) | None
# ---------------------------------------------------------------------------
#
# The core Vietnam-era MGRS normaliser.
#
# Accepts any of these input shapes (spaces stripped, case-insensitive):
#
#     "48P YS 426 694"   — full, correct zone
#     "48Q YS 426 694"   — full, WRONG zone  → auto-corrected 48Q→48P
#     "YS 426 694"       — partial, no zone   → zone inferred from square
#     "48PYS426694"      — compact (no spaces)
#     "YS426694"         — compact partial
#     "48Q YS 42600 69400" — 10-digit fine precision
#
# Datum tagging — prefix the MGRS with one of:
#     "I60:", "INDIAN1960:", or "INDIAN:"
# to force Indian 1960 (Vietnam) datum transformation (EPSG:24305/24306
# → EPSG:4326) instead of the default SVN60 shift.
# Example:  "I60:48P YS 734 982"  or  "I60:YS 734 982"
#
# Pipeline (each step is documented inline):
#
#   0. Detect optional Indian-1960 datum tag (I60:/INDIAN1960:/INDIAN:)
#   1. Clean & normalise whitespace / case
#   2. Match against a full-MGRS regex or a partial (no-GZD) regex
#   3. If partial, infer zone 48 + band P or Q from the square lookup table
#   4. Auto-correct 48Q → 48P for squares known to be in 48P
#   5. Split the numerical half into Easting / Northing components
#   6. Expand abbreviated digits to full-metre values
#   7a. IF Indian-1960: convert MGRS → UTM, then pyproj datum-shift to WGS84
#   7b. ELSE (default SVN60): shift easting/northing, reconstruct MGRS,
#        convert via mgrs library.
#
# Returns a (lat, lon) tuple rounded to 5 decimal places (~1 m precision),
# or None if the input does not match any Vietnam MGRS pattern.
# ---------------------------------------------------------------------------
def _try_parse_vietnam_mgrs(coord_str: str):
    # Deferred imports so the file can be loaded even without these libraries,
    # and to avoid a heavy import on every coordinate-parse attempt.
    import mgrs as mgrs_lib

    # ---- step 0: detect Indian-1960 datum tag ------------------------------
    use_indian1960 = False
    raw_input = str(coord_str).strip()
    indian_match = re.match(
        r'^(?:I60|INDIAN\s*1960|INDIAN)\s*[:/-]?\s*(.*)$',
        raw_input, re.IGNORECASE)
    if indian_match:
        use_indian1960 = True
        raw_input = indian_match.group(1).strip()

    # ---- step 1: normalise -------------------------------------------------
    # Strip all whitespace, convert to uppercase.  This collapses
    # "48P YS 426 694" → "48PYS426694" and "ys 426 694" → "YS426694".
    clean = re.sub(r"\s+", "", raw_input).upper()
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

    # ---- step 7: datum transformation (Indian-1960 or SVN60) -------------
    if use_indian1960:
        # ---- Indian 1960 pathway (pyproj datum transformation) ---------
        # Reconstruct the original (unshifted) MGRS string, use the mgrs
        # library's MGRSToUTM to parse it into UTM coordinates, then
        # transform from Indian 1960 datum to WGS84 via pyproj.
        #
        # MGRS-to-UTM conversion is datum-independent grid math — the
        # same easting/northing values apply regardless of datum.  The
        # datum only matters when converting UTM ↔ lat/lon, which pyproj
        # handles correctly.
        orig_mgrs = f"{zone_str}{lat_band}{square}{e_str}{n_str}"
        try:
            _, _, utm_e, utm_n = mgrs_lib.MGRS().MGRSToUTM(orig_mgrs)
        except Exception:
            return None
        result = _transform_indian1960_to_wgs84(zone, utm_e, utm_n, lat_band)
        if result is not None:
            lat, lon = result
            return round(lat, 5), round(lon, 5)
        # pyproj unavailable or zone not supported — fall through to
        # return None so the caller shows a helpful error.
        return None

    # ---- default SVN60 pathway (legacy shift + mgrs library) -----------
    #
    # The original coordinate was recorded on an SVN60 map.  To express the
    # same physical point in WGS84 (used by GPS, Google Maps, etc.) we must
    # shift the grid easting and northing by the datum offset.
    #
    #     SVN60 Easting + 205 m ≈ WGS84 Easting
    #     SVN60 Northing + 75 m ≈ WGS84 Northing
    _DATUM_SHIFT_E = 205
    _DATUM_SHIFT_N = 75
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
# _try_parse_awm_6r(coord_str: str) → (float, float) | None
# ---------------------------------------------------------------------------
#
# Parse Australian 6R map series partial grid references from AWM
# Commander Logs.  These are NOT MGRS — they are truncated UTM
# coordinates from the South Vietnam 1:50,000 map series (6430-II,
# 6430-III, 6429-I, 6429-IV) using the Australian 100 km square
# lettering (VU, UT, VT, VS, VR, UU).
#
# Accepted forms:
#     "6R 536567"              → default square (VU / Phuoc Tuy)
#     "6R VU 536567"           → explicit Australian square
#     "6R Phuoc Tuy 536567"    → province name (case-insensitive)
#     "536567"                 → bare 6 digits (auto-detected)
#
# Conversion path: UTM Zone 48 WGS-72 → WGS-84 lat/lon.
# Delegates to upm49p.awm_partial_to_latlon().
# ---------------------------------------------------------------------------
def _try_parse_awm_6r(coord_str: str):
    """Try to parse an Australian 6R partial grid reference.

    Returns (lat, lon) rounded to 5 decimal places, or None.
    """
    clean = str(coord_str).strip()
    if not clean:
        return None

    # ---- detect and strip "6R" prefix -----------------------------------
    had_prefix = False
    prefix_match = re.match(r'^6R\s+', clean, re.IGNORECASE)
    if prefix_match:
        clean = clean[prefix_match.end():].strip()
        had_prefix = True

    # ---- split into tokens; last token must be exactly 6 digits --------
    tokens = clean.split()
    if not tokens or not re.match(r'^\d{6}$', tokens[-1]):
        return None

    digits = tokens[-1]
    prefix_tokens = tokens[:-1]   # everything before the digits

    square = None
    province = None

    if prefix_tokens:
        # If the first prefix token is exactly 2 letters, treat as
        # an Australian 100 km square code (e.g. "VU", "UT", "VT").
        if re.match(r'^[A-Z]{2}$', prefix_tokens[0], re.IGNORECASE):
            square = prefix_tokens[0].upper()
        else:
            # Otherwise treat all prefix tokens as a province name
            # (e.g. "Phuoc Tuy", "Bien Hoa").
            province = ' '.join(prefix_tokens)
    elif not had_prefix:
        # Bare 6 digits with no "6R" prefix: only accept if the
        # original input is purely numeric (no stray letters) so we
        # don't steal input meant for another parser.
        if not re.match(r'^\s*\d{6}\s*$', str(coord_str).strip()):
            return None

    # ---- delegate to the UTM WGS-72 converter --------------------------
    try:
        from upm49p import awm_partial_to_latlon
        if square:
            lat, lon = awm_partial_to_latlon(digits, square=square)
        elif province:
            lat, lon = awm_partial_to_latlon(digits, province=province)
        else:
            lat, lon = awm_partial_to_latlon(digits)   # defaults to VU
        return round(lat, 5), round(lon, 5)
    except (ImportError, ValueError):
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
#    2        Australian 6R        "6R 536567"
#                                 "6R VU 536567"
#                                 "536567"  (bare 6 digits)
#    3        Vietnam-era MGRS     "48Q YS 426 694"
#                                 "YS 426 694"
#    4        Generic MGRS         "48PYS458630"
#                                 (any non-Vietnam MGRS worldwide)
#    5 (lo)   DMS                  "10° 20' N, 107° 04' E"
#
# Australian 6R (priority 2) and Vietnam-era MGRS (priority 3) are placed
# BEFORE generic MGRS (priority 4) so that Vietnam-specific corrections
# (UTM WGS-72 conversion for 6R, zone fix + datum shift for MGRS) are
# applied before the generic converter gets a chance to misinterpret the
# coordinate as a raw WGS84 MGRS.
#
# Returns a 3-tuple:
#   is_valid    True if a parser accepted the input
#   message     Human-readable validation result
#   coordinates (lat, lon) if parseable, else None
# ---------------------------------------------------------------------------

def _extract_coordinate_snippets(text: str):
    """Scan free-form text for embedded decimal-coordinate pairs.

    Returns a list of (lat_str, lat_hem, lon_str, lon_hem) tuples found
    in the text, ordered by occurrence.  Each tuple contains the raw
    number strings and optional N/S/E/W hemisphere letters.

    Matches patterns like:
        "16.75, 107.15"
        "16.75 N, 107.15 E"
        "16.75N, 107.15E"
        "-33.8688, 151.2093"
    Does NOT match integer-only pairs (avoids MGRS false positives).
    """
    # Two decimal-containing numbers, optionally signed, optionally with
    # N/S/E/W hemisphere letters, separated by comma, semicolon, or whitespace.
    pat = re.compile(
        r'(-?\d+\.\d+)\s*([NSns]?)\s*[,;\s]+\s*(-?\d+\.\d+)\s*([EWew]?)'
    )
    return pat.findall(text)


def validate_and_parse_coordinate(coord_str: str):
    # Guard: reject empty or whitespace-only input immediately.
    if not coord_str or not str(coord_str).strip():
        return False, "Input is empty.", None

    # Normalise: strip leading/trailing whitespace (but preserve internal
    # spaces — the regex patterns handle those themselves).
    coord_str = str(coord_str).strip()

    # ── Explicit //...// delimiter: user-wrapped coordinate takes priority ──
    # If the text contains //lat, lon// or //MGRS//, extract the content
    # between the first pair and parse only that.  The user can wrap any
    # coordinate they want the system to use with //...//.
    delim = re.search(r'//(.+?)//', coord_str)
    if delim:
        coord_str = delim.group(1).strip()

    # ── Pre-normalisation: strip degree symbols and trailing annotation ──
    # Users sometimes paste coordinates like "10.455° N  107.270° E MGRS".
    # Remove ° and trailing keywords so the parsers see clean numbers.
    coord_str = re.sub(r'°', '', coord_str)
    coord_str = re.sub(r'\s+(MGRS|UTM|DMS)\s*$', '', coord_str, flags=re.IGNORECASE)
    # Strip trailing [...] grid-reference fragments so the decimal parser
    # sees a clean "lat, lon" (e.g. "10.500, 107.200 [48 234567]").
    coord_str = re.sub(r'\s*\[[^]]*\]\s*$', '', coord_str).strip()

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
    #     "10.455 N  107.270 E"          (degree symbols already stripped)
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
    # PARSER 2 — Australian 6R partial grid (AWM Commander Logs, UTM WGS-72)
    # =========================================================================
    #
    # Handles truncated 6-digit grid references from the South Vietnam
    # 1:50,000 "6R" map series.  These are NOT MGRS — they use Australian
    # 100 km square lettering and must be converted via UTM Zone 48
    # WGS-72 → WGS-84.
    #
    # Checked before Vietnam MGRS because the "6R" prefix can be
    # misinterpreted as MGRS zone 6 band R by the MGRS parser
    # (e.g. "6R VU 536567" → "6RVU536567" looks like valid MGRS).
    #
    # Accepted forms:
    #     "6R 536567"              → default square (VU / Phuoc Tuy)
    #     "6R VU 536567"           → explicit Australian square
    #     "6R Phuoc Tuy 536567"    → province name
    #     "536567"                 → bare 6 digits (auto-detected)
    #
    # _try_parse_awm_6r returns None if the input does not match a 6R
    # pattern, which causes this parser to yield.
    awm6r_result = _try_parse_awm_6r(coord_str)
    if awm6r_result is not None:
        return (
            True,
            "Valid Australian 6R grid reference (UTM Zone 48 WGS-72)",
            awm6r_result,
        )

    # =========================================================================
    # PARSER 3 — Vietnam-era MGRS (with zone correction & datum shift)
    # =========================================================================
    #
    # Try the Vietnam-specific parser BEFORE the generic MGRS parser.
    # This ensures that "YS 426 694" gets the SVN60 → WGS84 treatment
    # rather than being rejected or interpreted as a generic WGS84 MGRS.
    #
    # _try_parse_vietnam_mgrs returns None if the input does not look
    # like a Vietnam-era MGRS, which causes this parser to yield and
    # let the next parser attempt it instead.
    vietnam_result = _try_parse_vietnam_mgrs(coord_str)
    if vietnam_result is not None:
        return (
            True,
            "Valid Vietnam-era MGRS (zone-corrected, datum-shifted)",
            vietnam_result,
        )

    # =========================================================================
    # PARSER 4 — Generic MGRS (worldwide, WGS84 assumed)
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
    # NOT match here — it was already handled by parser 3 (Vietnam MGRS).
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
    # PARSER 5 — Degrees/Minutes/Seconds (DMS)
    # =========================================================================
    #
    # Lightweight detection: looks for at least two degree-minute pairs
    # with at least one hemisphere letter (N/S/E/W).  Without a hemisphere
    # letter the input is too ambiguous — plain decimal coordinates like
    # "10.500, 107.200" would otherwise be misinterpreted as DMS.
    # Full mathematical conversion is not implemented (the `mgrs` library
    # doesn't handle DMS); this parser simply validates the *format* so the
    # user doesn't get an "unrecognized" error when pasting DMS coordinates.
    #
    # Now implements degrees + decimal-minutes → decimal conversion.
    # Each match captures (degrees, minutes, optional N/S/E/W).
    dms_regex = re.compile(
        r"(\d+)[^0-9A-Z]+(\d+)[^0-9A-Z]*([NSEW]?)", re.IGNORECASE
    )
    matches = list(dms_regex.finditer(coord_str))

    # Require at least one hemisphere letter — without it, numbers like
    # "10.500, 107.200" would be falsely interpreted as DMS (10°500', 107°200').
    has_hemisphere = any(m.group(3).upper() for m in matches)

    if len(matches) >= 2 and has_hemisphere:
        # Collect (degrees, minutes, hemisphere) triples
        dms_parts = []
        for m in matches:
            deg = int(m.group(1))
            min_val = float(m.group(2))
            hem = m.group(3).upper() if m.group(3) else ""
            dms_parts.append((deg, min_val, hem))
        # Assign latitude / longitude by hemisphere letter when present,
        # otherwise assume first two parts are (lat, lon).
        lat_part = None
        lon_part = None
        for deg, min_val, hem in dms_parts:
            if hem in ("N", "S"):
                lat_part = (deg, min_val, hem)
            elif hem in ("E", "W"):
                lon_part = (deg, min_val, hem)
        if lat_part is None and len(dms_parts) >= 1:
            lat_part = dms_parts[0]
        if lon_part is None and len(dms_parts) >= 2:
            lon_part = dms_parts[1]
        if lat_part and lon_part:
            lat = lat_part[0] + lat_part[1] / 60.0
            if lat_part[2] == "S":
                lat = -lat
            lon = lon_part[0] + lon_part[1] / 60.0
            if lon_part[2] == "W":
                lon = -lon
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return True, "Valid DMS (Degrees/Minutes)", (round(lat, 5), round(lon, 5))
        # DMS format was recognised but the computed coordinates were
        # out of range (e.g. decimal degrees mistaken for DMS).
        # Fall through to the snippet-extraction fallback instead of
        # returning — decimal-with-hemisphere often parses there.

    # =========================================================================
    # FALLBACK 1 — try extracting a coordinate snippet from free-form text
    # =========================================================================
    #
    # When the user pastes prose like "Best estimate: 16.75, 107.15 ; Ben Het",
    # none of the strict parsers above will match the full string.  Scan for
    # embedded decimal-degree pairs and try parsing each one.
    snippets = _extract_coordinate_snippets(coord_str)
    for lat_str, lat_hem, lon_str, lon_hem in snippets:
        lat_hem = lat_hem.upper()
        lon_hem = lon_hem.upper()
        # Reconstruct a clean "lat, lon" string for the decimal parser
        candidate = f"{lat_str} {lat_hem}, {lon_str} {lon_hem}".strip()
        # Remove trailing comma if hemisphere letters are empty
        candidate = candidate.rstrip(",").strip()
        # Try the decimal parser (regex from PARSER 1 above)
        dec_regex = re.compile(
            r"^(-?\d+\.\d+)\s*([NS]?)[,\s]+(-?\d+\.\d+)\s*([EW]?)$",
            re.IGNORECASE
        )
        m = dec_regex.match(candidate)
        if m:
            lat = float(m.group(1))
            lat_dir = m.group(2).upper() if m.group(2) else ""
            lon = float(m.group(3))
            lon_dir = m.group(4).upper() if m.group(4) else ""
            if lat_dir == 'S':
                lat *= -1
            if lon_dir == 'W':
                lon *= -1
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return True, "Extracted from free-form text", (round(lat, 5), round(lon, 5))

    # =========================================================================
    # FALLBACK 2 — nothing matched
    # =========================================================================
    #
    # Show the user which formats are accepted so they can retype or
    # reformat the coordinate.
    error_msg = (
        f"Unrecognized coordinate format: '{coord_str}'.\n"
        "Acceptable formats are:\n"
        "  1. Decimal Degrees: '10.34694 N, 107.07263 E'"
        " or '10.34694, 107.07263'\n"
        "  2. Australian 6R: '6R 536567' or '6R VU 536567'\n"
        "  3. Vietnam-era MGRS: 'YS 426 694' or '48P YS 426 694'\n"
        "  4. Indian-1960 MGRS: 'I60:48P YS 734 982' or 'I60:YS 734 982'\n"
        "  5. Standard MGRS: '48PYS458630' or '48P YS 458 630'\n"
        "  6. DMS: '10\u00b0 20' N, 107\u00b0 04' E'"
    )
    return False, error_msg, None


def parse_with_snippet(text: str):
    """Parse coordinate text and also return the extracted snippet for wrapping.

    Works like validate_and_parse_coordinate but additionally returns the
    raw coordinate text that was extracted, so the caller can wrap it in
    //...// delimiters for user visibility.

    Returns (is_valid, msg, parsed, snippet_text) where snippet_text is
    the raw coordinate substring extracted (or None if full-string parse).
    """
    text = str(text).strip() if text else ""
    if not text:
        return False, "Input is empty.", None, None

    # 1) Try explicit //...// delimiters first
    delim = re.search(r'//(.+?)//', text)
    if delim:
        inner = delim.group(1).strip()
        is_valid, msg, parsed = validate_and_parse_coordinate(inner)
        return is_valid, msg, parsed, inner

    # 2) Try full-string parse
    is_valid, msg, parsed = validate_and_parse_coordinate(text)
    if is_valid and parsed is not None and msg == "Extracted from free-form text":
        # Find which snippet was used so we can wrap it
        snippets = _extract_coordinate_snippets(text)
        for lat_str, lat_hem, lon_str, lon_hem in snippets:
            lat_hem = lat_hem.upper()
            lon_hem = lon_hem.upper()
            candidate = f"{lat_str} {lat_hem}, {lon_str} {lon_hem}".strip()
            candidate = candidate.rstrip(",").strip()
            # If no hemisphere letters, remove the stray space before comma
            if not lat_hem and not lon_hem:
                candidate = re.sub(r'\s+,', ',', candidate)
            dec_regex = re.compile(
                r"^(-?\d+\.\d+)\s*([NS]?)[,\s]+(-?\d+\.\d+)\s*([EW]?)$",
                re.IGNORECASE
            )
            m = dec_regex.match(candidate)
            if m:
                lat = float(m.group(1))
                lat_dir = m.group(2).upper() if m.group(2) else ""
                lon = float(m.group(3))
                lon_dir = m.group(4).upper() if m.group(4) else ""
                if lat_dir == 'S':
                    lat *= -1
                if lon_dir == 'W':
                    lon *= -1
                if (-90 <= lat <= 90 and -180 <= lon <= 180
                        and round(lat, 5) == parsed[0]
                        and round(lon, 5) == parsed[1]):
                    # Reconstruct the exact substring from original text
                    # Use the raw match boundaries for accuracy
                    return is_valid, msg, parsed, candidate
        return is_valid, msg, parsed, None

    return is_valid, msg, parsed, None


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
# ---------------------------------------------------------------------------
# Custom dialogs
# ---------------------------------------------------------------------------

ACCENT      = "#c63f3f"
ACCENT_HOV  = "#a53434"
BG_GREY     = "#f5f5f5"
WHITE       = "#ffffff"
TEXT_DARK   = "#222222"
TEXT_MUTED  = "#888888"
BORDER      = "#dcdcdc"
FONT        = "Segoe UI"


def _render_markdown(text_widget: tk.Text, message: str):
    """Insert message into a Text widget with basic markdown formatting.
    Supports: **bold**, ## heading, `code`, --- separator."""
    text_widget.configure(state="normal")
    text_widget.delete("1.0", tk.END)
    text_widget.tag_configure("bold", font=(FONT, 10, "bold"))
    text_widget.tag_configure("h2", font=(FONT, 11, "bold"), foreground=ACCENT)
    text_widget.tag_configure("code", font=(FONT, 9), foreground="#555555")
    lines = message.split("\n")
    for line in lines:
        if line.startswith("## "):
            text_widget.insert(tk.END, line[3:] + "\n", "h2")
        elif line.strip() and all(c in "\u2500-" for c in line.strip()):
            text_widget.insert(tk.END, "\n")
        else:
            parts = re.split(r'(\*\*.*?\*\*|`.*?`)', line)
            for part in parts:
                if part.startswith("**") and part.endswith("**"):
                    text_widget.insert(tk.END, part[2:-2], "bold")
                elif part.startswith("`") and part.endswith("`"):
                    text_widget.insert(tk.END, part[1:-1], "code")
                else:
                    text_widget.insert(tk.END, part)
            text_widget.insert(tk.END, "\n")
    text_widget.configure(state="disabled")


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
    # Use a scrollable Text widget for long messages (> 10 lines)
    line_count = message.count("\n") + 1
    if line_count > 10:
        msg_frame = ttk.Frame(dlg)
        msg_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 8))
        msg_text = tk.Text(msg_frame, font=(FONT, 10), wrap=tk.WORD,
                           bg=WHITE, fg=TEXT_DARK, relief=tk.FLAT,
                           width=52, height=min(line_count + 1, 20))
        _render_markdown(msg_text, message)
        scrollbar = ttk.Scrollbar(msg_frame, command=msg_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        msg_text.configure(yscrollcommand=scrollbar.set)
        msg_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    else:
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
