"""Mount generators: real library parts in, watertight single-body support-free STLs out."""
import pytest

pytest.importorskip("build123d")
import trimesh

from polyforge.robot import catalog, mounts as M
from polyforge.robot.printcheck import check_mesh


def _ok(shape, tmp_path, name):
    from build123d import Pos, export_stl
    bb = shape.bounding_box()
    shape = Pos(0, 0, -bb.min.Z) * shape
    export_stl(shape, str(tmp_path / f"{name}.stl"), tolerance=0.02, angular_tolerance=0.2)
    r = check_mesh(trimesh.load(tmp_path / f"{name}.stl", force="mesh"))
    assert r["ok"], (name, r["problems"], r["unsupported_regions"])
    return r


def test_check_mesh_catches_overhangs_and_allows_bridges(tmp_path):
    from build123d import Align, Box, Pos
    C = (Align.CENTER, Align.CENTER, Align.MIN)
    t_shape = Box(10, 10, 10, align=C) + Pos(0, 0, 10) * Box(40, 40, 3, align=C)
    bridge = Box(40, 30, 10, align=C) - Pos(0, 0, 3) * Box(20, 40, 4, align=C)
    from build123d import export_stl
    export_stl(t_shape, str(tmp_path / "t.stl")); export_stl(bridge, str(tmp_path / "b.stl"))
    assert not check_mesh(trimesh.load(tmp_path / "t.stl"))["supports_free"]
    assert check_mesh(trimesh.load(tmp_path / "b.stl"))["ok"]


@pytest.mark.parametrize("key,fix", [("rpi4b", "insert"), ("rpi_zero_2w", "clear"), ("esp32_devkitc_v4", "insert"),
                                     ("pca9685", "tap"), ("arduino_uno_r3", "insert")])
def test_board_trays_print_and_hit_the_real_holes(tmp_path, key, fix):
    tray, meta = M.board_tray(key, fix=fix)
    _ok(tray, tmp_path, key)
    b = catalog.board(key)
    if b.holes:
        assert sum(v for k, v in meta["screws"].items() if "tray" not in k) == len(b.holes)


def test_enclosure_cuts_every_side_connector(tmp_path):
    base, lid, meta = M.enclosure("rpi4b")
    _ok(base, tmp_path, "enc"); _ok(lid, tmp_path, "lid")
    sides = [k["name"] for k in catalog.board("rpi4b").keepouts if k["face"] in ("-x", "+x", "-y", "+y")]
    assert sides and set(meta["wall_cutouts"]) == set(sides)


@pytest.mark.parametrize("servo", ["sg90", "mg996r"])
@pytest.mark.parametrize("hollow", [False, True])
def test_servo_joint_parts_print(tmp_path, servo, hollow):
    cradle, cm = M.servo_cradle(servo, hollow_axis=hollow)
    u, um = M.servo_u_bracket(servo, hollow_axis=hollow)
    _ok(cradle, tmp_path, "cradle"); _ok(u, tmp_path, "u")
    s = catalog.servo(servo)
    # the U-bracket gap holds cradle floor + servo up to its spline + horn
    assert um["gap"] > cm["floor"] + s.shaft_top
    if hollow:
        _ok(M.hollow_pivot(servo)[0], tmp_path, "pivot")
        assert cm["hollow_axis"]["bore_d"] > cm["hollow_axis"]["channel_d"]


@pytest.mark.parametrize("fn,key", [(M.nema_mount, "nema17"), (M.byj_mount, "28byj_48"), (M.gear_motor_mount, "n20"),
                                    (M.gear_motor_mount, "tt_motor"), (M.gear_motor_mount, "motor_130"),
                                    (M.battery_tray, "battery_18650_2s_holder"), (M.battery_tray, "lipo_2s_2200")])
def test_motor_and_battery_mounts_print(tmp_path, fn, key):
    shape, _ = fn(key)
    _ok(shape, tmp_path, key)
