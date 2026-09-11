# Windows one-click demo launcher

The Windows launcher runs the same graded demo profile as the macOS launcher:

```text
DEMO_MODE=1
EXECUTOR=mock
AGENT_MODE=deterministic
RUNBOOK_STORE=ubuntu-26.04
MONITORING_ENABLED=1
MONITORING_URL=http://127.0.0.1:8001
```

The Windows machine is only the presentation host. `ubuntu-demo-01` remains an explicitly **simulated Ubuntu 26.04 endpoint**; no Windows service or host setting is remediated.

## Prerequisite

Prepare the repository once so Python can import the project dependencies. The launcher prefers:

```text
.venv\Scripts\python.exe
```

and otherwise tries `python.exe`, `python3.exe`, then the Windows `py -3` launcher.

A typical one-time setup from PowerShell is:

```powershell
cd C:\path\to\autonomous-it-support
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

No administrator rights are required for the demo launcher itself.

## One-click launch

In File Explorer, double-click:

```text
scripts\demo\Autonomous IT Support Demo.cmd
```

It will:

1. locate a usable Python environment;
2. force the deterministic/mock graded profile;
3. reject unknown processes already occupying ports 8000 or 8001;
4. start or safely reuse the Service Desk on `127.0.0.1:8001`;
5. start or safely reuse the endpoint runtime on `127.0.0.1:8000`;
6. run the existing preflight and verify the running health payload is still mock/deterministic;
7. reset the simulated endpoint;
8. verify Employee Support, Demo Lab, Demo Lab API and Service Desk;
9. open the three presentation pages in the default browser;
10. finish with `DEMO READY` or a clear `DEMO NOT READY` message.

Presentation pages:

```text
Employee Support   http://127.0.0.1:8000
Demo Lab           http://127.0.0.1:8000/static/demo.html
Service Desk       http://127.0.0.1:8001
```

Set `DEMO_OPEN_BROWSER=0` before launch if you want readiness checks without opening browser tabs.

## One-click stop

Double-click:

```text
scripts\demo\Stop Autonomous IT Support Demo.cmd
```

The stop launcher only terminates processes whose PID, creation timestamp, repository path, helper command and role all match the ownership record written by the launcher. It never uses process-name-wide kills and never kills an unknown process merely to free a port.

Runtime records and logs are stored under the existing gitignored directory:

```text
.demo-runtime\pids\
.demo-runtime\logs\
```

Windows keeps separate stdout/stderr logs for each service:

```text
service-desk.out.log
service-desk.err.log
endpoint.out.log
endpoint.err.log
```

## Desktop shortcuts

Do not copy the `.cmd` files out of the repository because they resolve the PowerShell scripts relative to their own location.

Instead:

1. Right-click `Autonomous IT Support Demo.cmd` → **Show more options** → **Send to → Desktop (create shortcut)**.
2. Repeat for `Stop Autonomous IT Support Demo.cmd`.
3. Rename the shortcuts if desired.

The shortcuts can live anywhere while the repository-relative launcher remains intact.

## PowerShell equivalents

For troubleshooting or manual invocation:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\demo\launch_all_windows.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\demo\stop_all_windows.ps1
```

`-ExecutionPolicy Bypass` applies only to that PowerShell process. The launcher does not modify the machine-wide execution policy.

## Safety behaviour

- A healthy existing copy of our own expected service may be reused but is not claimed as launcher-owned.
- A foreign process on port 8000/8001 causes launch to fail; it is never killed automatically.
- If startup fails after the launcher started one of the services, the launcher cleans up only the services it just started.
- The stop launcher is idempotent; running it when nothing is launcher-owned is safe.
- Real executor or live external-model runtime health fails readiness.

## Tests

Cross-platform regression coverage:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_mac_demo_launcher.py tests\test_windows_demo_launcher.py
```

Then run the normal demo acceptance suite before using a Windows machine for a graded presentation:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The final acceptance step still needs one real Windows launch/restart/stop rehearsal because CI or non-Windows development machines cannot prove Windows process-management behaviour end-to-end.
