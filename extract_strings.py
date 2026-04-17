"""Extract 40 strings from ../clements47/clements47.json for the Prelude-40 range.

L&H Prelude 40 string set (per Harp Connection catalog):
  1st octave E-F (strings 1-7):   Bow Brand Pedal Nylon
  2nd-4th octave (strings 8-28):  Sipario GutGold (gut)
  5th octave E-A (strings 29-33): Sipario GutGold (gut)
  5th octave G-F (strings 34-35): Bow Brand Pedal Concert Bass Wire
  6th octave E-A (strings 36-40): Bow Brand Pedal Concert Bass Wire

Harp-octave numbering (L&H): 1E = E7 (top), 6A = A1 (bottom).
Tuning: Eb major (strings labeled E/A/B voice Eb/Ab/Bb when lever off; lever on raises a semitone).
"""
import json
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "clements47" / "clements47.json"
DST = Path(__file__).resolve().parent / "clements40.json"

# Prelude string number -> (harp code, clements47 note key)
# String 1 = top (shortest, highest pitch), String 40 = bottom (longest, lowest)
ORDER = [
    ("1E", "e7"), ("1D", "d7"), ("1C", "c7"), ("1B", "b6"), ("1A", "a6"), ("1G", "g6"), ("1F", "f6"),
    ("2E", "e6"), ("2D", "d6"), ("2C", "c6"), ("2B", "b5"), ("2A", "a5"), ("2G", "g5"), ("2F", "f5"),
    ("3E", "e5"), ("3D", "d5"), ("3C", "c5"), ("3B", "b4"), ("3A", "a4"), ("3G", "g4"), ("3F", "f4"),
    ("4E", "e4"), ("4D", "d4"), ("4C", "c4"), ("4B", "b3"), ("4A", "a3"), ("4G", "g3"), ("4F", "f3"),
    ("5E", "e3"), ("5D", "d3"), ("5C", "c3"), ("5B", "b2"), ("5A", "a2"), ("5G", "g2"), ("5F", "f2"),
    ("6E", "e2"), ("6D", "d2"), ("6C", "c2"), ("6B", "b1"), ("6A", "a1"),
]
assert len(ORDER) == 40


def material(n):
    if n <= 7:
        return {"brand": "Bow Brand", "product": "Pedal Nylon", "core": "Nylon", "wrap": None}
    if n <= 33:
        return {"brand": "Sipario", "product": "GutGold", "core": "Gut", "wrap": None}
    return {"brand": "Bow Brand", "product": "Pedal Concert Bass Wire", "core": "Steel", "wrap": "Bronze"}


def main():
    src = json.loads(SRC.read_text())
    src_strings = src["st"]

    # Shift X so bass string (6A = a1) sits at x=0
    x_offset = src_strings["a1"]["o"]["x"]

    def shift(pt):
        return {"x": round(pt["x"] - x_offset, 3), "y": pt.get("y", 0), "z": round(pt.get("z", 0), 3)}

    strings = []
    for n, (harp_code, note) in enumerate(ORDER, start=1):
        s = src_strings[note]
        # In clements47 JSON, f.z is longest (pedal-harp flat). We reuse it as the
        # lever-off vibrating-length top on the lever harp (Eb tuning baseline).
        # n.z is shorter -- reused as the lever-on contact point (E natural).
        strings.append({
            "n": n,
            "harp": harp_code,           # L&H harp-octave code e.g. "1E"
            "sci": note.upper(),         # scientific pitch e.g. "E7"
            "grommet": shift(s["o"]),    # bottom anchor at soundboard
            "off":     shift(s["f"]),    # lever disengaged: top of vibrating length
            "on":      shift(s["n"]),    # lever engaged:    shortened top of vibrating
            "f_off":   s["f"]["f"],      # freq with lever off (Eb tuning -> plays labeled-flat)
            "f_on":    s["n"]["f"],      # freq with lever on  (plays labeled natural)
            "d":       s["d"],
            "cd":      s["cd"],
            "wd":      s["wd"],
            "T":       s["T"],           # tension N (per clements47 schema; natural position)
            "mat":     material(n),
        })

    soundbox_length = max(t["off"]["x"] for t in strings) + 40.0  # treble margin
    soundbox_bass_dia = 380.0   # mm, Prelude soundboard width at bass end (14-7/8")
    soundbox_treble_dia = 102.0  # mm, treble end (4")

    total_T_N = sum(t["T"] for t in strings)
    out = {
        "h": {"n": "CLEMENTS40", "d": "L&H Prelude-40 range lever harp (A1..E7), Eb tuning, harpcanada 3D levers"},
        "u": "mm",
        "ref_source": "derived from ../clements47/clements47.json with bass shifted to x=0",
        "sb": {
            "length": round(soundbox_length, 2),
            "bass_dia": soundbox_bass_dia,
            "treble_dia": soundbox_treble_dia,
            "limacon": {"a_over_b": 2.0, "dia_over_b": 6.0},
        },
        "tuning": {"base": "Eb major", "lever_semitones": 1},
        "strings": strings,
        "total_tension_N": round(total_T_N, 1),
        "total_tension_lbs": round(total_T_N * 0.224809, 1),
        "stringing": {
            "1-7":   "Bow Brand Pedal Nylon",
            "8-33":  "Sipario GutGold (gut)",
            "34-35": "Bow Brand Pedal Concert Bass Wire",
            "36-40": "Bow Brand Pedal Concert Bass Wire",
        },
    }
    DST.write_text(json.dumps(out, indent=1))
    print(f"Wrote {DST}: 40 strings, total tension {out['total_tension_N']} N = ~{out['total_tension_lbs']} lbs")
    print(f"  Bass string (6A=A1) at x=0, treble string (1E=E7) at x={strings[0]['off']['x']:.1f} mm")
    print(f"  Tallest pin z={max(t['off']['z'] for t in strings):.1f} mm")


if __name__ == "__main__":
    main()
