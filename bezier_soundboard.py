"""Emit the 7-knot soundboard curve as cubic Bezier segments and write arc-
length-resampled stations ready for limacon lofting (clements47 style).

Design choices locked in up to this point:
  * Neck = straight line (we derive it from the Bezier-free top row).
  * Strings vertical, tops at the bridge pin, length L preserved.
  * Levers horizontally aligned. Soundboard absorbs all the length variation.
  * Soundboard curve is a 7-knot LSQUnivariateSpline fit through (L - L_on)(x).
  * Residual (on the lever row): RMS 3.34 mm, max 10.89 mm.

Outputs:
  clements40.json["sb_curve"] -- replaced with:
    method:           "7-knot LSQ cubic, levers horizontal"
    residual:         {rms_mm, max_mm}
    bezier_segments:  list of 6 cubic Beziers, each {P0,P1,P2,P3} in harp coords
    stations:         70 arc-length-resampled points along the curve, each
                        {s, x, z, tx, tz, dia, b}
                      ready for build_clements40.py to loft limacons perpendicular
                      to the local tangent (a = 2b, dia = 6b, linear taper from
                      bass 380 mm to treble 102 mm)

The curve's y coordinate is stored as grommet.z (mm). Convention: on.z = 0 for
every string (levers on a horizontal rail at z=0), off.z = L_on, grommet.z =
L_on - L. So grommet.z is negative (below the lever rail).
"""
import json
import math
from pathlib import Path

import numpy as np
from scipy.interpolate import LSQUnivariateSpline

ROOT = Path("/home/clementsj/projects/clements40")
SPEC_PATH = ROOT / "clements40.json"

N_TOTAL_KNOTS    = 7
N_STATIONS       = 70
BASS_DIA         = 380.0
TREBLE_DIA       = 102.0


def bezier_from_cubic(x0, x1, y0, y1, y0p, y1p):
    """Cubic polynomial y(x) on [x0, x1] with endpoint slopes y0p, y1p
    -> the four control points of the equivalent cubic Bezier in (x, y)."""
    h = x1 - x0
    P0 = (x0,         y0)
    P1 = (x0 + h/3,   y0 + y0p * h / 3)
    P2 = (x1 - h/3,   y1 - y1p * h / 3)
    P3 = (x1,         y1)
    return P0, P1, P2, P3


def main() -> None:
    data = json.loads(SPEC_PATH.read_text())
    strings = sorted(data["strings"], key=lambda s: s["grommet"]["x"])

    xs    = np.array([s["grommet"]["x"] for s in strings])
    Ls    = np.array([s["off"]["z"] - s["grommet"]["z"] for s in strings])
    L_ons = np.array([s["off"]["z"] - s["on"]["z"]      for s in strings])

    # Rewrite strings so on.z = 0 (lever rail), off.z = L_on, grommet.z = L_on - L
    for s, L, L_on in zip(strings, Ls, L_ons):
        s["on"]["z"]      = 0.0
        s["off"]["z"]     = round(L_on, 3)
        s["grommet"]["z"] = round(L_on - L, 3)

    # Soundboard height is grommet.z = L_on - L  (negative below lever rail)
    sb_y = L_ons - Ls

    # --- 7-knot LSQ cubic fit -----------------------------------------------
    knot_x = np.linspace(xs[0], xs[-1], N_TOTAL_KNOTS)[1:-1]  # interior only
    cs = LSQUnivariateSpline(xs, sb_y, knot_x, k=3)
    resid = cs(xs) - sb_y
    rms = float(np.sqrt(np.mean(resid * resid)))
    peak = float(np.max(np.abs(resid)))
    print(f"7-knot LSQ fit: RMS {rms:.2f} mm, max {peak:.2f} mm")

    # --- Bezier control points -----------------------------------------------
    full_knots = np.concatenate(([xs[0]], knot_x, [xs[-1]]))     # 7 total
    bezier_segments = []
    for k0, k1 in zip(full_knots[:-1], full_knots[1:]):
        y0, y1 = float(cs(k0)), float(cs(k1))
        y0p, y1p = float(cs.derivative()(k0)), float(cs.derivative()(k1))
        P0, P1, P2, P3 = bezier_from_cubic(k0, k1, y0, y1, y0p, y1p)
        bezier_segments.append({
            "P0": {"x": round(P0[0], 3), "z": round(P0[1], 3)},
            "P1": {"x": round(P1[0], 3), "z": round(P1[1], 3)},
            "P2": {"x": round(P2[0], 3), "z": round(P2[1], 3)},
            "P3": {"x": round(P3[0], 3), "z": round(P3[1], 3)},
        })
    print(f"{len(bezier_segments)} Bezier segments (cubic, C² at knots)")
    for i, seg in enumerate(bezier_segments):
        p0, p3 = seg["P0"], seg["P3"]
        print(f"  seg {i+1}: ({p0['x']:7.2f}, {p0['z']:+8.2f}) -> "
              f"({p3['x']:7.2f}, {p3['z']:+8.2f})")

    # --- Arc-length resampling for limacon lofting --------------------------
    # Dense sampling, cumulative arc length, then equal-s interpolation.
    dx = (xs[-1] - xs[0]) / 5000
    dense_x = np.linspace(xs[0], xs[-1], 5001)
    dense_z = cs(dense_x)
    dz = np.gradient(dense_z, dx)
    ds = np.sqrt(1.0 + dz * dz) * dx
    cum = np.concatenate(([0.0], np.cumsum(ds[:-1])))
    total_s = float(cum[-1] + ds[-1])

    s_target = np.linspace(0.0, total_s, N_STATIONS)
    x_stn = np.interp(s_target, cum, dense_x)
    z_stn = cs(x_stn)
    dz_stn = cs.derivative()(x_stn)
    tlen = np.sqrt(1.0 + dz_stn * dz_stn)
    tx = 1.0 / tlen
    tz = dz_stn / tlen

    # Diameter tapers along arc length, bass -> treble
    dia = BASS_DIA + (TREBLE_DIA - BASS_DIA) * (s_target / total_s)
    b   = dia / 6.0

    stations = [
        {"s": float(s_target[i]), "x": float(x_stn[i]), "z": float(z_stn[i]),
         "tx": float(tx[i]), "tz": float(tz[i]),
         "dia": float(dia[i]), "b": float(b[i])}
        for i in range(N_STATIONS)
    ]
    print(f"{N_STATIONS} stations along the soundboard, arc length {total_s:.1f} mm")

    data["sb_curve"] = {
        "method": "7-knot LSQ cubic, levers horizontal",
        "fit_input": "(L - L_on)(x), same shape as L(x) scaled by 0.944",
        "n_total_knots":   N_TOTAL_KNOTS,
        "interior_knots":  [float(k) for k in knot_x],
        "residual_mm":     {"rms": rms, "max": peak},
        "bezier_segments": bezier_segments,
        "arc_length_mm":   total_s,
        "diameter_bass":   BASS_DIA,
        "diameter_treble": TREBLE_DIA,
        "stations":        stations,
        "note": ("on.z = 0 at every string is the lever rail; off.z = L_on; "
                 "grommet.z = L_on - L (soundboard height, negative below rail). "
                 "build_clements40.py should loft limacons perpendicular to "
                 "(tx, tz) at each station, with flat top in +normal direction "
                 "and bulb in -normal, mirroring clements47's fix_soundbox.py."),
    }

    SPEC_PATH.write_text(json.dumps(data, indent=1) + "\n")
    print(f"wrote sb_curve + rewritten on.z/off.z/grommet.z to {SPEC_PATH}")


if __name__ == "__main__":
    main()
