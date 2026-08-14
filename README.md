<p align="center">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="Works with any LLM" src="https://img.shields.io/badge/works%20with-Claude%20%7C%20ChatGPT%20%7C%20Gemini%20%7C%20local%20models-5A67D8">
  <img alt="Runs fully offline" src="https://img.shields.io/badge/runs-fully%20offline-10a37f">
  <img alt="Tests" src="https://img.shields.io/badge/tests-24%2F24%20passing-success">
  <img alt="PRs Welcome" src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg">
</p>

<p align="center">
  <b>PolyForge takes a description, a set of measurements, or an existing model and turns it into an editable, validated, 3D-printable CAD file.</b> Standalone, with no agent involved, or as a skill for whatever LLM you already use.
</p>

---

### Contents

- [Why I built this](#why-i-built-this)
- [What it does today](#what-it-does-today)
- [Roadmap](#roadmap)
- [Install](#install)
- [Usage](#usage)
- [Architecture](#architecture)
- [Layout](#layout)
- [Contributing](#contributing)
- [Author](#author)

## Why I built this

I originally put this together as a ChatGPT skill, just for OpenSCAD, so I could describe a bracket or an enclosure and get back something I could actually print on my modified Ender 3 V2 or my QALAM Pro 400, instead of hand-modeling every mount and shelf myself. It worked fine, but it only worked in ChatGPT, and it needed an agent (and an API bill) in the loop even for a plain shelf bracket. That felt backwards. A shelf doesn't need a language model to exist.

So I pulled it apart and rebuilt it as PolyForge. The part that turns a description into a common shape now runs completely on its own, no agent, no LLM, nothing. The richer part, the one that can reconstruct a busted STL or design something genuinely custom, is still an agent workflow, but it's no longer tied to one platform. Point Claude Code, ChatGPT, Gemini, or a local model at it and it works the same way, because the actual capability lives in a standalone Python package, not in something only one vendor's assistant knows how to run.

## What it does today

**Standalone, no LLM required.** A small library of parametric part templates, box, wall shelf, corner bracket, cable comb, standoff mount plate, each one filled in from plain text by keyword matching and regex extraction (dimensions, screw sizes, hole counts), then rendered to either of two CAD backends:

```bash
polyforge design "a wall shelf 200x150x5mm with 2 M4 holes"                    # writes a .scad
polyforge design "a wall shelf 200x150x5mm with 2 M4 holes" --backend freecad  # writes a .FCMacro
```

Every template is unit-tested and also compile-tested against the real `openscad` and `freecadcmd` binaries, with the two backends' output checked to match dimensionally. See [`tests/`](tests) if you want to see that for yourself.

**Agent-driven**, for everything a template can't cover. The full [`SKILL.md`](.claude/skills/polyforge/SKILL.md) workflow: create, understand, modify, reconstruct from an STL, repair a mesh, export, publish, plus printer-aware fit checks for a modified Ender 3 V2, a QALAM Pro 400, or a generic FDM profile. See [`references/printer-profiles.md`](.claude/skills/polyforge/references/printer-profiles.md) and [`references/design-and-repair.md`](.claude/skills/polyforge/references/design-and-repair.md).

**An optional local-model engine.** `--engine llm` asks a local model (Ollama by default) to fill in the same templates from more casual phrasing. Still fully offline, still limited to the shapes the template library actually knows.

## Roadmap

I'm building this one phase at a time, each on its own branch, tested before it merges into main.

- [x] **Phase 1, standalone offline CLI core.** Template library, the zero-ML text matcher, the optional local-LLM matcher, OpenSCAD preview/export, STL inspection, mesh repair.
- [x] **Phase 2, FreeCAD export backend.** A second parametric target through FreeCAD's headless Python API (`freecadcmd`), producing an editable `.FCMacro` plus STEP/STL export. No multi-view preview for it yet, that needs FreeCAD's GUI/OpenGL stack, not just the console CLI, so use `export` for a validated STL/STEP instead.
- [ ] **Phase 3, Blender export backend.** A mesh/organic-modeling target through `bpy`, for parts that don't belong in a parametric feature tree.
- [ ] **Phase 4, image-to-3D.** Multi-photo photogrammetry, offline, open-source structure-from-motion, producing a mesh that feeds into the existing reconstruct-from-STL workflow. It needs real photo coverage from more than one angle, and it approximates a mesh rather than recovering exact parametric intent, so treat it accordingly.
- [ ] **Somewhere after that, a low-poly vase generator.** Randomized low-poly faceting over a revolved profile, reusing the same OpenSCAD/FreeCAD split above.

If a box above isn't checked, that feature isn't built yet. Don't take my word for it either, go read the code.

## Install

**Standalone CLI, works anywhere, no agent needed:**

```bash
git clone https://github.com/rx290/polyforge.git
cd polyforge
pip install -e .              # add [repair] for mesh repair: pip install -e .[repair]
polyforge list-templates
```

**Claude Code:**

```bash
cp -r polyforge/.claude/skills/polyforge ~/.claude/skills/   # or into <project>/.claude/skills/
```

**ChatGPT / Codex:** ships [`agents/openai.yaml`](.claude/skills/polyforge/agents/openai.yaml) for native registration.

**Gemini, Kimi K2, other tool-calling models, or a bare LLM with no tool-calling:** see [`AGENTS.md`](AGENTS.md).

**Tooling you'll need for rendering, export, and repair:**

```bash
sudo apt install openscad   # or brew install openscad, or grab it from openscad.org: needed for preview/export
sudo apt install freecad    # or brew install freecad, or freecad.org: needed for --backend freecad export
python3 -m pip install trimesh   # optional, only for mesh repair
```

`design`, `list-templates`, and STL `inspect` don't need anything beyond the Python standard library.

## Usage

```bash
# Generate a part from text (the zero-ML template engine, the default)
polyforge design "a wall shelf 200x150x5mm with 2 M4 holes" --out shelf.scad

# Same thing, but let a local model (Ollama, say) read more casual phrasing
polyforge design "something to hold my cables together, six slots" --engine llm

# Override any specific parameter no matter which engine picked it
polyforge design "a box" --set width=100 --set wall=3

# Generate a FreeCAD macro instead of OpenSCAD
polyforge design "a corner bracket 100x30x30mm" --backend freecad --out bracket.FCMacro

# See every known template and its parameters/defaults
polyforge list-templates

# Render seven labeled views: isometric, front, back, left, right, top, bottom (OpenSCAD only)
polyforge preview path/to/model.scad

# Export and validate. The backend follows the file extension: .scad goes to OpenSCAD, .FCMacro to FreeCAD
polyforge export path/to/model.scad       # produces an STL, 7 views, MESH_REPORT.md, MODEL_SPEC.md
polyforge export path/to/model.FCMacro    # produces an STL, a STEP, MESH_REPORT.md, MODEL_SPEC.md

# Inspect an existing STL's geometry and topology, from either backend
polyforge inspect path/to/model.stl --markdown MESH_REPORT.md

# Conservative mesh repair: duplicate/degenerate faces, bad normals, small holes
polyforge repair input.stl repaired.stl --mode safe
```

Once the skill is installed in an agent, Claude Code, ChatGPT, or anything wired up through `AGENTS.md`, just ask for what you want in plain language, "design a cable comb with 8 slots for 3mm cables", and it follows the same workflow on its own, writing the `.scad` by hand for anything the template library doesn't cover.

## Architecture

```
polyforge design "text" ──▶ nlu.template_matcher (default, zero-ML)
                        │       keyword match -> template key
                        │       regex extraction -> dimensions, screw size, count
                        └──▶ nlu.llm_backend (--engine llm, optional)
                                same template vocabulary, filled in by a local model
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
              (openscad CLI, trimesh)               (freecadcmd, trimesh)
```

Neither NLU engine writes raw OpenSCAD or FreeCAD Python from scratch. They only ever pick a template key and fill in its params. That's a deliberate limit: it's what keeps the zero-ML path honest about what it can actually do, it's what lets the local-model path skip reimplementing every authoring rule (units, `assert()`-guarded dimensions, hole placement as a fraction of the part it sits in), and it's why both backends produce the same geometry, dimension for dimension, for the same template and params. See [`tests/test_freecad_backend.py`](tests/test_freecad_backend.py) if you want the proof.

One thing worth knowing if you're going to touch this code: `freecadcmd` catches exceptions raised inside a macro on its own and still exits 0. The only sign anything went wrong is a line of text in its output, so `geometry/freecad_export.py` checks for the string `"Exception while processing file"` instead of trusting the return code. Found that one the hard way.

## Layout

```
src/polyforge/
├── cli.py                     # the `polyforge` entry point
├── render.py                  # template key + params -> source text, whichever backend
├── templates/                 # the bounded part vocabulary
│   ├── base.py                 Param/Template/registry, plus the freecad_macro() boilerplate
│   ├── box.py                  each file has generate() for .scad and generate_freecad() for .FCMacro
│   ├── shelf_bracket.py
│   ├── l_bracket.py
│   ├── cable_comb.py
│   └── standoff_mount.py
├── nlu/
│   ├── template_matcher.py    # zero-ML text -> (template, params)
│   └── llm_backend.py         # optional local-model text -> (template, params)
└── geometry/
    ├── preview_export.py      # OpenSCAD preview and export
    ├── freecad_export.py      # FreeCAD export via freecadcmd
    ├── spec.py                # the MODEL_SPEC.md writer, shared by both backends
    ├── inspect.py             # dependency-free STL geometry and topology
    └── repair.py              # trimesh-backed conservative repair

.claude/skills/polyforge/
├── SKILL.md                   # the agent-driven workflow
├── agents/openai.yaml         # ChatGPT/Codex registration
├── references/                # printer profiles, design and repair guidance
└── assets/                    # starter .scad and manifest schema

tests/                         # pytest: templates, the freecad backend, matcher, render, CLI
AGENTS.md                      # how to wire PolyForge into any other LLM or agent
```

## Contributing

Issues and PRs are welcome. New part templates, printer profiles, phrasings the matcher should catch, or a hand with the Blender/image-to-3D phases, all fair game. Each phase lands on its own branch and gets tested before it merges, so expect the workflow and the template library to keep growing.

## Author

**Muhammad Asad Waseem**, [github.com/rx290](https://github.com/rx290)
