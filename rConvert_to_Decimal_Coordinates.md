# Coordinate Format Reference

This document explains the four coordinate formats accepted by the Fatalities Editor,
when to use each, and how they relate to one another.  All examples use a single
physical location — the Australian Task Force area in Phước Tuy Province,
South Vietnam — expressed in each format.

**How the editor processes a `grid_reference` entry:**  When you type or paste
a coordinate into the field and click Update Record, the app scans the input
against formats §2 (MGRS), §3 (GPS DMS), and §4 (UTM).  The first matching
format wins; the coordinate is then normalised and converted to signed decimal
(§1) for storage.  If the input cannot be interpreted as any of these formats
the editor shows an error dialog listing the accepted forms.

---

## 1. Decimal Coordinates (modern standard)

### What it is

Two signed numbers separated by a comma:

```
latitude, longitude
```

This is the format used by **Google Maps, GPS devices, and virtually all modern
mapping software**.  There are no letters — the sign carries the hemisphere.

### Sign rules

| Sign | Latitude means | Longitude means |
|------|---------------|-----------------|
| `+` (or no sign) | North of the Equator | East of Greenwich |
| `−` (minus) | South of the Equator | West of Greenwich |

### Examples (same physical point)

```
10.6895, 107.3305        ← southern Vietnam (N, E  — both positive)
-33.8688, 151.2093       ← Sydney, Australia (S, E)
38.9072, -77.0369        ← Washington DC, USA  (N, W)
-23.5505, -46.6333       ← São Paulo, Brazil   (S, W)
```

### How the editor handles it

Paste any of these into the `grid_reference` field and the editor will:

1. Parse the two numbers
2. Apply the sign (or N/S/E/W letter if you include one)
3. Reject values outside −90…+90 (lat) or −180…+180 (lon)
4. Round to 5 decimal places (~1.1 m precision)
5. Store as `"lat, lon"` — e.g. `"10.6895, 107.3305"`

### Google Maps quick-check

```
https://www.google.com/maps?q=10.6895,107.3305
```

---

## 2. MGRS Grid Reference (Military Grid Reference System)

### What it is

MGRS is the coordinate system used by NATO and allied military forces.  It
builds on UTM (§4) but replaces the numeric easting/northing with an
alphanumeric shorthand designed for rapid radio communication.

### Anatomy of an MGRS coordinate

```
48P YS 426 694
│││ ││  │││ │││
│││ ││  │││ └── Northing digits (metres within the 100 km square)
│││ ││  └── Easting digits  (metres within the 100 km square)
│││ └── 100 km × 100 km grid square letter pair
││└── Latitude band letter (C–X, omitting I and O)
│└── UTM zone number (1–60)
└── Grid Zone Designator (GZD): zone + band
```

Think of it like a postal address:

| Part | Meaning | Example |
|------|---------|---------|
| `48P` | Region (UTM zone + latitude band) | "State" |
| `YS` | 100 km × 100 km city block | "City" |
| `426 694` | Metre offset within that block | "House number" |

### Precision (how many digits?)

| Total digits | East / North digits | Precision | Typical use |
|-------------|--------------------|-----------|-------------|
| 2 | 1 + 1 | 10 000 m | Large-area reference |
| 4 | 2 + 2 | 1 000 m | Brigade/division planning |
| **6** | **3 + 3** | **100 m** | **Combat after-action reports ← MOST COMMON** |
| 8 | 4 + 4 | 10 m | Patrol routes, FSB locations |
| 10 | 5 + 5 | 1 m | Survey-grade, minefield records |

### The 48Q → 48P transcription error

Many Vietnam War casualty records contain `48Q YS …`.  This is almost certainly
a **clerical error**, because:

- The 100 km grid square **YS** physically exists **only in zone 48P**
- 48P covers southern Vietnam (III & IV Corps: Saigon, Biên Hoà, Vũng Tàu,
  Mekong Delta)
- 48Q covers northern Vietnam (I & II Corps: Huế, Đà Nẵng, Central Highlands)

The Fatalities Editor **auto-corrects** `48Q` → `48P` for squares in the
southern set (YS, YT, XS, XT, and others).  No manual fix required.

### The SVN60 datum shift

During the Vietnam War, U.S. and allied maps used the **South Vietnam 1960
(SVN60)** datum — a local geodetic reference that does **not** align with
modern WGS84 GPS.

For the Bà Rịa–Vũng Tàu / Phước Tuy Province area the offset is approximately:

| Direction | Correction |
|-----------|-----------|
| Easting | **+205 m** |
| Northing | **+75 m** |

### Full worked example: `48Q YS 426 694` → Google Maps

