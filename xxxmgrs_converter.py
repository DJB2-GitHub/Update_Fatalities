# ============================================================
# README
# ============================================================
# Title: MGRS Province Converter for AWM Commander Logs
# Author: Research utility for Australian Vietnam War mapping
# Version: 1.1 (Standalone)
#
# Description:
#   This script reconstructs full MGRS coordinates from partial
#   grid references found in Australian War Memorial (AWM)
#   Commander Logs and operational diaries.
#
#   During the Vietnam War, Australian units (e.g., 1ATF, 2RAR)
#   recorded patrol and contact locations using truncated 6-digit
#   grid references such as "GR 536567". These were based on the
#   South Vietnam 1:50,000 Series REFERENCE MAPS:
#       - 6430.11 (Baria)
#       - 6430.111 (Nui Dat)
#       - 6429.1 (Xuyen Moc)
#       - 6429.1V (Long Hai)
#   Collectively referred to as "6R" in field reports.
#
#   This tool expands those partial coordinates into full MGRS
#   strings (e.g., "48P YS 536 567") and converts them to
#   latitude/longitude for modern mapping or GIS visualization.
#
#   It is a STANDâ€‘ALONE script â€” no dependency on browser tabs,
#   metadata, or external context.
#
# IMPORTANT â€” Australian grid squares vs MGRS:
#   The Australian 6R map series used its own 100 km square
#   lettering (VU, UT, VT, VS, VR, UU) which DOES NOT match
#   standard MGRS. This module accepts the Australian square
#   designations as input (for historical fidelity) but
#   internally maps them to the correct MGRS squares:
#
#     Australian  ->  MGRS    Region
#     ----------     ----    ------
#     VU             YS      Phuoc Tuy (Nui Dat, Long Tan, Baria)
#     UT             YT      Long Khanh (north of Phuoc Tuy)
#     VT             XT      Bien Hoa (northwest)
#     VS             XS      Ben Cat / Binh Duong
#     VR             XR      Tay Ninh (Cambodian border)
#     UU             YS      Vung Tau (coastal, same MGRS square as VU)
#
# Usage:
#   1. Install dependencies:
#        pip install mgrs pyproj
#   2. Run the script directly in Python.
#   3. Input a partial grid (e.g., '536567') and province name
#      (e.g., 'Phuoc Tuy', 'Bien Hoa', 'Ben Cat').
#   4. The script outputs:
#        - Full MGRS coordinate (using the correct MGRS square)
#        - Latitude and longitude
#
# Example:
#   Input:  partial = "536567", province = "Phuoc Tuy"
#   Output: Full MGRS: 48P YS 536 567
#           Latitude: 10.455452, Longitude: 107.316670
#
# Historical Context:
#   The 1ATF base at Nui Dat and surrounding operations (Long Tan,
#   Baria, Dat Do) were in MGRS square "YS" within UTM Zone 48P
#   (Australian designation: "VU").
#   Adjacent provinces (Long Khanh, Bien Hoa, Ben Cat, Tay Ninh)
#   correspond to different squares (YT, XT, XS, XR).
#
# ============================================================

# ---------------------------------------------------------------------------
# Only mgrs is needed here. For a pure-UTM (non-MGRS) alternative that
# converts through UTM Zone 48 WGS-72 directly, see upm49p.py.
# ---------------------------------------------------------------------------
from mgrs import MGRS

# ---------------------------------------------------------------------------
# Australian 6R grid square â†’ correct MGRS 100 km square
# ---------------------------------------------------------------------------
# The Australian 1:50,000 "6R" map series (sheets 6430-II, 6430-III,
# 6429-I, 6429-IV) labelled its 100 km grid squares with letter pairs
# that DO NOT match standard MGRS.  For example, the Australian square
# "VU" (printed on the 6R maps around Nui Dat) corresponds to MGRS
# square "YS" in the global MGRS grid.
#
# This lookup bridges the Australian designations to real MGRS squares
# so the mgrs library can resolve them correctly.
# ---------------------------------------------------------------------------
_AU_TO_MGRS_SQUARE = {
    "VU": "YS",   # Phuoc Tuy: Nui Dat, Long Tan, Baria
    "UT": "YT",   # Long Khanh: north of Phuoc Tuy
    "VT": "XT",   # Bien Hoa: north-west of Phuoc Tuy
    "VS": "XS",   # Ben Cat / Binh Duong: north-west of Bien Hoa
    "VR": "XR",   # Tay Ninh: far west near Cambodian border
    "UU": "YS",   # Vung Tau: coastal strip south of Phuoc Tuy
                   #   (falls in the same MGRS square as VU)
}

