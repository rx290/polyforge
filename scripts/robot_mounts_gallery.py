#!/usr/bin/env python3
"""Generate a mount for every part in the robot library, print-check each STL and draw contact sheets.

usage: robot_mounts_gallery.py [out_dir]   (default /mnt/bulk/ai/robotics/mounts)
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from polyforge.robot import catalog, mounts as M   # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/bulk/ai/robotics/mounts")
groups = {"boards": {}, "servos": {}, "motors": {}, "power": {}}
skipped = []
t0 = time.time()
for cat in ("sbc", "mcu", "camera", "driver", "sensor"):
    for k in catalog.keys(cat):
        try:
            groups["boards"][f"tray_{k}"] = M.board_tray(k)
        except Exception as e:                     # noqa: BLE001
            skipped.append((k, repr(e)))
for k in ("rpi4b", "rpi5", "rpi_zero_2w", "esp32_devkitc_v4", "arduino_uno_r3"):
    base, lid, meta = M.enclosure(k)
    groups["boards"][f"enclosure_{k}"] = (base, meta)
    groups["boards"][f"enclosure_{k}_lid"] = (lid, {})
for k in catalog.keys("servo"):
    groups["servos"][f"cradle_{k}"] = M.servo_cradle(k)
    groups["servos"][f"u_bracket_{k}"] = M.servo_u_bracket(k)
for k in ("sg90", "mg996r"):
    groups["servos"][f"cradle_{k}_hollow"] = M.servo_cradle(k, hollow_axis=True)
    groups["servos"][f"u_bracket_{k}_hollow"] = M.servo_u_bracket(k, hollow_axis=True)
    groups["servos"][f"hollow_pivot_{k}"] = M.hollow_pivot(k)
    groups["servos"][f"horn_coupler_{k}"] = M.horn_coupler(k)
    groups["servos"][f"l_joint_{k}"] = M.servo_l_joint(k)
for k in ("nema17", "nema14", "nema17_pancake"):
    groups["motors"][f"mount_{k}"] = M.nema_mount(k)
groups["motors"]["mount_28byj_48"] = M.byj_mount("28byj_48")
for k in ("n20", "tt_motor", "jga25_370", "motor_130", "motor_180"):
    groups["motors"][f"mount_{k}"] = M.gear_motor_mount(k)
for k in catalog.keys("battery"):
    if k != "cell_18650":
        groups["power"][f"tray_{k}"] = M.battery_tray(k)
summary = {}
for g, parts in groups.items():
    res = M.export_checked(parts, out / g, sheet_title=f"PolyForge robot mounts: {g}")
    summary[g] = {n: r["check"]["ok"] for n, r in res.items()}
    bad = {n: r["check"]["problems"] for n, r in res.items() if not r["check"]["ok"]}
    print(f"{g}: {sum(summary[g].values())}/{len(parts)} pass", bad or "")
(out / "summary.json").write_text(json.dumps({"summary": summary, "skipped": skipped}, indent=1))
print("skipped:", skipped, f"{time.time() - t0:.0f}s")
