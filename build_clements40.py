"""Build Clements40.FCStd from clements40.json.

Generates a 40-string lever harp CAD model with:
  - limacon-taper soundbox (straight centerline along X, bass=380mm dia, treble=102mm dia)
  - 40 strings (cylinders from grommet at z=0 to tuning pin above)
  - bridge pins (top of vibrating length when lever off)
  - tuning pins
  - grommets at the soundboard
  - flat soundboard panel
  - box-beam neck along the pin line
  - column at the bass end
  - pedestal base

No discs/axles/pedals (this is a lever harp -- levers added separately in add_levers.py).
"""
import json
import math
from pathlib import Path

import FreeCAD  # noqa: F401 (provided by freecadcmd at runtime)
import Part

ROOT = Path("/home/clementsj/projects/clements40")
SPEC_PATH = ROOT / "clements40.json"
DOC_PATH  = ROOT / "Clements40.FCStd"

N_LIMACON_STATIONS = 70   # cross-sections along soundbox
N_LIMACON_POINTS   = 60   # points per cross-section
PIN_EXTRA_Z        = 40.0 # tuning pin extends this far above the "off" vibrating-length top
PIN_DIA            = 7.0
GROMMET_OD         = 6.0
GROMMET_ID         = 2.5
GROMMET_THICK      = 3.0
BRIDGE_PIN_DIA     = 3.0
BRIDGE_PIN_LEN     = 15.0
SOUNDBOARD_THICK   = 4.0
NECK_IW            = 180.0   # internal width (Y)
NECK_IH            = 220.0   # internal height (perpendicular to neck axis)
NECK_WALL          = 10.0
COLUMN_OD          = 55.0
COLUMN_ID          = 45.0
COLUMN_X           = -40.0   # bass side of soundbox


def limacon_points(b, a_over_b=2.0, n=N_LIMACON_POINTS):
    """Return unique limacon points (periodic -- no duplicate closing point)."""
    a = a_over_b * b
    pts = []
    for i in range(n):
        phi = 2.0 * math.pi * i / n
        r = a + b * math.cos(phi)
        # orient: phi=0 -> -z (bulb), phi=pi -> +z (flat top)
        y =  r * math.sin(phi)
        z = -r * math.cos(phi)
        pts.append((y, z))
    return pts


def make_limacon_wire(x_station, b):
    pts = limacon_points(b)
    vecs = [FreeCAD.Vector(x_station, y, z) for (y, z) in pts]
    bsp = Part.BSplineCurve()
    bsp.interpolate(vecs, PeriodicFlag=True)
    return bsp.toShape()


def build_soundbox(doc, length, bass_dia, treble_dia):
    sections = []
    for i in range(N_LIMACON_STATIONS):
        t = i / (N_LIMACON_STATIONS - 1)
        dia = bass_dia + (treble_dia - bass_dia) * t
        b = dia / 6.0
        x = t * length
        shape = make_limacon_wire(x, b)
        obj = doc.addObject("Part::Feature", f"Limacon_{i + 1:02d}")
        obj.Shape = shape
        sections.append(obj)

    loft = doc.addObject("Part::Loft", "Soundbox")
    loft.Sections = sections
    loft.Solid = True
    loft.Ruled = False
    loft.Closed = False


def build_soundboard(doc, length, bass_dia, treble_dia):
    # Flat spruce panel chord-width = 4b along soundboard plane (z=0)
    margin = 20.0
    bass_half = 4.0 * bass_dia / 6.0 / 2.0
    treble_half = 4.0 * treble_dia / 6.0 / 2.0
    # Trapezoid in x-y plane, extruded in +z
    poly = [
        FreeCAD.Vector(-margin,        -bass_half - margin, 0),
        FreeCAD.Vector(-margin,         bass_half + margin, 0),
        FreeCAD.Vector(length + margin, treble_half + margin, 0),
        FreeCAD.Vector(length + margin,-treble_half - margin, 0),
        FreeCAD.Vector(-margin,        -bass_half - margin, 0),
    ]
    wire = Part.makePolygon(poly)
    face = Part.Face(wire)
    sb = face.extrude(FreeCAD.Vector(0, 0, SOUNDBOARD_THICK))
    obj = doc.addObject("Part::Feature", "Soundboard")
    obj.Shape = sb


def build_strings(doc, strings):
    for s in strings:
        name = f"Str_{s['harp']}"
        r = max(s["d"], 0.3) / 2.0
        ox = s["grommet"]["x"]
        oz = s["grommet"]["z"]
        h  = s["off"]["z"] - oz  # from grommet to bridge (top of vibrating length)
        # Extend beyond the bridge up to the tuning pin
        total_h = h + PIN_EXTRA_Z
        cyl = Part.makeCylinder(r, total_h,
                                FreeCAD.Vector(ox, 0, oz),
                                FreeCAD.Vector(0, 0, 1))
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = cyl


