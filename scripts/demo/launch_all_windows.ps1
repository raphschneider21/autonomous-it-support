$ErrorActionPreference = "Stop"

$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Helper = Join-Path $ProjectDir "scripts\demo\mac_runtime.py"
$RuntimeDir = if ($env:DEMO_RUNTIME_DIR) { $env:DEMO_RUNTIME_DIR } else { Join-Path $ProjectDir ".demo-runtime" }
$LogDir = Join-Path $RuntimeDir "logs"
$PidDir = Join-Path $RuntimeDir "pids"
$script:PythonExe = $null
$script:PythonPrefix = @()
$script:StartedRoles = @()
$script:LaunchComplete = $false

function Write-Banner {
    Write-Host ""
    Write-Host "=========================================="
    Write-Host " AUTONOMOUS IT SUPPORT - DEMO LAUNCHER"
    Write-Host "=========================================="
    Write-Host ""
}

function Fail-Demo([string]$Message) {
    throw $Message
}

function Test-PythonCandidate([string]$Exe, [string[]]$Prefix = @()) {
    if (-not $Exe) { return $false }
    try {
        $allArgs = @($Prefix) + @("-c", "import sys; assert sys.version_info >= (3, 10); import fastapi, pydantic, uvicorn")
        & $Exe @allArgs *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Select-DemoPython {
    if ($env:DEMO_PYTHON) {
        if (-not (Test-PythonCandidate $env:DEMO_PYTHON)) {
            Fail-Demo "DEMO_PYTHON cannot import the project dependencies: $env:DEMO_PYTHON"
        }
        $script:PythonExe = $env:DEMO_PYTHON
        $script:PythonPrefix = @()
        return
    }

    $venvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"
    if (Test-PythonCandidate $venvPython) {
        $script:PythonExe = $venvPython
        $script:PythonPrefix = @()
        return
    }

    foreach ($name in @("python.exe", "python3.exe")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and (Test-PythonCandidate $cmd.Source)) {
            $script:PythonExe = $cmd.Source
            $script:PythonPrefix = @()
            return
        }
    }

    $py = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($py -and (Test-PythonCandidate $py.Source @("-3"))) {
        $script:PythonExe = $py.Source
        $script:PythonPrefix = @("-3")
        return
    }

    Fail-Demo "No Python 3.10+ interpreter with FastAPI, Pydantic and Uvicorn was found. Create .venv or set DEMO_PYTHON."
}

function Invoke-PythonCapture([string[]]$Arguments) {
    $allArgs = @($script:PythonPrefix) + @($Arguments)
    $output = & $script:PythonExe @allArgs 2>&1 | Out-String
    return [pscustomobject]@{
        Code = $LASTEXITCODE
        Output = $output.Trim()
    }
}

function Quote-ProcessArgument([string]$Value) {
    if ($Value -match '[\s"]') {
        return '"' + ($Value -replace '"', '\"') + '"'
    }
    return $Value
}

function Start-OrReuseService([string]$Role, [string]$Label, [string]$LogBase) {
    $probe = Invoke-PythonCapture @($Helper, "probe", "--role", $Role)
    if ($probe.Code -eq 0) {
        Write-Host "[OK] $Label already healthy; reusing it without taking ownership"
        return
    }
    if ($probe.Code -ne 10) {
        Fail-Demo "$Label cannot start: $($probe.Output)"
    }

    $stdoutLog = "$LogBase.out.log"
    $stderrLog = "$LogBase.err.log"
    Add-Content -Path $stdoutLog -Value "`n[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Starting $Label"

    $rawArgs = @($script:PythonPrefix) + @($Helper, "run", "--role", $Role)
    $argumentLine = (($rawArgs | ForEach-Object { Quote-ProcessArgument $_ }) -join " ")
    $startParams = @{
        FilePath = $script:PythonExe
        ArgumentList = $argumentLine
        WorkingDirectory = $ProjectDir
        RedirectStandardOutput = $stdoutLog
        RedirectStandardError = $stderrLog
        WindowStyle = "Hidden"
        PassThru = $true
    }
    $process = Start-Process @startParams

    $record = Invoke-PythonCapture @($Helper, "record", "--role", $Role, "--pid", "$($process.Id)", "--runtime-dir", $RuntimeDir)
    if ($record.Code -ne 0) {
        try { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue } catch {}
        Fail-Demo "Could not record ownership for ${Label}: $($record.Output)"
    }
    $script:StartedRoles += $Role

    $wait = Invoke-PythonCapture @($Helper, "wait", "--role", $Role, "--timeout", "20")
    if ($wait.Code -ne 0) {
        Fail-Demo "$Label failed health verification: $($wait.Output)"
    }
    Write-Host "[OK] $Label started (PID $($process.Id))"
}

function Stop-NewlyStartedServices {
    foreach ($role in @($script:StartedRoles | Select-Object -Unique)) {
        try {
            Invoke-PythonCapture @($Helper, "stop", "--role", $role, "--runtime-dir", $RuntimeDir) | Out-Null
        }
        catch {}
    }
}

Write-Banner

try {
    New-Item -ItemType Directory -Force -Path $LogDir, $PidDir | Out-Null
    Set-Location $ProjectDir
    Select-DemoPython
    Write-Host "[OK] Python environment: $script:PythonExe $($script:PythonPrefix -join ' ')"

    # Frozen graded profile. Existing shell/.env values cannot move the launcher
    # onto a real executor or external-model path.
    $env:DEMO_MODE = "1"
    $env:EXECUTOR = "mock"
    $env:AGENT_MODE = "deterministic"
    $env:RUNBOOK_STORE = "ubuntu-26.04"
    $env:MONITORING_ENABLED = "1"
    $env:MONITORING_URL = "http://127.0.0.1:8001"
    $env:ENDPOINT_NAME = "ubuntu-demo-01"
    $env:ENDPOINT_HOSTNAME = "ubuntu-demo-01"
    $env:DEMO_ENDPOINT_URL = "http://127.0.0.1:8000"

    $environmentCheck = Invoke-PythonCapture @("scripts/demo/preflight.py", "--endpoint-url", $env:DEMO_ENDPOINT_URL, "--environment-only")
    if ($environmentCheck.Code -ne 0) {
        Fail-Demo "Safe demo configuration was rejected: $($environmentCheck.Output)"
    }
    Write-Host "[OK] Deterministic mock configuration forced"

    Start-OrReuseService "service-desk" "Service Desk :8001" (Join-Path $LogDir "service-desk")
    Start-OrReuseService "endpoint" "Endpoint runtime :8000" (Join-Path $LogDir "endpoint")

    $preflight = Invoke-PythonCapture @("scripts/demo/preflight.py", "--endpoint-url", $env:DEMO_ENDPOINT_URL)
    if ($preflight.Code -ne 0) {
        Fail-Demo "Integrated preflight failed: $($preflight.Output)"
    }
    Write-Host "[OK] Simulated endpoint reset"
    Write-Host "[OK] Service Desk connected"
    Write-Host "[OK] EXECUTOR=mock and AGENT_MODE=deterministic confirmed by runtime health"

    $surfaces = Invoke-PythonCapture @($Helper, "check-surfaces")
    if ($surfaces.Code -ne 0) {
        Fail-Demo "Presentation surface check failed: $($surfaces.Output)"
    }
    Write-Host "[OK] Employee Support reachable"
    Write-Host "[OK] Demo Lab reachable"
    Write-Host "[OK] Service Desk UI reachable"

    $urls = @(
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8000/static/demo.html",
        "http://127.0.0.1:8001"
    )

    if ($env:DEMO_OPEN_BROWSER -ne "0") {
        $browserOk = $true
        foreach ($url in $urls) {
            try { Start-Process $url | Out-Null } catch { $browserOk = $false }
        }
        if ($browserOk) {
            Write-Host "[OK] Opened Employee Support, Demo Lab and Service Desk"
        }
        else {
            Write-Host "[WARN] Browser launch failed; services remain healthy. Open manually:"
            $urls | ForEach-Object { Write-Host "  $_" }
        }
    }
    else {
        Write-Host "Browser opening disabled. Presentation URLs:"
        $urls | ForEach-Object { Write-Host "  $_" }
    }

    $script:LaunchComplete = $true
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "               DEMO READY"
    Write-Host "=========================================="
    Write-Host "Logs: $LogDir"
    Write-Host "Stop with: $(Join-Path $PSScriptRoot 'Stop Autonomous IT Support Demo.cmd')"
    exit 0
}
catch {
    if (-not $script:LaunchComplete) {
        Stop-NewlyStartedServices
    }
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host "             DEMO NOT READY" -ForegroundColor Red
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "Logs: $LogDir"
    exit 1
}
