"""Update clements40.json string diameters + tensions to match the Prelude 40
'Gut 2nd Octave' factory stringing.

Diameters come from the public Camac gauge charts (hundredths of millimetre),
which are the closest published per-string gauges to Bow Brand / Sipario at
pedal tension for this exact note range. Lengths (grommet.z / off.z / on.z)
and x-spacing are NOT touched -- we keep the inherited pedal-harp geometry.

Sources:
  camac-harps.com/en/product/string-gauge-charts/
    - calibrenylon2025.jpg      (nylon, "For upper oct. harp with gut strings")
    - camac-gut-strings-gauge-2022.jpg (gut, Classique "Standard")
    - calibresfilees.jpg        (bass wire, "Pedal / Standard" overall OD)

Tension model:
  mu = rho * pi * (d/2)^2       kg/m
  T  = (2 * L * f_off)^2 * mu   newtons
where d is overall OD, L is vibrating length off the lever (metres), and
f_off is the pitch the string is actually tuned to with the lever OFF.

Eb-major base tuning:
  Strings A / B / E rest at Ab / Bb / Eb (one semitone flat of scientific).
  All other strings rest at their scientific natural.
  Engaging the lever raises pitch by one semitone.

rho values:
  Nylon : 1140 kg/m^3   (solid extruded nylon)
  Gut   : 1300 kg/m^3   (natural sheep gut / synthetic-gut sub)
  Wire  : 3500 kg/m^3   (effective density for silver-wound steel core --
                         chosen to land per-string bass tension in the
                         published 25-40 lbf-per-string range; real
                         construction is steel core + air-gapped silver
                         wrap, so rho_eff is well below solid steel).

Note: the 'f_off' / 'f_on' fields inherited from clements47 were wrong.
clements47 stored 'f' = sharpened pitch (Erard first-disc) and 'n' = natural.
extract_strings.py copied 'f'->f_off and 'n'->f_on, which is backwards for a
lever harp: on a Prelude 40 the lever OFF position is the base tuning, not
a sharpened one. This script rewrites both fields from sci + Eb-major rule.
"""
import json
import math
from pathlib import Path

ROOT = Path("/home/clementsj/projects/clements40")
SPEC_PATH = ROOT / "clements40.json"

RHO_NYLON = 1140.0
RHO_GUT   = 1300.0
RHO_WIRE  = 3500.0

SEMITONE = 2.0 ** (1.0 / 12.0)

# scientific-pitch frequency (Hz) of the natural for every sci note we use.
# Built procedurally: A4 = 440 Hz, each semitone = factor SEMITONE.
NOTE_SEMITONE_FROM_C = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def sci_freq(sci: str) -> float:
    """e.g. sci_freq('A1') = 55.0, sci_freq('C4') = 261.6256."""
    letter = sci[0]
    octave = int(sci[1:])
    midi = 12 * (octave + 1) + NOTE_SEMITONE_FROM_C[letter]
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def eb_major_rest_freq(sci: str) -> float:
    """Lever-OFF pitch: flatten A/B/E strings by one semitone (Eb-major rule)."""
    letter = sci[0]
    f_nat = sci_freq(sci)
    if letter in ("A", "B", "E"):
        return f_nat / SEMITONE
    return f_nat

# ---- Camac gauge lookup (mm), by harp-octave-letter name ----
# Keys use the same "1E".."6A" scheme as clements40.json["strings"][i]["harp"]

NYLON_D = {  # For upper oct. harp with gut strings (pedal with gut 2nd oct)
    "1E": 0.56, "1D": 0.58, "1C": 0.61, "1B": 0.64,
    "1A": 0.66, "1G": 0.69, "1F": 0.71,
}

GUT_D = {  # Camac Classique Standard (pedal gut)
    "2E": 0.70, "2D": 0.74, "2C": 0.78, "2B": 0.82,
    "2A": 0.86, "2G": 0.88, "2F": 0.90,
    "3E": 0.93, "3D": 0.96, "3C": 1.00, "3B": 1.05,
    "3A": 1.10, "3G": 1.15, "3F": 1.20,
    "4E": 1.24, "4D": 1.30, "4C": 1.40, "4B": 1.46,
    "4A": 1.59, "4G": 1.68, "4F": 1.77,
    "5E": 1.87, "5D": 1.97, "5C": 2.07, "5B": 2.18, "5A": 2.29,
}

WIRE_D = {  # Galli-Camac wire strings "Pedal / Standard" (overall OD)
    "5G": 1.60, "5F": 1.73,
    "6E": 1.82, "6D": 1.92, "6C": 2.00, "6B": 2.10, "6A": 2.20,
}


