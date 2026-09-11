[CmdletBinding()]
param()

# Native stderr is captured and evaluated through $LASTEXITCODE below.
$ErrorActionPreference = "Continue"
$ScriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDirectory = (Resolve-Path (Join-Path $ScriptDirectory "..\..")).Path
$Helper = Join-Path $ScriptDirectory "demo_runtime.py"
$RuntimeDirectory = if ($env:DEMO_RUNTIME_DIR) {
    [System.IO.Path]::GetFullPath($env:DEMO_RUNTIME_DIR)
} else {
    Join-Path $ProjectDirectory ".demo-runtime"
}
$PythonExe = $null
$PythonPrefix = @()

function Write-Check([string]$Message) {
    Write-Host "$([char]0x2713) $Message"
}

function Test-PythonCandidate($Candidate) {
    try {
        & $Candidate.Executable @($Candidate.Prefix) -c "import sys; assert sys.version_info >= (3, 10)" *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Select-DemoPython {
    $Candidates = [System.Collections.Generic.List[object]]::new()
    if ($env:DEMO_PYTHON) {
        $Candidates.Add([pscustomobject]@{ Executable = $env:DEMO_PYTHON; Prefix = @() })
    }
    $VenvPython = Join-Path $ProjectDirectory ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $VenvPython -PathType Leaf) {
        $Candidates.Add([pscustomobject]@{ Executable = $VenvPython; Prefix = @() })
    }
    $PathPython = Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($PathPython) {
        $Candidates.Add([pscustomobject]@{ Executable = $PathPython.Source; Prefix = @() })
    }
    $PathPy = Get-Command py.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($PathPy) {
        $Candidates.Add([pscustomobject]@{ Executable = $PathPy.Source; Prefix = @("-3") })
    }
    foreach ($Candidate in $Candidates) {
        if (Test-PythonCandidate $Candidate) {
            $script:PythonExe = $Candidate.Executable
            $script:PythonPrefix = @($Candidate.Prefix)
            return
        }
    }
    throw "Python 3.10+ is unavailable, so PID ownership cannot be verified safely."
}

function Stop-DemoRole([string]$Role, [string]$Label) {
    $Output = & $script:PythonExe @script:PythonPrefix $Helper stop --role $Role `
        --runtime-dir $RuntimeDirectory 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "$Label was not stopped safely: $($Output -join [Environment]::NewLine)"
    }
    $Result = $Output -join [Environment]::NewLine
    if ($Result -like "STOPPED:*") {
        Write-Check "$Label stopped"
    } elseif ($Result -like "STALE:*") {
        Write-Check "$Label stale PID record cleaned"
    } elseif ($Result -like "FOREIGN:*") {
        Write-Check "$Label unrelated process left untouched; stale record cleaned"
    } else {
        Write-Check "$Label was not started by this launcher"
    }
}

try {
    Set-Location -LiteralPath $ProjectDirectory
    Write-Host ""
    Write-Host "Stopping Autonomous IT Support Demo..."
    Write-Host ""
    Select-DemoPython
    Stop-DemoRole "endpoint" "Endpoint"
    Stop-DemoRole "service-desk" "Service Desk"

    $PidDirectory = Join-Path $RuntimeDirectory "pids"
    if ((Test-Path -LiteralPath $PidDirectory) -and
        -not (Get-ChildItem -LiteralPath $PidDirectory -Force -ErrorAction SilentlyContinue)) {
        Remove-Item -LiteralPath $PidDirectory
    }
    Write-Check "Launcher PID files cleaned; logs preserved at $(Join-Path $RuntimeDirectory 'logs')"
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "              DEMO STOPPED"
    Write-Host "=========================================="
    exit 0
} catch {
    Write-Host "DEMO NOT STOPPED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
