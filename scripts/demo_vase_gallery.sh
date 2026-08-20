#!/usr/bin/env bash
# Headless gallery generator for the vase template's free-text shape
# vocabulary -- no browser, no manual screenshot tool: for each sample
# prompt below, generates the model and renders it via the existing
# `polyforge design`/`preview` CLI, then copies the isometric view into
# docs/images/ for the README. Re-run any time the vocabulary or the
# template's defaults change instead of re-taking screenshots by hand.
#
# Usage: ./scripts/demo_vase_gallery.sh [polyforge-command...]
#   Defaults to `polyforge` on PATH; pass a full command (e.g. a venv's
#   python -m polyforge.cli) as arguments if that's not installed globally.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
POLYFORGE=("${@:-polyforge}")

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

IMAGES_DIR="$REPO_ROOT/docs/images"
mkdir -p "$IMAGES_DIR"

# slug|prompt -- slug becomes docs/images/vase-gallery-<slug>.png
SAMPLES=(
  "plain-smooth|a plain smooth vase 200mm height 90mm diameter"
  "hourglass-ripples|an hourglass vase with wave ripples"
  "bulb-holder|a vase with a bulb holder on top"
  "low-poly-twisted|a low poly twisted vase"
  "support-free|a detailed vase with smooth texture that prints without support"
  "combined|an hourglass vase with a plain neck and a bulb holder on top and wave ripples"
)

for entry in "${SAMPLES[@]}"; do
  slug="${entry%%|*}"
  prompt="${entry#*|}"
  scad="$WORKDIR/${slug}.scad"

  echo "=== $slug: \"$prompt\" ==="
  "${POLYFORGE[@]}" design "$prompt" --out "$scad"
  "${POLYFORGE[@]}" preview "$scad" --imgsize 900,900
  cp "$WORKDIR/previews/isometric.png" "$IMAGES_DIR/vase-gallery-${slug}.png"
  echo "Wrote $IMAGES_DIR/vase-gallery-${slug}.png"
done
