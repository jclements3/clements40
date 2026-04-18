"""Build Clements40.FCStd from clements40.json (new design).

Pieces produced:
  - Neck_Plate_Bass and Neck_Plate_Audience: two 10 mm plywood plates, outline
    is the closed cubic-Bezier path exported by make_svg.py under
    clements40.json["harp_3d"]["neck_profile"]. Plates extrude in Y at
    y_centers = -10 and +10 (so inner faces are 10 mm apart, matching the
    10 mm gap the column T and soundbox W tongues fill).
  - Column: 30 mm x 45 mm arc board in the X-Z plane (Y thickness 30 mm,
    radial thickness 45 mm). Endpoints at the neck-bottom and the base
    plane, uniform thickness along the arc.
  - Soundbox: limacon loft using sb_curve.stations from the JSON; each
    limacon cross-section is perpendicular to the local tangent of the
    soundboard curve, with the bulb hanging away from the strings.
  - Strings, grommets, bridge pins, tuning pins: cylinders as before.
  - Soundboard: flat 4 mm panel above the limacons (placeholder).

Deferred: column T extension into the neck gap, soundbox W cap, base-plane
cut, bolts. These come next.

Coordinate system (per CLAUDE.md):
  X: bass (0, string 40=6A) -> treble (619.2, string 1=1E)
  Y: harpist (-Y) -> audience (+Y); strings at y=0
  Z: vertical, soundboard-attach line crosses z=0 between strings

Run:
  echo 'exec(open("build_clements40.py").read())' | \
    /home/clementsj/projects/clements47/squashfs-root/usr/bin/freecadcmd
"""
import json
import math
from pathlib import Path

import FreeCAD  # noqa: F401 (provided by freecadcmd at runtime)
import Part

import os as _os
ROOT      = Path("/home/clementsj/projects/clements40")
# HARP_SPEC env var selects which JSON to build from (default: clements40.json).
# Doc name is derived from the spec stem with its first letter uppercased.
_SPEC_NAME = _os.environ.get("HARP_SPEC", "clements40.json")
SPEC_PATH  = ROOT / _SPEC_NAME
_stem      = Path(_SPEC_NAME).stem
DOC_PATH   = ROOT / (_stem[:1].upper() + _stem[1:] + ".FCStd")

# --- Constants ---
PLATE_T        = 10.0       # plywood plate thickness (Y)
NECK_GAP       = 10.0       # gap between plates
PIN_EXTRA_Z    = 40.0       # tuning pin extends this far above lever-off top
PIN_DIA        = 7.0
GROMMET_OD     = 6.0
GROMMET_ID     = 2.5
GROMMET_THICK  = 3.0
BRIDGE_PIN_DIA = 3.0
BRIDGE_PIN_LEN = 15.0
SOUNDBOARD_THICK = 4.0
N_LIMACON_POINTS = 60       # points per limacon cross-section


def V(x, y, z):
    return FreeCAD.Vector(float(x), float(y), float(z))


# --- Neck plates from the exported Bezier profile ----------------------------
def build_neck_plates(doc, harp_3d):
    segs = harp_3d["neck_profile"]["segments"]
    edges = []
    for seg in segs:
        p0 = V(seg["P0"]["x"], 0.0, seg["P0"]["z"])
        p1 = V(seg["P1"]["x"], 0.0, seg["P1"]["z"])
        p2 = V(seg["P2"]["x"], 0.0, seg["P2"]["z"])
        p3 = V(seg["P3"]["x"], 0.0, seg["P3"]["z"])
        bez = Part.BezierCurve()
        bez.setPoles([p0, p1, p2, p3])
        edges.append(bez.toShape())
    wire = Part.Wire(edges)
    face = Part.Face(wire)

    # Extrude each plate in +Y, centered on its y_center with thickness PLATE_T.
    plate_t = harp_3d["plates"]["thickness_mm"]
    for y_center, suffix in zip(harp_3d["plates"]["y_centers_mm"],
                                ("Bass", "Audience")):
        # face.copy() lives in the y=0 plane; move so its lower-y face is at
        # y_center - plate_t/2, then extrude by plate_t in +Y.
        f2 = face.copy()
        f2.translate(V(0.0, y_center - plate_t / 2.0, 0.0))
        solid = f2.extrude(V(0.0, plate_t, 0.0))
        obj = doc.addObject("Part::Feature", f"Neck_Plate_{suffix}")
        obj.Shape = solid


# --- Column arc board (30 mm x 45 mm, arc in X-Z) ---------------------------
def build_column(doc, harp_3d):
    col = harp_3d["column"]
    axis_x       = col["axis_x"]
    rad_thick    = col["radial_thickness"]    # 45 mm (X-Z thickness)
    y_thick      = col["y_thickness"]         # 30 mm (Y thickness)
    top_z        = col["top_z"]
    bot_z        = col["bot_z"]
    arc_R        = col["arc_R"]
    sag          = col["arc_sag"]
    dx           = rad_thick / 2.0

    # Outer and inner arcs both bow toward -X by `sag` at the chord midpoint.
    col_left_x  = axis_x - dx              # outer arc endpoint x (top & bottom)
    col_right_x = axis_x + dx              # inner arc endpoint x (top & bottom)
    mid_z       = (top_z + bot_z) / 2.0

    outer_mid = V(col_left_x  - sag, 0.0, mid_z)
    inner_mid = V(col_right_x - sag, 0.0, mid_z)

    top_L = V(col_left_x,  0.0, top_z)
    top_R = V(col_right_x, 0.0, top_z)
    bot_L = V(col_left_x,  0.0, bot_z)
    bot_R = V(col_right_x, 0.0, bot_z)

    # Wire goes: top_L -> top_R (line) -> bot_R (inner arc down) ->
    #            bot_L (line) -> top_L (outer arc up)
    top_line   = Part.LineSegment(top_L, top_R).toShape()
    inner_arc  = Part.Arc(top_R, inner_mid, bot_R).toShape()
    bot_line   = Part.LineSegment(bot_R, bot_L).toShape()
    outer_arc  = Part.Arc(bot_L, outer_mid, top_L).toShape()
    wire       = Part.Wire([top_line, inner_arc, bot_line, outer_arc])
    face       = Part.Face(wire)
    face.translate(V(0.0, -y_thick / 2.0, 0.0))
    solid      = face.extrude(V(0.0, y_thick, 0.0))
    obj        = doc.addObject("Part::Feature", "Column")
    obj.Shape  = solid


