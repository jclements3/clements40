"""Generate Clements40.svg -- vertical strings with cubic-spline soundboard curve.

Approach (mirrors clements47 fix_soundbox.py logic, applied to clements40):
  - Pick 9 anchor strings spaced across the 40.
  - Fit a clamped cubic spline through (x_anchor, L_anchor) pairs, with
    endpoint slopes from least-squares regression of the outermost 5
    strings on each side. This is the SOUNDBOARD curve -- maximally smooth
    and passes exactly through the anchors.
  - For every string, its bottom rests on the soundboard curve at
    y_bottom = top_pad + SB(x). Its top is y_top = y_bottom - L(x).
    At anchors the top lands on the flat top_pad line; elsewhere the top
    deviates slightly -- this residual is the "tuning pin jaggedness".
  - A small circle to the right of each string top, tangent to the string,
    shows the tuning pin position.
"""
import json
from pathlib import Path

import numpy as np
from scipy.interpolate import LSQUnivariateSpline, UnivariateSpline

ROOT = Path("/home/clementsj/projects/clements40")
SPEC_PATH = ROOT / "clements40.json"
SVG_PATH  = ROOT / "Clements40.svg"

PIN_DIA   = 7.0
LEVER_DIA = 6.0

# Soundboard extension connects to the neck-bottom horizontal this far past
# string 1 (E7, treble). NECK_DROP is derived from this and the soundboard
# slope so the tangent extension reaches the horizontal at exactly this x offset.
SOUNDBOARD_CONNECT_INCHES = 1.0

# 7-knot LSQ cubic -- matches bezier_soundboard.py / sb_curve in clements40.json.
N_TOTAL_KNOTS = 7

# Alignment mode: "pins" = bridge pins horizontal, levers curved below
#                "levers" = levers horizontal, bridge pins curved above
ALIGN_MODE = "levers"