def build_grommets(doc, strings):
    for s in strings:
        name = f"Grommet_{s['harp']}"
        ox = s["grommet"]["x"]
        outer = Part.makeCylinder(GROMMET_OD / 2.0, GROMMET_THICK,
                                  FreeCAD.Vector(ox, 0, -GROMMET_THICK / 2.0),
                                  FreeCAD.Vector(0, 0, 1))
        inner = Part.makeCylinder(GROMMET_ID / 2.0, GROMMET_THICK + 0.1,
                                  FreeCAD.Vector(ox, 0, -GROMMET_THICK / 2.0 - 0.05),
                                  FreeCAD.Vector(0, 0, 1))
        ring = outer.cut(inner)
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = ring


def build_bridge_pins(doc, strings):
    """Small horizontal pin at top of vibrating length (lever-off bridge). Axis along +Y."""
    for s in strings:
        name = f"Bridge_{s['harp']}"
        ox = s["off"]["x"]
        oz = s["off"]["z"]
        pin = Part.makeCylinder(BRIDGE_PIN_DIA / 2.0, BRIDGE_PIN_LEN,
                                FreeCAD.Vector(ox, -BRIDGE_PIN_LEN / 2.0, oz),
                                FreeCAD.Vector(0, 1, 0))
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = pin


def build_tuning_pins(doc, strings):
    for s in strings:
        name = f"Pin_{s['harp']}"
        ox = s["off"]["x"]
        oz = s["off"]["z"]
        # pin extends from bridge up through the neck
        cyl = Part.makeCylinder(PIN_DIA / 2.0, PIN_EXTRA_Z + 30.0,
                                FreeCAD.Vector(ox, 0, oz),
                                FreeCAD.Vector(0, 0, 1))
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = cyl


def build_neck(doc, strings):
    """Hollow box beam running along the pin line, bass-to-treble."""
    # Use first (top treble) and last (bottom bass) string pin positions as endpoints
    bass = strings[-1]   # 6A
    treble = strings[0]  # 1E
    bass_pt = FreeCAD.Vector(bass["off"]["x"], 0, bass["off"]["z"] + PIN_EXTRA_Z)
    treble_pt = FreeCAD.Vector(treble["off"]["x"], 0, treble["off"]["z"] + PIN_EXTRA_Z)
    axis = treble_pt - bass_pt
    length = axis.Length
    axis.normalize()

    outer_w = NECK_IW + 2 * NECK_WALL
    outer_h = NECK_IH + 2 * NECK_WALL
    # build neck centered along X-axis locally, then transform
    outer = Part.makeBox(length, outer_w, outer_h,
                         FreeCAD.Vector(0, -outer_w / 2.0, -outer_h / 2.0))
    inner = Part.makeBox(length + 2, NECK_IW, NECK_IH,
                         FreeCAD.Vector(-1, -NECK_IW / 2.0, -NECK_IH / 2.0))
    hollow = outer.cut(inner)

    # Transform: rotate +X axis to align with `axis`, translate to bass_pt
    placement = FreeCAD.Placement()
    placement.Base = bass_pt
    # Compute rotation that maps (1,0,0) to axis
    src = FreeCAD.Vector(1, 0, 0)
    rot = FreeCAD.Rotation(src, axis)
    placement.Rotation = rot
    hollow.Placement = placement

    obj = doc.addObject("Part::Feature", "Neck")
    obj.Shape = hollow


def build_column(doc, strings):
    """Hollow vertical tube at the bass end from soundbox to neck."""
    bass = strings[-1]  # 6A is bass / longest string
    top_z = bass["off"]["z"] + PIN_EXTRA_Z + NECK_IH
    outer = Part.makeCylinder(COLUMN_OD / 2.0, top_z,
                              FreeCAD.Vector(COLUMN_X, 0, 0),
                              FreeCAD.Vector(0, 0, 1))
    inner = Part.makeCylinder(COLUMN_ID / 2.0, top_z + 2,
                              FreeCAD.Vector(COLUMN_X, 0, -1),
                              FreeCAD.Vector(0, 0, 1))
    tube = outer.cut(inner)
    obj = doc.addObject("Part::Feature", "Column")
    obj.Shape = tube


def main():
    data = json.loads(SPEC_PATH.read_text())
    strings = data["strings"]  # already ordered 1 (top) to 40 (bottom)
    sb = data["sb"]

    doc = FreeCAD.newDocument("Clements40")

    print("building soundbox...")
    build_soundbox(doc, sb["length"], sb["bass_dia"], sb["treble_dia"])
    print("building soundboard...")
    build_soundboard(doc, sb["length"], sb["bass_dia"], sb["treble_dia"])
    print("building strings...")
    build_strings(doc, strings)
    print("building grommets...")
    build_grommets(doc, strings)
    print("building bridge pins...")
    build_bridge_pins(doc, strings)
    print("building tuning pins...")
    build_tuning_pins(doc, strings)
    print("building neck...")
    build_neck(doc, strings)
    print("building column...")
    build_column(doc, strings)

    doc.recompute()
    doc.saveAs(str(DOC_PATH))
    print(f"saved {DOC_PATH}")
    print(f"objects: {len(doc.Objects)}")


main()