```
1. INPUT
   48Q YS 426 694

2. ZONE CORRECTION
   48Q → 48P   (YS square exists only in 48P)

3. EXPAND DIGITS
   426 → 42 600 m Easting    (3 digits × 100 m precision)
   694 → 69 400 m Northing

4. APPLY SVN60 → WGS84 DATUM SHIFT
   Easting  42 600 + 205 = 42 805 m
   Northing 69 400 +  75 = 69 475 m

5. CONSTRUCT CORRECTED MGRS
   48P YS 428 695

6. CONVERT TO DECIMAL (via mgrs library)
   10.57183, 107.21889

7. GOOGLE MAPS
   https://www.google.com/maps?q=10.57183,107.21889
```

### How the editor handles it

The Fatalities Editor accepts any of these MGRS forms (case-insensitive,
spaces optional):

| Input | What happens |
|-------|-------------|
| `48Q YS 426 694` | Zone-corrected + datum-shifted → decimal |
| `48P YS 426 694` | Datum-shifted → decimal |
| `YS 426 694` | Zone inferred (48P) + datum-shifted → decimal |
| `YS426694` | Same as above (compact) |

The final decimal coordinate is stored in the JSON as `"lat, lon"`.

### Accuracy

| Source | Precision |
|--------|-----------|
| 6‑digit MGRS input | ±100 m |
| SVN60 → WGS84 datum shift | adds ~150–250 m correction |
| **Final location** | **accurate to within ~200 m** of the 1970 map point |

---

## 3. GPS Latitude / Longitude

### What it is

The classic **degrees-minutes-seconds (DMS)** or **degrees-decimal-minutes**
notation traditionally used on paper maps and nautical charts.

### Formats

| Name | Example | Notes |
|------|---------|-------|
| DMS with letters | `10° 41′ 22″ N, 107° 19′ 50″ E` | Degrees, minutes, seconds + hemisphere |
| DMS compact | `10 41 22 N, 107 19 50 E` | Same, without symbols |
| Decimal minutes | `10° 41.370′ N, 107° 19.830′ E` | Minutes with decimal fraction |
| Signed decimal degrees | `10.6895, 107.3305` | Actually just §1 above |

### Hemisphere letters

| Letter | Meaning |
|--------|---------|
| `N` | North of the Equator (positive latitude) |
| `S` | South of the Equator (negative latitude) |
| `E` | East of Greenwich (positive longitude) |
| `W` | West of Greenwich (negative longitude) |

### How the editor handles it

The editor **detects** DMS input (two or more number‑pair groups with optional
N/S/E/W letters) and accepts it, but **does not yet perform the
degrees‑minutes‑seconds → decimal conversion**.  For now, enter decimal
coordinates (§1) for automatic parsing.

### Quick conversion (mental)

```
1°  = 60′  = 3600″
1′  = 60″
1″  ≈ 30.9 m  (latitude, at any point)
1″  ≈ 30.9 m × cos(latitude)  (longitude)

Example:  10° 41′ 22″ N
  = 10 + 41/60 + 22/3600
  = 10 + 0.6833 + 0.0061
  = 10.6894° N
```

---

## 4. UTM Coordinates (Universal Transverse Mercator)

### What it is

UTM divides the Earth into **60 north‑south zones**, each 6° of longitude wide.
A UTM coordinate locates a point by:

```
Zone  Easting  Northing
```

- **Zone** — a number (1–60) plus a latitude band letter (optional)
- **Easting** — metres east of the zone's central meridian (always 6 digits)
- **Northing** — metres north of the Equator (7 digits in the southern
  hemisphere; the Equator is given a false northing of 10 000 000 m)

### Why UTM matters for Vietnam War records

Every MGRS coordinate (§2) is a shorthand for a UTM coordinate.  When you
convert an MGRS grid reference to a modern decimal coordinate, the pipeline is:

```
MGRS  →  UTM (SVN60 datum)  →  datum shift  →  UTM (WGS84)  →  decimal lat/lon
```

Understanding UTM is the bridge between the old grid and modern GPS.

### Example — the same physical point

| Datum | Zone | Easting | Northing |
|-------|------|---------|----------|
| SVN60 (wartime maps) | 48P | 42600 m | 69400 m |
| WGS84 (modern GPS) | 48P | 42805 m | 69475 m |

The difference (+205 m E, +75 m N) is the **SVN60 → WGS84 datum shift**.

### How the editor handles it

UTM input is **not yet parsed directly** — enter the equivalent MGRS (§2) or
decimal coordinates (§1) instead.

---

## Quick-reference table

| Format | Example | Copiable to Google Maps? |
|--------|---------|--------------------------|
| Decimal degrees | `10.6895, 107.3305` | ✅ Yes |
| Vietnam-era MGRS | `48Q YS 426 694` | ❌ No (editor converts automatically) |
| DMS with letters | `10° 41′ 22″ N, 107° 19′ 50″ E` | ❌ No (paste decimal) |
| UTM (WGS84) | `48P 42805 69475` | ❌ No (paste decimal) |
