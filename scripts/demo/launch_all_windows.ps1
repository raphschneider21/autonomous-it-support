[CmdletBinding()]
param()

# Windows PowerShell 5 surfaces each native stderr line as an ErrorRecord. Keep
# native output capturable and make every Python decision from $LASTEXITCODE.
$ErrorActionPreference = "Continue"
$ScriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDirectory = (Resolve-Path (Join-Path $ScriptDirectory "..\..")).Path
$Helper = Join-Path $ScriptDirectory "demo_runtime.py"
$RuntimeDirectory = if ($env:DEMO_RUNTIME_DIR) {
    [System.IO.Path]::GetFullPath($env:DEMO_RUNTIME_DIR)
} else {
    Join-Path $ProjectDirectory ".demo-runtime"
}
$LogDirectory = Join-Path $RuntimeDirectory "logs"
$StartedRoles = [System.Collections.Generic.List[string]]::new()
$PythonExe = $null
$PythonPrefix = @()

function Write-Check([string]$Message) {
    Write-Host "$([char]0x2713) $Message"
}

function Set-SafeDemoEnvironment {
    $env:DEMO_MODE = "1"
    $env:EXECUTOR = "mock"
    $env:AGENT_MODE = "deterministic"
    $env:RUNBOOK_STORE = "ubuntu-26.04"
    $env:MONITORING_ENABLED = "1"
    $env:MONITORING_URL = "http://127.0.0.1:8001"
    $env:ENDPOINT_NAME = "ubuntu-demo-01"
    $env:ENDPOINT_HOSTNAME = "ubuntu-demo-01"
    $env:DEMO_ENDPOINT_URL = "http://127.0.0.1:8000"
}

function Test-PythonCandidate($Candidate) {
    try {
        & $Candidate.Executable @($Candidate.Prefix) -c (
            "import sys; assert sys.version_info >= (3, 10); " +
            "import fastapi, pydantic, uvicorn; " +
            "from src.main import app as endpoint_app; " +
            "from src.monitoring.app import app as service_desk_app"
        ) *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Select-DemoPython {
    $Candidates = [System.Collections.Generic.List[object]]::new()
    if ($env:DEMO_PYTHON) {
        $Candidates.Add([pscustomobject]@{ Executable = $env:DEMO_PYTHON; Prefix = @() })
    } else {
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
    }

    foreach ($Candidate in $Candidates) {
        if (Test-PythonCandidate $Candidate) {
            $script:PythonExe = $Candidate.Executable
            $script:PythonPrefix = @($Candidate.Prefix)
            return
        }
    }
    if ($env:DEMO_PYTHON) {
        throw "DEMO_PYTHON is not Python 3.10+ with the required project imports: $env:DEMO_PYTHON"
    }
    throw "No Python 3.10+ interpreter with the project dependencies was found. Create .venv or set DEMO_PYTHON."
}

function Start-OrReuseDemoService(
    [string]$Role,
    [string]$Label,
    [string]$LogFile
) {
    $ProbeOutput = & $script:PythonExe @script:PythonPrefix $Helper probe --role $Role 2>&1
    $ProbeStatus = $LASTEXITCODE
    if ($ProbeStatus -eq 0) {
        Write-Check "$Label already healthy; reusing it without taking ownership"
        return
    }
    if ($ProbeStatus -ne 10) {
        throw "$Label cannot start: $($ProbeOutput -join [Environment]::NewLine)"
    }

    $StartOutput = & $script:PythonExe @script:PythonPrefix $Helper start --role $Role `
        --runtime-dir $RuntimeDirectory --log-file $LogFile 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed to start. Inspect $LogFile. $($StartOutput -join [Environment]::NewLine)"
    }
    $StartedRoles.Add($Role)
    $WaitOutput = & $script:PythonExe @script:PythonPrefix $Helper wait --role $Role --timeout 20 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed health verification. Inspect $LogFile. $($WaitOutput -join [Environment]::NewLine)"
    }
    $StartedPid = $StartOutput | Select-Object -Last 1
    Write-Check "$Label (PID $StartedPid)"
}

function Stop-StartedServices {
    for ($Index = $StartedRoles.Count - 1; $Index -ge 0; $Index--) {
        & $script:PythonExe @script:PythonPrefix $Helper stop --role $StartedRoles[$Index] `
            --runtime-dir $RuntimeDirectory *> $null
    }
}

try {
    Write-Host ""
    Write-Host "=========================================="
    Write-Host " AUTONOMOUS IT SUPPORT $([char]0x2014) DEMO LAUNCHER"
    Write-Host "=========================================="
    Write-Host ""

    Set-Location -LiteralPath $ProjectDirectory
    New-Item -ItemType Directory -Force -Path $LogDirectory, (Join-Path $RuntimeDirectory "pids") | Out-Null
    Set-SafeDemoEnvironment
    Select-DemoPython
    Write-Check "Python environment"

    $EnvironmentOutput = & $PythonExe @PythonPrefix "scripts/demo/preflight.py" `
        --endpoint-url $env:DEMO_ENDPOINT_URL --environment-only 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Safe demo configuration was rejected: $($EnvironmentOutput -join [Environment]::NewLine)"
    }

    Start-OrReuseDemoService "service-desk" "Service Desk :8001" (Join-Path $LogDirectory "service-desk.log")
    Start-OrReuseDemoService "endpoint" "Endpoint runtime :8000" (Join-Path $LogDirectory "endpoint.log")

    $PreflightOutput = & $PythonExe @PythonPrefix "scripts/demo/preflight.py" `
        --endpoint-url $env:DEMO_ENDPOINT_URL 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Integrated preflight failed: $($PreflightOutput -join [Environment]::NewLine)"
    }
    Write-Check "EXECUTOR=mock"
    Write-Check "AGENT_MODE=deterministic"
    Write-Check "Simulated endpoint reset"
    Write-Check "Service Desk connected"

    $SurfaceOutput = & $PythonExe @PythonPrefix $Helper check-surfaces 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Presentation surface check failed: $($SurfaceOutput -join [Environment]::NewLine)"
    }
    Write-Check "Employee Support reachable"
    Write-Check "Demo Lab reachable"

    $Urls = @(
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8000/static/demo.html",
        "http://127.0.0.1:8001"
    )
    if ($env:DEMO_OPEN_BROWSER -ne "0") {
        $BrowserFailed = $false
        foreach ($Url in $Urls) {
            try {
                Start-Process $Url -ErrorAction Stop
            } catch {
                $BrowserFailed = $true
            }
        }
        if ($BrowserFailed) {
            Write-Warning "Browser launch failed; services remain healthy. Open these URLs manually:"
            $Urls | ForEach-Object { Write-Host "  $_" }
        }
    } else {
        Write-Host "Browser opening disabled. Presentation URLs:"
        $Urls | ForEach-Object { Write-Host "  $_" }
    }

    Write-Host ""
    Write-Host "=========================================="
    Write-Host "              DEMO READY"
    Write-Host "=========================================="
    Write-Host "Logs: $LogDirectory"
    Write-Host "Stop with: $(Join-Path $ScriptDirectory 'Stop Autonomous IT Support Demo.cmd')"
    exit 0
} catch {
    if ($PythonExe) {
        Stop-StartedServices
    }
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host "             DEMO NOT READY" -ForegroundColor Red
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "Logs: $LogDirectory"
    exit 1
}
