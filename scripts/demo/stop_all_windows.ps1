$ErrorActionPreference = "Stop"

$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Helper = Join-Path $ProjectDir "scripts\demo\mac_runtime.py"
$RuntimeDir = if ($env:DEMO_RUNTIME_DIR) { $env:DEMO_RUNTIME_DIR } else { Join-Path $ProjectDir ".demo-runtime" }
$script:PythonExe = $null
$script:PythonPrefix = @()

function Test-PythonCandidate([string]$Exe, [string[]]$Prefix = @()) {
    if (-not $Exe) { return $false }
    try {
        $allArgs = @($Prefix) + @("-c", "import sys; assert sys.version_info >= (3, 10)")
        & $Exe @allArgs *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch { return $false }
}

function Select-DemoPython {
    if ($env:DEMO_PYTHON -and (Test-PythonCandidate $env:DEMO_PYTHON)) {
        $script:PythonExe = $env:DEMO_PYTHON
        return
    }

    $venvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"
    if (Test-PythonCandidate $venvPython) {
        $script:PythonExe = $venvPython
        return
    }

    foreach ($name in @("python.exe", "python3.exe")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and (Test-PythonCandidate $cmd.Source)) {
            $script:PythonExe = $cmd.Source
            return
        }
    }

    $py = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($py -and (Test-PythonCandidate $py.Source @("-3"))) {
        $script:PythonExe = $py.Source
        $script:PythonPrefix = @("-3")
        return
    }

    throw "Python 3.10+ is unavailable, so launcher PID ownership cannot be verified safely."
}

function Invoke-PythonCapture([string[]]$Arguments) {
    $allArgs = @($script:PythonPrefix) + @($Arguments)
    $output = & $script:PythonExe @allArgs 2>&1 | Out-String
    return [pscustomobject]@{ Code = $LASTEXITCODE; Output = $output.Trim() }
}

function Stop-One([string]$Role, [string]$Label) {
    $result = Invoke-PythonCapture @($Helper, "stop", "--role", $Role, "--runtime-dir", $RuntimeDir)
    if ($result.Code -ne 0) {
        throw "$Label could not be stopped safely: $($result.Output)"
    }
    if ($result.Output -like "STOPPED:*") {
        Write-Host "[OK] $Label stopped"
    }
    elseif ($result.Output -like "NOT-RUNNING:*") {
        Write-Host "[OK] $Label was not started by this launcher"
    }
    elseif ($result.Output -like "STALE:*") {
        Write-Host "[OK] $Label stale PID record cleaned"
    }
    elseif ($result.Output -like "FOREIGN:*") {
        Write-Host "[OK] $Label unrelated process left untouched; stale record cleaned"
    }
    else {
        Write-Host "[OK] $Label: $($result.Output)"
    }
}

try {
    Set-Location $ProjectDir
    Select-DemoPython
    Write-Host ""
    Write-Host "Stopping Autonomous IT Support Demo..."
    Write-Host ""

    Stop-One "endpoint" "Endpoint"
    Stop-One "service-desk" "Service Desk"

    $pidDir = Join-Path $RuntimeDir "pids"
    if (Test-Path $pidDir) {
        try { Remove-Item $pidDir -Force -ErrorAction SilentlyContinue } catch {}
    }

    Write-Host "[OK] Launcher PID files cleaned; logs preserved at $(Join-Path $RuntimeDir 'logs')"
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "              DEMO STOPPED"
    Write-Host "=========================================="
    exit 0
}
catch {
    Write-Host ""
    Write-Host "DEMO NOT STOPPED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
