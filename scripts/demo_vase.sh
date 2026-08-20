#!/usr/bin/env bash
# Headless demo/screenshot generator for the "vase" template -- no browser,
# no manual screenshot tool: generates the model and renders it via the
# existing `polyforge design`/`preview` CLI, then copies the isometric view
# into docs/images/ for the README. Re-run this any time the template
# changes instead of re-taking screenshots by hand.
#
# Usage: ./scripts/demo_vase.sh [polyforge-command...]
#   Defaults to `polyforge` on PATH; pass a full command (e.g. a venv's
#   python -m polyforge.cli) as arguments if that's not installed globally.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
POLYFORGE=("${@:-polyforge}")

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

SCAD="$WORKDIR/vase_demo.scad"
"${POLYFORGE[@]}" design "a low poly twisted vase" --out "$SCAD"
"${POLYFORGE[@]}" preview "$SCAD" --imgsize 1000,1000

PREVIEW_DIR="$WORKDIR/previews"
mkdir -p "$REPO_ROOT/docs/images"
cp "$PREVIEW_DIR/isometric.png" "$REPO_ROOT/docs/images/vase-demo.png"

echo "Wrote $REPO_ROOT/docs/images/vase-demo.png"
