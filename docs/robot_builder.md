# Robot builder

Custom robot bodies sized around the parts you actually own: boards, servos, motors, batteries. Everything is
built with build123d, exported as STL + STEP, and every STL goes through a print check before it is called done.

![quadruped](images/robot/quadruped_mg996r.png)

## Quick start

```bash
polyforge robot examples/robots/quadruped_mg996r_pizero.json --out out/quad     # 12-servo walker
polyforge robot examples/robots/biped_sg90_pizero.json --out out/biped          # Otto-style biped
polyforge robot --list-parts                                                    # the parts library
polyforge robot --mounts mg996r --hollow --out out/mg996r                       # mounts for one part
```

Each robot run writes `print/*.stl` (+ `.step`), `print/contact_sheet.png`, `print/checks.json`,
`assembly.png`, `assembly.step` (quadruped), `BOM.md`, `ASSEMBLY.md` and `report.json`.

## Parts library

`src/polyforge/robot/parts/*.json`, schema in [`parts/SCHEMA.md`](../src/polyforge/robot/parts/SCHEMA.md):
80 parts (36 boards, 20 actuators, 24 modules) with PCB size, hole positions, component heights, connector
keepouts, weight and the source URL for every number. `verified: true` means an official drawing, or two
independent sources that agree (the TT motor, NEMA 17 and 130 motor were measured from Adafruit's own STEP
models). Generic clones (L298N, LM2596, GY-521, most servos) have no maker drawing, so they stay
`verified: false` and every robot report lists them under "measure before printing".

Your own measurements win: put JSON files with the same schema in `~/.config/polyforge/parts/` (or a folder in
`POLYFORGE_PARTS_PATH`), or add `"overrides"` to a spec.

## Mounts (`robot/mounts.py`)

Board trays and enclosures (standoffs with heat-set insert, self-tap or bolt-and-nut holes on the real hole
pattern, snap clips for boards without holes, wall cut-outs from the connector keepouts), servo cradles,
U-brackets, horn couplers, L joints, a hollow pivot for wires through the joint axis, NEMA / 28BYJ-48 / N20 /
TT / JGA25 / 130-can mounts and battery trays. `scripts/robot_mounts_gallery.py` builds a mount for every part
in the library (96 STLs, all pass).

![servo mounts](images/robot/servo_mounts.png)

## Print check (`robot/printcheck.py`)

Watertight, one shell, lowest point on the bed, and the 45 degree rule: a face steeper than 45 degrees must be
on the bed, a bridge between two walls (25 mm max) or a ledge within 3 mm of a wall. Horizontal holes are
teardrops, rails and gussets are 45 degree prisms. The renders are drawn with numpy + PIL, so it all runs
headless.

## Wiring (`robot/wiring.py`, research in [`robot_wiring.md`](robot_wiring.md))

Channels are sized from the bundle (servo leads, power pairs by AWG) at a 40 percent fill factor and widened
for a plug when one has to pass; service loops come from the joint travel and a 10 x OD bend radius. Printable
cable clips, a zip-tie anchor and a drag chain whose links are collision-checked at every bend angle in the
tests. The quadruped femur carries a closed tunnel for the knee lead, the reports give the cable runs and say
when you need extension leads.

## Robots

- **Quadruped** (`robot/quadruped.py`): hip servos in the body end walls, horn coupler + L joint + shoulder
  cradle, femur with the knee cradle on its inner face, tibia with a rubber-foot tip. The body packs the
  controller, PCA9685, regulator, IMU and battery and picks a SpotMicro-like aspect. Optional character shell
  with a 45 degree hipped roof (prints without support). Parts are collision-checked in the assembly.
- **Biped** (`robot/biped.py`): hip servos hang through the floor, battery shelf and electronics deck slide on
  45 degree rails, ultrasonic eyes in the front wall, cradle legs with roll ankles, feet or wheels.
- **Rover** (`robot/builder.py`): deck + motor brackets + caster, unchanged.

![biped](images/robot/biped_sg90.png)

## Limits

- Servo tab holes and spline positions come from open measured models, not maker drawings; tab holes are
  slotted 2 mm to forgive clone differences. Measure your servo before printing a full set.
- The quadruped hip and shoulder joints run on the servo's own bearing (no idler); the U-bracket with idler is
  in the mounts library for heavier builds.
- Drag chain links have no bend stops; run them lying on a surface or vertical.
