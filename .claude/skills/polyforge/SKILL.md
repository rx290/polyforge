---
name: polyforge
description: Create, understand, explain, modify, reconstruct, validate, document, render, and export 3D-printable OpenSCAD models. Use for .scad and .stl work, parametric CAD, dimensioned mechanical parts, brackets, mounts, enclosures, printer upgrades, STL-to-SCAD reconstruction, mesh diagnosis or repair, multi-angle model previews, and printer-specific fit or printability checks for the user's modified Ender 3 V2, QALAM Pro 400, or another FDM printer.
---

# PolyForge

Create an editable `.scad` source as the normal deliverable. Export STL, repair meshes, or make a publication pack only when requested or needed to verify geometry.

Everything below describes the agent-driven workflow (this SKILL.md, used by Claude Code, ChatGPT/Codex, or any agent that can load it as instructions). For a quick common shape, or when no agent/LLM is available at all, the same underlying engine also runs completely standalone from the command line — see "Standalone CLI" below.

## Start safely

1. Inspect every supplied image, `.scad`, `.stl`, measurement, and mating part before designing.
2. Read `references/printer-profiles.md` when printability, fit, orientation, or machine limits matter.
3. Ask only for missing measurements that materially affect fit or function. Clearly label provisional dimensions.
4. Never claim a render, export, measurement, or repair succeeded unless the corresponding tool completed and its output was inspected.
5. Preserve originals. Write revisions and repaired meshes to new files unless the user explicitly requests replacement.

## Choose the workflow

- **Create:** Build a new parametric model from dimensions, images, or a description.
- **Understand:** Explain modules, parameters, coordinate systems, feature construction, dimensions, and likely print orientation.
- **Modify:** Change source parameters or features while preserving unaffected interfaces.
- **Reconstruct:** Treat an STL as evidence, not editable source. Measure it, inspect cross-sections, infer design intent, then recreate important geometry parametrically.
- **Repair:** Diagnose first, choose the least geometry-changing repair, compare before/after dimensions and volume, and escalate to reconstruction when topology repair would not restore design intent.
- **Export:** Compile the requested STL and validate the resulting mesh.
- **Publish:** Generate STL, multi-angle images, and a readable model specification package.

## Model authoring rules

