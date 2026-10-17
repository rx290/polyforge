"""Real component dimensions for the robot builder (mm, from datasheets).

Board coordinates: x along the long side, y along the short side, origin at the board's lower-left corner,
holes as (x, y). `verify=True` marks numbers that vary between makers or that I could not confirm from
an official drawing: measure your part and override them in the spec (see robot/builder.py).
"""

PARTS = {
    # ---- controllers
    "rpi4": dict(label="Raspberry Pi 4 Model B", size=(85.0, 56.0, 17.0), hole_d=2.7, screw="M2.5",
                 holes=[(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)], mount="standoffs", standoff=6.0),
    "rpi5": dict(label="Raspberry Pi 5", size=(85.0, 56.0, 19.0), hole_d=2.7, screw="M2.5",
                 holes=[(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)], mount="standoffs", standoff=6.0),
    "arduino_uno": dict(label="Arduino Uno R3", size=(68.6, 53.4, 15.0), hole_d=3.2, screw="M3",
                        holes=[(13.97, 2.54), (15.24, 50.8), (66.04, 7.62), (66.04, 35.56)], mount="standoffs", standoff=5.0),
    "arduino_nano": dict(label="Arduino Nano", size=(45.0, 18.0, 8.0), hole_d=1.8, screw="M1.6",
                         holes=[(0.9, 0.9), (44.1, 0.9), (0.9, 17.1), (44.1, 17.1)], mount="cradle", standoff=3.0, verify=True),
    "esp32_devkitc": dict(label="ESP32-DevKitC (38 pin)", size=(55.0, 28.0, 10.0), hole_d=0, screw=None,
                          holes=[], mount="cradle", standoff=3.0, verify=True),
    # ---- drivers / power
    "l298n": dict(label="L298N motor driver module", size=(43.0, 43.0, 27.0), hole_d=3.2, screw="M3",
                  holes=[(3.0, 3.0), (40.0, 3.0), (3.0, 40.0), (40.0, 40.0)], mount="standoffs", standoff=4.0),
    "battery_18650_2s": dict(label="2 x 18650 holder", size=(77.0, 41.0, 20.0), hole_d=3.2, screw="M3",
                             holes=[(17.0, 20.5), (60.0, 20.5)], mount="flat", standoff=0.0, verify=True),
    # ---- servos (body dims; tab holes along x)
    "servo_sg90": dict(label="SG90 micro servo", size=(22.5, 12.2, 22.7), hole_d=2.0, screw="M2",
                       holes=[(-2.65, 6.1), (25.15, 6.1)], mount="pocket", tab_span=32.3, verify=False),
    "servo_mg996r": dict(label="MG996R servo", size=(40.7, 19.7, 42.9), hole_d=4.5, screw="M4",
                         holes=[(-4.4, 4.85), (-4.4, 14.85), (45.1, 4.85), (45.1, 14.85)], mount="pocket", tab_span=54.5),
    # ---- drive motors
    "tt_motor": dict(label="TT gear motor (yellow)", size=(70.0, 22.5, 18.7), hole_d=3.2, screw="M3",
                     holes=[(12.0, 9.35), (29.5, 9.35)], mount="bracket", shaft_x=11.0, verify=True),
    "n20_motor": dict(label="N20 gear motor", size=(24.0, 12.0, 10.0), hole_d=0, screw=None,
                      holes=[], mount="clamp", shaft_x=0.0, verify=True),
}

WHEELS = {"tt_motor": 65.0, "n20_motor": 34.0}   # common wheel diameters for each motor


def part(key, overrides=None):
    if key not in PARTS:
        raise KeyError(f"unknown part {key!r}; known: {', '.join(sorted(PARTS))}")
    p = dict(PARTS[key]); p.update((overrides or {}).get(key, {}))
    return p
