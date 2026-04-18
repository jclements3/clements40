"""Generate erand47.json from ../clements47/clements47.json.

Reads all 47 Erard-style strings (c1 bass ... g7 treble), translates to the
same schema as clements40.json (used by make_svg.py / build_clements40.py),
applies the straight-neck convention (on.z = 0, off.z = L_on,
grommet.z = L_on - L), and computes a sb_curve (7-knot LSQ cubic) with 70
arc-length-resampled limacon stations.

Size differences from clements40:
  - 47 strings instead of 40 (C1..G7 full pedal-harp range)
  - Strings are longer -> soundbox is bigger: BASS_DIA 450 mm, TREBLE_DIA 120 mm

Usage:
  python3 extract_erand47.py
"""
import json
import math
from pathlib import Path

import numpy as np
from scipy.interpolate import LSQUnivariateSpline

SRC = Path("/home/clementsj/projects/clements47/clements47.json")
DST = Path("/home/clementsj/projects/clements40/erand47.json")

BASS_DIA         = 450.0          # soundbox bass diameter (larger harp)
TREBLE_DIA       = 120.0          # soundbox treble diameter
N_TOTAL_KNOTS    = 7              # soundboard fit knots
N_STATIONS       = 70             # arc-length-resampled limacon stations


def main() -> None:
    src = json.loads(SRC.read_text())
    src_st = src["st"]

    # Filter to real string entries (have o/f/n/s keys)
    raw = {k: v for k, v in src_st.items() if isinstance(v, dict) and "o" in v}

    # Nudge c1 to x = d1.x - 17.9 so adjacent bass strings don't collide
    # (the source data has c1 and d1 both at x=0, which breaks spline fits).
    if math.isclose(raw["c1"]["o"]["x"], raw["d1"]["o"]["x"], abs_tol=0.5):
        d1_x = raw["d1"]["o"]["x"]
        spacing = raw["e1"]["o"]["x"] - d1_x          # 17.9 mm typical
        new_c1_x = d1_x - spacing
        for pt_key in ("o", "f", "n", "s"):
            raw["c1"][pt_key]["x"] = new_c1_x

    # Shift so bass-most string sits at x=0
    all_x = [v["o"]["x"] for v in raw.values()]
    x_offset = min(all_x)

    def shifted(pt: dict) -> dict:
        return {"x": round(pt["x"] - x_offset, 3),
                "y": pt.get("y", 0),
                "z": round(pt.get("z", 0), 3)}

    # Build the 47-string list, sorted bass -> treble. Preserve the three
    # pedal positions per string: off (pedal up, flat, longest), on (pedal
    # middle, natural disc, medium), and sharp (pedal down, sharp disc,
    # shortest). f_off / f_on / f_sharp hold the corresponding frequencies.
    items = sorted(raw.items(), key=lambda kv: kv[1]["o"]["x"])
    strings = []
    for i, (note_key, s) in enumerate(items):
        harp_code = note_key.upper()                  # "C1", "D1", ..., "G7"
        strings.append({
            "n":       i + 1,                         # 1 at bass
            "harp":    harp_code,
            "sci":     harp_code,
            "grommet": shifted(s["o"]),
            "off":     shifted(s["f"]),
            "on":      shifted(s["n"]),
            "sharp":   shifted(s["s"]),
            "f_off":   s["f"].get("f"),
            "f_on":    s["n"].get("f"),
            "f_sharp": s["s"].get("f"),
            "d":       s.get("d"),
            "cd":      s.get("cd"),
            "wd":      s.get("wd"),
            "T":       s.get("T"),
            "mat":     {"brand": "Erard", "product": "Pedal",
                        "core": s.get("cm"), "wrap": s.get("wm")},
        })

    # --- Apply straight-neck convention: on.z = 0 (natural-disc rail),
    # off.z = L_on, grommet.z = L_on - L. Sharp shifts by -on.z_orig too, so
    # sharp.z is the signed offset from the natural rail (negative when the
    # sharp disc sits further from the pin than the natural disc).
    xs_arr    = np.array([s["grommet"]["x"] for s in strings])
    Ls_arr    = np.array([s["off"]["z"] - s["grommet"]["z"] for s in strings])
    L_ons_arr = np.array([s["off"]["z"] - s["on"]["z"]      for s in strings])
    for s, L, L_on in zip(strings, Ls_arr, L_ons_arr):
        on_z_orig    = s["on"]["z"]
        sharp_z_orig = s["sharp"]["z"]
        s["on"]["z"]      = 0.0
        s["off"]["z"]     = round(float(L_on), 3)
        s["grommet"]["z"] = round(float(L_on - L), 3)
        s["sharp"]["z"]   = round(float(sharp_z_orig - on_z_orig), 3)

    # --- sb_curve (7-knot LSQ cubic) + 70 arc-length stations ---------------
    sb_y = L_ons_arr - Ls_arr                         # grommet.z (CAD, negative)
    knot_x = np.linspace(xs_arr[0], xs_arr[-1], N_TOTAL_KNOTS)[1:-1]
    cs = LSQUnivariateSpline(xs_arr, sb_y, knot_x, k=3)
    resid = cs(xs_arr) - sb_y
    rms  = float(np.sqrt(np.mean(resid * resid)))
    peak = float(np.max(np.abs(resid)))
    print(f"{N_TOTAL_KNOTS}-knot LSQ fit: RMS {rms:.2f} mm, max {peak:.2f} mm")

    # Arc-length sampling
    dx = (xs_arr[-1] - xs_arr[0]) / 5000
    dense_x = np.linspace(xs_arr[0], xs_arr[-1], 5001)
    dense_z = cs(dense_x)
    dz      = np.gradient(dense_z, dx)
    ds      = np.sqrt(1.0 + dz * dz) * dx
    cum     = np.concatenate(([0.0], np.cumsum(ds[:-1])))
    total_s = float(cum[-1] + ds[-1])

    s_target = np.linspace(0.0, total_s, N_STATIONS)
    x_stn    = np.interp(s_target, cum, dense_x)
    z_stn    = cs(x_stn)
    dz_stn   = cs.derivative()(x_stn)
    tlen     = np.sqrt(1.0 + dz_stn * dz_stn)
    tx       = 1.0 / tlen
    tz       = dz_stn / tlen
    dia      = BASS_DIA + (TREBLE_DIA - BASS_DIA) * (s_target / total_s)
    b        = dia / 6.0

    stations = [
        {"s": float(s_target[i]), "x": float(x_stn[i]), "z": float(z_stn[i]),
         "tx": float(tx[i]), "tz": float(tz[i]),
         "dia": float(dia[i]), "b": float(b[i])}
        for i in range(N_STATIONS)
    ]

    out = {
        "meta": {"name": "Erand47",
                 "description": ("47-string Erard-style pedal harp model. "
                                 "Strings c1..g7 (C1 = 32.7 Hz bass, G7 = "
                                 "3322 Hz treble). Straight-neck convention "
                                 "with curved soundboard absorbing L(x).")},
        "units":   "mm",
        "strings": strings,
        "sb_curve": {
            "method":           "7-knot LSQ cubic, levers horizontal",
            "n_total_knots":    N_TOTAL_KNOTS,
            "interior_knots":   [float(k) for k in knot_x],
            "residual_mm":      {"rms": rms, "max": peak},
            "arc_length_mm":    total_s,
            "diameter_bass":    BASS_DIA,
            "diameter_treble":  TREBLE_DIA,
            "stations":         stations,
            "note": ("on.z = 0 at every string is the lever rail; "
                     "off.z = L_on; grommet.z = L_on - L."),
        },
    }
    DST.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {DST}  ({len(strings)} strings, arc length {total_s:.1f} mm)")


if __name__ == "__main__":
    main()
