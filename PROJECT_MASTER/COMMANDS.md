# PowerShell command guide

Commands were checked against existing files, CLI declarations and script arguments; installation/build commands were not executed. The helper prints these commands without running them. Use the session setup in [SETUP_WINDOWS.md](SETUP_WINDOWS.md) to define `$PythonExe`, `JAVA_HOME` and SDK variables.

## Enter / inspect status

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\Codex\2026-09-09\bro\work\pothole-reporter'
git rev-parse --show-toplevel
git status --short
git diff --stat
& .\PROJECT_MASTER\RUN_PROJECT.ps1 -Mode Help
```

## Dependency installation (explicit later setup only)

```powershell
Push-Location .\android-app
try { npm.cmd ci } finally { Pop-Location }
```

This uses the existing package lock and replaces installed Node modules. Optional Python tooling/venv instructions are in the setup guide. There is no valid npm test script: `android-app/package.json`'s `test` script is a placeholder that exits with failure. There is no npm dev/start web server declared; use the actual Python server.

## Local preview

```powershell
& $PythonExe .\tests\serve_app.py --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/web-app/`; `/` previews the Android web assets. Ctrl+C stops the foreground server. Preview does not implement native bridges or cloud inference.

## Selected lightweight checks (when separately requested)

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
node --check .\static\standalone.js
node --check .\android-app\www\standalone.js
& $PythonExe .\tests\tender_source_registry_test.py
& $PythonExe .\tests\tender_scope_test.py
& $PythonExe .\tests\sec007_workflow_security_test.py WorkflowSecurityTest
git diff --check
```

The SEC-007 argument selects only the seven workflow contracts, not its temporary Git-repository transfer suite. The parser/scope checks use existing local fixtures. These are selected checks, not a release test gate; they do not make paid/provider requests. None was rerun to create this documentation. The existing full runner `tests/run-all.sh` is a Bash/full-suite tool and is outside the lightweight path. Its live-service mode is not authorized here.

## Debug build (conditional; not performed)

The existing wrapper supports `:app:assembleDebug`. The following sequence uses the preserved Android web tree and copies it into generated packaged assets; it does not overwrite `static/`, `docs/`, or `android-app/www/`.

Before a build, inspect the existing web mirrors and stop if they diverge—do not copy over prior remediation work to hide a difference:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath .\static\standalone.js, .\android-app\www\standalone.js, .\docs\standalone.js
Get-FileHash -Algorithm SHA256 -LiteralPath .\static\index.html, .\android-app\www\index.html, .\docs\index.html
```

The inspected key mirrors match. This is a narrow readiness check, not complete artifact verification. Only after environment/blocker resolution and explicit authorization to generate assets/build:

```powershell
Push-Location .\android-app
try {
    & .\node_modules\.bin\cap.cmd copy android
    if ($LASTEXITCODE -ne 0) { throw 'Capacitor asset copy failed' }
} finally { Pop-Location }
Push-Location .\android-app\android
try {
    & .\gradlew.bat --no-daemon --offline :app:assembleDebug
    if ($LASTEXITCODE -ne 0) { throw 'Android debug build failed' }
} finally { Pop-Location }
```

`--offline` requires an already provisioned dependency cache and does not fix transformed-JAR access denial. If the generated Cordova prerequisite is absent in another checkout, existing verification recorded that `cap sync android`, rather than `cap copy android`, generated it. `sync` regenerates native/Cordova configuration and is not part of this documentation task or an approved NEW-002 fix. Do not run it blindly over this existing authoritative tree.

The existing signed release workflow is `tools/build-play-release.sh` (Bash/POSIX tooling). It validates signing, manifests, assets and R8 and uses Gradle offline. No PowerShell replacement, bypass, private signing values or speculative release procedure was added. Keep NEW-001/NEW-002 open before a new production release.

## Find APK/AAB artifacts

```powershell
Get-ChildItem -LiteralPath .\android-app\android\app\build -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in '.apk', '.aab' } |
    Select-Object FullName, LastWriteTime, Length
```

Standard future output names declared by the existing build scripts are debug `app-debug.apk`, release `app-release.apk`, and release `app-release.aab`. Their expected subpaths under the existing `android-app/android/app/build` directory are `outputs/apk/debug`, `outputs/apk/release`, and `outputs/bundle/release`; the output files need not exist until a successful build. No APK/AAB was found in the inspected repository build outputs, and none was produced here. A filename or recent timestamp alone does not establish provenance/security fixes.

## Security/remediation status

```powershell
Get-Content -LiteralPath .\PROJECT_MASTER\SECURITY_STATUS.md
Get-Content -LiteralPath .\SECURITY_REMEDIATION_SEC007.md
$reportRoot = 'C:\Users\user\Documents\Codex\2026-09-09\bro\outputs'
Get-ChildItem -LiteralPath $reportRoot -Filter 'SECURITY_REMEDIATION_SEC00*.md' | Select-Object Name
Select-String -Path "$reportRoot\SECURITY_REMEDIATION_SEC00*.md" -Pattern 'Status:|STATUS:|Final SEC-001 status:'
```

The earlier reports remain outside the repository. This prints recorded statuses, not credentials, audit scans or a new security verdict. Do not dump `.env`, keystore properties, certificates or credential-bearing environment variables.