def classify(harp: str) -> str:
    """Return 'nylon' | 'gut' | 'wire' for the Gut-2nd-Oct Prelude 40 stringing."""
    if harp in NYLON_D:
        return "nylon"
    if harp in GUT_D:
        return "gut"
    if harp in WIRE_D:
        return "wire"
    raise KeyError(f"unknown harp note {harp!r}")


def lookup_d(harp: str) -> float:
    return (NYLON_D | GUT_D | WIRE_D)[harp]


def rho_for(kind: str) -> float:
    return {"nylon": RHO_NYLON, "gut": RHO_GUT, "wire": RHO_WIRE}[kind]


def mat_for(kind: str, harp: str) -> dict:
    if kind == "nylon":
        return {"brand": "Bow Brand", "product": "Pedal Nylon",
                "core": "Nylon", "wrap": None}
    if kind == "gut":
        return {"brand": "Sipario", "product": "GutGold Pedal",
                "core": "Gut", "wrap": None}
    return {"brand": "Bow Brand", "product": "Pedal Concert Bass Wire",
            "core": "Steel", "wrap": "Silver-plated"}


def tension_N(length_mm: float, freq_hz: float, d_mm: float, rho: float) -> float:
    L = length_mm / 1000.0
    d = d_mm / 1000.0
    mu = rho * math.pi * (d / 2.0) ** 2
    return (2.0 * L * freq_hz) ** 2 * mu


def main() -> None:
    data = json.loads(SPEC_PATH.read_text())
    strings = data["strings"]

    per_section = {"nylon": 0.0, "gut": 0.0, "wire": 0.0}
    per_count   = {"nylon": 0,   "gut": 0,   "wire": 0}

    for s in strings:
        harp = s["harp"]
        kind = classify(harp)
        d = lookup_d(harp)
        rho = rho_for(kind)

        L_mm = s["off"]["z"] - s["grommet"]["z"]
        f_off = eb_major_rest_freq(s["sci"])
        f_on  = f_off * SEMITONE
        T = tension_N(L_mm, f_off, d, rho)
        s["f_off"] = round(f_off, 2)
        s["f_on"]  = round(f_on, 2)

        # Preserve cd/wd ratios for wire strings; for solid strings cd=d, wd=0.
        if kind == "wire":
            # Existing ratio from clements47 data -- keep structure consistent.
            prev_d  = s.get("d",  d) or d
            prev_cd = s.get("cd", 0.3 * d)
            prev_wd = s.get("wd", 0.5 * (d - prev_cd))
            ratio_cd = (prev_cd / prev_d) if prev_d else 0.35
            cd = round(d * ratio_cd, 3)
            wd = round((d - cd) / 2.0, 3)
        else:
            cd = d
            wd = 0.0

        s["d"]   = d
        s["cd"]  = cd
        s["wd"]  = wd
        s["T"]   = round(T, 2)
        s["mat"] = mat_for(kind, harp)

        per_section[kind] += T
        per_count[kind]   += 1

    # Record provenance so we remember where the gauges came from.
    data["gauge_source"] = {
        "nylon": "Camac 'For upper oct. harp with gut strings' (2025 chart)",
        "gut":   "Camac Classique Standard (2022 chart)",
        "wire":  "Galli-Camac Pedal/Standard (overall OD)",
        "note":  ("Camac gauges used as proxy for Bow Brand Pedal Nylon / "
                  "Sipario GutGold / Bow Brand Pedal Concert Bass Wire; "
                  "gauges at these pitches are interchangeable at pedal tension."),
        "rho_kg_m3": {"nylon": RHO_NYLON, "gut": RHO_GUT, "wire_effective": RHO_WIRE},
    }

    SPEC_PATH.write_text(json.dumps(data, indent=1) + "\n")

    total = sum(per_section.values())
    print("=== per-section totals ===")
    for kind in ("nylon", "gut", "wire"):
        n, T = per_count[kind], per_section[kind]
        print(f"  {kind:>5}: {n:2d} strings   {T:7.1f} N   ({T/4.4482:6.1f} lbf)")
    print(f"  TOTAL: {len(strings)} strings  {total:7.1f} N   ({total/4.4482:6.1f} lbf)")
    target_N = 5295.0
    pct = 100.0 * total / target_N
    print(f"  target (CLAUDE.md): {target_N:.0f} N   --> actual is {pct:.1f}% of target")


if __name__ == "__main__":
    main()
