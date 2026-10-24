"""Parts library: every entry is complete, sourced, and geometrically sane (robot/parts/*.json)."""
import json
from pathlib import Path

import pytest

from polyforge.robot import catalog

FILES = sorted(catalog.PARTS_DIR.glob("*.json"))
PARTS = [(f.name, p) for f in FILES for p in json.loads(f.read_text()).get("parts", [])]
CATS = {"sbc", "mcu", "camera", "servo", "stepper", "gear_motor", "dc_motor", "driver", "sensor", "power",
        "battery", "connector", "switch", "horn"}
PCB = {"sbc", "mcu", "camera", "driver", "sensor"}
FACES = {"-x", "+x", "-y", "+y", "top", "bottom"}


def test_library_files_exist_and_are_big_enough():
    assert {f.name for f in FILES} >= {"boards.json", "actuators.json", "modules.json"}
    assert len(PARTS) >= 80


def test_keys_are_unique():
    keys = [p["key"] for _, p in PARTS]
    assert len(keys) == len(set(keys)), [k for k in keys if keys.count(k) > 1]


@pytest.mark.parametrize("fname,p", PARTS, ids=[p["key"] for _, p in PARTS])
def test_part_is_complete(fname, p):
    for k in ("key", "label", "category", "dims", "holes", "sources", "verified"):
        assert k in p, k
    assert p["category"] in CATS
    assert isinstance(p["verified"], bool)
    d = p["dims"]
    assert d["length"] and d["length"] > 0 and d["width"] and d["width"] > 0, "dims need length and width"
    h = p["holes"]
    assert isinstance(h.get("positions"), list)
    if not h["positions"]:
        assert (h.get("none_reason") or "").strip(), "empty holes need a reason"
    else:
        assert h.get("diameter") and h["diameter"] > 0
    assert p["sources"] and all(s["url"].startswith("http") for s in p["sources"])
    if p["verified"]:
        assert len(p["sources"]) >= 1


@pytest.mark.parametrize("fname,p", [x for x in PARTS if x[1]["category"] in PCB], ids=lambda v: v if isinstance(v, str) else v["key"])
def test_board_holes_inside_outline_and_keepouts_valid(fname, p):
    L, W = p["dims"]["length"], p["dims"]["width"]
    for x, y in p["holes"]["positions"]:
        assert 0 < x < L and 0 < y < W, (x, y)
    for ko in p.get("keepouts") or []:
        assert ko["face"] in FACES, ko
        x0, y0, z0, x1, y1, z1 = ko["box"]
        assert x1 > x0 and y1 > y0 and z1 > z0, ko


def test_catalog_normalises_every_board_and_servo():
    for k in catalog.keys("servo"):
        s = catalog.servo(k)
        assert s.tab_span > s.L and s.shaft_top > s.tab_z and len(s.holes) >= 2, k
    for cat in PCB:
        for k in catalog.keys(cat):
            b = catalog.board(k)
            assert b.L > 0 and b.W > 0


def test_known_datasheet_numbers():
    pi4 = catalog.board("rpi4b") if catalog.has("rpi4b") else catalog.board("rpi_4b")
    xs = sorted({x for x, _ in pi4.holes}); ys = sorted({y for _, y in pi4.holes})
    assert (pi4.L, pi4.W) == (85.0, 56.0)
    assert xs[-1] - xs[0] == pytest.approx(58.0) and ys[-1] - ys[0] == pytest.approx(49.0)
    n17 = catalog.get("nema17")["mech"]
    assert n17["hole_spacing"] == 31.0 and n17["pilot_d"] == 22.0


def test_counts_report(capsys):
    v = sum(p["verified"] for _, p in PARTS)
    print(f"{len(PARTS)} parts, {v} verified, {len(PARTS) - v} unverified")
