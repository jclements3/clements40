# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## What This Is

40-string Celtic/lever harp CAD model in FreeCAD 1.1, patterned on the
Lyon & Healy Prelude 40 range (**1E → 6A** in L&H harp-octave naming =
**A1 → E7** in scientific pitch). Eb-major base tuning; each string has
one harpcanada 3D-printed lever that raises its note by one semitone.

No discs, no pedals, no linkage. This is the lever-harp sibling of
`../clements47` (Erard-style concert pedal harp).

## Key Files

- `clements40.json` — machine-readable spec: 40 strings with positions,
  frequencies (lever off/on), diameters, materials, tensions. Soundbox
  dimensions. Derived from `../clements47/clements47.json`.
- `extract_strings.py` — regenerates `clements40.json` by subsetting
  `../clements47/clements47.json` to strings a1..e7 and shifting x so the
  bass string (6A = a1) sits at x=0.
- `build_clements40.py` — FreeCAD script that produces `Clements40.FCStd`
  from `clements40.json`. Rebuilds from scratch on each run.
- `Clements40.FCStd` — main FreeCAD model.
- `3d-lever-manual-book.pdf` — harpcanada DIY lever manual (geometry reference).
- `The Harp Connection Search Results.html` — cataloged Prelude-40 string set
  (Bow Brand Pedal Nylon 1E–1F, Sipario GutGold 2E–5A, Bow Brand Pedal
  Concert Bass Wire 5G–6A).

## String Set (per Harp Connection catalog — Prelude 40, Gut 2nd Octave)

| Strings | Notes        | Material                         |
|---------|--------------|----------------------------------|
| 1–7     | 1E–1F        | Bow Brand Pedal Nylon            |
| 8–14    | 2E–2F        | Sipario GutGold (gut)            |
| 15–21   | 3E–3F        | Sipario GutGold                  |
| 22–28   | 4E–4F        | Sipario GutGold                  |
| 29–33   | 5E–5A        | Sipario GutGold                  |
| 34–35   | 5G, 5F       | Bow Brand Pedal Concert Bass Wire |
| 36–40   | 6E–6A        | Bow Brand Pedal Concert Bass Wire |

L&H octave numbering descends E→F within each octave; 4th-octave contains
middle C (4C = C4 in scientific). Total tension: ~1190 lbs (5295 N).

## Coordinate System

- X: along the soundboard, bass (x=0, string 40=6A) to treble (x≈619 mm, string 1=1E)
- Y: harpist (−Y) to audience (+Y); strings at y=0
- Z: vertical, soundboard at z=0, pins above (max z ≈ 1380 mm at bass)

## Soundbox Geometry

Straight-along-X limacon loft. Same convention as clements47:
`r = a + b*cos(theta)` with `a = 2b` and nominal `diameter = 6b` (b =
diameter/6). Bass `diameter = 380 mm` (Prelude soundboard width
14-7/8"), treble `diameter = 102 mm` (4"). 70 cross-sections, linear
taper. Flat side faces up (+Z), bulb hangs below (−Z).

The limacon's chord at z=0 is `4b`, so the visible soundboard width
tapers 253 mm (bass) → 68 mm (treble). Max perpendicular width is
`4.4b` mid-section.

## Clements40.FCStd Model Structure (234 objects)

- **Limacon_01 .. Limacon_70** (70): cross-sections along X
- **Soundbox** (1): Part::Loft through the 70 limacon wires
- **Soundboard** (1): flat 4 mm panel at z=0
- **Str_1E .. Str_6A** (40): string cylinders from grommet to tuning pin
- **Grommet_1E .. Grommet_6A** (40): brass eyelets at z=0 (6 mm OD)
- **Bridge_1E .. Bridge_6A** (40): Y-axis pins at the lever-off vibrating-
  length top; define the open-string pitch
- **Pin_1E .. Pin_6A** (40): vertical tuning pins (7 mm dia) above the bridge
- **Neck** (1): hollow box beam along the pin line (IW 180, IH 220, wall 10)
- **Column** (1): hollow tube at x=−40, floor to neck (OD 55, ID 45)

Objects use `Part::Feature` with explicit `.Shape` — no Sketcher, no Part
Design bodies, no App::Link. Every object is parametrically regenerable
by rerunning `build_clements40.py`.

## Build / Regenerate

```bash
cd /home/clementsj/projects/clements40
# 1. Regenerate spec from clements47
python3 extract_strings.py
# 2. Build the FreeCAD model from scratch
echo 'exec(open("build_clements40.py").read())' | \
  /home/clementsj/projects/clements47/squashfs-root/usr/bin/freecadcmd
```

To open in FreeCAD 1.1:
```bash
~/.local/bin/freecad ~/projects/clements40/Clements40.FCStd
```

## Open Items (2026-04-17)

### Levers not yet modeled
The harpcanada parametric lever (from `3d-lever-manual-book.pdf`) is
the next piece. Each of the 40 strings needs one lever mounted just
below the tuning pin. When engaged it pinches the string at
`clements40.json.strings[i].on` (= `n.z` from the clements47 data),
shortening the vibrating length by one semitone. An `add_levers.py`
script is planned — it should read `clements40.json`, read lever geometry
from the manual (or the STLs if/when downloaded), and place 40 instances.

### STL download incomplete
`Unconfirmed 877837.crdownload` in this directory is an in-progress browser
download, probably the harpcanada lever STL package (217 MB). Rename after
download finishes and commit separately (large binary — may want Git LFS).

### Frequency labels from clements47
The `f`/`n`/`s` frequency fields in the parent clements47.json have an
unusual relationship: `f > n < s` on pitch. The `n` values match
scientific pitch exactly (e.g. c1.n.f = 32.7 Hz = C1). For clements40 we
reuse `f` as "lever off" (top of vibrating length) and `n` as "lever on"
— pitches will need a sanity check when tuning is defined rigorously.

### Soundbox alignment
Unlike clements47 (which has an open Option A/B issue between mm mechanism
and inch soundbox), clements40 is built entirely in mm with a single
coordinate frame — no alignment problem.
