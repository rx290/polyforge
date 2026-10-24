# Robot parts library schema

One JSON file per category group in this folder: `{"group": "<name>", "parts": [ <part>, ... ]}`.
All lengths in mm, weights in g. Every number should come from an official datasheet or mechanical drawing
when one exists, cross-checked with a second source.

## Part

```json
{
  "key": "rpi4b",                         // unique snake_case id, used in robot specs
  "label": "Raspberry Pi 4 Model B",
  "category": "sbc",                      // sbc | mcu | camera | servo | stepper | gear_motor | dc_motor |
                                          // driver | sensor | power | battery | connector | switch | horn
  "aliases": ["rpi4"],                    // optional older keys
  "dims": {"length": 85.0, "width": 56.0, "thickness": 1.4,
           "height_top": 16.0,            // tallest part above the PCB top face (or body height for non-PCB parts)
           "height_bottom": 2.0},         // tallest part below the PCB bottom face (pins, SD card), 0 if none
  "holes": {"diameter": 2.7, "screw": "M2.5",
            "positions": [[3.5, 3.5], [61.5, 3.5], [3.5, 52.5], [61.5, 52.5]],
            "none_reason": ""},           // required non-empty when positions is empty
  "keepouts": [                           // connectors that need a hole in an enclosure wall or clear space
    {"name": "USB-C power", "face": "-y", "box": [3.5, -1.0, 0.0, 12.5, 7.0, 3.2]}
  ],
  "mech": {},                             // category-specific numbers, see below
  "weight_g": 46.0,                       // null if no source gives it
  "sources": [{"url": "https://...", "what": "mechanical drawing PDF"}, {"url": "...", "what": "cross-check"}],
  "verified": true,                       // true only when an official drawing/datasheet gives the numbers, or two
                                          // independent sources agree; generic clones without one maker stay false
  "notes": "what is uncertain or varies between makers"
}
```

## Coordinates

- Boards and modules: origin at the PCB lower-left corner seen from the top, x along the long edge, y along the short
  edge, z = 0 on the PCB top face (bottom face is z = -thickness). Holes are `[x, y]` hole centres.
- Keepout `box` is `[x0, y0, z0, x1, y1, z1]` in the same frame; `face` is the side the connector is reached from
  (`-x`, `+x`, `-y`, `+y`, `top`, `bottom`). A box may stick out past the PCB edge (USB, SD card overhang).
- Servos: body box origin at the body's lower-left-bottom corner, x along the mounting-tab axis, y across, z up to the
  output shaft side. Tab holes as `[x, y]` (x can be negative or longer than the body).
- Motors: see mech keys; face holes are `[dx, dy]` from the shaft centre on the mounting face.

## mech keys per category

- servo: `tab_span` (overall length over tabs), `tab_thickness`, `tab_z` (tab underside above body bottom),
  `shaft_x`, `shaft_y`, `shaft_top` (spline top above body bottom), `spline_teeth`, `spline_od`, `horn_screw`,
  `torque_kgcm` ({"4.8V": x, "6V": y}), `voltage` ([min, max]), `stall_current_a`, `rotation_deg`, `gear`.
- stepper (NEMA): `face`, `body_length`, `hole_spacing`, `hole_thread`, `hole_depth`, `pilot_d`, `pilot_h`,
  `shaft_d`, `shaft_len`, `shaft_flat`, `face_holes`.
- stepper (28BYJ-48): `body_d`, `body_h`, `ear_hole_spacing`, `ear_hole_d`, `shaft_offset`, `shaft_d`, `shaft_flats`,
  `shaft_len`, `boss_d`, `boss_h`.
- gear_motor / dc_motor: `shaft_d`, `shaft_flat` (D-flat size or null), `shaft_len`, `shaft_pos` ([x, y, z] in body
  frame), `shaft_axis` ("x", "y" or "z"), `face_holes`, `face_hole_thread`, `can_d`, `can_flats`, `gearbox_len`,
  `voltage`, `rpm`, `stall_current_a`.
- horn: `spline_teeth`, `spline_od`, `hub_d`, `hub_h`, `arm_len`, `hole_pitch`, `hole_d`.
- battery: `cells`, `cell` ("18650", "AA", "LiPo"), `voltage_nominal`, `capacity_mah`, `connector`.
- connector: `pitch`, `housing` dims, `current_a`, `wire_awg`.
