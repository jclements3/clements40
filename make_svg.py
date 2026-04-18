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
import math
from pathlib import Path

import numpy as np
from scipy.interpolate import LSQUnivariateSpline, UnivariateSpline

import os as _os
ROOT = Path("/home/clementsj/projects/clements40")
# HARP_SPEC env var selects which JSON to render (default: clements40.json).
# The SVG file is named from the spec stem with its first letter uppercased
# (clements40.json -> Clements40.svg, erand47.json -> Erand47.svg).
_SPEC_NAME = _os.environ.get("HARP_SPEC", "clements40.json")
SPEC_PATH  = ROOT / _SPEC_NAME
_stem      = Path(_SPEC_NAME).stem
SVG_PATH   = ROOT / (_stem[:1].upper() + _stem[1:] + ".svg")

PIN_DIA   = 7.0
LEVER_DIA = 6.0

# Soundboard extension connects to the neck-bottom horizontal this far past
# string 1 (E7, treble). NECK_DROP is derived from this and the soundboard
# slope so the tangent extension reaches the horizontal at exactly this x offset.
SOUNDBOARD_CONNECT_MM = 25.0

# 7-knot LSQ cubic -- matches bezier_soundboard.py / sb_curve in clements40.json.
N_TOTAL_KNOTS = 6

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
    # SOUNDBOARD_CONNECT_MM past string 1.
    x_treb = float(xs[-1])
    y_treb = float(cs(x_treb))
    slope_treb = float(cs.derivative()(x_treb))
    dist_past_string1 = SOUNDBOARD_CONNECT_MM
    NECK_DROP = y_treb + slope_treb * dist_past_string1
    x_tangent_hit = x_treb + dist_past_string1

    # Sloped under-belly (Erard pedal harps): the belly follows the sharp-disc
    # row with SHARP_WALL_BELOW mm of wood below each disc. Deep at the bass
    # (column side) where sharp discs sit far below the natural rail, shallow
    # at the treble end. NECK_DROP stays at the original treble-tangent value
    # -- it continues to define the treble top corner TB3 and the soundboard-
    # connect geometry. BELLY_BASS_SBY / BELLY_TREBLE_SBY are the under-belly
    # anchor heights; they reduce to NECK_DROP on harps without a "sharp"
    # field (e.g. clements40).
    SHARP_WALL_BELOW = 15.0
    sharp_strings = [s for s in strings if "sharp" in s]
    if sharp_strings:
        # sort bass-first by grommet.x to pick extremes
        _bs = sorted(sharp_strings, key=lambda s: s["grommet"]["x"])
        # -sharp.z because sharp.z is CAD (negative below rail); sby is positive below rail
        BELLY_BASS_SBY    = max(NECK_DROP,
                                -float(_bs[0]["sharp"]["z"])  + SHARP_WALL_BELOW)
        BELLY_TREBLE_SBY  = max(NECK_DROP,
                                -float(_bs[-1]["sharp"]["z"]) + SHARP_WALL_BELOW)
    else:
        BELLY_BASS_SBY = BELLY_TREBLE_SBY = NECK_DROP
    import math as _m
    angle_treb = _m.degrees(_m.atan(abs(slope_treb)))

    # --- Treble tangent extension of the soundBACK ---
    # Soundback position at the treble end = treble bulge point.
    tlen_t = (1.0 + slope_treb * slope_treb) ** 0.5
    tx_t = 1.0 / tlen_t
    tz_t = slope_treb / tlen_t
    # Pull the soundbox diameters from the spec so the soundback / base / bulge
    # curves all use the same b_bass and b_treb (they diverge if these are
    # hardcoded and the spec's diameter doesn't match, leaving visible gaps at
    # the treble soundback->neck junction and the bass base->bulge junction).
    _sb_cfg        = data.get("sb_curve") or {}
    _bass_dia_cfg  = float(_sb_cfg.get("diameter_bass",   380.0))
    _treb_dia_cfg  = float(_sb_cfg.get("diameter_treble", 102.0))
    b_treb = _treb_dia_cfg / 6.0
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
    b_bass = _bass_dia_cfg / 6.0
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
    _inner_peak_x = float(xs[0]) - 40.0
    _sag_col      = COLUMN_X - (_inner_peak_x - _dx)
    _col_top_sby  = BELLY_BASS_SBY
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
    # Bass extension: the soundboard curve takes off from the column's outer-
    # base corner with a vertical tangent, joining the fit's slope at x=0 for
    # G1 continuity. Rendered as a cubic Bezier sampled into the same polyline.
    _ba_A_x = COLUMN_X - _dx                      # col_left_x_top = -62.5
    _ba_A_y = float(bz_bass)                      # col_bot_sby (base plane in sby)
    _ba_B_y = _y_bass                             # cs at xs[0]
    _tlen_ba = (1.0 + _slope_bass * _slope_bass) ** 0.5
    # Handles scale with the vertical gap A->B so the curve shape stays
    # consistent across harp sizes (clements40 ~95 mm gap, erand47 much bigger).
    _ba_gap = max(_ba_A_y - _ba_B_y, 1.0)
    _ba_hA  = _ba_gap * 0.20                      # short vertical-up handle at A
    _ba_hB  = _ba_gap * 0.80                      # slope-match handle at B
    _ba_P1 = (_ba_A_x, _ba_A_y - _ba_hA)          # vertical-up tangent at A
    _ba_P2 = (_x0 - _ba_hB / _tlen_ba,
              _ba_B_y - _ba_hB * _slope_bass / _tlen_ba)  # match fit's slope at B
    _ba_pts = []
    for _i in range(40):
        _t = _i / 39.0
        _u = 1.0 - _t
        _px = (_u**3 * _ba_A_x + 3 * _u**2 * _t * _ba_P1[0]
               + 3 * _u * _t**2 * _ba_P2[0] + _t**3 * _x0)
        _py = (_u**3 * _ba_A_y + 3 * _u**2 * _t * _ba_P1[1]
               + 3 * _u * _t**2 * _ba_P2[1] + _t**3 * _ba_B_y)
        _ba_pts.append(f"{X(_px):.2f},{top_pad + _py + y_offset:.2f}")
    # Soundboard curve: cubic Bezier spline with 4 anchors and G1 continuity.
    # SBa  (base bass corner, vertical-up tangent)
    # SBb  (internal, tangent = local LSQ slope)
    # SBc  (internal, tangent = local LSQ slope)
    # SBd  (treble neck corner, vertical-up tangent)
    # -> 3 Bezier segments. Internal-anchor y-values, their tangent slopes,
    # and 6 handle lengths (2 per segment) are co-optimized by scipy
    # least_squares to minimize y-residual on the 47 grommets.
    _sb_A_x, _sb_A_y = _ba_A_x, _ba_A_y               # SBa = bass base corner
    _sb_D_x, _sb_D_y = float(x_tangent_hit), NECK_DROP # SBd = treble neck corner
    _sb_B_x = _sb_A_x + (_sb_D_x - _sb_A_x) * (1.0 / 3.0)
    _sb_C_x = _sb_A_x + (_sb_D_x - _sb_A_x) * (2.0 / 3.0)

    _sb_xs = xs
    _sb_ys = (Ls - L_ons)

    def _bez_eval(A_x, A_y, P1, P2, D_x, D_y, ts):
        u = 1.0 - ts
        bx = (u**3 * A_x + 3*u**2*ts * P1[0]
              + 3*u*ts**2 * P2[0] + ts**3 * D_x)
        by = (u**3 * A_y + 3*u**2*ts * P1[1]
              + 3*u*ts**2 * P2[1] + ts**3 * D_y)
        return bx, by

    def _seg_y_at_xs(A_x, A_y, P1, P2, D_x, D_y, xs_target):
        """Return by(t) for each xg where bx(t)=xg. Assumes x-monotone."""
        ts_dense = np.linspace(0.0, 1.0, 2001)
        bx_d, by_d = _bez_eval(A_x, A_y, P1, P2, D_x, D_y, ts_dense)
        order = np.argsort(bx_d)
        return np.interp(np.asarray(xs_target, dtype=float),
                         bx_d[order], by_d[order])

    _seg1_mask = (_sb_xs >= _sb_A_x) & (_sb_xs <= _sb_B_x)
    _seg2_mask = (_sb_xs >  _sb_B_x) & (_sb_xs <= _sb_C_x)
    _seg3_mask = (_sb_xs >  _sb_C_x) & (_sb_xs <= _sb_D_x)

    def _unit(tx, ty):
        n = math.hypot(tx, ty)
        return (tx / n, ty / n)

    def _sb_residuals(params):
        (B_y, C_y, mB, mC,
         h1A, h1B, h2B, h2C, h3C, h3D) = params
        # Tangent unit vectors at each anchor (direction of motion A -> D):
        tA = (0.0, -1.0)                      # vertical UP at SBa
        tB = _unit(1.0, mB)                   # along (+x, slope) at SBb
        tC = _unit(1.0, mC)                   # along (+x, slope) at SBc
        tD = (0.0, -1.0)                      # vertical UP at SBd
        # Segment 1: SBa -> SBb
        P1_1 = (_sb_A_x + h1A * tA[0], _sb_A_y + h1A * tA[1])
        P2_1 = (_sb_B_x - h1B * tB[0], B_y    - h1B * tB[1])
        # Segment 2: SBb -> SBc
        P1_2 = (_sb_B_x + h2B * tB[0], B_y    + h2B * tB[1])
        P2_2 = (_sb_C_x - h2C * tC[0], C_y    - h2C * tC[1])
        # Segment 3: SBc -> SBd
        P1_3 = (_sb_C_x + h3C * tC[0], C_y    + h3C * tC[1])
        P2_3 = (_sb_D_x - h3D * tD[0], _sb_D_y - h3D * tD[1])

        ys_pred = np.empty_like(_sb_ys, dtype=float)
        if _seg1_mask.any():
            ys_pred[_seg1_mask] = _seg_y_at_xs(
                _sb_A_x, _sb_A_y, P1_1, P2_1, _sb_B_x, B_y,
                _sb_xs[_seg1_mask])
        if _seg2_mask.any():
            ys_pred[_seg2_mask] = _seg_y_at_xs(
                _sb_B_x, B_y, P1_2, P2_2, _sb_C_x, C_y,
                _sb_xs[_seg2_mask])
        if _seg3_mask.any():
            ys_pred[_seg3_mask] = _seg_y_at_xs(
                _sb_C_x, C_y, P1_3, P2_3, _sb_D_x, _sb_D_y,
                _sb_xs[_seg3_mask])
        return ys_pred - _sb_ys

    # Initial guess: B_y, C_y from the LSQ fit; slopes from cs derivative;
    # handles at 1/3 of each segment's x-span.
    _csd = cs.derivative()
    _sb_B_y0 = float(cs(_sb_B_x)) if xs[0] <= _sb_B_x <= xs[-1] else \
               _sb_A_y + (_sb_D_y - _sb_A_y) / 3.0
    _sb_C_y0 = float(cs(_sb_C_x)) if xs[0] <= _sb_C_x <= xs[-1] else \
               _sb_A_y + (_sb_D_y - _sb_A_y) * 2 / 3.0
    _mB0 = float(_csd(_sb_B_x)) if xs[0] <= _sb_B_x <= xs[-1] else \
           (_sb_C_y0 - _sb_A_y) / (_sb_C_x - _sb_A_x)
    _mC0 = float(_csd(_sb_C_x)) if xs[0] <= _sb_C_x <= xs[-1] else \
           (_sb_D_y - _sb_B_y0) / (_sb_D_x - _sb_B_x)
    _span1 = (_sb_B_x - _sb_A_x) / 3.0
    _span2 = (_sb_C_x - _sb_B_x) / 3.0
    _span3 = (_sb_D_x - _sb_C_x) / 3.0
    _sb_p0 = np.array([_sb_B_y0, _sb_C_y0, _mB0, _mC0,
                    _span1, _span1, _span2, _span2, _span3, _span3])
    _y_lo = min(_sb_A_y, _sb_D_y) - 50.0
    _y_hi = max(_sb_A_y, _sb_D_y) + 50.0
    _lo = np.array([_y_lo, _y_lo, -20.0, -20.0,
                    1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    _hi = np.array([_y_hi, _y_hi,  20.0,  20.0,
                    (_sb_B_x - _sb_A_x) * 1.5, (_sb_B_x - _sb_A_x) * 1.5,
                    (_sb_C_x - _sb_B_x) * 1.5, (_sb_C_x - _sb_B_x) * 1.5,
                    (_sb_D_x - _sb_C_x) * 1.5, (_sb_D_x - _sb_C_x) * 1.5])
    try:
        from scipy.optimize import least_squares
        _res = least_squares(_sb_residuals, _sb_p0, bounds=(_lo, _hi))
        (_sb_B_y, _sb_C_y, _sb_mB, _sb_mC,
         _sb_h1A, _sb_h1B, _sb_h2B, _sb_h2C,
         _sb_h3C, _sb_h3D) = [float(v) for v in _res.x]
        _sb_rms = float(np.sqrt(np.mean(_res.fun * _res.fun)))
        _sb_max = float(np.max(np.abs(_res.fun)))
    except Exception as _e:
        print(f"Soundboard LSQ fit failed ({_e}); falling back to initial guess")
        (_sb_B_y, _sb_C_y, _sb_mB, _sb_mC,
         _sb_h1A, _sb_h1B, _sb_h2B, _sb_h2C,
         _sb_h3C, _sb_h3D) = (_sb_B_y0, _sb_C_y0, _mB0, _mC0,
                              _span1, _span1, _span2, _span2, _span3, _span3)
        _sb_rms = _sb_max = float('nan')
    print(f"Soundboard 3-seg Bezier fit: "
          f"SBb=({_sb_B_x:.0f},{_sb_B_y:.0f}) SBc=({_sb_C_x:.0f},{_sb_C_y:.0f})  "
          f"h1A={_sb_h1A:.0f} h1B={_sb_h1B:.0f} h2B={_sb_h2B:.0f} h2C={_sb_h2C:.0f} "
          f"h3C={_sb_h3C:.0f} h3D={_sb_h3D:.0f}  "
          f"RMS {_sb_rms:.2f} mm  max {_sb_max:.2f} mm")

    # Rebuild final control points from the solution.
    # SBd1 override: the LSQ fit pushes h3D to its floor (the grommets are
    # nearly vertical there already), which makes the neck takeoff look kinked.
    # Override to a fraction of segment 3's x-span so the curve eases into
    # the vertical neck tangent more roundly. Trades some grommet fit near
    # the treble for visual smoothness.
    _sb_h3D_draw = (_sb_D_x - _sb_C_x) * 0.35
    _tA = (0.0, -1.0)
    _tB = _unit(1.0, _sb_mB)
    _tC = _unit(1.0, _sb_mC)
    _tD = (0.0, -1.0)
    _sb_SBa1 = (_sb_A_x + _sb_h1A * _tA[0], _sb_A_y + _sb_h1A * _tA[1])
    _sb_SBb1 = (_sb_B_x - _sb_h1B * _tB[0], _sb_B_y - _sb_h1B * _tB[1])
    _sb_SBb2 = (_sb_B_x + _sb_h2B * _tB[0], _sb_B_y + _sb_h2B * _tB[1])
    _sb_SBc1 = (_sb_C_x - _sb_h2C * _tC[0], _sb_C_y - _sb_h2C * _tC[1])
    _sb_SBc2 = (_sb_C_x + _sb_h3C * _tC[0], _sb_C_y + _sb_h3C * _tC[1])
    _sb_SBd1 = (_sb_D_x - _sb_h3D_draw * _tD[0], _sb_D_y - _sb_h3D_draw * _tD[1])

    parts.append(
        f'<path d="M {X(_sb_A_x):.2f},{top_pad + _sb_A_y + y_offset:.2f} '
        f'C {X(_sb_SBa1[0]):.2f},{top_pad + _sb_SBa1[1] + y_offset:.2f} '
        f'{X(_sb_SBb1[0]):.2f},{top_pad + _sb_SBb1[1] + y_offset:.2f} '
        f'{X(_sb_B_x):.2f},{top_pad + _sb_B_y + y_offset:.2f} '
        f'C {X(_sb_SBb2[0]):.2f},{top_pad + _sb_SBb2[1] + y_offset:.2f} '
        f'{X(_sb_SBc1[0]):.2f},{top_pad + _sb_SBc1[1] + y_offset:.2f} '
        f'{X(_sb_C_x):.2f},{top_pad + _sb_C_y + y_offset:.2f} '
        f'C {X(_sb_SBc2[0]):.2f},{top_pad + _sb_SBc2[1] + y_offset:.2f} '
        f'{X(_sb_SBd1[0]):.2f},{top_pad + _sb_SBd1[1] + y_offset:.2f} '
        f'{X(_sb_D_x):.2f},{top_pad + _sb_D_y + y_offset:.2f}" '
        f'fill="none" stroke="#7a2a2a" stroke-width="0.8" '
        f'stroke-dasharray="4,3"/>'
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
    # Bulge offset (kept for station-dot placement below -- no longer rendered
    # as a polyline since the soundback curve is now a single cubic Bezier).
    bulge_x = dense_x - 3.0 * dense_b * tz
    bulge_z = cs(dense_x) + 3.0 * dense_b * tx

    # Soundback curve: a SINGLE cubic Bezier from BKa (bass base corner at the
    # bulge bass-bulb tip) to BKd (treble neck corner), both endpoints with
    # vertical tangents. Shape controlled entirely by BKa1 and BKd1.
    _bk_A_x, _bk_A_y = float(bx_bass), float(bz_bass)     # BKa
    _bk_D_x, _bk_D_y = float(x_sbk_hit), NECK_DROP        # BKd
    _bk_vspan = max(_bk_A_y - _bk_D_y, 1.0)
    _bk_hA = _bk_vspan * 0.55                             # vertical handle at BKa
    _bk_hD = _bk_vspan * 0.55                             # vertical handle at BKd
    _bk_P1 = (_bk_A_x, _bk_A_y - _bk_hA)                  # BKa1
    _bk_P2 = (_bk_D_x, _bk_D_y + _bk_hD)                  # BKd1
    parts.append(
        f'<path d="M {X(_bk_A_x):.2f},{top_pad + _bk_A_y + y_offset:.2f} '
        f'C {X(_bk_P1[0]):.2f},{top_pad + _bk_P1[1] + y_offset:.2f} '
        f'{X(_bk_P2[0]):.2f},{top_pad + _bk_P2[1] + y_offset:.2f} '
        f'{X(_bk_D_x):.2f},{top_pad + _bk_D_y + y_offset:.2f}" '
        f'fill="none" stroke="#1a5" stroke-width="1.2"/>'
    )
    parts.append(
        f'<circle cx="{X(_bk_D_x):.2f}" cy="{top_pad + _bk_D_y + y_offset:.2f}" '
        f'r="3" fill="#1a5"/>'
    )

    # --- Bass base: horizontal at bz_bass from the soundback bass bulb to the
    # column's outer-base corner (col_left_x_top = COLUMN_X - dx), so the base
    # visually meets the column's foot rather than stopping short of it.
    COLUMN_X = -40.0
    COLUMN_OD_HERE = 45.0
    base_y = top_pad + bz_bass + y_offset
    base_p0x = X(bx_bass);                       base_p0y = base_y
    base_p3x = X(COLUMN_X - COLUMN_OD_HERE/2.0); base_p3y = base_y
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
        # Sharp disc (Erard pedal harps have a second disc per string). Drawn
        # only when the spec preserves a "sharp" field, as erand47.json does.
        # sharp.z is the z offset from the natural-disc rail (negative => the
        # sharp disc sits below the natural rail, closer to the grommet).
        if "sharp" in s:
            y_sharp = y_lever - float(s["sharp"]["z"])
            parts.append(
                f'<circle cx="{x + r_lever:.2f}" cy="{y_sharp:.2f}" '
                f'r="{r_lever:.2f}" fill="#d06020" stroke="#5a2a00" '
                f'stroke-width="0.4"/>'
            )

    # --- Column: uniform 45 mm wide, bowed out to the left as a SIMPLE
    # CIRCULAR ARCH (not a spline or bezier). Both edges are arcs of the
    # same radius, parallel-offset by 45 mm so the column width is uniform.
    # Arc depth is sized so the inner edge's apex sits 1.5" from string 40.
    wall_above    = 10.0
    COLUMN_OD     = 45.0
    COLUMN_X      = -40.0
    col_top_sby   = BELLY_BASS_SBY                     # column top tracks the belly at bass
    col_bot_sby   = float(bz_bass)
    dx            = COLUMN_OD / 2.0
    INNER_PEAK_DIST_FROM_STR40_MM = 40.0
    inner_peak_x   = float(xs[0]) - INNER_PEAK_DIST_FROM_STR40_MM
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
    M_pin_idx = len(xs) - prelude_string_at_M  # sort-by-x index (bass-first)
    M_pin_idx = max(0, min(len(xs) - 1, M_pin_idx))
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
    tilt_deg = 4.0
    _c, _s = _m3.cos(_m3.radians(tilt_deg)), _m3.sin(_m3.radians(tilt_deg))
    _tx_new = arch_tx_lo * _c + arch_ty_lo * _s
    _ty_new = -arch_tx_lo * _s + arch_ty_lo * _c
    arch_tx_lo, arch_ty_lo = _tx_new, _ty_new

    # Bridge control-handle lengths (tunable)
    h_col    = 180.0   # column-tangent handle (into bass bridge)
    h_M_L    = 303.75  # P2 handle length (bass side of M)
    h_M_R    = 398.70  # P3 handle length (treble side of M)
    h_TB0    = 200.0   # pin-arch-tangent handle approaching TB0 from M side
    h_arch_R =  35.0   # treble-side arch-tangent handle (leaving TB0 into treble bridge)
    h_sbk    =  59.20  # soundback-vertical handle (P4) -- overridden below

    # Extend P3 and P4 so they meet at a common point. P4 is vertical above
    # TB3 at x = neck_right_x, so the intersection sits at that x; P3's ray
    # from M in direction (arch_tx_lo, arch_ty_lo) hits it at parameter t.
    _t_isect = (neck_right_x - arch_x_lo) / arch_tx_lo
    h_M_R = _t_isect
    h_sbk = NECK_DROP - (arch_y_lo + _t_isect * arch_ty_lo)
    print(f"P3/P4 intersection: h_M_R={h_M_R:.2f} mm, h_sbk={h_sbk:.2f} mm")

    # Extend P1 and P2 so they meet at their intersection (solve the 2x2
    # system where P1 leaves BB0 along col_tan_up and P2 leaves M along
    # -arch_tan_lo).
    _bb0x, _bb0y = col_left_x_top, col_top_sby
    _den_12 = col_tan_up_x * arch_ty_lo - col_tan_up_y * arch_tx_lo
    _dmx = arch_x_lo - _bb0x
    _dmy = arch_y_lo - _bb0y
    h_col = (_dmx * arch_ty_lo - _dmy * arch_tx_lo) / _den_12
    h_M_L = (col_tan_up_x * _dmy - col_tan_up_y * _dmx) / _den_12
    print(f"P1/P2 intersection: h_col={h_col:.2f} mm, h_M_L={h_M_L:.2f} mm")

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
    UB3 = (float(x_tangent_hit), BELLY_TREBLE_SBY)   # soundboard-connect point (belly at treble)
    UB0 = (COLUMN_X + dx,         BELLY_BASS_SBY)    # column inner top (belly at bass, deep)

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
    UBM_idx        = len(xs) - UBM_string_num          # sort-by-x index (works for 40 or 47 strings)
    UBM_idx        = max(0, min(len(xs) - 1, UBM_idx))
    # UBM y: linearly interpolated between UB3 (treble belly) and UB0 (bass
    # belly), then lifted 25 mm above the belly (same as clements40 did when
    # the belly was horizontal). This keeps UBM on the sloped belly curve.
    _ubm_x      = float(xs[UBM_idx])
    _ubm_t      = (_ubm_x - UB3[0]) / (UB0[0] - UB3[0])
    _ubm_belly  = UB3[1] + _ubm_t * (UB0[1] - UB3[1])
    UBM         = (_ubm_x, _ubm_belly - 25.0)          # 25 mm ABOVE the sloped belly
    UBM_L = (UBM[0] - h_ub_mid_L, UBM[1])              # left-of-UBM handle (horizontal tangent)
    UBM_R = (UBM[0] + h_ub_mid_R, UBM[1])              # right-of-UBM handle (horizontal tangent)
    UB2 = (UB3[0], UB3[1] - h_ub_sbk)                   # UB3-side handle (vertical tangent UP)
    # UB0-side handle. For a horizontal belly (clements40) the column's inner
    # tangent (mostly vertical up) gives a smooth transition that then bulges
    # toward UBM. For a sloped belly (Erard-style) a vertical-up handle rises
    # the curve too quickly and the bass-most sharp discs end up outside the
    # neck outline; a horizontal handle keeps the belly deep long enough to
    # cover them before turning up toward UBM.
    if sharp_strings:
        _h_ub_col_x = 90.0                             # mm of horizontal extension
        UB1 = (UB0[0] + _h_ub_col_x, UB0[1])           # horizontal tangent (belly stays deep)
    else:
        UB1 = (UB0[0] + h_ub_col * inner_tan_up_x,     # inner-arc tangent (clements40 legacy)
               UB0[1] + h_ub_col * inner_tan_up_y)

    # Corner Beziers replace the two L segments for a fully-Bezier closed path.
    # Handles are G1-continuous with the adjacent curves so the corners round
    # smoothly instead of making 90° turns.
    CORNER_H = 0.0                                     # mm, corner-handle length (0 = sharp corners)
    # Right corner TB3 -> UB3: both incoming (from P4 above) and outgoing
    # (into UB2 above) tangents are vertical, so handles drop straight DOWN.
    cornerR_h1 = (TB3[0], TB3[1] + CORNER_H)
    cornerR_h2 = (UB3[0], UB3[1] + CORNER_H)
    # Left corner UB0 -> BB0: G1 with UB1 (incoming at UB0) and BB1 (outgoing
    # at BB0). At UB0 the tangent continues in direction UB0-UB1. At BB0 the
    # tangent arrives in direction col_tan_up (same as BB0->BB1).
    _ub_out_x = UB0[0] - UB1[0]
    _ub_out_y = UB0[1] - UB1[1]
    _ub_out_len = (_ub_out_x**2 + _ub_out_y**2) ** 0.5 or 1.0
    cornerL_h1 = (UB0[0] + CORNER_H * _ub_out_x / _ub_out_len,
                  UB0[1] + CORNER_H * _ub_out_y / _ub_out_len)
    cornerL_h2 = (BB0[0] - CORNER_H * col_tan_up_x,
                  BB0[1] - CORNER_H * col_tan_up_y)

    def ptA(p): return f"{X(p[0]):.2f},{top_pad + p[1] + y_offset:.2f}"
    neck_path = (
        f"M {ptA(BB0)} "
        f"C {ptA(BB1)} {ptA(BB2)} {ptA(BB3)} "           # bass bridge P0->P1->P2->M
        f"C {ptA(M_OUT)} {ptA(TB2)} {ptA(TB3)} "         # single Bezier M->P3/P4->P5 (TB0 removed to avoid the dip)
        f"C {ptA(cornerR_h1)} {ptA(cornerR_h2)} {ptA(UB3)} "   # right corner P5 -> UB3
        f"C {ptA(UB2)} {ptA(UBM_R)} {ptA(UBM)} "         # under-belly segment 1: UB3 -> UBM
        f"C {ptA(UBM_L)} {ptA(UB1)} {ptA(UB0)} "         # under-belly segment 2: UBM -> UB0
        f"C {ptA(cornerL_h1)} {ptA(cornerL_h2)} {ptA(BB0)} Z"  # left corner UB0 -> BB0
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
    # Neck labels use the soundboard style:
    #   NT  = Neck Top   (arched top, 3 anchors NTa/NTb/NTc, 2 segments)
    #   NB  = Neck Bottom (under belly, 3 anchors NBa/NBb/NBc, 2 segments)
    pts = {
        "NTa":  arch_P0, "NTa1": arch_P1,
        "NTb1": arch_P2, "NTb":  arch_M, "NTb2": arch_P3,
        "NTc1": arch_P4, "NTc":  arch_P5,
        "NBc":  UB3,     "NBc1": UB2,
        "NBb2": UBM_R,   "NBb":  UBM,    "NBb1": UBM_L,
        "NBa1": UB1,     "NBa":  UB0,
    }
    handle_pairs = [
        ("NTa", "NTa1"), ("NTb", "NTb1"), ("NTb", "NTb2"), ("NTc", "NTc1"),
        ("NBa", "NBa1"), ("NBc", "NBc1"),
        ("NBb", "NBb1"), ("NBb", "NBb2"),
    ]
    for anchor, handle in handle_pairs:
        sa, sb = ptXY(pts[anchor]), ptXY(pts[handle])
        parts.append(
            f'<line x1="{sa[0]:.2f}" y1="{sa[1]:.2f}" x2="{sb[0]:.2f}" y2="{sb[1]:.2f}" '
            f'stroke="#26c" stroke-width="0.8" stroke-dasharray="3,2"/>'
        )
    anchor_names = {"NTa", "NTb", "NTc", "NBa", "NBb", "NBc"}
    for name, p in pts.items():
        xp, yp = ptXY(p)
        is_anchor = name in anchor_names
        fill = "#d13" if is_anchor else "#26c"
        r = 2.0 if is_anchor else 1.5
        parts.append(
            f'<circle cx="{xp:.2f}" cy="{yp:.2f}" r="{r}" fill="{fill}"/>'
        )
        if name in ("NTa", "NBa"):
            lbl_dx, anc = 5, "start"
        elif name == "NTb2":
            lbl_dx, anc = -5, "end"
        elif name == "NTb":
            lbl_dx, anc = 0, "middle"
        else:
            lbl_dx, anc = -5, "end"
        if name == "NTb":
            dy = -6
        elif name == "NTb2":
            dy = -6
        elif name.startswith("NB"):
            dy = 9
        else:
            dy = 3
        text_fill = "#600" if is_anchor else "#024"
        parts.append(
            f'<text x="{xp + lbl_dx:.2f}" y="{yp + dy:.2f}" '
            f'font-size="7" fill="{text_fill}" '
            f'text-anchor="{anc}">{name}</text>'
        )

    # --- Soundboard / Soundback Bezier control-point overlay -----------------
    # Each curve is now a SINGLE cubic Bezier from outer bass anchor to outer
    # treble anchor with vertical tangents at both endpoints. Two anchors +
    # two handles per curve.
    sbd_pts = {
        "SBa":  (_sb_A_x, _sb_A_y), "SBa1": _sb_SBa1,
        "SBb1": _sb_SBb1, "SBb": (_sb_B_x, _sb_B_y), "SBb2": _sb_SBb2,
        "SBc1": _sb_SBc1, "SBc": (_sb_C_x, _sb_C_y), "SBc2": _sb_SBc2,
        "SBd1": _sb_SBd1, "SBd":  (_sb_D_x, _sb_D_y),
    }
    sbk_pts = {
        "BKa":  (_bk_A_x, _bk_A_y), "BKa1": _bk_P1,
        "BKd1": _bk_P2,              "BKd":  (_bk_D_x, _bk_D_y),
    }
    sb_anchor_names = {"SBa", "SBb", "SBc", "SBd"}
    bk_anchor_names = {"BKa", "BKd"}
    sb_handle_pairs = [("SBa", "SBa1"),
                       ("SBb", "SBb1"), ("SBb", "SBb2"),
                       ("SBc", "SBc1"), ("SBc", "SBc2"),
                       ("SBd", "SBd1")]
    bk_handle_pairs = [("BKa", "BKa1"), ("BKd", "BKd1")]
    # Handle lines (dashed, curve-color)
    for anchor, handle in sb_handle_pairs:
        sa, sh = ptXY(sbd_pts[anchor]), ptXY(sbd_pts[handle])
        parts.append(
            f'<line x1="{sa[0]:.2f}" y1="{sa[1]:.2f}" x2="{sh[0]:.2f}" y2="{sh[1]:.2f}" '
            f'stroke="#c33" stroke-width="0.7" stroke-dasharray="3,2"/>'
        )
    for anchor, handle in bk_handle_pairs:
        sa, sh = ptXY(sbk_pts[anchor]), ptXY(sbk_pts[handle])
        parts.append(
            f'<line x1="{sa[0]:.2f}" y1="{sa[1]:.2f}" x2="{sh[0]:.2f}" y2="{sh[1]:.2f}" '
            f'stroke="#1a5" stroke-width="0.7" stroke-dasharray="3,2"/>'
        )
    # Points + labels. Anchors = filled solid dots, handles = small hollow-ish.
    for name, p in sbd_pts.items():
        xp, yp = ptXY(p)
        is_anchor = name in sb_anchor_names
        fill = "#a11" if is_anchor else "#e66"
        r = 2.0 if is_anchor else 1.4
        parts.append(f'<circle cx="{xp:.2f}" cy="{yp:.2f}" r="{r}" fill="{fill}"/>')
        parts.append(
            f'<text x="{xp + 4:.2f}" y="{yp - 3:.2f}" font-size="7" fill="#600">'
            f'{name}</text>'
        )
    for name, p in sbk_pts.items():
        xp, yp = ptXY(p)
        is_anchor = name in bk_anchor_names
        fill = "#063" if is_anchor else "#4b8"
        r = 2.0 if is_anchor else 1.4
        parts.append(f'<circle cx="{xp:.2f}" cy="{yp:.2f}" r="{r}" fill="{fill}"/>')
        parts.append(
            f'<text x="{xp + 4:.2f}" y="{yp + 9:.2f}" font-size="7" fill="#042">'
            f'{name}</text>'
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
        f'COLUMN (45 mm wide, 40 mm bow, uniform width)</text>'
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

    # --- Export the neck profile + column + soundbox extension in CAD coords
    # (z_cad = -sby) for build_clements40.py. Writes into clements40.json under
    # "harp_3d" without touching anything else.
    def _c(p): return {"x": round(float(p[0]), 3), "y": 0.0,
                        "z": round(-float(p[1]), 3)}
    harp_3d = {
        "units": "mm",
        "neck_profile": {
            "description": ("Closed Bezier outline of each plywood plate in "
                            "the X-Z plane. Four cubic segments + two "
                            "corner segments. Traversed CCW."),
            "segments": [
                {"name": "bass_arch",    "P0": _c(BB0),   "P1": _c(BB1),        "P2": _c(BB2),        "P3": _c(BB3)},
                {"name": "treble_arch",  "P0": _c(BB3),   "P1": _c(M_OUT),      "P2": _c(TB2),        "P3": _c(TB3)},
                {"name": "right_corner", "P0": _c(TB3),   "P1": _c(cornerR_h1), "P2": _c(cornerR_h2), "P3": _c(UB3)},
                {"name": "belly_treble", "P0": _c(UB3),   "P1": _c(UB2),        "P2": _c(UBM_R),      "P3": _c(UBM)},
                {"name": "belly_bass",   "P0": _c(UBM),   "P1": _c(UBM_L),      "P2": _c(UB1),        "P3": _c(UB0)},
                {"name": "left_corner",  "P0": _c(UB0),   "P1": _c(cornerL_h1), "P2": _c(cornerL_h2), "P3": _c(BB0)},
            ],
            "anchors": {
                "P0":  _c(BB0), "M":   _c(BB3), "P5":  _c(TB3),
                "UB3": _c(UB3), "UBM": _c(UBM), "UB0": _c(UB0),
            },
        },
        "plates": {
            "thickness_mm": 10.0,
            "gap_mm":       10.0,
            "stack_y_mm":   30.0,
            "y_centers_mm": [-10.0, 10.0],
        },
        "column": {
            "description":         "30mm x 45mm arc board in the X-Z plane.",
            "axis_x":              COLUMN_X,
            "radial_thickness":    COLUMN_OD,          # 45 mm
            "y_thickness":         30.0,
            "inner_peak_x":        inner_peak_x,
            "outer_left_x_top":    col_left_x_top,
            "arc_R":               arc_R,
            "arc_sag":             sag,
            "top_z":               round(-col_top_sby, 3),
            "bot_z":               round(-col_bot_sby, 3),
            "top_chord_y_half":    COLUMN_OD / 2.0,
        },
        "base_plane": {
            "z": round(-col_bot_sby, 3),
            "description": "Horizontal floor plane where the soundbox is cut off.",
        },
        "soundboard_bass_extension": {
            "description":    ("Cubic Bezier from the column outer-base corner "
                               "(vertical tangent) to the first string grommet "
                               "at x=0 (matching slope of the 7-knot LSQ fit)."),
            "P0": _c((_ba_A_x, _ba_A_y)),
            "P1": _c((_ba_P1[0], _ba_P1[1])),
            "P2": _c((_ba_P2[0], _ba_P2[1])),
            "P3": _c((_x0, _ba_B_y)),
            "handle_A_mm":    _ba_hA,
            "handle_B_mm":    _ba_hB,
        },
    }
    data["harp_3d"] = harp_3d
    SPEC_PATH.write_text(json.dumps(data, indent=1) + "\n")
    print(f"wrote harp_3d geometry to {SPEC_PATH}")


if __name__ == "__main__":
    main()
