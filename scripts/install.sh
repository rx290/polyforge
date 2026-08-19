#!/usr/bin/env bash
# PolyForge installer -- Linux.
#
# Installs the polyforge package (zero-dependency core), optionally into a
# fresh virtualenv, checks for OpenSCAD, detects your GPU (NVIDIA/CUDA or
# AMD/ROCm via nvidia-smi/rocm-smi) and recommends an Ollama model size to
# match, and can install Ollama + pull that model -- each of the last two
# steps asks first, since they run a remote installer script / download
# several GB respectively.
#
# Usage: ./scripts/install.sh [--yes]
#   --yes   don't prompt for the venv/Ollama-install/model-pull questions;
#           assume yes to all of them (for CI or a fully unattended install)

set -euo pipefail

ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y) ASSUME_YES=1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

confirm() {
  # $1 = prompt. Returns 0 (yes) if --yes was passed or stdin isn't a
  # terminal (non-interactive run); otherwise asks. For low-risk, reversible
  # steps (venv creation, an extra pip install) only.
  if [ "$ASSUME_YES" = "1" ] || [ ! -t 0 ]; then
    return 0
  fi
  read -r -p "$1 [y/N] " reply
  case "$reply" in
    [yY]|[yY][eE][sS]) return 0 ;;
    *) return 1 ;;
  esac
}

confirm_risky() {
  # Same prompt, but for a step that runs a remote install script or
  # downloads several GB: defaults to NO when non-interactive unless --yes
  # was passed explicitly -- a silent "yes" here is a real cost, not just a
  # convenience default, so it must be opted into rather than assumed.
  if [ "$ASSUME_YES" = "1" ]; then
    return 0
  fi
  if [ ! -t 0 ]; then
    echo "(non-interactive, skipping: $1 -- pass --yes to include this step)"
    return 1
  fi
  read -r -p "$1 [y/N] " reply
  case "$reply" in
    [yY]|[yY][eE][sS]) return 0 ;;
    *) return 1 ;;
  esac
}

echo "== PolyForge installer =="

# ---- 1. Python ----
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    version=$("$candidate" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
    major=${version%.*}; minor=${version#*.}
    if [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; then
      PYTHON_BIN="$candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo "error: no Python 3.10+ found on PATH." >&2
  echo "Install it with your distro's package manager, e.g.:" >&2
  echo "  Debian/Ubuntu: sudo apt install python3 python3-venv python3-pip" >&2
  echo "  Fedora:        sudo dnf install python3 python3-pip" >&2
  echo "  Arch:          sudo pacman -S python python-pip" >&2
  exit 1
fi
echo "Python: $("$PYTHON_BIN" --version) ($PYTHON_BIN)"

# ---- 2. Virtual environment ----
INSTALL_PYTHON="$PYTHON_BIN"
if confirm "Create a virtual environment at $REPO_ROOT/.venv (recommended, keeps this off your system Python)?"; then
  "$PYTHON_BIN" -m venv "$REPO_ROOT/.venv"
  INSTALL_PYTHON="$REPO_ROOT/.venv/bin/python"
  echo "Created $REPO_ROOT/.venv -- activate later with: source $REPO_ROOT/.venv/bin/activate"
else
  echo "Installing into $PYTHON_BIN's environment directly (--user)."
fi

# ---- 3. Install the package ----
if [ "$INSTALL_PYTHON" = "$PYTHON_BIN" ]; then
  "$INSTALL_PYTHON" -m pip install --user -e "$REPO_ROOT"
else
  "$INSTALL_PYTHON" -m pip install -e "$REPO_ROOT"
fi

if confirm "Also install the 'repair' extra (trimesh, for 'polyforge repair')?"; then
  "$INSTALL_PYTHON" -m pip install -e "$REPO_ROOT[repair]"
fi

POLYFORGE_BIN="$("$INSTALL_PYTHON" -c 'import shutil,sys; print(shutil.which("polyforge") or "")')"
if [ -z "$POLYFORGE_BIN" ]; then
  # Editable console-script entry points land in the venv's own bin/ (or
  # --user's bin/ dir) -- fall back to invoking the module directly if that
  # directory isn't on PATH yet.
  POLYFORGE_CMD=("$INSTALL_PYTHON" -m polyforge.cli)
else
  POLYFORGE_CMD=("$POLYFORGE_BIN")
fi

# ---- 4. OpenSCAD (needed for preview/export) ----
if command -v openscad >/dev/null 2>&1; then
  echo "OpenSCAD: found ($(command -v openscad))"
else
  echo "OpenSCAD: not found -- needed for 'polyforge preview'/'export'. Install it with:"
  echo "  Debian/Ubuntu: sudo apt install openscad"
  echo "  Fedora:        sudo dnf install openscad"
  echo "  Arch:          sudo pacman -S openscad"
fi

# ---- 5. Ollama + hardware-aware model recommendation ----
if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama: not found (needed only for 'polyforge design --engine llm')."
  if confirm_risky "Install it now by running the official installer (curl -fsSL https://ollama.com/install.sh | sh)?"; then
    curl -fsSL https://ollama.com/install.sh | sh
  else
    echo "Skipping. Install later from https://ollama.com/download, or use --engine templates (no LLM needed at all)."
  fi
fi

if command -v ollama >/dev/null 2>&1; then
  echo
  echo "-- Hardware scan --"
  "${POLYFORGE_CMD[@]}" hardware-scan
  if confirm_risky "Pull the recommended model now (multi-GB download)?"; then
    "${POLYFORGE_CMD[@]}" hardware-scan --pull
  fi
fi

echo
echo "Done. Try: ${POLYFORGE_CMD[*]} design \"a wall shelf 200x150x5mm with 2 M4 holes\""
echo "Or the GUI: ${POLYFORGE_CMD[*]} gui"
