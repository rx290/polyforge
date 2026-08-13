<p align="center">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="Works with any LLM" src="https://img.shields.io/badge/works%20with-Claude%20%7C%20ChatGPT%20%7C%20Gemini%20%7C%20local%20models-5A67D8">
  <img alt="Runs fully offline" src="https://img.shields.io/badge/runs-fully%20offline-10a37f">
  <img alt="Tests" src="https://img.shields.io/badge/tests-17%2F17%20passing-success">
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
text via keyword + dimension/screw-size/count extraction:

```bash
polyforge design "a wall shelf 200x150x5mm with 2 M4 holes"
```

Every template is unit-tested and openscad-compile-tested in CI-style fashion — see
[`tests/`](tests).

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
      mesh repair. *(this release)*
- [ ] **Phase 2 — FreeCAD export backend.** A second parametric target via FreeCAD's
      headless Python API, for workflows that want a feature-tree CAD file instead of
      (or alongside) OpenSCAD source.
- [ ] **Phase 3 — Blender export backend.** A mesh/organic-modeling target via `bpy`,
      for parts that don't fit a parametric feature tree.
- [ ] **Phase 4 — Image-to-3D.** Multi-photo photogrammetry (offline, open-source
      structure-from-motion) producing a mesh that feeds the existing
      reconstruct-from-STL workflow. Needs real photo coverage from multiple angles —
      it approximates a mesh, it doesn't recover exact parametric intent.

Don't take FreeCAD/Blender/image-to-3D as already working — check the boxes above.

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

# See every known template and its parameters/defaults
polyforge list-templates

# Render seven labeled views (isometric, front, back, left, right, top, bottom)
polyforge preview path/to/model.scad

# Export STL, render views, validate the mesh, and write MODEL_SPEC.md
polyforge export path/to/model.scad

# Inspect an existing STL's geometry/topology
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
                              templates.<key>.generate(params)
                                       │
                                       ▼
                              validated parametric .scad text
                                       │
                                       ▼
                    geometry.preview_export / inspect / repair
                        (OpenSCAD CLI, dependency-free STL parsing, trimesh)
```

Both NLU engines only ever pick a **template key + params** — neither one writes
arbitrary OpenSCAD from scratch. That's what keeps the zero-ML path honest about what
it can do, and keeps the local-LLM path from needing to reproduce all the authoring
rules (units, `assert()`-guarded dimensions, fraction-based hole placement) baked into
each template.

## Layout

```
src/polyforge/
├── cli.py                     # `polyforge` entry point
├── render.py                  # template key + params -> .scad text
├── templates/                 # the bounded part vocabulary
│   ├── base.py                 (Param/Template/registry)
│   ├── box.py
│   ├── shelf_bracket.py
│   ├── l_bracket.py
│   ├── cable_comb.py
│   └── standoff_mount.py
├── nlu/
│   ├── template_matcher.py    # zero-ML text -> (template, params)
│   └── llm_backend.py         # optional local-model text -> (template, params)
└── geometry/
    ├── preview_export.py      # OpenSCAD preview/export/spec
    ├── inspect.py             # dependency-free STL geometry/topology
    └── repair.py              # trimesh-backed conservative repair

.claude/skills/polyforge/
├── SKILL.md                   # the agent-driven workflow
├── agents/openai.yaml         # ChatGPT/Codex registration
├── references/                # printer profiles, design & repair guidance
└── assets/                    # starter .scad + manifest schema

tests/                         # pytest: templates, matcher, render, CLI
AGENTS.md                      # wiring PolyForge into any other LLM/agent
```

## Contributing

Issues and PRs welcome — new part templates, printer profiles, matcher phrasings, or
progress on the FreeCAD/Blender/image-to-3D roadmap are all fair game. Each roadmap
phase lands on its own branch and gets tested before merging, so expect the workflow
rules and template library to keep growing.

## Author

**Muhammad Asad Waseem** — [github.com/rx290](https://github.com/rx290)
