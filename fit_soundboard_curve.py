"""Fit a smoothing cubic spline through the 40 Prelude-40 pin positions.

Re-does the clements47 fix_soundbox.py analysis for the 40-string subset.
Produces a clamped cubic spline that passes exactly through 9 anchor strings
and approximately through the remaining 31. Along that curve we then
arc-length resample 70 limacon cross-section stations so the soundbox loft
rides the pin line rather than a flat X axis.

Writes the curve and stations into clements40.json under "sb_curve", and
prints pin-deviation metrics analogous to the clements47 report
(RMS 0.156 in, max 0.647 in for 47 strings).
"""
import json
import math
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline

ROOT = Path("/home/clementsj/projects/clements40")
SPEC_PATH = ROOT / "clements40.json"

# Nine anchors spread across the 40 strings -- same spacing strategy as
# fix_soundbox.py's ANCHOR_IDX = [0, 5, 11, 17, 23, 29, 35, 41, 46] for 47
# strings, rescaled for 40 strings:
ANCHOR_STRING_NUMS = [1, 6, 12, 18, 24, 30, 35, 38, 40]
N_STATIONS = 70
BASS_DIA = 380.0
TREBLE_DIA = 102.0


def least_squares_slope(xs, zs):
    m, _ = np.polyfit(xs, zs, 1)
    return float(m)


def main() -> None:
    data = json.loads(SPEC_PATH.read_text())
    # Bass-first ordering (string n=40 = 6A sits at smallest x)
    strings = sorted(data["strings"], key=lambda s: s["grommet"]["x"])

    xs = np.array([s["grommet"]["x"] for s in strings], dtype=float)
    zs = np.array([s["off"]["z"]     for s in strings], dtype=float)

    # Clamped endpoint slopes from least-squares regression of the outer 5
    slope_bass   = least_squares_slope(xs[:5],  zs[:5])
    slope_treble = least_squares_slope(xs[-5:], zs[-5:])

    # Anchors
    anchor_idx = [n - 1 for n in ANCHOR_STRING_NUMS]
    anchor_idx_sorted = sorted(anchor_idx, key=lambda i: xs[i])
    ax = xs[anchor_idx_sorted]
    az = zs[anchor_idx_sorted]
    cs = CubicSpline(ax, az, bc_type=((1, slope_bass), (1, slope_treble)))

    # Arc-length resample: dense integration then equal-s interpolation.
    x_dense = np.linspace(ax[0], ax[-1], 5001)
    dz_dense = cs(x_dense, 1)
    # arc length element = sqrt(1 + (dz/dx)^2) * dx
    dx = x_dense[1] - x_dense[0]
    ds = np.sqrt(1.0 + dz_dense * dz_dense) * dx
    s_cum = np.concatenate(([0.0], np.cumsum(ds[:-1])))
    total_s = float(s_cum[-1] + ds[-1])
    # build inverse: given s, find x
    s_target = np.linspace(0.0, total_s, N_STATIONS)
    x_stn = np.interp(s_target, s_cum, x_dense)
    z_stn = cs(x_stn)
    dz_stn = cs(x_stn, 1)
    # unit tangent (tx, tz) in X-Z plane
    tlen = np.sqrt(1.0 + dz_stn * dz_stn)
    tx = 1.0 / tlen
    tz = dz_stn / tlen

    # Diameter tapers along arc length, not along x, so the loft stays
    # proportioned when the curve deviates from the x-axis.
    dia = BASS_DIA + (TREBLE_DIA - BASS_DIA) * (s_target / total_s)
    b   = dia / 6.0

    # Pin deviation: original off.z vs curve z at that x
    z_curve_at_pin = cs(xs)
    dev = zs - z_curve_at_pin
    dev_rms = float(np.sqrt(np.mean(dev * dev)))
    dev_max = float(np.max(np.abs(dev)))

    data["sb_curve"] = {
        "anchors": [
            {"n": int(ANCHOR_STRING_NUMS[i]),
             "x": float(xs[n-1]), "z": float(zs[n-1])}
            for i, n in enumerate(ANCHOR_STRING_NUMS)
        ],
        "bc_slope_bass":   slope_bass,
        "bc_slope_treble": slope_treble,
        "arc_length_mm":   total_s,
        "diameter_bass":   BASS_DIA,
        "diameter_treble": TREBLE_DIA,
        "stations": [
            {"s": float(s_target[i]), "x": float(x_stn[i]), "z": float(z_stn[i]),
             "tx": float(tx[i]), "tz": float(tz[i]),
             "dia": float(dia[i]), "b": float(b[i])}
            for i in range(N_STATIONS)
        ],
        "pin_deviation": {
            "rms_mm": dev_rms,
            "max_mm": dev_max,
            "rms_in": dev_rms / 25.4,
            "max_in": dev_max / 25.4,
            "per_string": [
                {"n": int(strings[i]["n"]), "harp": strings[i]["harp"],
                 "dev_mm": float(dev[i])}
                for i in range(len(strings))
            ],
        },
    }

    SPEC_PATH.write_text(json.dumps(data, indent=1) + "\n")

    print(f"anchors (string #s):  {ANCHOR_STRING_NUMS}")
    print(f"endpoint slopes:      bass={slope_bass:+.4f}  treble={slope_treble:+.4f}")
    print(f"arc length along s:   {total_s:.1f} mm  ({total_s/25.4:.2f} in)")
    print(f"pin deviation vs cs:  RMS {dev_rms:.2f} mm  ({dev_rms/25.4:.3f} in)")
    print(f"                      max {dev_max:.2f} mm  ({dev_max/25.4:.3f} in)")
    # clements47 reference for comparison:
    print(f"(clements47 47-string: RMS 0.156 in, max 0.647 in)")


if __name__ == "__main__":
    main()
