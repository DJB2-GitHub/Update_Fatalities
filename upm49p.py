# ============================================================
# Correct UTM Converter for AWM Commander Logs (Vietnam War)
# ============================================================
# Converts partial Australian grid references (e.g. "536567")
# from South Vietnam 1:50,000 Series maps (6430-II, 6430-III,
# 6429-I, 6429-IV — often called "6R") into correct latitude/
# longitude using UTM Zone 48N on the WGS-72 ellipsoid.
#
# IMPORTANT — this module deliberately avoids the MGRS library:
#   The grid references in AWM Commander Logs are NOT standard
#   MGRS coordinates.  The Australian 6R map series printed its
#   own 100 km square letter pairs (VU, UT, VT, VS, VR, UU) that
#   DO NOT match the global MGRS grid.  Feeding these Australian
#   square codes to an MGRS library silently produces wrong
#   locations (e.g. "48P VU 536 567" -> Cambodia, not Phuoc Tuy).
#
#   This module treats the coordinates as raw UTM easting/northing
#   within Zone 48 (northern hemisphere) on the WGS-72 datum that
#   was the operational mapping standard for US and allied forces
#   in Vietnam.  Each 100 km square baseline (SW corner) was
#   calibrated from the actual geographic centroid of its province.
#
#   For a module that bridges the Australian square names into
#   real MGRS strings, see mgrs_converter.py.
#
# Datum note — WGS-72 vs WGS-84:
#   WGS-72 was the reference ellipsoid used during the Vietnam War.
#   The difference between WGS-72 and modern WGS-84 is on the order
#   of 20-30 metres at this latitude — negligible for the 100 m
#   precision of a 6-digit grid reference, but the conversion uses
#   WGS-72 for historical accuracy.  Output is WGS-84 lat/lon.
#
# Grid resolution:
#   Each digit in the 6-digit reference represents 100 metres on the
#   ground (3 easting digits × 3 northing digits within a 100 km
#   square).  The multiplier is therefore x100, not x1000.
# ============================================================

from pyproj import Proj, Transformer

# ---------------------------------------------------------------------------
# Coordinate system objects (module-level — created once at import)
# ---------------------------------------------------------------------------
# UTM Zone 48, northern hemisphere, WGS-72 ellipsoid.
#   south=False  -> northern hemisphere (false northing = 0 at equator).
#   zone=48      -> UTM Zone 48 (102E - 108E, central meridian 105E).
#   ellps='WGS72' -> the operational datum of the Vietnam War era.
# Target: standard WGS-84 lat/lon for modern GIS / Google Earth.
# ---------------------------------------------------------------------------
_UTM48_WGS72 = Proj(proj='utm', zone=48, ellps='WGS72', south=False)
_WGS84      = Proj(proj='latlong', datum='WGS84')
_TRANSFORMER = Transformer.from_proj(_UTM48_WGS72, _WGS84)

# ---------------------------------------------------------------------------
# 100 km square UTM baselines (SW corner easting/northing in metres)
# ---------------------------------------------------------------------------
# Each Australian 6R square corresponds to a 100 km × 100 km cell on
# the UTM grid.  The values below are the absolute UTM Zone 48 easting
# and northing of each square's south-west corner.  They were obtained
# by converting the centroid of each province to MGRS (to identify the
# real MGRS 100 km square), reading the SW corner of that square, then
# projecting that corner into UTM Zone 48 coordinates.
#
#   Square   Easting    Northing   Area
#   ──────   ───────    ────────   ────────────────────────────
#   VU       700 000    1 100 000   Phuoc Tuy (Nui Dat / Baria)
#   UT       700 000    1 200 000   Long Khanh (north)
#   VT       600 000    1 200 000   Bien Hoa (north-west)
#   VS       600 000    1 100 000   Ben Cat / Binh Duong
#   VR       600 000    1 000 000   Tay Ninh (far west)
#   UU       700 000    1 100 000   Vung Tau (coastal, same as VU)
# ---------------------------------------------------------------------------
_SQUARE_BASELINES = {
    "VU": (700000, 1100000),
    "UT": (700000, 1200000),
    "VT": (600000, 1200000),
    "VS": (600000, 1100000),
    "VR": (600000, 1000000),
    "UU": (700000, 1100000),
}

