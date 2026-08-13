<p align="center">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-blue">
  <img alt="Built for Claude Code" src="https://img.shields.io/badge/built%20for-Claude%20Code-5A67D8">
  <img alt="Also works in ChatGPT/Codex" src="https://img.shields.io/badge/also%20works%20in-ChatGPT%20%2F%20Codex-10a37f">
  <img alt="PRs Welcome" src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg">
</p>

<p align="center">
  <b>A Claude Code / ChatGPT / Codex skill for creating, understanding, reconstructing, repairing, and printer-checking OpenSCAD models.</b><br>
  Point it at a description, a set of measurements, an existing <code>.scad</code>, or a raw <code>.stl</code>, and it produces an editable, documented, parametric CAD source instead of an opaque mesh.
</p>

---

### Contents

- [Why this exists](#why-this-exists)
- [What it does](#what-it-does)
- [Install](#install)
- [Usage](#usage)
- [How it works](#how-it-works)
- [Layout](#layout)
- [Contributing](#contributing)
- [Author](#author)

## Why this exists

Most "make me a 3D-printable part" prompts either produce a `.scad` file nobody checks for printability, or they skip straight to an STL that can't be edited once a dimension is wrong. Neither is good enough for parts that actually have to fit something — a bracket, a mount, a printer upgrade.

This skill treats the editable `.scad` source as the deliverable, not a byproduct. It keeps nominal, measured, and compensated dimensions separate, requires a named printer profile before calling a fit correct, and never claims a render or export succeeded without inspecting the actual output.

## What it does

- **Create** a new parametric model from dimensions, images, or a description.
- **Understand** an existing model — modules, parameters, coordinate systems, likely print orientation.
- **Modify** parameters or features while preserving unaffected interfaces.
- **Reconstruct** an STL as evidence (not source): measure it, cross-section it, infer intent, rebuild it parametrically.
- **Repair** a mesh — diagnose first, apply the least geometry-changing fix, and escalate to reconstruction when a topology repair would destroy design intent.
- **Export** a validated STL from a `.scad` source.
- **Publish** a full package: STL, seven-angle preview images, and a human-readable `MODEL_SPEC.md`.

Printer awareness is built in for a modified Ender 3 V2 and a QALAM Pro 400, plus a generic fallback profile — see [`references/printer-profiles.md`](.claude/skills/openscad-print-modeler/references/printer-profiles.md).

## Install

**Claude Code** — drop the skill folder into your project or user skills directory:

```bash
git clone https://github.com/rx290/openscad-print-modeler.git
cp -r openscad-print-modeler/.claude/skills/openscad-print-modeler ~/.claude/skills/
```

(Or keep it project-scoped by copying into `<your-project>/.claude/skills/`.)

**ChatGPT / Codex** — the package ships an [`agents/openai.yaml`](.claude/skills/openscad-print-modeler/agents/openai.yaml) manifest, so it can be registered the same way as any other Codex/ChatGPT skill package.

**Tooling required for rendering/export/repair:**

```bash
# OpenSCAD CLI — required for preview/export
sudo apt install openscad   # or brew install openscad / download from openscad.org
# set OPENSCAD_BIN if the binary isn't on PATH

# optional, only needed for mesh_repair.py
python3 -m pip install trimesh
```

`stl_inspect.py` has no dependencies beyond the standard library.

## Usage

Once the skill is installed, just ask naturally — e.g. *"design a 4-slot cable comb, M3 mounting holes, for my Ender 3"* — and Claude/ChatGPT will follow the skill's workflow automatically. The underlying scripts can also be run directly:

```bash
# Render seven labeled views (isometric, front, back, left, right, top, bottom)
python3 scripts/openscad_pack.py preview path/to/model.scad

# Export STL, render views, validate the mesh, and write a spec from the manifest
python3 scripts/openscad_pack.py export path/to/model.scad

# Inspect an existing STL's geometry/topology
python3 scripts/stl_inspect.py path/to/model.stl --markdown MESH_REPORT.md

# Conservative mesh repair (duplicate/degenerate faces, bad normals, small holes)
python3 scripts/mesh_repair.py input.stl repaired.stl --mode safe
```

## How it works

The skill is a set of instructions plus supporting assets, not a standalone app:

- [`SKILL.md`](.claude/skills/openscad-print-modeler/SKILL.md) — the workflow the model follows: start-safely checklist, which mode to use, model-authoring rules, dimension discipline (nominal vs. measured vs. compensated), printer-aware checks, and the required `MODEL_SPEC.md` contents.
- [`references/printer-profiles.md`](.claude/skills/openscad-print-modeler/references/printer-profiles.md) — working defaults per printer; profile values are defaults, not overrides of the user's live config.
- [`references/design-and-repair.md`](.claude/skills/openscad-print-modeler/references/design-and-repair.md) — reconstruction method, repair classification (safe-automatic vs. approval-required vs. reconstruct), and the validation checklist.
- [`assets/parametric-part.scad`](.claude/skills/openscad-print-modeler/assets/parametric-part.scad) — a structural starting point (parameters → derived dimensions → modules → additive → subtractive → assembly) with `assert()`-guarded dimensions.
- [`assets/model-manifest.json`](.claude/skills/openscad-print-modeler/assets/model-manifest.json) — documentation metadata (parameters, features, printer profile, assumptions) that feeds the generated `MODEL_SPEC.md`.
- [`scripts/`](.claude/skills/openscad-print-modeler/scripts) — the only parts that actually execute: rendering/export (`openscad_pack.py`), dependency-free STL inspection (`stl_inspect.py`), and conservative mesh repair (`mesh_repair.py`).

## Layout

```
.claude/skills/openscad-print-modeler/
├── SKILL.md                       # the workflow definition
├── agents/openai.yaml             # ChatGPT/Codex registration manifest
├── references/
│   ├── printer-profiles.md
│   └── design-and-repair.md
├── assets/
│   ├── parametric-part.scad
│   └── model-manifest.json
└── scripts/
    ├── openscad_pack.py           # preview + export + validate
    ├── stl_inspect.py             # geometry/topology inspection
    └── mesh_repair.py             # safe/aggressive STL repair
```

## Contributing

Issues and PRs are welcome — printer profiles for other machines, additional repair heuristics, or workflow refinements are all fair game. This is a fresh skill, so expect the workflow rules to evolve.

## Author

**Muhammad Asad Waseem** — [github.com/rx290](https://github.com/rx290)
