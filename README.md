<p align="center">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="Works with any LLM" src="https://img.shields.io/badge/works%20with-Claude%20%7C%20ChatGPT%20%7C%20Gemini%20%7C%20local%20models-5A67D8">
  <img alt="Runs fully offline" src="https://img.shields.io/badge/runs-fully%20offline-10a37f">
  <img alt="Tests" src="https://img.shields.io/badge/tests-24%2F24%20passing-success">
  <img alt="PRs Welcome" src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg">
</p>

<p align="center">
  <b>PolyForge turns a description, a set of measurements, or an existing model into an editable, validated, 3D-printable CAD file — as a standalone offline tool, or as a skill for whatever LLM you're already using.</b>
</p>

---

### Contents

- [Why this exists](#why-this-exists)
- [What it does today](#what-it-does-today)
- [Roadmap](#roadmap)
- [Install](#install)
- [Usage](#usage)
- [Architecture](#architecture)
- [Layout](#layout)
- [Contributing](#contributing)
- [Author](#author)

## Why this exists

Most "make me a 3D-printable part" prompts either produce a `.scad` file nobody checks
for printability, or skip straight to an STL that can't be edited once a dimension is
wrong. And every one of them requires an agent (and usually a paid API key) in the loop
for even the most common shapes — a box, a shelf bracket, a cable comb.

PolyForge treats the editable `.scad` source as the deliverable, not a byproduct, and
splits its capability in two: a bounded, **zero-dependency Python engine** that turns
plain text into common parts with no LLM involved at all, and a richer **agent
workflow** (Claude Code / ChatGPT / any model you paste the instructions into) for
everything bespoke that a fixed template can't cover.

## What it does today

**Standalone, no LLM required** — a small library of parametric part templates (box,
wall shelf, corner bracket, cable comb, standoff mount plate), each rendered from plain
text via keyword + dimension/screw-size/count extraction, to either of two CAD backends:

```bash
polyforge design "a wall shelf 200x150x5mm with 2 M4 holes"                    # -> .scad (default)
polyforge design "a wall shelf 200x150x5mm with 2 M4 holes" --backend freecad  # -> .FCMacro
```

Every template is unit-tested and compile-tested against both the real `openscad` and
`freecadcmd` binaries, with the two backends' exported geometry asserted to match
dimensionally — see [`tests/`](tests).

**Agent-driven** — the full [`SKILL.md`](.claude/skills/polyforge/SKILL.md) workflow for
anything a template doesn't cover: create, understand, modify, reconstruct-from-STL,
repair, export, and publish, with printer-aware fit/printability checks for a modified
Ender 3 V2, a QALAM Pro 400, or a generic FDM profile. See
[`references/printer-profiles.md`](.claude/skills/polyforge/references/printer-profiles.md)
and
[`references/design-and-repair.md`](.claude/skills/polyforge/references/design-and-repair.md).

**Optional local-model engine** — `--engine llm` asks a local model (Ollama by default)
to fill in the same template vocabulary from more casually phrased text, still fully
offline, still bounded to known shapes.

## Roadmap

Being built one phase at a time, each on its own branch, tested before merging:

- [x] **Phase 1 — Standalone offline CLI core.** Template library, zero-ML text
      matcher, optional local-LLM matcher, OpenSCAD preview/export, STL inspection,
      mesh repair.
- [x] **Phase 2 — FreeCAD export backend.** A second parametric target via FreeCAD's
      headless Python API (`freecadcmd`), producing an editable `.FCMacro` + STEP/STL
      export. No multi-view preview yet — that needs FreeCAD's GUI/OpenGL stack, not
      just the console CLI; use `export` for validated STL/STEP instead. *(this release)*
- [ ] **Phase 3 — Blender export backend.** A mesh/organic-modeling target via `bpy`,
      for parts that don't fit a parametric feature tree.
- [ ] **Phase 4 — Image-to-3D.** Multi-photo photogrammetry (offline, open-source
      structure-from-motion) producing a mesh that feeds the existing
      reconstruct-from-STL workflow. Needs real photo coverage from multiple angles —
      it approximates a mesh, it doesn't recover exact parametric intent.

Don't take Blender/image-to-3D as already working, or FreeCAD preview as available —
check the boxes above.

## Install

**Standalone CLI (any platform, no agent needed):**

```bash
git clone https://github.com/rx290/polyforge.git
cd polyforge
pip install -e .              # add `[repair]` for mesh repair: pip install -e .[repair]
polyforge list-templates
```

**Claude Code:**

```bash
cp -r polyforge/.claude/skills/polyforge ~/.claude/skills/   # or into <project>/.claude/skills/
```

**ChatGPT / Codex:** ships [`agents/openai.yaml`](.claude/skills/polyforge/agents/openai.yaml) for native registration.

**Gemini, Kimi K2, other tool-calling models, or a bare LLM with no tool-calling:** see [`AGENTS.md`](AGENTS.md).

**Tooling required for rendering/export/repair:**

```bash
sudo apt install openscad   # or brew install openscad / openscad.org — required for preview/export
sudo apt install freecad    # or brew install freecad / freecad.org — required for --backend freecad export
python3 -m pip install trimesh   # optional, only for mesh_repair
```

`design`, `list-templates`, and STL `inspect` need nothing beyond the Python standard library.

## Usage

```bash
# Generate a part from text (zero-ML template engine, the default)
polyforge design "a wall shelf 200x150x5mm with 2 M4 holes" --out shelf.scad

# Same, but let a local model (e.g. Ollama) fill in the template from casual phrasing
polyforge design "something to hold my cables together, six slots" --engine llm

# Override any specific parameter regardless of engine
polyforge design "a box" --set width=100 --set wall=3

# Generate a FreeCAD macro instead of OpenSCAD
polyforge design "a corner bracket 100x30x30mm" --backend freecad --out bracket.FCMacro

# See every known template and its parameters/defaults
polyforge list-templates

# Render seven labeled views (isometric, front, back, left, right, top, bottom) -- OpenSCAD only
polyforge preview path/to/model.scad

# Export + validate. Backend is chosen by file extension: .scad -> OpenSCAD, .FCMacro -> FreeCAD
polyforge export path/to/model.scad       # -> STL, 7 views, MESH_REPORT.md, MODEL_SPEC.md
polyforge export path/to/model.FCMacro    # -> STL, STEP, MESH_REPORT.md, MODEL_SPEC.md

# Inspect an existing STL's geometry/topology (works on an STL from either backend)
polyforge inspect path/to/model.stl --markdown MESH_REPORT.md

# Conservative mesh repair (duplicate/degenerate faces, bad normals, small holes)
polyforge repair input.stl repaired.stl --mode safe
```

Once the skill is installed in an agent (Claude Code, ChatGPT, or via `AGENTS.md`
elsewhere), just ask naturally — "design a cable comb with 8 slots for 3mm cables" —
and it follows the same workflow automatically, falling back to hand-written `.scad`
for anything the template library doesn't cover.

## Architecture

```
polyforge design "text" ──▶ nlu.template_matcher (default, zero-ML)
                        │       keyword match → template key
                        │       regex extraction → dimensions / screw size / count
                        └──▶ nlu.llm_backend (--engine llm, optional)
                                same template vocabulary, filled by a local model
                                       │
                                       ▼
                              template key + params
                                       │
                        ┌──────────────┴──────────────┐
                        ▼                              ▼
              templates.<key>.generate()    templates.<key>.generate_freecad()
                        │                              │
                        ▼                              ▼
              validated parametric .scad    validated FreeCAD .FCMacro
                        │                              │
                        ▼                              ▼
          geometry.preview_export / inspect      geometry.freecad_export / inspect
              (openscad CLI + trimesh)              (freecadcmd + trimesh)
```

Both NLU engines only ever pick a **template key + params** — neither one writes
arbitrary OpenSCAD or FreeCAD Python from scratch. That's what keeps the zero-ML path
honest about what it can do, keeps the local-LLM path from needing to reproduce all the
authoring rules (units, `assert()`-guarded dimensions, fraction-based hole placement)
baked into each template, and is what makes both backends produce dimensionally
identical geometry for the same template + params (asserted directly in
[`tests/test_freecad_backend.py`](tests/test_freecad_backend.py)).

One backend-specific gotcha worth knowing if you extend this: `freecadcmd` catches
exceptions raised inside a macro internally and still exits `0` — the only signal is a
line of text in its output, so `geometry/freecad_export.py` greps for
`"Exception while processing file"` rather than trusting the return code.

## Layout

```
src/polyforge/
├── cli.py                     # `polyforge` entry point
├── render.py                  # template key + params -> source text, per backend
├── templates/                 # the bounded part vocabulary
│   ├── base.py                 (Param/Template/registry, freecad_macro() boilerplate)
│   ├── box.py                  each has generate() -> .scad and generate_freecad() -> .FCMacro
│   ├── shelf_bracket.py
│   ├── l_bracket.py
│   ├── cable_comb.py
│   └── standoff_mount.py
├── nlu/
│   ├── template_matcher.py    # zero-ML text -> (template, params)
│   └── llm_backend.py         # optional local-model text -> (template, params)
└── geometry/
    ├── preview_export.py      # OpenSCAD preview/export
    ├── freecad_export.py      # FreeCAD (freecadcmd) export
    ├── spec.py                # MODEL_SPEC.md writer shared by both backends
    ├── inspect.py             # dependency-free STL geometry/topology
    └── repair.py              # trimesh-backed conservative repair

.claude/skills/polyforge/
├── SKILL.md                   # the agent-driven workflow
├── agents/openai.yaml         # ChatGPT/Codex registration
├── references/                # printer profiles, design & repair guidance
└── assets/                    # starter .scad + manifest schema

tests/                         # pytest: templates, freecad backend, matcher, render, CLI
AGENTS.md                      # wiring PolyForge into any other LLM/agent
```

## Contributing

Issues and PRs welcome — new part templates, printer profiles, matcher phrasings, or
progress on the FreeCAD/Blender/image-to-3D roadmap are all fair game. Each roadmap
phase lands on its own branch and gets tested before merging, so expect the workflow
rules and template library to keep growing.

## Author

**Muhammad Asad Waseem** — [github.com/rx290](https://github.com/rx290)
