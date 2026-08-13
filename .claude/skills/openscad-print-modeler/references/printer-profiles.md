# Printer profiles

Use these as editable working defaults. Confirm the live machine configuration before a long or dimension-critical print.

## Modified Ender 3 V2

- Motion/firmware: Klipper; modified dual independent Z, linear-rail and IDEX-related hardware may be present depending on the current build state.
- Nominal XY bed: 220 × 220 mm. Do not assume the entire area is reachable after carriage, probe, duct, or IDEX modifications.
- Z: custom 500 mm Z extrusions/lead screws are known, but the collision-free printable height is not yet a confirmed profile value.
- Common nozzle inventory: 0.3, 0.4, 0.5, 0.6, 0.8, and 1.0 mm. The 0.6 mm nozzle is a common active configuration.
- Materials in regular scope: PLA, PET/PETG, and ABS.
- Require current toolhead, nozzle, usable bounds, and intended material before final printability approval.

## QALAM Pro 400

- Nominal class: 400 mm build platform; verify exact usable X/Y/Z and origin from the current machine profile before using near-limit dimensions.
- Stock/default nozzle commonly used by the user: 0.4 mm; 0.6 and 0.8 mm nozzles are available.
- Prefer this printer for detailed work with the 0.4 mm nozzle unless the user's current setup says otherwise.

## Generic fallback

- Ask for usable X/Y/Z, nozzle diameter, extrusion width, layer height, material, enclosure, and intended orientation.
- Starting clearances are hypotheses, not guarantees: about 0.15 mm press, 0.25 mm close, 0.30 mm sliding, and 0.40 mm loose per mating interface. Calibrate for the actual printer/material pair.
- Prefer at least three extrusion lines for structural walls. Compute the wall from actual extrusion width rather than a fixed universal number.
- Heat-set insert and fastener holes must follow the actual hardware datasheet or measured sample.
