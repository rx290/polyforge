from .base import Param, Template, freecad_macro, register


def _generate(p: dict) -> str:
    return f"""// PolyForge template: cable_comb
// units: millimetres
// A bar with evenly spaced open-top slots for routing/organizing cable bundles.

/* [Primary dimensions] */
comb_width = {p['comb_width']};     // X, overall length of the bar
comb_depth = {p['comb_depth']};     // Y, bar thickness (front to back)
comb_height = {p['comb_height']};   // Z, overall height

/* [Slots] */
slot_count = {p['slot_count']};
slot_width = {p['slot_width']};     // clear width of each slot (cable bundle diameter + clearance)
slot_depth = {p['slot_depth']};     // how far each slot cuts down from the top
base_height = {p['base_height']};   // solid strip left at the bottom, must exceed 0

/* [Quality] */
$fn = $preview ? 32 : 96;
eps = 0.01;

assert(slot_count >= 1, "slot_count must be at least 1");
assert(base_height > 0 && base_height < comb_height, "base_height must be a positive fraction of comb_height");
assert(slot_depth <= comb_height - base_height, "slot_depth cannot exceed the room above base_height");
assert(slot_width > 0, "slot_width must be positive");

module comb_bar() {{
    cube([comb_width, comb_depth, comb_height]);
}}

module slots() {{
    margin = comb_width / (slot_count * 2);
    step = comb_width / slot_count;
    for (i = [0 : slot_count - 1]) {{
        x = margin + i * step - slot_width / 2;
        translate([x, -eps, comb_height - slot_depth])
            cube([slot_width, comb_depth + 2 * eps, slot_depth + eps]);
    }}
}}

difference() {{
    comb_bar();
    slots();
}}
"""


def _generate_freecad(p: dict) -> str:
    param_lines = (
        f"comb_width = {p['comb_width']}\n"
        f"comb_depth = {p['comb_depth']}\n"
        f"comb_height = {p['comb_height']}\n"
        f"slot_count = {p['slot_count']}\n"
        f"slot_width = {p['slot_width']}\n"
        f"slot_depth = {p['slot_depth']}\n"
        f"base_height = {p['base_height']}\n\n"
        'assert slot_count >= 1, "slot_count must be at least 1"\n'
        'assert 0 < base_height < comb_height, "base_height must be a positive fraction of comb_height"\n'
        'assert slot_depth <= comb_height - base_height, "slot_depth cannot exceed the room above base_height"\n'
        'assert slot_width > 0, "slot_width must be positive"'
    )
    body = """bar = Part.makeBox(comb_width, comb_depth, comb_height)

margin = comb_width / (slot_count * 2)
step = comb_width / slot_count
for i in range(slot_count):
    x = margin + i * step - slot_width / 2
    slot = Part.makeBox(
        slot_width, comb_depth + 2 * eps, slot_depth + eps,
        FreeCAD.Vector(x, -eps, comb_height - slot_depth),
    )
    bar = bar.cut(slot)
shape = bar"""
    return freecad_macro("cable_comb", param_lines, body)


TEMPLATE = register(
    Template(
        key="cable_comb",
        title="Cable management comb",
        keywords=("cable comb", "comb", "cable management", "cable organizer", "wire comb"),
        params=[
            Param("comb_width", 80, description="X, overall length"),
            Param("comb_depth", 10, description="Y, bar thickness"),
            Param("comb_height", 20, description="Z, overall height"),
            Param("slot_count", 6, description="number of cable slots"),
            Param("slot_width", 4, description="clear width of each slot"),
            Param("slot_depth", 12, description="depth each slot cuts from the top"),
            Param("base_height", 6, description="solid strip left at the bottom"),
        ],
        generate=_generate,
        generate_freecad=_generate_freecad,
        description="A slotted comb bar for routing and separating cable bundles.",
    )
)
