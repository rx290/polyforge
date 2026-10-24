"""Wire routing for printed robots: gauge-aware channel sizing, cable clips, a printable drag chain.

Numbers (wire outer diameters, fill factor, bend radius factor) come from parts/wires.json when it exists
(research notes in docs/robot_wiring.md); the defaults below are the fallbacks.

- bundle(): what runs through a limb (servo cables, power pairs, signal wires) -> area, equivalent diameter
- channel_size(): channel width/height for a bundle at the fill factor, wide enough for a connector to pass
- channel_cutter(): a straight tunnel with a 45 degree roof (prints without support) to subtract from a limb
- service_loop(): slack a joint needs when the cable loops outside instead of passing through the axis
- cable_clip(), zip_tie_anchor(), drag_chain_link(), drag_chain(): printable parts
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from .mounts import CLEAR, _extrude_fused, box, teardrop, vhole
from .catalog import SCREWS

WIRES_JSON = Path(__file__).with_name("parts") / "wires.json"

_DEFAULTS = {
    # outer diameter in mm per AWG, PVC hookup wire and silicone wire
    "awg": {"18": {"od_pvc": 2.0, "od_silicone": 2.3}, "20": {"od_pvc": 1.8, "od_silicone": 1.9},
            "22": {"od_pvc": 1.6, "od_silicone": 1.7}, "24": {"od_pvc": 1.4, "od_silicone": 1.5},
            "26": {"od_pvc": 1.2, "od_silicone": 1.3}, "28": {"od_pvc": 1.0, "od_silicone": 1.1}},
    # flat 3-wire servo leads: width x thickness (mm); connector housing that may have to pass (w x h)
    "servo_cables": {"micro": {"flat": [3.8, 1.2], "awg": "26", "connector": [7.8, 2.6]},
                     "standard": {"flat": [4.8, 1.5], "awg": "22", "connector": [7.8, 2.6]}},
    "fill_factor": 0.4,
    "bend_radius_factor": 10.0,      # flexing cable: bend radius >= factor x outer diameter
}


@lru_cache(maxsize=1)
def rules() -> dict:
    r = json.loads(json.dumps(_DEFAULTS))
    if WIRES_JSON.exists():
        try:
            data = json.loads(WIRES_JSON.read_text())
        except json.JSONDecodeError:
            return r
        for awg, v in (data.get("awg") or {}).items():
            cur = r["awg"].setdefault(str(awg), {})
            cur.update({k: x for k, x in v.items() if x is not None})
        for cls, v in (data.get("servo_cables") or {}).items():
            if isinstance(v, dict):
                r["servo_cables"].setdefault(cls, {}).update({k: x for k, x in v.items() if x is not None})
        for k in ("fill_factor", "bend_radius_factor"):
            if isinstance(data.get(k), (int, float)):
                r[k] = float(data[k])
    return r


def wire_od(awg, insulation="pvc") -> float:
    a = rules()["awg"].get(str(awg))
    if not a:
        raise KeyError(f"no outer diameter for {awg} AWG")
    return float(a.get(f"od_{insulation}") or a.get("od_pvc"))


def bundle(servos=None, pairs=None, wires=None, servo_class="micro", insulation="pvc") -> dict:
    """servos: number of servo leads; pairs: list of AWG for 2-wire power runs; wires: list of AWG singles."""
    r = rules()
    area, largest = 0.0, 0.0
    sc = r["servo_cables"][servo_class]
    if servos:
        w, t = sc["flat"]
        area += servos * w * t
        largest = max(largest, w)
    for awg in pairs or []:
        d = wire_od(awg, insulation); area += 2 * math.pi * d * d / 4; largest = max(largest, 2 * d)
    for awg in wires or []:
        d = wire_od(awg, insulation); area += math.pi * d * d / 4; largest = max(largest, d)
    eq_d = math.sqrt(4 * area / math.pi) if area else 0.0
    return {"area_mm2": round(area, 2), "equivalent_d": round(eq_d, 2), "largest": round(largest, 2),
            "servo_class": servo_class, "count": (servos or 0) + len(pairs or []) + len(wires or [])}


def channel_size(b: dict, pass_connector=False, min_size=4.0) -> tuple[float, float]:
    """Channel (width, height) for a bundle: area / fill factor, at least the widest cable, and when the
    servo plug must be threaded through, at least the plug housing plus clearance."""
    r = rules()
    need = b["area_mm2"] / r["fill_factor"]
    w = max(min_size, b["largest"] + 2 * CLEAR, math.sqrt(need * 1.6))
    h = max(min_size * 0.75, need / w)
    if pass_connector:
        cw, ch = r["servo_cables"][b["servo_class"]]["connector"]
        w, h = max(w, cw + 2 * CLEAR + 0.4), max(h, ch + 2 * CLEAR + 0.4)
    return round(w, 1), round(h, 1)


def min_bend_radius(b: dict) -> float:
    return round(rules()["bend_radius_factor"] * max(b["equivalent_d"], b["largest"] / 2), 1)


def service_loop(angle_deg: float, b: dict, margin=10.0) -> float:
    """Slack (mm) for a cable that loops round a joint of the given travel at the minimum bend radius."""
    return round(math.radians(angle_deg) * min_bend_radius(b) + margin, 1)


def channel_cutter(length, w, h, axis="x", roof=True):
    """Straight tunnel centred on the origin, floor at z = -h/2. The roof is a 45 degree peak so the tunnel
    prints lying down without support; when it prints upright (axis z) it is a plain rectangle."""
    import build123d as bd
    if axis == "z":
        return bd.Pos(0, 0, -length / 2) * bd.Box(w, h, length, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    if roof and h > w / 2:
        prof = bd.Polygon((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2 - w / 2), (0, h / 2),
                          (-w / 2, h / 2 - w / 2), align=None)
    else:                            # too flat for a peak: the roof is a short bridge (w <= bridge limit)
        prof = bd.Rectangle(w, h)
    solid = bd.extrude(bd.Plane.YZ * prof, amount=length / 2, both=True)       # along x
    if axis == "y":
        solid = bd.Rot(0, 0, 90) * solid
    return solid


# ------------------------------------------------------------------ printable parts

def cable_clip(bundle_d=6.0, screw="M3", wall=1.6, height=6.0, opening=0.6):
    """C-clip that snaps over a bundle, with a screw tab. Pure 2D extrusion: prints flat, no support."""
    import build123d as bd
    ri = bundle_d / 2 + CLEAR
    ro = ri + wall
    ring = bd.Circle(ro) - bd.Circle(ri)
    gap = bd.Pos(0, ro) * bd.Rectangle(2 * ri * opening, 2 * wall + 1)          # snap opening at +y
    tab_l = SCREWS[screw]["head"] + 4
    tab = bd.Pos(0, -ro - tab_l / 2 + wall / 2) * bd.Rectangle(tab_l, tab_l)
    clip = _extrude_fused(ring - gap, height) + _extrude_fused(tab - bd.Circle(ri), height)
    # screw goes through the tab sideways (along y), so the clip can sit on a flat limb face
    clip -= bd.Pos(0, -ro - tab_l / 2 + wall / 2, height / 2) * teardrop(SCREWS[screw]["clear"], tab_l + 2)
    return clip, {"bundle_d": bundle_d, "screw": screw}


def cable_clip_flat(bundle_d=6.0, screw="M3", wall=1.6, width=8.0):
    """Saddle clip printed lying down: an arch over the bundle with two screw feet. Arch top is a short bridge."""
    import build123d as bd
    ri = bundle_d / 2 + CLEAR
    span = 2 * ri
    foot = SCREWS[screw]["head"] + 3
    total = span + 2 * wall + 2 * foot
    base = box(total, width, wall)
    arch = box(span + 2 * wall, width, ri + wall + wall) - box(span, width + 2, ri + wall, 0, 0, 0)
    clip = base + arch - box(span, width + 2, ri + wall, 0, 0, 0)
    for sx in (-1, 1):
        clip -= vhole(SCREWS[screw]["clear"], wall, sx * (span / 2 + wall + foot / 2), 0, 0)
    return clip, {"bundle_d": bundle_d, "screw": screw, "fits_under_mm": [round(span, 1), round(ri + wall, 1)]}


def zip_tie_anchor(tie_w=3.0, tie_t=1.4, base=12.0, screw="M3"):
    """Screw-down anchor with a tunnel for a zip tie (tunnel roof is a short bridge)."""
    t = 2.0
    a = box(base, base, t + tie_t + 1.6)
    a -= box(base + 2, tie_w + 0.6, tie_t + 0.4, 0, 0, t)
    a -= vhole(SCREWS[screw]["clear"], t + tie_t + 1.6, 0, 0, 0)
    return a, {"tie": f"{tie_w} mm zip tie"}


def drag_chain_link(inner_w=10.0, inner_h=8.0, pitch=None, plate=1.6, bar=1.6, pin_d=3.0, clearance=0.3):
    """One printable drag-chain link (prints standing on its bottom bar, no support).

    x runs along the chain, the rear pin axis is at x = 0, z = H/2. Each side plate has an inner rear part and an
    outer front part joined by a jog; link n+1's inner part sits inside link n's outer part and its short pin
    clicks into link n's front hole. Bars join the inner parts only, ahead of the next link's swing circle, so
    neighbours never collide at any bend angle (checked in tests/test_robot_wiring.py).
    """
    import build123d as bd
    H = inner_h + 2 * bar
    r = H / 2
    pitch = pitch or round(max(2 * r + 7.0, 12.0), 1)
    y_in, y_mid = inner_w / 2, inner_w / 2 + plate
    y_out0, y_out1 = y_mid + clearance, y_mid + clearance + plate
    jog0, jog1 = pitch - r - clearance - 2.0, pitch - r - clearance

    def rounded(x0, x1, ya, yb, end):
        seg = box(x1 - x0, yb - ya, H, (x0 + x1) / 2, (ya + yb) / 2, 0)
        cx = x0 if end == "rear" else x1
        return seg + bd.Pos(cx, (ya + yb) / 2, r) * bd.Rot(90, 0, 0) * bd.Cylinder(r, yb - ya)

    link = None
    for side in (1, -1):
        inner = rounded(0.0, jog1, y_in, y_mid, "rear")
        outer = rounded(jog0, pitch, y_out0, y_out1, "front")
        jog = box(jog1 - jog0, y_out1 - y_in, H, (jog0 + jog1) / 2, (y_in + y_out1) / 2, 0)
        pin_len = clearance + plate * 0.9 + 0.3                  # 0.3 mm buried in the plate so it fuses
        pin = bd.Pos(0, y_mid - 0.3 + pin_len / 2, r) * bd.Rot(90, 0, 0) * bd.Cylinder(pin_d / 2, pin_len)
        part = inner + outer + jog + pin
        part -= bd.Pos(pitch, (y_out0 + y_out1) / 2, r) * teardrop(pin_d + 2 * clearance, plate + 2)
        if side < 0:
            part = bd.mirror(part, bd.Plane.XZ)
        link = part if link is None else link + part
    bx0, bx1 = r * 0.3, jog1 - 0.5
    link += box(bx1 - bx0, 2 * y_mid, bar, (bx0 + bx1) / 2, 0, 0)            # bottom bar (on the bed)
    link += box(bx1 - bx0, 2 * y_mid, bar, (bx0 + bx1) / 2, 0, H - bar)      # top bar (bridge over inner_w)
    meta = {"inner_w": inner_w, "inner_h": inner_h, "pitch": pitch, "outer_w": round(2 * y_out1, 2),
            "outer_h": round(H, 2), "pin_axis_z": round(r, 2),
            "min_bend_radius_mm": round(pitch / (2 * math.sin(math.radians(15))), 1), "per_link_angle_deg": 30,
            "note": "no bend stops: lay the chain on a surface or run it vertically; limit bend with the cable"}
    return link, meta


def drag_chain_for(b: dict, travel_mm=150.0):
    """Size a drag chain for a bundle: inner section at the fill factor, number of links for the travel."""
    w, h = channel_size(b)
    link, meta = drag_chain_link(inner_w=max(w, 6.0), inner_h=max(h, 5.0))
    n = int(math.ceil(travel_mm / 2 / meta["pitch"] + math.pi * meta["min_bend_radius_mm"] / meta["pitch"])) + 2
    meta["links_needed"] = n
    return link, meta
