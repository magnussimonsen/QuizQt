# PowerShell build helper for QuizQt on Windows
# Usage: from repo root run `pwsh quiz_app/build_quizqt.ps1`
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-Python {
    param(
        [string[]]$Candidates
    )

    foreach ($candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }

        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }

        try {
            $cmd = Get-Command $candidate -ErrorAction Stop
            if ($cmd -and $cmd.Source) {
                return $cmd.Source
            }
        }
        catch {
            continue
        }
    }

    return $null
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $scriptDir
try {
    $pythonCandidates = @(
        (Join-Path $scriptDir '..\.venv\Scripts\python.exe'),
        (Join-Path $scriptDir '.\.venv\Scripts\python.exe'),
        'py',
        'python'
    )

    $pythonExe = Resolve-Python -Candidates $pythonCandidates
    if (-not $pythonExe) {
        throw 'Unable to locate python executable. Activate your virtual environment or ensure python is on PATH.'
    }

    Write-Host "Using Python: $pythonExe"

    & $pythonExe -m pip show pyinstaller > $null 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'PyInstaller not found. Installing into the active environment...'
        & $pythonExe -m pip install --upgrade pip
        & $pythonExe -m pip install pyinstaller
    }

    Write-Host 'Building executable with PyInstaller (QuizQt.spec)...'
    & $pythonExe -m PyInstaller QuizQt.spec
    if ($LASTEXITCODE -ne 0) {
        throw 'PyInstaller build failed.'
    }

    $outputPath = Join-Path $scriptDir 'dist/QuizQt.exe'
    if (Test-Path $outputPath) {
        Write-Host "Build complete: $outputPath"
    }
    else {
        throw 'Build finished, but dist/QuizQt.exe was not found.'
    }
}
finally {
    Pop-Location
}
