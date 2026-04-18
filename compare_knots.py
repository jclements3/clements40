"""Render soundboard + strings + pins + levers at several fixed knot counts
so we can compare 6, 7, 8, 9-knot LSQUnivariateSpline fits side-by-side.

Layout: 4 columns, one per knot count. Each column has the same geometry as
make_svg.py (levers aligned horizontally, soundboard through smoothed fit of
L - L_on, pin arch above levers). Residual appears in the lever row.
"""
import json
import numpy as np
from pathlib import Path
from scipy.interpolate import LSQUnivariateSpline

ROOT = Path("/home/clementsj/projects/clements40")
SPEC_PATH = ROOT / "clements40.json"
OUT = ROOT / "Clements40_knots.svg"

PIN_DIA   = 7.0
LEVER_DIA = 6.0

KNOT_COUNTS = [6, 7, 8, 9]  # total knots (interior + 2 boundary)


def main() -> None:
    data = json.loads(SPEC_PATH.read_text())
    strings = sorted(data["strings"], key=lambda s: s["grommet"]["x"])
    xs    = np.array([s["grommet"]["x"] for s in strings])
    Ls    = np.array([s["off"]["z"] - s["grommet"]["z"] for s in strings])
    L_ons = np.array([s["off"]["z"] - s["on"]["z"]      for s in strings])
    y_fit = Ls - L_ons

    # Shared SVG layout: each panel is this wide, plus small gutters.
    panel_w_mm = 750.0
    gutter     = 60.0
    pad        = 40.0
    x_min = xs.min()
    x_max = xs.max() + PIN_DIA
    string_span = x_max - x_min

    panel_scale = (panel_w_mm - 2 * pad) / string_span  # mm of drawing per mm of data
    # Max L determines vertical extent
    max_L = Ls.max()
    max_above = L_ons.max()
    panel_h_mm = max_L * panel_scale + max_above * panel_scale + 2 * pad + 80  # extra for labels

    total_w = len(KNOT_COUNTS) * (panel_w_mm + gutter) + gutter
    total_h = panel_h_mm

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w:.0f} {total_h:.0f}" '
        f'width="{total_w*0.65:.0f}" height="{total_h*0.65:.0f}" font-family="sans-serif" font-size="12">'
    ]

    for col, n_total in enumerate(KNOT_COUNTS):
        x0 = gutter + col * (panel_w_mm + gutter)
        # interior knots evenly spaced between xs[0] and xs[-1]
        knot_x = np.linspace(xs[0], xs[-1], n_total)[1:-1]
        sp = LSQUnivariateSpline(xs, y_fit, knot_x, k=3)
        sb_at_string = sp(xs)
        r = sb_at_string - y_fit
        rms = float(np.sqrt(np.mean(r * r)))
        mx  = float(np.max(np.abs(r)))

        # Map x to panel coords
        def X(x): return x0 + pad + (x - x_min) * panel_scale
        lever_row_y = 80.0 + max_above * panel_scale   # absolute svg y of the lever rail
        def Y_from_sb(sb_val): return lever_row_y + sb_val * panel_scale

        # Panel header
        parts.append(
            f'<text x="{x0 + pad}" y="30" font-size="18" font-weight="bold">'
            f'{n_total} knots</text>'
        )
        parts.append(
            f'<text x="{x0 + pad}" y="52" font-size="12" fill="#666">'
            f'residual on lever row: RMS {rms:.2f} mm   max {mx:.2f} mm</text>'
        )

        # Soundboard curve (dashed red)
        dense_x = np.linspace(xs[0], xs[-1], 400)
        dense_sb = sp(dense_x)
        curve_pts = " ".join(f"{X(x):.1f},{Y_from_sb(v):.1f}" for x, v in zip(dense_x, dense_sb))
        parts.append(f'<polyline points="{curve_pts}" fill="none" '
                     f'stroke="#7a2a2a" stroke-width="0.9" stroke-dasharray="4,3"/>')

        # Knot markers on the curve
        for k in knot_x:
            parts.append(f'<circle cx="{X(k):.1f}" cy="{Y_from_sb(sp(k)):.1f}" '
                         f'r="3.5" fill="#7a2a2a"/>')
        # Boundary knots too
        for k in (xs[0], xs[-1]):
            parts.append(f'<circle cx="{X(k):.1f}" cy="{Y_from_sb(sp(k)):.1f}" '
                         f'r="3.5" fill="#7a2a2a"/>')

        # Horizontal lever-row reference line
        parts.append(
            f'<line x1="{x0 + pad - 10}" y1="{lever_row_y:.1f}" '
            f'x2="{x0 + panel_w_mm - pad + 10}" y2="{lever_row_y:.1f}" '
            f'stroke="#0a7" stroke-width="0.5" stroke-dasharray="2,3"/>'
        )

        # Strings, pins, levers
        r_pin   = PIN_DIA   / 2.0 * panel_scale
        r_lever = LEVER_DIA / 2.0 * panel_scale
        pin_dia_s   = PIN_DIA   * panel_scale
        for i, s in enumerate(strings):
            x = X(xs[i])
            y_bottom = Y_from_sb(sb_at_string[i])
            y_lever  = y_bottom - (Ls[i] - L_ons[i]) * panel_scale
            y_top    = y_lever - L_ons[i] * panel_scale
            parts.append(f'<line x1="{x:.2f}" y1="{y_top:.1f}" '
                         f'x2="{x:.2f}" y2="{y_bottom:.1f}" '
                         f'stroke="#111" stroke-width="0.6"/>')
            parts.append(f'<circle cx="{x + r_pin:.2f}" cy="{y_top:.1f}" r="{r_pin:.2f}" '
                         f'fill="#bfbfbf" stroke="#555" stroke-width="0.4"/>')
            parts.append(f'<circle cx="{x + r_lever:.2f}" cy="{y_lever:.1f}" r="{r_lever:.2f}" '
                         f'fill="#3050a0" stroke="#0b1a40" stroke-width="0.4"/>')

    parts.append('</svg>')
    OUT.write_text("\n".join(parts) + "\n")
    print(f"wrote {OUT}  ({total_w:.0f} x {total_h:.0f} mm)")


if __name__ == "__main__":
    main()