- Use millimetres and place user-editable parameters at the top.
- Separate parameters, derived dimensions, reusable modules, additive features, subtractive features, and final assembly.
- Name dimensions by purpose; avoid unexplained numeric coordinates.
- Derive mating features from shared datums and parameters.
- Put subtractive holes, slots, and pockets late in the feature tree.
- Extend cutters beyond the target by a small epsilon to avoid coplanar boolean artifacts.
- Use `assert()` for impossible dimensions, inadequate walls, or invalid clearances. Prefer expressing dependent positions (a hole row's height, an offset from a bend) as a *fraction* of the dimension they sit within rather than a fixed absolute — that keeps the model valid under arbitrary parameter overrides instead of only the author's original numbers. See `src/polyforge/templates/shelf_bracket.py` and `l_bracket.py` for the pattern.
- Set preview and export facet quality separately. Avoid excessive `$fn` on non-critical geometry.
- Make the preferred print face flat when practical and avoid trapped supports.
- Do not silently scale an STL to solve a dimensional mismatch. Establish whether the cause is model dimensions, shrinkage, slicer scaling, extrusion calibration, or measurement error.
- For imported STL edits, use `import()` only for simple add/subtract operations that do not need true parametric control. Reconstruct functional interfaces when editability or dimensional accuracy matters.

Use `assets/parametric-part.scad` as a structural starting point and `assets/model-manifest.json` for documentation metadata.

## Standalone CLI

For common part shapes (box/enclosure, wall shelf, corner bracket, cable comb, standoff mount plate), the skill's actual generation logic lives in the `polyforge` Python package (`src/polyforge/`), not only in this document — so it also runs with **no agent and no LLM required**:

```bash
pip install -e .
polyforge design "a wall shelf 200x150x5mm with 2 M4 holes"
polyforge list-templates   # see every known template and its parameters
```

This uses the zero-dependency `templates` engine by default (keyword + regex matching against a bounded template library — it only knows the shapes above, it will not invent novel geometry). Pass `--engine llm` to instead ask a local model (e.g. Ollama) to fill in the same templates from more casually phrased text; see the package README for setup.

Pass `--backend freecad` to get an editable FreeCAD `.FCMacro` (built on FreeCAD's Part API) instead of OpenSCAD source — useful when the destination workflow is FreeCAD-based. `polyforge export model.FCMacro` runs it headlessly via `freecadcmd` and validates the resulting mesh the same way as the OpenSCAD path; there's no multi-view PNG preview for FreeCAD yet (that needs its GUI/OpenGL stack).

As an agent, prefer this path only for a quick, common shape the templates already cover. For anything bespoke — custom features, unusual constraints, mating parts, images to reconstruct from — write the `.scad` (or FreeCAD Python) yourself following the authoring rules above; the CLI's vocabulary is intentionally bounded.

## Dimension and fit discipline

Record three kinds of dimensions separately:

1. **Nominal:** intended CAD value.
2. **Measured:** value obtained from the reference part, mesh, or printed sample.
3. **Compensated:** value adjusted for printer/material behavior.

State uncertainty and measurement source. For mating parts, prioritize hole spacing, hole diameter, counterbore/countersink geometry, slot width, locating faces, rail/extrusion interfaces, and clearance direction. Never infer screw or insert standards solely from a blurry image when a wrong choice could waste a print.

Read `references/design-and-repair.md` for reconstruction, mesh-repair decisions, and the required validation checklist.

## Printer-aware checks

- Select a named printer profile, nozzle, material, and intended orientation.
- Treat profile values as defaults, not facts overriding the user's current configuration.
- Compare bounding dimensions against the usable—not merely advertised—build envelope.
- Relate minimum walls to extrusion width and perimeter count.
- Check bridges, overhangs, elephant-foot-sensitive fits, heat-set insert bosses, screw access, tool access, and assembly order.
- For structural printer parts, call out load direction, layer adhesion, stress concentrations, heat exposure, and whether a metal fastener or captured nut carries the load.

## Rendering and visual verification

When OpenSCAD is available, run:

```bash
polyforge preview path/to/model.scad
```

Generate seven clearly named views: isometric, front, back, left, right, top, and bottom. Inspect every image. A successful command alone does not prove the model is correct. Look for missing features, inverted axes, occluded holes, disconnected bodies, unexpectedly thin walls, and incorrect orientation.

## STL export

Export only when requested, or when an STL is necessary for validation:

```bash
polyforge export path/to/model.scad
```

The command exports STL, generates all views, inspects the mesh, and writes a model specification from the manifest plus measured mesh facts. Keep the `.scad` as the source of truth.

For an existing STL, inspect it with:

```bash
polyforge inspect path/to/model.stl --markdown path/to/MESH_REPORT.md
```

## Mesh repair decision

Choose among all three behaviors intelligently:

- Automatically fix harmless topology defects such as duplicate or degenerate faces, unreferenced vertices, small holes, inconsistent winding, or broken normals when dimensions remain stable.
- Ask before repair when closing gaps, filling large holes, removing components, smoothing, voxelizing, remeshing, or changing fit surfaces could alter function.
- Reconstruct in OpenSCAD when the mesh is severely damaged, non-parametric modification would be fragile, or mounting geometry must be exact.

If optional `trimesh` is installed (`pip install -e .[repair]`), use:

```bash
polyforge repair input.stl repaired.stl --mode safe
```

Use `--mode aggressive` only with explicit approval after explaining likely geometry changes. Always inspect and compare input and output reports.

## Required model specification

For any completed design, maintain a human-readable `MODEL_SPEC.md` or equivalent containing:

- model name, purpose, revision, units, and source files;
- overall X/Y/Z dimensions measured from the rendered mesh when available;
- user-adjustable parameters and their current values;
- holes, slots, pockets, bosses, inserts, fasteners, and critical spacing;
- nominal, measured, and compensated dimensions where relevant;
- coordinate origin, axes, construction summary, and major modules;
- selected printer, nozzle, material, orientation, supports, and fit assumptions;
- validation performed, warnings, and any unverified assumptions.

Do not pretend mesh analysis can reliably discover every hole diameter. Take semantic feature data from the parametric source/manifest and cross-check overall bounds against the exported mesh.

## Roadmap: beyond OpenSCAD

This skill produces OpenSCAD/STL and, for the five bounded templates, FreeCAD `.FCMacro`/STEP via the standalone CLI (`--backend freecad`). Still planned, not yet built: a Blender export backend and multi-photo-to-mesh reconstruction feeding the existing STL-reconstruct workflow. Don't claim either exists until it lands — check the repo README for current status.

## Completion standard

Return the editable `.scad` by default. Summarize what changed, important dimensions, assumptions, and checks performed. When export or publishing was requested, also return the verified STL, seven view images (or a contact sheet if produced), mesh report, and model specification. Clearly identify anything that could not be verified locally.
