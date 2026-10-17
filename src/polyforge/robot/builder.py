"""Robot builder: a printable chassis sized around real parts.

Spec (JSON):
{
  "name": "rover",
  "parts": ["rpi4", "l298n", "battery_18650_2s"],
  "motors": {"type": "tt_motor", "count": 2},          // 2 or 4 drive motors, mounted under the deck
  "caster": true,                                      // front ball-caster boss for 2-wheel builds
  "head": {"servo": "servo_sg90"},                     // optional pan servo pocket on a front neck
  "plate": 4.0, "margin": 6.0, "gap": 6.0,             // deck thickness, edge margin, space between parts
  "overrides": {"tt_motor": {"holes": [[12, 9.35], [30, 9.35]]}}   // your measured numbers win
}
Output: deck, motor brackets, caster boss and neck as separate STEP + STL files, a BOM, and a layout report.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .library import WHEELS, part


@dataclass
class Placed:
    key: str
    x: float
    y: float
    spec: dict = field(default_factory=dict)


def layout(keys, overrides, margin, gap, min_width):
    """Shelf packing: largest parts first, rows along x; returns placements and deck size."""
    items = sorted(keys, key=lambda k: -part(k, overrides)["size"][0] * part(k, overrides)["size"][1])
    width_cap = max(min_width - 2 * margin, max(part(k, overrides)["size"][1] for k in items))
    rows, row, row_w, row_len = [], [], 0.0, 0.0
    for k in items:
        L, W = part(k, overrides)["size"][:2]
        if row and row_w + gap + W > width_cap:
            rows.append((row, row_len)); row, row_w, row_len = [], 0.0, 0.0
        row.append(k); row_w += (gap if len(row) > 1 else 0) + W; row_len = max(row_len, L)
    if row:
        rows.append((row, row_len))
    placed, x = [], margin
    for keys_in_row, row_len in rows:
        y = margin
        for k in keys_in_row:
            p = part(k, overrides); placed.append(Placed(k, x, y, p)); y += p["size"][1] + gap
        x += row_len + gap
    length = x - gap + margin
    width = max(min_width, max(pl.y + pl.spec["size"][1] for pl in placed) + margin)
    return placed, length, width


def build(spec: dict, out: Path) -> dict:
    from build123d import Align, Box, Cylinder, Pos, export_step, export_stl

    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    ov = spec.get("overrides", {})
    plate, margin, gap = spec.get("plate", 4.0), spec.get("margin", 6.0), spec.get("gap", 6.0)
    motors = spec.get("motors", {"type": "tt_motor", "count": 2})
    mot = part(motors["type"], ov); n_mot = int(motors.get("count", 2))
    wheel = float(motors.get("wheel_d", WHEELS.get(motors["type"], 65.0)))
    min_width = 2 * mot["size"][1] + 60.0          # room for two motors side by side under the deck
    placed, L, W = layout(spec["parts"], ov, margin, gap, min_width)
    MIN = (Align.MIN, Align.MIN, Align.MIN)
    deck = Box(L, W, plate, align=MIN)
    bom, warnings, screws = [], [], {}

    for pl in placed:
        p = pl.spec
        bom.append(p["label"])
        if p.get("verify"):
            warnings.append(f"{p['label']}: dimensions vary between makers, measure yours and override '{pl.key}'")
        if p["mount"] == "standoffs":
            for hx, hy in p["holes"]:
                cx, cy = pl.x + hx, pl.y + hy
                ro = max(p["hole_d"] * 1.1, 2.6)
                deck += Pos(cx, cy, plate) * Cylinder(ro, p["standoff"], align=(Align.CENTER, Align.CENTER, Align.MIN))
                deck -= Pos(cx, cy, 0) * Cylinder(p["hole_d"] / 2 * 0.9, plate + p["standoff"], align=(Align.CENTER, Align.CENTER, Align.MIN))
                screws[p["screw"]] = screws.get(p["screw"], 0) + 1
        elif p["mount"] == "cradle":                 # four corner posts with a lip, board drops in
            bl, bw = p["size"][:2]
            for cx, cy in ((pl.x - 1.2, pl.y - 1.2), (pl.x + bl - 1.8, pl.y - 1.2), (pl.x - 1.2, pl.y + bw - 1.8), (pl.x + bl - 1.8, pl.y + bw - 1.8)):
                deck += Pos(cx, cy, plate) * Box(3.0, 3.0, p["standoff"] + 4.0, align=MIN)
        elif p["mount"] == "flat":
            for hx, hy in p["holes"]:
                deck -= Pos(pl.x + hx, pl.y + hy, 0) * Cylinder(p["hole_d"] / 2, plate, align=(Align.CENTER, Align.CENTER, Align.MIN))
                screws[p["screw"]] = screws.get(p["screw"], 0) + 1
        # cable slot next to every part
        deck -= Pos(pl.x + p["size"][0] / 2 - 6, pl.y - gap / 2 - 2, 0) * Box(12, 4, plate, align=MIN)

    # drive motor brackets: L-plates hanging under the deck at the rear corners (and front for 4WD)
    ml, mw, mh = mot["size"]
    xs = [margin + 4.0] + ([L - margin - 4.0 - ml] if n_mot == 4 else [])
    brackets = []
    for bx in xs:
        for side in (0, 1):
            by = 0.0 if side == 0 else W - 3.0
            br = Pos(bx, by, -mh - 2) * Box(ml * 0.6, 3.0, mh + 2, align=MIN)
            for hx, hz in mot["holes"]:
                br -= Pos(bx + hx, by - 0.1, -mh - 2 + hz) * Box(mot["hole_d"], 3.2, mot["hole_d"], align=(Align.CENTER, Align.MIN, Align.CENTER))
            brackets.append(br); screws[mot["screw"] or "clamp"] = screws.get(mot["screw"] or "clamp", 0) + len(mot["holes"])
            bom.append(mot["label"])
    if mot.get("verify"):
        warnings.append(f"{mot['label']}: hole positions vary, measure yours and override '{motors['type']}'")

    parts_out = {"deck": deck}
    for i, br in enumerate(brackets):
        parts_out[f"motor_bracket_{i + 1}"] = br
    if spec.get("caster", n_mot == 2):
        drop = wheel / 2 - mh / 2 - 2 - plate      # caster height that keeps the deck level
        parts_out["caster_boss"] = Pos(L - margin - 12, W / 2 - 12, -max(drop, 4.0)) * Box(24, 24, max(drop, 4.0), align=MIN) \
            - Pos(L - margin, W / 2, -max(drop, 4.0)) * Cylinder(6.5, max(drop, 4.0), align=(Align.CENTER, Align.CENTER, Align.MIN))
        bom.append(f"ball caster, needs {max(drop, 4.0):.0f} mm boss height (12-13 mm ball)")
    if spec.get("head"):
        s = part(spec["head"]["servo"], ov)
        sl, sw, _ = s["size"]
        neck = Pos(L - margin - sl - 8, W / 2 - sw / 2 - 6, plate) * Box(sl + 16, sw + 12, 6, align=MIN)
        neck -= Pos(L - margin - sl - 8 + 8, W / 2 - sw / 2, plate) * Box(sl + 0.4, sw + 0.4, 6, align=MIN)   # servo pocket
        for hx, hy in s["holes"]:
            neck -= Pos(L - margin - sl - 8 + 8 + hx, W / 2 - sw / 2 + hy, plate) * Cylinder(s["hole_d"] / 2, 6, align=(Align.CENTER, Align.CENTER, Align.MIN))
        parts_out["neck_pan_servo"] = neck; bom.append(s["label"] + " (pan)")

    # one printed chassis: brackets, caster boss and neck are fused to the deck (print it upside down, no supports
    # for the hanging brackets); the separate pieces are still exported for anyone who wants to bolt them on
    chassis = parts_out["deck"]
    for name, shape in parts_out.items():
        if name != "deck":
            chassis += shape
    parts_out = {"chassis": chassis, **parts_out}
    files = []
    for name, shape in parts_out.items():
        export_stl(shape, str(out / f"{name}.stl")); export_step(shape, str(out / f"{name}.step"))
        files.append(name)
    report = {"name": spec.get("name", "robot"), "deck_mm": [round(L, 1), round(W, 1), plate], "wheel_d": wheel,
              "layout": [{"part": p.key, "x": round(p.x, 1), "y": round(p.y, 1)} for p in placed],
              "files": files, "bom": bom, "screws": screws, "warnings": warnings}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    return report