def main() -> None:
    data = json.loads(SPEC_PATH.read_text())
    strings = sorted(data["strings"], key=lambda s: s["grommet"]["x"])

    xs    = np.array([s["grommet"]["x"] for s in strings], dtype=float)
    Ls    = np.array([s["off"]["z"] - s["grommet"]["z"] for s in strings], dtype=float)
    L_ons = np.array([s["off"]["z"] - s["on"]["z"]      for s in strings], dtype=float)
    # Fit target -- what we smooth depends on ALIGN_MODE.
    # "pins"   : align pin tops, soundboard-to-pin distance = L  (fit to L)
    # "levers" : align levers,   soundboard-to-lever distance = L - L_on (fit to that)
    fit_y = Ls if ALIGN_MODE == "pins" else (Ls - L_ons)

    # 7-knot LSQ cubic: interior knots evenly spaced in x
    knot_x = np.linspace(xs[0], xs[-1], N_TOTAL_KNOTS)[1:-1]
    cs = LSQUnivariateSpline(xs, fit_y, knot_x, k=3)
    sb_at_string = cs(xs)
    residual = sb_at_string - fit_y
    rms  = float(np.sqrt(np.mean(residual * residual)))
    peak = float(np.max(np.abs(residual)))
    row = "pin row" if ALIGN_MODE == "pins" else "lever row"
    print(f"[align={ALIGN_MODE}]  {N_TOTAL_KNOTS}-knot LSQ cubic  "
          f"residual on {row}: "
          f"RMS {rms:.2f} mm ({rms/25.4:.3f}\"), "
          f"max {peak:.2f} mm ({peak/25.4:.3f}\")")

    # --- Treble tangent extension (string 1 = E7 side) of the soundBOARD ---
    # Derive NECK_DROP so the soundboard tangent hits the horizontal exactly
    # SOUNDBOARD_CONNECT_INCHES past string 1.
    x_treb = float(xs[-1])
    y_treb = float(cs(x_treb))
    slope_treb = float(cs.derivative()(x_treb))
    dist_past_string1 = SOUNDBOARD_CONNECT_INCHES * 25.4
    NECK_DROP = y_treb + slope_treb * dist_past_string1
    x_tangent_hit = x_treb + dist_past_string1
    import math as _m
    angle_treb = _m.degrees(_m.atan(abs(slope_treb)))

    # --- Treble tangent extension of the soundBACK ---
    # Soundback position at the treble end = treble bulge point.
    tlen_t = (1.0 + slope_treb * slope_treb) ** 0.5
    tx_t = 1.0 / tlen_t
    tz_t = slope_treb / tlen_t
    b_treb = 102.0 / 6.0
    bx_treble = x_treb - 3.0 * b_treb * tz_t
    bz_treble = y_treb + 3.0 * b_treb * tx_t
    # Place the soundback's horizontal-hit point exactly 3*b_treble to the
    # right of the soundboard's hit point -- same as the perpendicular
    # string-1 offset between soundboard and soundback.
    x_sbk_hit = x_tangent_hit + 3.0 * b_treb
    # Bass end of the soundback for the horizontal base line.
    slope_bass = float(cs.derivative()(xs[0]))
    y_bass = float(cs(xs[0]))
    tlen_b = (1.0 + slope_bass * slope_bass) ** 0.5
    b_bass = 380.0 / 6.0
    bx_bass = xs[0] - 3.0 * b_bass * (slope_bass / tlen_b)
    bz_bass = y_bass + 3.0 * b_bass * (1.0 / tlen_b)

    # --- SVG layout ---
    pad = 30.0
    x_min = min(xs.min(), -40.0 - 45.0 - 45.0/2.0, bx_bass) - pad  # include bowed column
    x_max = max(xs.max() + PIN_DIA, x_tangent_hit, x_sbk_hit) + pad
    top_pad = pad
    # Bottoms evaluated along a dense grid to find total drawable area
    dense_x = np.linspace(xs.min(), xs.max(), 400)
    dense_sb = cs(dense_x)
    # Also need room for the bulge curve, which sits below the soundboard
    # at max offset 3*b in +SB_y direction. Compute bulge SB_y max.
    dense_dz = cs.derivative()(dense_x)
    _tlen = np.sqrt(1.0 + dense_dz * dense_dz)
    _tx = 1.0 / _tlen
    _dense_ds = _tlen * (dense_x[1] - dense_x[0])
    _cum = np.concatenate(([0.0], np.cumsum(_dense_ds[:-1])))
    _frac = _cum / _cum[-1]
    sb_cfg = data.get("sb_curve") or {}
    _bass_dia = sb_cfg.get("diameter_bass", 380.0)
    _trb_dia  = sb_cfg.get("diameter_treble", 102.0)
    _dense_b = (_bass_dia + (_trb_dia - _bass_dia) * _frac) / 6.0
    bulge_sb_y_max = float((dense_sb + 3.0 * _dense_b * _tx).max())

    # Lowest svg y needed (highest point in image) -- string tops, neck top,
    # AND the neck-top Bezier control handle P1 which can sit several hundred
    # mm above the rail.
    _wall_above = 10.0
    _neck_top_sby = -float(L_ons.max()) - PIN_DIA / 2.0 - _wall_above
    # Rough estimate of the highest neck-top point: pin arch peaks at the
    # bass pin around SB_y ≈ -80, and the bass-bridge column-tangent handle
    # BB1 might push slightly higher. Leave 150 mm of margin.
    _p1_sby_estimate = NECK_DROP - 200.0
    y_top_min = min(
        float((top_pad + sb_at_string - Ls).min()),
        top_pad + _neck_top_sby,
        top_pad + _p1_sby_estimate,
    )
    y_bot_max = max(float((top_pad + dense_sb).max()),
                    top_pad + bulge_sb_y_max)

    w = x_max - x_min
    h = y_bot_max + pad
    # Shift everything down if top goes negative
    y_offset = max(0.0, pad - y_top_min)
    h += y_offset

    def X(x): return x - x_min

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {w:.2f} {h:.2f}" '
        f'width="{w*0.8:.0f}" height="{h*0.8:.0f}">'
    )

    # Soundboard curve (dashed) -- connects the string bottoms.
    # Also extend at the bass end along the tangent line until it hits the
    # column's inner edge.
    # (Column geometry is computed below, but we can pre-compute the intersection
    # here using the column parameters we'll use later.)
    COLUMN_OD = 45.0
    COLUMN_X  = -40.0
    _dx = COLUMN_OD / 2.0
    _inner_peak_x = float(xs[0]) - 1.5 * 25.4
    _sag_col      = COLUMN_X - (_inner_peak_x - _dx)
    _col_top_sby  = NECK_DROP
    _col_bot_sby  = float(bz_bass)
    _chord_col    = _col_bot_sby - _col_top_sby
    _R_col        = (_chord_col * _chord_col) / (8.0 * _sag_col) + _sag_col / 2.0
    _col_center_y = (_col_top_sby + _col_bot_sby) / 2.0
    _inner_chord_x = COLUMN_X + _dx
    _col_center_x_inner = _inner_chord_x + (_R_col - _sag_col)

    # Tangent at soundboard bass end
    _slope_bass = float(cs.derivative()(xs[0]))   # dSB/dx at bass end
    _y_bass     = float(cs(xs[0]))                # SB_y at bass end
    # Solve tangent-line vs inner-arc intersection.
    # y = _y_bass + _slope_bass * (x - xs[0])
    # (x - _col_center_x_inner)^2 + (y - _col_center_y)^2 = _R_col^2
    import math as _m2
    _x0 = float(xs[0])
    _a = 1.0 + _slope_bass * _slope_bass
    _yrel0 = _y_bass - _col_center_y
    _b = 2.0 * ((_x0 - _col_center_x_inner) + _slope_bass * (_yrel0 - _slope_bass * _x0))
    _c = (_x0 - _col_center_x_inner) ** 2 + (_yrel0 - _slope_bass * _x0) ** 2 - _R_col ** 2
    _disc = _b * _b - 4.0 * _a * _c
    if _disc > 0:
        _sqd = _m2.sqrt(_disc)
        _x_hit_a = (-_b - _sqd) / (2.0 * _a)
        _x_hit_b = (-_b + _sqd) / (2.0 * _a)
        # Choose root with x closer to 0 (the bass end), i.e. the one within
        # a few hundred mm of the soundboard's bass end.
        _candidates = [x for x in (_x_hit_a, _x_hit_b)
                       if abs(x - _x0) < 200.0 and x < _x0 + 5.0]
        if _candidates:
            _x_hit = _candidates[0] if abs(_candidates[0] - _x0) < abs(_candidates[-1] - _x0) else _candidates[-1]
            _y_hit = _y_bass + _slope_bass * (_x_hit - _x0)
            ext_pts = f"{X(_x_hit):.2f},{top_pad + _y_hit + y_offset:.2f} "
        else:
            ext_pts = ""
    else:
        ext_pts = ""
    curve_pts = ext_pts + " ".join(f"{X(x):.2f},{top_pad + cs(x) + y_offset:.2f}"
                                   for x in dense_x)
    parts.append(
        f'<polyline points="{curve_pts}" fill="none" stroke="#7a2a2a" '
        f'stroke-width="0.8" stroke-dasharray="4,3"/>'
    )

    # Bulge-point curve: offset 3b perpendicular to the local tangent, on the
    # away-from-strings side (CW rotation of the tangent in X-Z).
    # At each dense x, normal_cw = (tz, -tx) where (tx, tz) = unit tangent.
    sb = data.get("sb_curve") or {}
    bass_dia   = sb.get("diameter_bass", 380.0)
    treble_dia = sb.get("diameter_treble", 102.0)
    arc_len = sb.get("arc_length_mm", None)
    dense_dz = cs.derivative()(dense_x)
    tlen = np.sqrt(1.0 + dense_dz * dense_dz)
    tx = 1.0 / tlen
    tz = dense_dz / tlen
    # Arc-length fraction along the curve at each dense x -> taper diameter
    dense_ds = np.sqrt(1.0 + dense_dz * dense_dz) * (dense_x[1] - dense_x[0])
    s_cum = np.concatenate(([0.0], np.cumsum(dense_ds[:-1])))
    frac = s_cum / s_cum[-1]
    dense_dia = bass_dia + (treble_dia - bass_dia) * frac
    dense_b = dense_dia / 6.0
    # Bulge offset: perpendicular to tangent, on the AWAY-from-strings side.
    # In (x, SB_y) space with SB decreasing (dSB/dx < 0), the outward normal
    # is (-tz, +tx) -- i.e. bulge sits at larger x and larger SB_y (deeper).
    bulge_x = dense_x - 3.0 * dense_b * tz
    bulge_z = cs(dense_x) + 3.0 * dense_b * tx
    bulge_pts = " ".join(f"{X(x):.2f},{top_pad + z + y_offset:.2f}"
                         for x, z in zip(bulge_x, bulge_z))
    parts.append(
        f'<polyline points="{bulge_pts}" fill="none" stroke="#1a5" '
        f'stroke-width="1.2"/>'
    )

    # --- Soundback treble extension as a cubic Bezier: starts tangent to the
    # soundback, arrives horizontally at SB_y=0. Solid to match the soundback.
    yBk  = top_pad + bz_treble + y_offset
    yHk  = top_pad + NECK_DROP + y_offset
    h_bk = ((x_sbk_hit - bx_treble)**2 + (bz_treble - NECK_DROP)**2) ** 0.5 / 3.0
    bk_p0x = X(bx_treble);   bk_p0y = yBk
    bk_p3x = X(x_sbk_hit);   bk_p3y = yHk
    bk_p1x = bk_p0x + h_bk * tx_t
    bk_p1y = bk_p0y + h_bk * tz_t
    # Vertical takeoff at P3 (straight up into the neck) -- P2 directly below P3.
    bk_p2x = bk_p3x
    bk_p2y = bk_p3y + h_bk
    parts.append(
        f'<path d="M {bk_p0x:.2f},{bk_p0y:.2f} '
        f'C {bk_p1x:.2f},{bk_p1y:.2f} {bk_p2x:.2f},{bk_p2y:.2f} '
        f'{bk_p3x:.2f},{bk_p3y:.2f}" fill="none" '
        f'stroke="#1a5" stroke-width="1.2"/>'
    )
    parts.append(
        f'<circle cx="{bk_p3x:.2f}" cy="{bk_p3y:.2f}" r="3" fill="#1a5"/>'
    )

    # --- Bass base as a cubic Bezier: starts tangent to the soundback (backward
    # direction) at the bass end, arrives horizontally at the column. Smooth
    # continuation of the soundback curve into a horizontal base toward the column.
    COLUMN_X = -40.0
    base_y = top_pad + bz_bass + y_offset
    base_p0x = X(bx_bass);    base_p0y = base_y
    base_p3x = X(COLUMN_X);   base_p3y = base_y
    # Both base-line control points horizontal: the base is a straight
    # horizontal segment from the soundback bass end to the column.
    h_base = (bx_bass - COLUMN_X) / 3.0
    base_p1x = base_p0x - h_base
    base_p1y = base_p0y
    base_p2x = base_p3x + h_base
    base_p2y = base_p3y
    parts.append(
        f'<path d="M {base_p0x:.2f},{base_p0y:.2f} '
        f'C {base_p1x:.2f},{base_p1y:.2f} {base_p2x:.2f},{base_p2y:.2f} '
        f'{base_p3x:.2f},{base_p3y:.2f}" fill="none" '
        f'stroke="#1a5" stroke-width="1.2"/>'
    )
    parts.append(
        f'<circle cx="{base_p0x:.2f}" cy="{base_p0y:.2f}" r="3" fill="#1a5"/>'
    )
    # also dots at each of the 70 limacon stations, on the bulge curve.
    # stations are stored in (x, grommet.z) coords where z = L_on - L (negative);
    # make_svg works in SB_y = L - L_on (positive). Flip the z sign and flip
    # tz sign to work in the SB_y frame, then the outward normal is (-tz, +tx).
    if "stations" in sb:
        for st in sb["stations"]:
            sb_y = -st["z"]
            tz_sby = -st["tz"]     # tangent z-component in SB_y frame
            tx_sby =  st["tx"]
            bx      = st["x"] - 3.0 * st["b"] * tz_sby
            bz_sb_y = sb_y     + 3.0 * st["b"] * tx_sby
            parts.append(
                f'<circle cx="{X(bx):.2f}" cy="{top_pad + bz_sb_y + y_offset:.2f}" '
                f'r="1.2" fill="#1a5"/>'
            )


    # Strings + tuning pins (tangent to string top) + lever dots (tangent at on.z)
    # In "pins" mode: y_bottom = top_pad + SB(x); y_top = y_bottom - L; y_lever = y_top + L_on
    # In "levers" mode: y_bottom = (lever_row) + SB(x); y_lever = y_bottom - (L - L_on); y_top = y_lever - L_on
    r_pin   = PIN_DIA   / 2.0
    r_lever = LEVER_DIA / 2.0
    for i, s in enumerate(strings):
        x = X(xs[i])
        if ALIGN_MODE == "pins":
            y_bottom = top_pad + sb_at_string[i] + y_offset
            y_top    = y_bottom - Ls[i]
            y_lever  = y_top + L_ons[i]
        else:  # "levers"
            y_bottom = top_pad + sb_at_string[i] + y_offset
            y_lever  = y_bottom - (Ls[i] - L_ons[i])
            y_top    = y_lever - L_ons[i]
        # Color-code C strings red, F strings blue (traditional harp marking).
        note_letter = s["harp"][-1]   # e.g. "4C" -> "C", "6A" -> "A"
        if note_letter == "C":
            string_stroke, string_width = "#c00", 0.9
        elif note_letter == "F":
            string_stroke, string_width = "#00c", 0.9
        else:
            string_stroke, string_width = "#111", 0.6
        parts.append(
            f'<line x1="{x:.2f}" y1="{y_top:.2f}" '
            f'x2="{x:.2f}" y2="{y_bottom:.2f}" '
            f'stroke="{string_stroke}" stroke-width="{string_width}"/>'
        )
        parts.append(
            f'<circle cx="{x + r_pin:.2f}" cy="{y_top:.2f}" r="{r_pin:.2f}" '
            f'fill="#bfbfbf" stroke="#555" stroke-width="0.4"/>'
        )
        parts.append(
            f'<circle cx="{x + r_lever:.2f}" cy="{y_lever:.2f}" r="{r_lever:.2f}" '
            f'fill="#3050a0" stroke="#0b1a40" stroke-width="0.4"/>'
        )

    # --- Column: uniform 45 mm wide, bowed out to the left as a SIMPLE
    # CIRCULAR ARCH (not a spline or bezier). Both edges are arcs of the
    # same radius, parallel-offset by 45 mm so the column width is uniform.
    # Arc depth is sized so the inner edge's apex sits 1.5" from string 40.
    wall_above    = 10.0
    COLUMN_OD     = 45.0
    COLUMN_X      = -40.0
    col_top_sby   = NECK_DROP
    col_bot_sby   = float(bz_bass)
    dx            = COLUMN_OD / 2.0
    INNER_PEAK_DIST_FROM_STR40_IN = 1.5
    inner_peak_x   = float(xs[0]) - INNER_PEAK_DIST_FROM_STR40_IN * 25.4
    # Axis apex x = inner peak - dx (inner edge is +dx from axis).
    axis_apex_x     = inner_peak_x - dx
    sag             = COLUMN_X - axis_apex_x       # how far left the axis bows
    chord_len       = col_bot_sby - col_top_sby
    arc_R           = (chord_len * chord_len) / (8.0 * sag) + sag / 2.0
    p_top_y         = col_top_sby
    p_bot_y         = col_bot_sby
    col_left_x_top  = COLUMN_X - dx
    col_right_x_top = COLUMN_X + dx

    def pt(p): return f"{X(p[0]):.2f},{top_pad + p[1] + y_offset:.2f}"
    # Column silhouette: right arc down, base across, left arc up (reversed).
    col_path = (
        f"M {pt((col_right_x_top, p_top_y))} "
        f"A {arc_R:.2f} {arc_R:.2f} 0 0 0 {pt((col_right_x_top, p_bot_y))} "
        f"L {pt((col_left_x_top, p_bot_y))} "
        f"A {arc_R:.2f} {arc_R:.2f} 0 0 1 {pt((col_left_x_top, p_top_y))} Z"
    )
    parts.append(
        f'<path d="{col_path}" fill="#b08a55" fill-opacity="0.42" '
        f'stroke="#3a2a10" stroke-width="0.8"/>'
    )

    # Apex of the left edge arc (for labeling)
    apex_axis_x = COLUMN_X - sag
    sby_str40_center = (col_top_sby + col_bot_sby) / 2.0

    # Neck: top is a cubic Bezier arch from the column's outer-edge top
    # (tangent-continuous with the column) over the tuning pins and back to
    # the soundback vertical takeoff. Bottom is horizontal at NECK_DROP.
    neck_top_sby = -float(L_ons.max()) - PIN_DIA / 2.0 - wall_above
    neck_left_x  = COLUMN_X - dx
    neck_right_x = float(x_sbk_hit)

    # Tangent direction from column's outer-edge top, heading UP out of the
    # column. Column outer chord at x = col_left_x_top; center to the right
    # at (col_left_x_top + (_R_col - _sag_col), (col_top_sby + col_bot_sby)/2).
    col_center_x_outer = col_left_x_top + (arc_R - sag)
    col_center_y       = (col_top_sby + col_bot_sby) / 2.0
    # Radius vector at top of column, rotate 90° CCW to get tangent
    rx = col_left_x_top - col_center_x_outer
    ry = col_top_sby    - col_center_y
    rlen = (rx*rx + ry*ry) ** 0.5
    # Column arc traverses from top CCW (visually CW in SVG y-flipped) to
    # bottom. Tangent going INTO the arc at top is rotate 90° CW of radius.
    tang_in_x =  ry / rlen
    tang_in_y = -rx / rlen
    # Tangent going OUT of the column (ABOVE the top) is the opposite:
    col_tan_up_x = -tang_in_x
    col_tan_up_y = -tang_in_y   # nearly (0, -1) pointing up

    # Neck top follows the smoothed pin arch: y_neck_top(x) = -0.0595·cs(x) - wall
    # (same smoothing trick as the soundboard, since L_on ∝ L).
    # The neck consists of three pieces:
    #   1) Bass bridge  : P0 (column top)  -> BB3 (pin arch bass end)
    #   2) Pin arch     : polyline from BB3 along -0.0595·cs(x) - wall to TB0
    #   3) Treble bridge: TB0 (pin arch treble end) -> TB3 (soundback takeoff)
    wall = PIN_DIA / 2.0 + 10.0    # 10 mm wall above each pin's top edge (nominal)
    pin_arch_scale = -0.0595       # L_on / (L - L_on)  i.e. L_on = scale · cs
    # M (= bass-end anchor of pin-arch follower) sits over string 33's pin
    # with extra clearance so the wood does not crack around the heavy bass
    # transition pins.
    prelude_string_at_M = 28                   # Prelude numbering: string 28 = 4F (F below middle C, same octave)
    M_pin_idx = 40 - prelude_string_at_M       # sort-by-x index (bass-first) = 16
    EXTRA_WALL_AT_M = 20.0                     # same extra mm above this pin as before
    arch_x_lo = float(xs[M_pin_idx])
    arch_y_lo = float(pin_arch_scale * sb_at_string[M_pin_idx] - wall - EXTRA_WALL_AT_M)
    # The pin-arch polyline runs from M to the treble-most pin.
    arch_xs = xs[M_pin_idx:]
    arch_ys = pin_arch_scale * sb_at_string[M_pin_idx:] - wall
    arch_x_hi = float(xs[-1])
    arch_y_hi = float(arch_ys[-1])

    # Slope of the pin arch at each endpoint.
    slope_arch_lo = pin_arch_scale * float(cs.derivative()(arch_x_lo))
    slope_arch_hi = pin_arch_scale * float(cs.derivative()(arch_x_hi))
    tlen_lo = (1.0 + slope_arch_lo**2) ** 0.5
    arch_tx_lo, arch_ty_lo = 1.0 / tlen_lo, slope_arch_lo / tlen_lo
    tlen_hi = (1.0 + slope_arch_hi**2) ** 0.5
    arch_tx_hi, arch_ty_hi = 1.0 / tlen_hi, slope_arch_hi / tlen_hi

    # Tilt the P2-P3 line (tangent at M): net 1° CCW.
    import math as _m3
    tilt_deg = 2.0
    _c, _s = _m3.cos(_m3.radians(tilt_deg)), _m3.sin(_m3.radians(tilt_deg))
    _tx_new = arch_tx_lo * _c + arch_ty_lo * _s
    _ty_new = -arch_tx_lo * _s + arch_ty_lo * _c
    arch_tx_lo, arch_ty_lo = _tx_new, _ty_new

    # Bridge control-handle lengths (tunable)
    h_col    = 180.0   # column-tangent handle (into bass bridge)
    h_M_L    = 303.75  # P2 handle length (bass side of M)
    h_M_R    =  39.87  # P3 handle length (treble side of M)
    h_TB0    = 200.0   # pin-arch-tangent handle approaching TB0 from M side
    h_arch_R =  35.0   # treble-side arch-tangent handle (leaving TB0 into treble bridge)
    h_sbk    =  65.78  # soundback-vertical handle (P4)

    # Bass bridge BB0 -> BB3 (= M). Short symmetric handles P2 and P3 at M.
    BB0 = (col_left_x_top, col_top_sby)
    BB1 = (BB0[0] + h_col * col_tan_up_x, BB0[1] + h_col * col_tan_up_y)
    BB3 = (arch_x_lo, arch_y_lo)                               # M
    BB2 = (BB3[0] - h_M_L * arch_tx_lo, BB3[1] - h_M_L * arch_ty_lo)   # P2, handle on bass side of M

    # Middle Bezier from M to TB0 replaces the old polyline so M has an
    # outgoing handle P3 collinear with P2 (G1 through M).
    M_OUT = (BB3[0] + h_M_R * arch_tx_lo, BB3[1] + h_M_R * arch_ty_lo) # P3, handle on treble side of M

    # Treble bridge TB0 -> TB3
    TB0 = (arch_x_hi, arch_y_hi)
    TB0_IN = (TB0[0] - h_TB0 * arch_tx_hi, TB0[1] - h_TB0 * arch_ty_hi)  # incoming handle at TB0 (from M side)
    TB1 = (TB0[0] + h_arch_R * arch_tx_hi, TB0[1] + h_arch_R * arch_ty_hi)  # outgoing handle at TB0 (into treble bridge)
    TB3 = (neck_right_x, NECK_DROP)
    TB2 = (TB3[0], TB3[1] - h_sbk)

    # Expose as a dict for control-point visualization below
    arch_P0 = BB0; arch_P1 = BB1
    arch_P2 = BB2                 # P2, short incoming handle at M (bass side)
    arch_M  = BB3                 # M (pin arch bass-end anchor)
    arch_P3 = M_OUT               # P3, short outgoing handle at M (collinear with P2)
    arch_P4 = TB2                 # soundback-vertical handle
    arch_P5 = TB3
    M_x = arch_x_lo; M_y = arch_y_lo
    h_L = h_col; h_R = h_sbk

    # --- Under-belly of the neck: curve from the soundboard-connect point
    # (vertical takeoff) to the column inner top (tangent matches the
    # column's inner arc, going up out of the column). ---
    UB3 = (float(x_tangent_hit), NECK_DROP)       # soundboard-connect point
    UB0 = (COLUMN_X + dx, NECK_DROP)              # column inner top

    # Inner-arc tangent direction at the top, UP out of the column:
    # (at column top the inner-arc's tangent-line is nearly vertical; the
    # small +x component comes from the arc bowing left).
    col_center_x_inner = (COLUMN_X + dx) + (arc_R - sag)
    ir_rx = UB0[0] - col_center_x_inner
    ir_ry = UB0[1] - col_center_y
    ir_rlen = (ir_rx*ir_rx + ir_ry*ir_ry) ** 0.5
    # CW rotation of radius (sin θ, -cos θ) gives DOWN-LEFT tangent at top.
    # Negate for UP-RIGHT direction (going up out of the column into neck).
    inner_tan_up_x =  ir_ry / ir_rlen            # ≈ -0.065  ...  wait, let me recompute
    inner_tan_up_y = -ir_rx / ir_rlen            # ≈ +0.998
    # Actually both signs above produce (ry, -rx)/rlen = (negative, positive)
    # which would be DOWN-LEFT. Flip to get UP-RIGHT:
    inner_tan_up_x = -inner_tan_up_x
    inner_tan_up_y = -inner_tan_up_y

    # Under belly: two cubic Bezier segments joined at UBM under string 26.
    # Tangents at UB0 and UB3 match the adjacent curves going UP; UBM
    # tangent is horizontal (belly's deepest point).
    h_ub_sbk = 30.69   # UB2 handle
    h_ub_col = 32.71   # UB1 handle
    h_ub_mid_L = 200.0
    h_ub_mid_R = 300.0
    UBM_string_num = 26                                # Prelude numbering
    UBM_idx        = 40 - UBM_string_num               # sort-by-x index
    UBM   = (float(xs[UBM_idx]), NECK_DROP - 25.4)     # 1" (25.4 mm) ABOVE the neck-bottom horizontal
    UBM_L = (UBM[0] - h_ub_mid_L, UBM[1])              # left-of-UBM handle (horizontal tangent)
    UBM_R = (UBM[0] + h_ub_mid_R, UBM[1])              # right-of-UBM handle (horizontal tangent)
    UB2 = (UB3[0], UB3[1] - h_ub_sbk)                   # UB3-side handle (vertical tangent UP)
    UB1 = (UB0[0] + h_ub_col * inner_tan_up_x,          # UB0-side handle (inner-arc direction)
           UB0[1] + h_ub_col * inner_tan_up_y)

    def ptA(p): return f"{X(p[0]):.2f},{top_pad + p[1] + y_offset:.2f}"
    neck_path = (
        f"M {ptA(BB0)} "
        f"C {ptA(BB1)} {ptA(BB2)} {ptA(BB3)} "           # bass bridge P0->P1->P2->M
        f"C {ptA(M_OUT)} {ptA(TB0_IN)} {ptA(TB0)} "      # middle Bezier M->P3->TB0_IN->TB0
        f"C {ptA(TB1)} {ptA(TB2)} {ptA(TB3)} "           # treble bridge TB0->TB1->TB2->P5
        f"L {ptA(UB3)} "                                 # across from soundback-connect to soundboard-connect
        f"C {ptA(UB2)} {ptA(UBM_R)} {ptA(UBM)} "         # under-belly segment 1: UB3 -> UBM
        f"C {ptA(UBM_L)} {ptA(UB1)} {ptA(UB0)} "         # under-belly segment 2: UBM -> UB0
        f"L {ptA((neck_left_x,  NECK_DROP))} Z"          # back across the column top to BB0
    )
    parts.append(
        f'<path d="{neck_path}" fill="#c49a6c" fill-opacity="0.35" '
        f'stroke="#3a2a10" stroke-width="0.8"/>'
    )
    parts.append(
        f'<text x="{X((neck_left_x + neck_right_x) / 2):.2f}" '
        f'y="{top_pad + (neck_top_sby + NECK_DROP) / 2 + y_offset:.2f}" '
        f'text-anchor="middle" font-size="11" fill="#3a2a10">NECK (arched top)</text>'
    )

    # --- Bezier control polygon + labels (debug/tuning overlay) ---
    def ptXY(p): return (X(p[0]), top_pad + p[1] + y_offset)
    pts = {
        "P0": arch_P0, "P1": arch_P1,
        "P2": arch_P2, "M": arch_M, "P3": arch_P3,
        "P4": arch_P4, "P5": arch_P5,
        "UB3": UB3, "UB2": UB2,
        "UBM_R": UBM_R, "UBM": UBM, "UBM_L": UBM_L,
        "UB1": UB1, "UB0": UB0,
    }
    # Handle LINES (blue dashed) -- anchor → handle for each anchor point.
    # Neck top: P0→P1, M→P2, M→P3, P5→P4
    # Under belly: UB0→UB1, UB3→UB2, UBM→UBM_L, UBM→UBM_R
    handle_pairs = [
        ("P0",  "P1"),  ("M",   "P2"),  ("M",   "P3"),  ("P5",  "P4"),
        ("UB0", "UB1"), ("UB3", "UB2"),
        ("UBM", "UBM_L"), ("UBM", "UBM_R"),
    ]
    for anchor, handle in handle_pairs:
        sa, sb = ptXY(pts[anchor]), ptXY(pts[handle])
        parts.append(
            f'<line x1="{sa[0]:.2f}" y1="{sa[1]:.2f}" x2="{sb[0]:.2f}" y2="{sb[1]:.2f}" '
            f'stroke="#26c" stroke-width="0.8" stroke-dasharray="3,2"/>'
        )
    # Control point markers + labels.
    # Anchors (curve endpoints & joins) are RED solid; handles are BLUE dots.
    anchor_names = {"P0", "M", "P5", "UB0", "UB3", "UBM"}
    for name, p in pts.items():
        xp, yp = ptXY(p)
        is_anchor = name in anchor_names
        fill = "#d13" if is_anchor else "#26c"
        r = 2.0 if is_anchor else 1.5
        parts.append(
            f'<circle cx="{xp:.2f}" cy="{yp:.2f}" r="{r}" fill="{fill}"/>'
        )
        if name in ("P0", "UB0"):
            lbl_dx, anc = 5, "start"
        elif name == "P3":
            lbl_dx, anc = -5, "end"
        elif name == "M":
            lbl_dx, anc = 0, "middle"
        else:
            lbl_dx, anc = -5, "end"
        if name == "M":
            dy = -6
        elif name == "P3":
            dy = -6
        elif name.startswith("UB"):
            dy = 9
        else:
            dy = 3
        text_fill = "#600" if is_anchor else "#024"
        parts.append(
            f'<text x="{xp + lbl_dx:.2f}" y="{yp + dy:.2f}" '
            f'font-size="7" fill="{text_fill}" '
            f'text-anchor="{anc}">{name} ({p[0]:.0f}, {p[1]:.0f})</text>'
        )

    # Handle-length report below the title
    parts.append(
        f'<text x="10" y="56" font-size="10" fill="#d13">'
        f'h_L = {h_L:.0f} mm · h_M_L/R = {h_M_L:.0f}/{h_M_R:.0f} mm · h_R = {h_R:.0f} mm · '
        f'M above string 20 at y = {M_y:.0f} mm</text>'
    )
    parts.append(
        f'<text x="{X(apex_axis_x - dx):.2f}" '
        f'y="{top_pad + sby_str40_center + y_offset:.2f}" '
        f'text-anchor="middle" font-size="11" fill="#3a2a10" '
        f'transform="rotate(-90 {X(apex_axis_x - dx):.2f} '
        f'{top_pad + sby_str40_center + y_offset:.2f})">'
        f'COLUMN (45 mm, 1.5″ bow, uniform width)</text>'
    )

    # Soundboard extension as a cubic Bezier that starts tangent to the
    # soundboard curve and arrives at the neck-bottom horizontal horizontally,
    # so there's no abrupt straight-line kink.
    yB = top_pad + y_treb + y_offset                    # string-1 bottom, in SVG y
    yH = top_pad + NECK_DROP + y_offset                 # neck-bottom horizontal (SB_y = NECK_DROP)
    h_sb = ((x_tangent_hit - x_treb)**2 + (y_treb - NECK_DROP)**2) ** 0.5 / 3.0
    sb_p0x = X(x_treb);       sb_p0y = yB
    sb_p3x = X(x_tangent_hit); sb_p3y = yH
    sb_p1x = sb_p0x + h_sb * tx_t
    sb_p1y = sb_p0y + h_sb * tz_t
    # Vertical takeoff at P3: curve arrives heading straight up (0, -1) in SVG.
    # P2 sits directly below P3 by h so tangent at P3 points upward.
    sb_p2x = sb_p3x
    sb_p2y = sb_p3y + h_sb
    parts.append(
        f'<path d="M {sb_p0x:.2f},{sb_p0y:.2f} '
        f'C {sb_p1x:.2f},{sb_p1y:.2f} {sb_p2x:.2f},{sb_p2y:.2f} '
        f'{sb_p3x:.2f},{sb_p3y:.2f}" fill="none" '
        f'stroke="#7a2a2a" stroke-width="0.8" stroke-dasharray="4,3"/>'
    )
    # Horizontal at the bottom of the neck
    parts.append(
        f'<line x1="{X(xs.min()):.2f}" y1="{yH:.2f}" '
        f'x2="{X(x_tangent_hit + 20):.2f}" y2="{yH:.2f}" '
        f'stroke="#0a7" stroke-width="0.5" stroke-dasharray="2,3"/>'
    )
    parts.append(
        f'<circle cx="{X(x_tangent_hit):.2f}" cy="{yH:.2f}" r="3" fill="#7a2a2a"/>'
    )

    parts.append('</svg>')
    SVG_PATH.write_text("\n".join(parts) + "\n")
    print(f"wrote {SVG_PATH}  ({w:.0f} x {h:.0f} mm, {len(strings)} strings)")


if __name__ == "__main__":
    main()
