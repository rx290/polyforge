# Design, reconstruction, and repair guide

## Contents

1. Creating and modifying
2. Reconstructing STL geometry
3. Repair classification
4. Validation checklist
5. Publication package

## 1. Creating and modifying

Start from functional interfaces and datums. Lock mating geometry before cosmetic geometry. When modifying a working part, make a revision and compare critical values before and after. Use difference-based feature construction for brackets and mounts when it makes the design intent clearer.

For image-driven work, correct perspective where possible and require at least one trustworthy scale reference. Multiple orthogonal images reduce ambiguity but do not replace measurements.

## 2. Reconstructing STL geometry

1. Inspect triangle count, bounds, watertightness, components, volume, and surface area.
2. Determine likely print orientation and symmetry.
3. Take cross-sections at feature transitions, not merely evenly spaced slices.
4. Identify datums, repeated spacing, standard fasteners, constant wall regions, and primitive families.
5. Rebuild functional geometry parametrically. Do not trace tessellation noise.
6. Export the reconstruction and compare bounds, sections, interface locations, and boolean differences when suitable tools exist.
7. Report deviations at critical features rather than relying only on one global similarity score.

## 3. Repair classification

### Safe automatic repair

- remove duplicate or degenerate faces;
- remove unreferenced vertices;
- merge vertices within a very small tolerance;
- repair normals and face winding;
- fill only small, unambiguous holes when doing so does not bridge functional openings.

### Approval required

- fill large or ambiguous holes;
- remove disconnected shells that might be intentional;
- smooth, decimate, remesh, voxelize, or wrap the mesh;
- change scale, wall thickness, or mating surfaces;
- close gaps whose intended topology is uncertain.

### Reconstruct instead

- functional dimensions must change;
- the STL contains severe self-intersections or missing regions;
- direct mesh booleans are unstable;
- the user needs future parametric revisions;
- mounting holes, rails, bearings, inserts, or motor interfaces must be dimensionally controlled.

## 4. Validation checklist

- OpenSCAD parses and fully renders without geometry warnings.
- Exactly the intended solids/components exist.
- Exported mesh is non-empty and has plausible bounds.
- Mesh is watertight/manifold where required and has consistent winding.
- Overall bounds match intended values within stated tessellation tolerance.
- Critical holes, spacing, slots, walls, and clearances match the source parameters.
- Part fits the selected printer's usable envelope in the intended orientation.
- Bottom, top, front, back, left, right, and isometric images were inspected.
- Repair comparisons show no unauthorized dimensional or volume change.
- Specification distinguishes verified facts from assumptions.

## 5. Publication package

Use stable filenames:

```text
project/
  src/model.scad
  output/model.stl
  previews/isometric.png
  previews/front.png
  previews/back.png
  previews/left.png
  previews/right.png
  previews/top.png
  previews/bottom.png
  MODEL_SPEC.md
  MESH_REPORT.md
```

Optionally create a contact sheet, but retain individual full-resolution views for upload platforms.
