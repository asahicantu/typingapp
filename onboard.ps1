#Requires -Version 5.1
<#
.SYNOPSIS
    One-shot installer + launcher for Typing Tutor.
.DESCRIPTION
    Creates a local virtual environment (if missing), installs the app and
    its dependencies into it, then launches the app. Safe to re-run — it
    reuses the existing environment on subsequent runs.
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

function Write-Step($msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Invoke-Checked {
    & $args[0] $args[1..($args.Length - 1)]
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Command failed: $($args -join ' ')" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

function Get-PythonCommand {
    foreach ($candidate in @("python", "py")) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) {
            try {
                $versionOutput = & $candidate --version 2>&1
                if ($versionOutput -match "Python (\d+)\.(\d+)") {
                    $major = [int]$Matches[1]
                    $minor = [int]$Matches[2]
                    if ($major -eq 3 -and $minor -ge 10) {
                        return $candidate
                    }
                }
            } catch {
                continue
            }
        }
    }
    return $null
}

Write-Step "Checking for Python 3.10+"
$PythonCmd = Get-PythonCommand
if (-not $PythonCmd) {
    Write-Host "Python 3.10+ was not found on your PATH." -ForegroundColor Red
    Write-Host "Install it from https://www.python.org/downloads/ (make sure to check 'Add python.exe to PATH' during setup), then re-run this script."
    exit 1
}
Write-Host "Using '$PythonCmd' ($(& $PythonCmd --version))"

$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Step "Creating virtual environment in .venv"
    & $PythonCmd -m venv $VenvDir
} else {
    Write-Step "Reusing existing virtual environment (.venv)"
}

Write-Step "Installing dependencies"
Invoke-Checked $VenvPython -m pip install --upgrade pip --quiet
Invoke-Checked $VenvPython -m pip install -e . --quiet
Invoke-Checked $VenvPython -m pip install pytest --quiet

Write-Step "Launching Typing Tutor"
& $VenvPython -m typingapp
