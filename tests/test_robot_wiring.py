"""Wiring: gauge-aware channel sizing, printable clips, drag chain links that mate without collisions."""
import pytest

pytest.importorskip("build123d")
import build123d as bd
import trimesh

from polyforge.robot import wiring as W
from polyforge.robot.printcheck import check_mesh


def _printable(shape, tmp_path, name):
    bb = shape.bounding_box()
    bd.export_stl(bd.Pos(0, 0, -bb.min.Z) * shape, str(tmp_path / f"{name}.stl"), tolerance=0.02, angular_tolerance=0.2)
    r = check_mesh(trimesh.load(tmp_path / f"{name}.stl", force="mesh"))
    assert r["ok"], (name, r["problems"])


def test_rules_come_from_the_research_file():
    r = W.rules()
    assert r["fill_factor"] == pytest.approx(0.4) and r["bend_radius_factor"] >= 5
    assert W.wire_od(22) > W.wire_od(28)


def test_channel_grows_with_the_bundle_and_fits_a_plug_when_asked():
    small = W.bundle(servos=1)
    big = W.bundle(servos=4, pairs=["22"])
    ws, hs = W.channel_size(small); wb, hb = W.channel_size(big)
    assert wb * hb > ws * hs
    assert wb * hb >= big["area_mm2"] / W.rules()["fill_factor"] - 1e-6
    wp, hp = W.channel_size(small, pass_connector=True)
    cw, ch = W.rules()["servo_cables"]["micro"]["connector"]
    assert wp >= cw and hp >= ch


def test_service_loop_scales_with_travel():
    b = W.bundle(servos=2)
    assert W.service_loop(180, b) > W.service_loop(90, b) > 0


@pytest.mark.parametrize("name,fn", [("clip", lambda: W.cable_clip(6)), ("clip_flat", lambda: W.cable_clip_flat(5)),
                                     ("zip", W.zip_tie_anchor), ("link", W.drag_chain_link)])
def test_printable_wiring_parts(tmp_path, name, fn):
    _printable(fn()[0], tmp_path, name)


def test_limb_with_channel_prints(tmp_path):
    from polyforge.robot.mounts import box
    w, h = W.channel_size(W.bundle(servos=3, pairs=["22"]))
    limb = box(60, w + 6, h + 5) - bd.Pos(0, 0, (h + 5) / 2) * W.channel_cutter(70, w, h)
    _printable(limb, tmp_path, "limb")


@pytest.mark.parametrize("angle", [0, 20, 30, -30])
def test_drag_chain_links_mate_without_collision(angle):
    link, m = W.drag_chain_link()
    p, r = m["pitch"], m["pin_axis_z"]
    nxt = bd.Pos(p, 0, r) * bd.Rot(0, angle, 0) * bd.Pos(0, 0, -r) * link
    inter = link & nxt
    vol = sum(s.volume for s in inter.solids()) if inter else 0.0
    assert vol < 0.01
