"""Loader for the JSON parts library in robot/parts/*.json (schema in parts/SCHEMA.md).

`get(key)` returns the raw part dict, `servo(key)` / `board(key)` return normalised geometry the mount
generators use, `legacy(key)` converts a library part to the older dict format used by builder.py/biped.py.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PARTS_DIR = Path(__file__).with_name("parts")
USER_PARTS_DIR = Path.home() / ".config/polyforge/parts"     # your own measured parts, same schema, win over the library


def _dirs():
    extra = [Path(p) for p in os.environ.get("POLYFORGE_PARTS_PATH", "").split(os.pathsep) if p]
    return [PARTS_DIR, USER_PARTS_DIR, *extra]

# screw sizes: clearance hole, pilot for self-tapping into plastic, heat-set insert hole (dia, depth), head dia
SCREWS = {
    "M1.6": dict(clear=1.9, tap=1.3, insert=(2.6, 3.0), head=3.2, nut=3.2),
    "M2": dict(clear=2.4, tap=1.7, insert=(3.2, 4.0), head=3.8, nut=4.0),
    "M2.5": dict(clear=2.9, tap=2.1, insert=(3.6, 4.5), head=4.5, nut=5.0),
    "M3": dict(clear=3.4, tap=2.6, insert=(4.0, 5.7), head=5.5, nut=5.5),
    "M4": dict(clear=4.5, tap=3.4, insert=(5.6, 8.1), head=7.0, nut=7.0),
}


def screw_for_hole(d):
    """Best screw size for a board hole of diameter d."""
    for name, lim in (("M1.6", 2.0), ("M2", 2.5), ("M2.5", 3.0), ("M3", 3.8), ("M4", 99)):
        if d <= lim:
            return name
    return "M3"


@lru_cache(maxsize=1)
def _load():
    parts = {}
    for f in [f for d in _dirs() if d.is_dir() for f in sorted(d.glob("*.json"))]:
        data = json.loads(f.read_text())
        for p in data.get("parts", []):
            p = dict(p); p["_file"] = f.name
            parts[p["key"]] = p
    aliases = {}
    for k, p in parts.items():
        for a in p.get("aliases") or []:
            aliases.setdefault(a, k)
    return parts, aliases


def reload():
    _load.cache_clear()


def keys(category=None):
    parts, _ = _load()
    return sorted(k for k, p in parts.items() if category is None or p.get("category") == category)


def get(key):
    parts, aliases = _load()
    k = key if key in parts else aliases.get(key)
    if k is None:
        raise KeyError(f"unknown part {key!r}; see `polyforge robot --list-parts`")
    return parts[k]


def has(key):
    parts, aliases = _load()
    return key in parts or key in aliases


def _num(v, default):
    return default if v is None else float(v)


@dataclass
class Board:
    key: str
    label: str
    L: float
    W: float
    T: float
    top: float
    bottom: float
    hole_d: float
    screw: str
    holes: list
    keepouts: list = field(default_factory=list)
    verified: bool = False
    weight: float | None = None


def board(key, overrides=None) -> Board:
    p = dict(get(key)); p.update((overrides or {}).get(key, {}))
    d, h = p["dims"], p.get("holes") or {}
    hd = _num(h.get("diameter"), 0.0)
    return Board(key=p["key"], label=p["label"], L=float(d["length"]), W=float(d["width"]),
                 T=_num(d.get("thickness"), 1.6), top=_num(d.get("height_top"), 10.0),
                 bottom=_num(d.get("height_bottom"), 2.0), hole_d=hd,
                 screw=h.get("screw") or (screw_for_hole(hd) if hd else "M2.5"),
                 holes=[tuple(map(float, xy)) for xy in h.get("positions") or []],
                 keepouts=p.get("keepouts") or [], verified=bool(p.get("verified")), weight=p.get("weight_g"))


@dataclass
class Servo:
    key: str
    label: str
    L: float            # body along the tab axis
    W: float
    H: float            # body height, bottom to the top of the case (without the spline)
    tab_span: float
    tab_t: float
    tab_z: float        # tab underside above the body bottom
    hole_d: float
    holes: list         # [x, y] tab holes in the body frame
    shaft_x: float
    shaft_y: float
    shaft_top: float    # spline top above the body bottom
    spline_od: float
    spline_teeth: int | None
    horn_screw: str
    weight: float | None
    verified: bool


# fallback numbers per size class when a datasheet leaves a field out
_SERVO_DEFAULTS = {
    "micro": dict(tab_t=2.5, tab_z=15.9, spline_od=4.8, shaft_extra=4.0, horn_screw="M2"),
    "standard": dict(tab_t=2.5, tab_z=26.6, spline_od=5.8, shaft_extra=5.0, horn_screw="M3"),
}


def servo(key, overrides=None) -> Servo:
    p = dict(get(key)); p.update((overrides or {}).get(key, {}))
    d, m, h = p["dims"], p.get("mech") or {}, p.get("holes") or {}
    L, W = float(d["length"]), float(d["width"])
    H = _num(d.get("height_top"), _num(d.get("thickness"), 22.0))
    cls = "micro" if L < 30 else "standard"
    df = _SERVO_DEFAULTS[cls]
    tab_span = _num(m.get("tab_span"), L + (10 if cls == "micro" else 14))
    hole_d = _num(h.get("diameter"), 2.0 if cls == "micro" else 4.5)
    holes = [tuple(map(float, xy)) for xy in h.get("positions") or []]
    if not holes:
        inset = (tab_span - L) / 4
        holes = [(-inset, W / 2), (L + inset, W / 2)]
    shaft_x = _num(m.get("shaft_x"), L / 4)
    shaft_top = _num(m.get("shaft_top"), H + df["shaft_extra"])
    return Servo(key=p["key"], label=p["label"], L=L, W=W, H=H, tab_span=tab_span,
                 tab_t=_num(m.get("tab_thickness"), df["tab_t"]), tab_z=_num(m.get("tab_z"), df["tab_z"]),
                 hole_d=hole_d, holes=holes, shaft_x=shaft_x, shaft_y=_num(m.get("shaft_y"), W / 2),
                 shaft_top=shaft_top, spline_od=_num(m.get("spline_od"), df["spline_od"]),
                 spline_teeth=m.get("spline_teeth"), horn_screw=m.get("horn_screw") or df["horn_screw"],
                 weight=p.get("weight_g"), verified=bool(p.get("verified")))


def legacy(key, overrides=None) -> dict:
    """Library part in the older builder.py dict format (size, holes, hole_d, screw, mount, standoff ...)."""
    p = get(key)
    cat = p.get("category")
    if cat == "servo":
        s = servo(key, overrides)
        return dict(label=s.label, size=(s.L, s.W, s.H), hole_d=s.hole_d, screw=s.horn_screw, holes=s.holes,
                    mount="pocket", tab_span=s.tab_span, tab_z=s.tab_z, tab_t=s.tab_t, shaft_x=s.shaft_x,
                    horn_hub_d=s.spline_od + 2.4, verify=not s.verified)
    d, h = p["dims"], p.get("holes") or {}
    hd = _num(h.get("diameter"), 0.0)
    height = _num(d.get("height_top"), 10.0) + _num(d.get("thickness"), 0.0) if cat in (
        "sbc", "mcu", "driver", "sensor", "power", "camera") else _num(d.get("height_top"), 10.0)
    holes = [tuple(map(float, xy)) for xy in h.get("positions") or []]
    mount = "standoffs" if holes and hd >= 1.8 else ("flat" if cat == "battery" else "cradle")
    out = dict(label=p["label"], size=(float(d["length"]), float(d["width"]), height), hole_d=hd,
               screw=h.get("screw") or (screw_for_hole(hd) if hd else None), holes=holes, mount=mount,
               standoff=4.0 if mount != "flat" else 0.0, verify=not p.get("verified"))
    m = p.get("mech") or {}
    for k in ("eye_d", "eye_spacing"):
        if k in m:
            out[k] = m[k]
    return out
