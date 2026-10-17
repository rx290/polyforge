"""Robot builder: real hole patterns end up as real holes, everything prints as one solid chassis."""
import json
import pytest

pytest.importorskip("build123d")
import trimesh
from polyforge.robot.builder import build, layout
from polyforge.robot.library import PARTS, part

SPEC = {"name": "t", "parts": ["rpi4", "l298n", "battery_18650_2s"], "motors": {"type": "tt_motor", "count": 2},
        "caster": True, "head": {"servo": "servo_sg90"}}


def test_chassis_is_one_watertight_solid_and_reports_bom(tmp_path):
    r = build(SPEC, tmp_path)
    m = trimesh.load(tmp_path / "chassis.stl")
    assert m.is_watertight and m.body_count == 1
    assert (tmp_path / "chassis.step").stat().st_size > 1000
    assert r["screws"]["M2.5"] == 4 and any("Raspberry Pi 4" in b for b in r["bom"])
    assert any("TT gear motor" in w for w in r["warnings"])   # unverified dims are flagged, not hidden


def test_parts_never_overlap_and_fit_on_the_deck():
    placed, L, W = layout(SPEC["parts"], {}, 6.0, 6.0, 105.0)
    boxes = [(p.x, p.y, p.x + p.spec["size"][0], p.y + p.spec["size"][1]) for p in placed]
    for i, a in enumerate(boxes):
        assert a[2] <= L and a[3] <= W
        for b in boxes[i + 1:]:
            assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]


def test_overrides_win_over_the_library():
    assert part("tt_motor", {"tt_motor": {"holes": [[1, 2]]}})["holes"] == [[1, 2]]
    with pytest.raises(KeyError):
        part("not_a_board")


def test_pi_hole_pattern_matches_the_datasheet():
    xs = sorted({x for x, _ in PARTS["rpi4"]["holes"]}); ys = sorted({y for _, y in PARTS["rpi4"]["holes"]})
    assert xs[1] - xs[0] == pytest.approx(58.0) and ys[1] - ys[0] == pytest.approx(49.0)


def test_biped_parts_print_as_solids_and_every_part_fits(tmp_path):
    from polyforge.robot.biped import build_biped
    r = build_biped({}, tmp_path)
    assert all(r["fits"].values())
    for f in ("body", "lid", "leg_left", "foot_left", "wheel_left"):
        m = trimesh.load(tmp_path / f"{f}.stl")
        assert m.is_watertight and m.body_count == 1, f
