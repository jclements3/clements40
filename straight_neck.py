"""Make the neck a STRAIGHT line and curve the soundboard to absorb string-length variation.

Design principle (per modern harp reference): the neck is a straight 2x4 beam,
not a fitted curve. Each string has a fixed vibrating length L (from the
Bow Brand / Sipario gauge + pitch + tension). To keep the neck straight while
respecting L, the soundboard grommet must sit at:

    grommet.z(x) = pin_straight(x) - L(x)

where pin_straight is the straight line connecting the bass pin (6A at x=0)
to the treble pin (1E at x=619). Because L(x) is not linear in x (string
length roughly doubles per octave, not per x-position), grommet.z(x) is a
curve -- the soundboard curves to absorb the nonlinearity.

Writes the new off.z and grommet.z values back into clements40.json and
rewrites the "sb_curve" section so that downstream scripts (make_svg.py,
build_clements40.py) pick up the new geometry. String vibrating lengths L
are preserved exactly.
"""
import json
import math
from pathlib import Path

ROOT = Path("/home/clementsj/projects/clements40")
SPEC_PATH = ROOT / "clements40.json"

N_SB_STATIONS = 70
BASS_DIA   = 380.0
TREBLE_DIA = 102.0


def main() -> None:
    data = json.loads(SPEC_PATH.read_text())
    strings = sorted(data["strings"], key=lambda s: s["grommet"]["x"])

    # Endpoints of the straight pin line: the current bass and treble pins
    bass   = strings[0]                    # 6A at x=0
    treble = strings[-1]                   # 1E at x=619
    x_bass,   z_bass_pin   = bass["grommet"]["x"],   bass["off"]["z"]
    x_treble, z_treble_pin = treble["grommet"]["x"], treble["off"]["z"]

    def pin_straight(x: float) -> float:
        t = (x - x_bass) / (x_treble - x_bass)
        return z_bass_pin + t * (z_treble_pin - z_bass_pin)

    # Rewrite each string's off.z (on the straight line) and grommet.z (= pin - L)
    for s in strings:
        x = s["grommet"]["x"]
        L = s["off"]["z"] - s["grommet"]["z"]           # preserve
        L_on = s["off"]["z"] - s["on"]["z"]             # preserve lever-on shortening
        new_off_z = pin_straight(x)
        new_grommet_z = new_off_z - L
        new_on_z = new_off_z - L_on
        s["off"]["z"]     = round(new_off_z, 3)
        s["grommet"]["z"] = round(new_grommet_z, 3)
        s["on"]["z"]      = round(new_on_z, 3)

    # Re-derive sb_curve stations: the soundboard curve is grommet.z(x) along
    # bass->treble, now a real physical curve. Arc-length resample 70 stations
    # between bass-most and treble-most grommets, with limacon cross-section
    # perpendicular to the local tangent.
    xs = [s["grommet"]["x"] for s in strings]
    zs = [s["grommet"]["z"] for s in strings]

    def interp(x, xs, ys):
        if x <= xs[0]:  return ys[0]
        if x >= xs[-1]: return ys[-1]
        for i in range(len(xs) - 1):
            if xs[i] <= x <= xs[i + 1]:
                t = (x - xs[i]) / (xs[i + 1] - xs[i])
                return ys[i] + t * (ys[i + 1] - ys[i])
        return ys[-1]

    # Dense sampling along the soundboard (grommet) curve for arc length
    dense_xs = [xs[0] + i * (xs[-1] - xs[0]) / 5000 for i in range(5001)]
    dense_zs = [interp(x, xs, zs) for x in dense_xs]
    # Cumulative arc length
    cum_s = [0.0]
    for i in range(1, len(dense_xs)):
        dx = dense_xs[i] - dense_xs[i - 1]
        dz = dense_zs[i] - dense_zs[i - 1]
        cum_s.append(cum_s[-1] + math.hypot(dx, dz))
    total_s = cum_s[-1]

    # Resample at 70 equal arc-length positions
    stations = []
    for i in range(N_SB_STATIONS):
        s_target = i * total_s / (N_SB_STATIONS - 1)
        # find dense index
        j = 0
        while j < len(cum_s) - 1 and cum_s[j + 1] < s_target:
            j += 1
        if j >= len(cum_s) - 1:
            x_st, z_st = dense_xs[-1], dense_zs[-1]
        else:
            span = cum_s[j + 1] - cum_s[j]
            t = (s_target - cum_s[j]) / span if span > 0 else 0
            x_st = dense_xs[j] + t * (dense_xs[j + 1] - dense_xs[j])
            z_st = dense_zs[j] + t * (dense_zs[j + 1] - dense_zs[j])
        # Tangent via finite difference on dense curve
        jj = min(j + 1, len(dense_xs) - 1)
        tx_raw = dense_xs[jj] - dense_xs[j]
        tz_raw = dense_zs[jj] - dense_zs[j]
        tlen = math.hypot(tx_raw, tz_raw) or 1.0
        tx = tx_raw / tlen
        tz = tz_raw / tlen
        # Diameter tapers linearly along arc length
        frac = s_target / total_s if total_s > 0 else 0.0
        dia = BASS_DIA + (TREBLE_DIA - BASS_DIA) * frac
        stations.append({
            "s": s_target, "x": x_st, "z": z_st,
            "tx": tx, "tz": tz,
            "dia": dia, "b": dia / 6.0,
        })

    data["sb_curve"] = {
        "method":           "straight neck + curved soundboard",
        "neck_endpoints":   [{"x": x_bass, "z": z_bass_pin},
                             {"x": x_treble, "z": z_treble_pin}],
        "arc_length_mm":    total_s,
        "diameter_bass":    BASS_DIA,
        "diameter_treble":  TREBLE_DIA,
        "stations":         stations,
        "soundboard_extremum": {
            "max_z": max(zs), "min_z": min(zs),
            "at_max": xs[zs.index(max(zs))],
            "at_min": xs[zs.index(min(zs))],
        },
    }

    SPEC_PATH.write_text(json.dumps(data, indent=1) + "\n")

    print(f"pin line: ({x_bass:.1f}, {z_bass_pin:.1f}) -> ({x_treble:.1f}, {z_treble_pin:.1f})  "
          f"(angle {math.degrees(math.atan2(z_treble_pin - z_bass_pin, x_treble - x_bass)):+.1f}°)")
    print(f"soundboard curve: arc length {total_s:.1f} mm")
    print(f"  grommet z range: {min(zs):+.1f} to {max(zs):+.1f} mm "
          f"(peak at x={xs[zs.index(max(zs))]:.0f})")
    print(f"  string lengths preserved")


if __name__ == "__main__":
    main()
