# PolyForge installer -- Windows (PowerShell).
#
# Mirrors scripts/install.sh: installs polyforge (zero-dependency core),
# optionally into a fresh virtualenv, checks for OpenSCAD, detects your GPU
# (NVIDIA/CUDA or AMD/ROCm via nvidia-smi/rocm-smi -- both ship Windows
# builds, so polyforge's own hardware.py needs no Windows-specific code) and
# recommends an Ollama model size, and can install Ollama + pull that model
# -- each of the last two asks first, since one runs a downloaded installer
# and the other pulls several GB.
#
# NOT YET RUN ON A REAL WINDOWS MACHINE (this was written and reasoned
# through, but only scripts/install.sh could actually be executed and
# verified in the Linux environment it was built in). Report anything that
# doesn't work as written -- don't assume it's been verified end to end the
# way the Linux script has.
#
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1 [-Yes]
#   (or just double-click install.bat, which runs this for you)

param(
    [switch]$Yes
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Confirm-Step {
    # Low-risk, reversible steps (venv creation, an extra pip install) only.
    param([string]$Prompt)
    if ($Yes -or [Console]::IsInputRedirected) { return $true }
    $reply = Read-Host "$Prompt [y/N]"
    return $reply -match '^(y|yes)$'
}

function Confirm-RiskyStep {
    # A step that runs a downloaded installer or pulls several GB: defaults
    # to NO when non-interactive unless -Yes was passed explicitly -- same
    # reasoning as install.sh's confirm_risky.
    param([string]$Prompt)
    if ($Yes) { return $true }
    if ([Console]::IsInputRedirected) {
        Write-Host "(non-interactive, skipping: $Prompt -- pass -Yes to include this step)"
        return $false
    }
    $reply = Read-Host "$Prompt [y/N]"
    return $reply -match '^(y|yes)$'
}

Write-Host "== PolyForge installer =="

# ---- 1. Python ----
# PowerShell's `array[1..($array.Length-1)]` is NOT a safe "everything after
# the first element" slice: when the array has only one element, 1..0 is a
# DESCENDING range (@(1,0)), not empty, and would index out of bounds. This
# helper returns a real empty array in that case instead.
function Get-ExtraArgs {
    param([string[]]$Parts)
    if ($Parts.Length -le 1) { return @() }
    return $Parts[1..($Parts.Length - 1)]
}

$PythonBin = $null
foreach ($candidate in @("py -3.13", "py -3.12", "py -3.11", "py -3.10", "py -3", "python")) {
    $parts = $candidate -split " "
    $exe = $parts[0]
    if (Get-Command $exe -ErrorAction SilentlyContinue) {
        try {
            $versionArgs = (Get-ExtraArgs $parts) + @("-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')")
            $version = & $exe @versionArgs 2>$null
            if ($version -match '^(\d+)\.(\d+)$') {
                $major = [int]$Matches[1]; $minor = [int]$Matches[2]
                if ($major -eq 3 -and $minor -ge 10) {
                    $PythonBin = $candidate
                    break
                }
            }
        } catch {}
    }
}

if (-not $PythonBin) {
    Write-Error "No Python 3.10+ found. Install it from https://www.python.org/downloads/ (check 'Add python.exe to PATH' in the installer), or `winget install Python.Python.3.12`."
    exit 1
}
Write-Host "Python: $PythonBin"
$PythonParts = $PythonBin -split " "
$PythonExe = $PythonParts[0]
$PythonArgs = Get-ExtraArgs $PythonParts

# ---- 2. Virtual environment ----
$InstallPython = $PythonBin
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Confirm-Step "Create a virtual environment at $RepoRoot\.venv (recommended, keeps this off your system Python)?") {
    & $PythonExe @PythonArgs -m venv (Join-Path $RepoRoot ".venv")
    $InstallPythonExe = $VenvPython
    $InstallPythonArgs = @()
    Write-Host "Created $RepoRoot\.venv -- activate later with: $RepoRoot\.venv\Scripts\Activate.ps1"
} else {
    $InstallPythonExe = $PythonExe
    $InstallPythonArgs = $PythonArgs
    Write-Host "Installing into $PythonBin's environment directly (--user)."
}

# ---- 3. Install the package ----
if ($InstallPythonExe -eq $PythonExe) {
    & $InstallPythonExe @InstallPythonArgs -m pip install --user -e $RepoRoot
} else {
    & $InstallPythonExe @InstallPythonArgs -m pip install -e $RepoRoot
}

if (Confirm-Step "Also install the 'repair' extra (trimesh, for 'polyforge repair')?") {
    & $InstallPythonExe @InstallPythonArgs -m pip install -e "$RepoRoot[repair]"
}

$PolyforgeExe = Join-Path (Split-Path $InstallPythonExe -Parent) "polyforge.exe"
if (Test-Path $PolyforgeExe) {
    $PolyforgeCmd = { & $PolyforgeExe @args }
} else {
    $PolyforgeCmd = { & $InstallPythonExe @InstallPythonArgs -m polyforge.cli @args }
}

# ---- 4. OpenSCAD (needed for preview/export) ----
if (Get-Command openscad -ErrorAction SilentlyContinue) {
    Write-Host "OpenSCAD: found"
} else {
    Write-Host "OpenSCAD: not found -- needed for 'polyforge preview'/'export'. Install with:"
    Write-Host "  winget install OpenSCAD.OpenSCAD"
    Write-Host "  or download from https://openscad.org/downloads.html"
}

# ---- 5. Ollama + hardware-aware model recommendation ----
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama: not found (needed only for 'polyforge design --engine llm')."
    if (Confirm-RiskyStep "Download and run the official Ollama installer for Windows now?") {
        $installerPath = Join-Path $env:TEMP "OllamaSetup.exe"
        Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $installerPath
        Write-Host "Running the installer -- follow its prompts (a silent/unattended flag isn't confirmed for this installer, so this opens its normal UI)."
        Start-Process -FilePath $installerPath -Wait
    } else {
        Write-Host "Skipping. Install later from https://ollama.com/download, or use --engine templates (no LLM needed at all)."
    }
}

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host ""
    Write-Host "-- Hardware scan --"
    & $PolyforgeCmd hardware-scan
    if (Confirm-RiskyStep "Pull the recommended model now (multi-GB download)?") {
        & $PolyforgeCmd hardware-scan --pull
    }
}

$ExampleHint = if (Test-Path $PolyforgeExe) { $PolyforgeExe } else { "$InstallPythonExe $($InstallPythonArgs -join ' ') -m polyforge.cli" }
Write-Host ""
Write-Host "Done. Try: $ExampleHint design `"a wall shelf 200x150x5mm with 2 M4 holes`""
Write-Host "Or the GUI: $ExampleHint gui"