# Province → Australian 6R square (user-facing names)
_PROVINCE_MAP = {
    "phuoc tuy":  "VU",
    "long khanh": "UT",
    "bien hoa":   "VT",
    "ben cat":    "VS",
    "binh duong": "VS",
    "tay ninh":   "VR",
    "vung tau":   "UU",
}


def awm_partial_to_latlon(
    partial_grid: str,
    square: str = None,
    province: str = None,
):
    """
    Convert a 6-digit AWM grid reference to WGS-84 latitude/longitude.

    Takes a truncated 6-digit grid reference from an Australian War
    Memorial Commander Log (e.g. "536567") and returns the equivalent
    WGS-84 decimal-degree coordinate.

    The conversion path is:

      1. Resolve the 100 km square (by province name, explicit square
         code, or default to VU — Phuoc Tuy).
      2. Build the absolute UTM easting/northing:
           UTM_E = square_baseline_E + first_3_digits × 100
           UTM_N = square_baseline_N + last_3_digits  × 100
      3. Transform UTM Zone 48 WGS-72 -> WGS-84 lat/lon.

    Parameters:
        partial_grid: 6-digit grid reference string.
            Three easting digits then three northing digits
            (e.g. "536567").  Each digit represents 100 m.
        square:       100 km square code from the Australian 6R maps
            (e.g. "VU", "UT", "VT").  Case-insensitive.
            Takes precedence over province.
        province:     Province name (e.g. "Phuoc Tuy", "Bien Hoa").
            Case-insensitive.  Ignored when square is given.

    Returns:
        tuple: (latitude, longitude) in decimal degrees on WGS-84.

    Raises:
        ValueError: if partial_grid is not 6 digits, or if the
            province / square is unrecognised.
    """
    partial_grid = partial_grid.strip().replace(" ", "")
    if len(partial_grid) != 6 or not partial_grid.isdigit():
        raise ValueError("Partial grid must be 6 digits like '536567'.")

    # ---- resolve 100 km square ------------------------------------------------
    if square:
        square = square.upper()
    elif province:
        square = _PROVINCE_MAP.get(province.lower())
        if square is None:
            raise ValueError(
                f"Unknown province: '{province}'. "
                f"Known: {list(_PROVINCE_MAP.keys())}"
            )
    else:
        square = "VU"   # default: Phuoc Tuy / Nui Dat operational area

    base_e, base_n = _SQUARE_BASELINES.get(square, (None, None))
    if base_e is None:
        raise ValueError(
            f"Unknown square: '{square}'. "
            f"Known: {list(_SQUARE_BASELINES.keys())}"
        )

    # ---- build absolute UTM and convert ---------------------------------------
    # 3 easting digits × 100 m each, 3 northing digits × 100 m each.
    easting  = base_e + int(partial_grid[:3]) * 100
    northing = base_n + int(partial_grid[3:]) * 100

    lon, lat = _TRANSFORMER.transform(easting, northing)
    return lat, lon


# ============================================================
# Quick self-test (run with:  python upm49p.py)
# ============================================================
if __name__ == "__main__":
    # "536567" — a patrol grid from the AWM Commander Diaries,
    # Phuoc Tuy province, August 1967 (Nui Dat / Long Tan area).
    lat, lon = awm_partial_to_latlon("536567", province="Phuoc Tuy")
    print(f"Partial  : 536567  (Phuoc Tuy)")
    print(f"Latitude : {lat:.6f} N")
    print(f"Longitude: {lon:.6f} E")
    print()
    print("Reference: Nui Dat base ~ 10.55 N, 107.25 E")
