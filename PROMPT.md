# Handoff to Lab Claude

The previous session just committed `db411dc` and pushed to `main`. Start by
reading this file, then `CLAUDE.md` (project conventions), then
`~/.claude/projects/-home-clementsj-projects-clements40/memory/MEMORY.md`
(user's auto-memory).

## Where things stand

Two harp models share this repo:

| Harp | Strings | Range | Spec | SVG | FCStd |
|---|---|---|---|---|---|
| clements40 | 40 (lever) | 1E..6A | `clements40.json` | `Clements40.svg` | `Clements40.FCStd` |
| Erand47   | 47 (pedal) | C1..G7  | `erand47.json`    | `Erand47.svg`    | `Erand47.FCStd`    |

Both are driven by the same scripts (`make_svg.py`, `build_clements40.py`).
Which harp to build is selected by `HARP_SPEC` env var (default
`clements40.json`). `extract_strings.py` regenerates `clements40.json` from
`../clements47/clements47.json`; `extract_erand47.py` regenerates
`erand47.json`.

## Just-landed changes (`db411dc`)

* Soundboard curve is a **3-segment cubic Bezier** with 4 anchors
  `SBa / SBb / SBc / SBd` (`SBa` = bass base corner with vertical-up
  tangent, `SBd` = treble neck corner with vertical-up tangent, `SBb` and
  `SBc` are internal anchors at 1/3 and 2/3 of the x-span).
* Internal-anchor **tangent slopes are optimized** (not locked horizontal),
  tracking the local LSQ-fit slope. `scipy.optimize.least_squares` jointly
  fits SBb.y, SBc.y, two slopes, and six handle lengths (2 per segment).
* Fit quality on grommets:
  * Erand47: RMS **3.48 mm**, max 11.68 mm over 1373 mm vertical span.
  * Clements40: RMS **3.97 mm**, max 16.25 mm.
* `SBd1` handle is **overridden** after the LSQ fit to
  `0.35 × (SBd.x − SBc.x)` so the curve eases into the vertical neck
  takeoff more roundly. The LSQ optimum drives `h3D` to its 1 mm floor,
  which produces a visible kink; the override trades a bit of grommet fit
  near the treble for visual smoothness (the user explicitly asked for
  this). Search `_sb_h3D_draw` in `make_svg.py` to find it.
* Neck overlay labels renamed from P0/P1/.../UB0/UBM/... to soundboard
  style: `NTa/NTa1/NTb1/NTb/NTb2/NTc1/NTc` for the arched top, and
  `NBa/NBa1/NBb1/NBb/NBb2/NBc1/NBc` for the under-belly. **Only the
  overlay labels changed** — the internal variable names (`arch_P0`,
  `UBM`, `UB3`, etc.) are untouched because they're referenced all over
  the geometry math.
* `build_clements40.py` reads `HARP_SPEC`; the FreeCAD doc name is
  derived from the spec stem.
* Fixed `round(numpy.ndarray)` crash in the `harp_3d` exporter at the
  bottom of `make_svg.py`.

## How to run / iterate

```bash
cd /home/clementsj/projects/clements40

# Regenerate both SVGs from the existing JSON specs
python3 make_svg.py                             # -> Clements40.svg
HARP_SPEC=erand47.json python3 make_svg.py      # -> Erand47.svg

# Rebuild both FreeCAD docs from their JSON specs
FREECADCMD=/home/clementsj/projects/clements47/squashfs-root/usr/bin/freecadcmd
echo 'exec(open("build_clements40.py").read())' | $FREECADCMD              # -> Clements40.FCStd
echo 'exec(open("build_clements40.py").read())' | HARP_SPEC=erand47.json $FREECADCMD  # -> Erand47.FCStd

# Regenerate specs from source data (rare)
python3 extract_strings.py     # subsets clements47.json -> clements40.json
python3 extract_erand47.py     # translates clements47.json -> erand47.json
```

To inspect SVGs visually: `rsvg-convert -w 2400 Erand47.svg -o /tmp/x.png`
then `Read /tmp/x.png`. For zoomed crops use `convert /tmp/x.png -crop
WxH+X+Y /tmp/crop.png`.

## Open threads the user may pick up

* **SBd1 scale tuning.** Currently `0.35 × seg3_x_span`. User was offered
  `0.25` (tighter, closer to treble grommets) or `0.50` (more rounded,
  lifts further from grommets) but hadn't chosen. Symmetric override for
  `SBa1` (bass base) was also offered but not yet applied — if the user
  asks for that, mirror the same pattern using `_sb_h1A_draw =
  (SBb.x − SBa.x) * 0.35` (or whatever factor).
* **More internal anchors on the soundboard.** A third internal anchor
  (A–E pattern) tested slightly *worse* (RMS 4.2 mm vs 3.5 mm) due to
  overfit/local-minimum. A clamped spline with 47 anchors would pass
  through every grommet exactly. User currently accepts 12 mm max.
* **Under-belly / neck-top fit to pins.** The neck-top (`NT*`) and
  belly (`NB*`) curves are currently hand-tuned via magic handle
  lengths (`h_M_L`, `h_M_R`, `h_sbk`, `h_ub_sbk`, `h_ub_col`, ...). A
  similar scipy-LSQ fit against the pin positions and lever positions
  is the natural next step, but the user hasn't asked for it yet.
* **Levers.** Clements40's harpcanada levers (see `3d-lever-manual-
  book.pdf`) are still unmodeled. `add_levers.py` planned per `CLAUDE.md`.
  The STL bundle (`Unconfirmed 877837.crdownload`) may or may not have
  finished downloading.

## Conventions to respect

* Coordinate system: X = bass→treble, Y = harpist(−)→audience(+),
  Z = vertical. Straight-neck convention in JSON: `on.z = 0`,
  `off.z = L_on`, `grommet.z = L_on − L`. See `CLAUDE.md`.
* The user prefers **terse responses**. No leading preambles, no trailing
  summaries unless asked. Short updates between tool calls are fine.
* The user iterates visually on the SVG, then rebuilds 3D. When tuning
  the curve, re-render and show a focused crop (e.g. of the region being
  tuned) — don't dump the full image unless asked.
* Per memory: **straight neck, curved soundboard, fixed string lengths**.
  Don't cubic-spline the pin line; the soundboard absorbs `L(x)`. Don't
  hang the limacon bulb along the local normal — hang it in −Z.
* **Don't rename the internal variables** (`arch_P0`, `UBM`, etc.). The
  overlay label rename was a display-only change.
* Don't commit screenshots in `Screenshot 2026-*.png` — those are user
  artifacts.