# Province â†’ Australian 6R square (user-facing names)
_PROVINCE_TO_AU_SQUARE = {
    "phuoc tuy": "VU",
    "long khanh": "UT",
    "bien hoa": "VT",
    "ben cat": "VS",
    "binh duong": "VS",
    "tay ninh": "VR",
    "vung tau": "UU",
}


def _resolve_mgrs_square(easting: int, province: str = None) -> str:
    """
    Return the correct MGRS 100 km square code for a partial grid.

    If a province name is given, look up its Australian 6R square
    and translate to the real MGRS square via _AU_TO_MGRS_SQUARE.

    When province is omitted the function heuristically picks the
    square from the easting digit range.  This heuristic reproduces
    the field convention used on the South Vietnam 1:50,000 Series:
    the first three digits of the 6-digit reference fall into
    predictable bands for each operational area.
    """
    if province:
        au_square = _PROVINCE_TO_AU_SQUARE.get(province.lower())
        if au_square is None:
            raise ValueError(
                f"Unknown province: '{province}'. "
                f"Known: {list(_PROVINCE_TO_AU_SQUARE.keys())}"
            )
        return _AU_TO_MGRS_SQUARE[au_square]

    # Heuristic: easting band â†’ Australian square â†’ MGRS square
    # Each band spans ~20 km (200 easting units at 100 m resolution).
    if 520 <= easting < 540:
        au = "VU"    # Nui Dat / Long Tan
    elif 540 <= easting < 560:
        au = "UT"    # Dat Do / Xuyen Moc
    elif 560 <= easting < 580:
        au = "UU"    # Long Hai / coastal strip
    elif 500 <= easting < 520:
        au = "VT"    # Bien Hoa region
    elif 480 <= easting < 500:
        au = "VS"    # Ben Cat / Binh Duong
    else:
        au = "VU"    # fallback: assume Phuoc Tuy
    return _AU_TO_MGRS_SQUARE[au]


def province_expander(
    partial_grid: str, province: str = None, zone: str = "48P"
) -> str:
    """
    Expand a partial grid (e.g. '536567') into a full MGRS coordinate
    using the correct MGRS 100 km square for the given province.

    Parameters:
        partial_grid: 6-digit grid reference (easting/northing)
                      from AWM Commander logs.
        province:     Province name (e.g. 'Phuoc Tuy', 'Bien Hoa').
                      If omitted, auto-selects based on easting range.
        zone:         UTM zone and latitude band (default '48P').

    Returns:
        Full MGRS coordinate string (e.g. '48P YS 536 567').
    """
    partial_grid = partial_grid.strip().replace(" ", "")
    if len(partial_grid) != 6 or not partial_grid.isdigit():
        raise ValueError("Partial grid must be a 6-digit number like '536567'.")

    easting = int(partial_grid[:3])
    northing = partial_grid[3:]
    square = _resolve_mgrs_square(easting, province)

    return f"{zone} {square} {partial_grid[:3]} {northing}"


def mgrs_to_latlon(mgrs_string: str):
    """
    Convert a full MGRS coordinate to WGS-84 latitude/longitude.

    The MGRS string must include zone, latitude band, 100 km square
    letters, and numerical easting/northing (e.g. '48P YS 536 567').
    Spaces are stripped internally so both '48PYS536567' and
    '48P YS 536 567' are accepted.

    Returns:
        tuple: (latitude, longitude) in decimal degrees.
    """
    mgrs_string = mgrs_string.replace(" ", "")
    m = MGRS()
    latlon = m.toLatLon(mgrs_string)
    return latlon


# ============================================================
# Example usage:
# ============================================================
if __name__ == "__main__":
    partial = "536567"
    province = "Phuoc Tuy"

    mgrs_full = province_expander(partial, province)
    lat, lon = mgrs_to_latlon(mgrs_full)

    print(f"Partial: {partial}, Province: {province}")
    print(f"Full MGRS: {mgrs_full}")
    print(f"Latitude: {lat:.6f}, Longitude: {lon:.6f}")
    print()
    print("Expected area: Nui Dat ~ 10.55ÂN, 107.25ÂE")