# --- Soundbox limacon loft along the soundboard curve -----------------------
def limacon_local_points(b, n=N_LIMACON_POINTS):
    """Return (y_local, z_local) points on a limacon r = 2b + b*cos(phi).
    z_local=0 is the chord level; z_local<0 is the bulb side."""
    pts = []
    for i in range(n):
        phi = 2.0 * math.pi * i / n
        r = 2.0 * b + b * math.cos(phi)
        y_local =  r * math.sin(phi)
        z_local = -r * math.cos(phi)
        pts.append((y_local, z_local))
    return pts


def make_limacon_wire(station):
    """Place the limacon cross-section perpendicular to the local tangent.
    Local frame at (x, 0, z):
      X_local  = (0, 1, 0)                 (harp Y axis)
      Z_local  = (tz, 0, -tx)              (normal in X-Z, pointing INTO bulb,
                                            i.e. away from strings)
    A local point (y_l, z_l) maps to global:
      (x + z_l * tz, y_l, z - z_l * tx)
    """
    x0, z0 = station["x"], station["z"]
    tx, tz = station["tx"], station["tz"]
    b      = station["b"]
    pts = []
    for y_l, z_l in limacon_local_points(b):
        gx = x0 + z_l * tz
        gy = y_l
        gz = z0 - z_l * tx
        pts.append(V(gx, gy, gz))
    bsp = Part.BSplineCurve()
    bsp.interpolate(pts, PeriodicFlag=True)
    return bsp.toShape()


def build_soundbox(doc, sb_curve):
    sections = []
    for i, st in enumerate(sb_curve["stations"]):
        shape = make_limacon_wire(st)
        obj = doc.addObject("Part::Feature", f"Limacon_{i + 1:02d}")
        obj.Shape = shape
        sections.append(obj)
    loft = doc.addObject("Part::Loft", "Soundbox")
    loft.Sections = sections
    loft.Solid = True
    loft.Ruled = False
    loft.Closed = False


# --- Strings, grommets, bridge pins, tuning pins ----------------------------
def build_strings(doc, strings):
    for s in strings:
        name = f"Str_{s['harp']}"
        r = max(s["d"], 0.3) / 2.0
        ox, oz = s["grommet"]["x"], s["grommet"]["z"]
        h      = s["off"]["z"] - oz
        total_h = h + PIN_EXTRA_Z
        cyl = Part.makeCylinder(r, total_h, V(ox, 0, oz), V(0, 0, 1))
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = cyl


def build_grommets(doc, strings):
    for s in strings:
        name = f"Grommet_{s['harp']}"
        ox, oz = s["grommet"]["x"], s["grommet"]["z"]
        outer = Part.makeCylinder(GROMMET_OD / 2.0, GROMMET_THICK,
                                  V(ox, 0, oz - GROMMET_THICK / 2.0),
                                  V(0, 0, 1))
        inner = Part.makeCylinder(GROMMET_ID / 2.0, GROMMET_THICK + 0.2,
                                  V(ox, 0, oz - GROMMET_THICK / 2.0 - 0.1),
                                  V(0, 0, 1))
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = outer.cut(inner)


def build_bridge_pins(doc, strings):
    for s in strings:
        name = f"Bridge_{s['harp']}"
        ox, oz = s["off"]["x"], s["off"]["z"]
        pin = Part.makeCylinder(BRIDGE_PIN_DIA / 2.0, BRIDGE_PIN_LEN,
                                V(ox, -BRIDGE_PIN_LEN / 2.0, oz),
                                V(0, 1, 0))
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = pin


def build_tuning_pins(doc, strings):
    for s in strings:
        name = f"Pin_{s['harp']}"
        ox, oz = s["off"]["x"], s["off"]["z"]
        cyl = Part.makeCylinder(PIN_DIA / 2.0, PIN_EXTRA_Z + 30.0,
                                V(ox, 0, oz), V(0, 0, 1))
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = cyl


def main():
    data = json.loads(SPEC_PATH.read_text())
    if "harp_3d" not in data:
        raise RuntimeError("clements40.json has no harp_3d block -- run "
                           "make_svg.py first to export the 3D geometry.")

    strings  = sorted(data["strings"], key=lambda s: s["grommet"]["x"])
    harp_3d  = data["harp_3d"]
    sb_curve = data["sb_curve"]

    doc = FreeCAD.newDocument("Clements40")

    print("building soundbox (limacon loft along the soundboard curve)...")
    build_soundbox(doc, sb_curve)
    print("building neck plates...")
    build_neck_plates(doc, harp_3d)
    print("building column arc board...")
    build_column(doc, harp_3d)
    print("building strings...")
    build_strings(doc, strings)
    print("building grommets...")
    build_grommets(doc, strings)
    print("building bridge pins...")
    build_bridge_pins(doc, strings)
    print("building tuning pins...")
    build_tuning_pins(doc, strings)

    doc.recompute()
    doc.saveAs(str(DOC_PATH))
    print(f"saved {DOC_PATH}")
    print(f"objects: {len(doc.Objects)}")


main()
