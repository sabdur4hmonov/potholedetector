<#
.SYNOPSIS
Print verified project commands without executing setup, tests, preview or builds.
.DESCRIPTION
Documentation helper only. Uses the existing source tree and existing execution
policy. No secrets, downloads, file changes, asset sync, child process, or API call.
#>
[CmdletBinding()]
param(
    [ValidateSet('Help', 'Status', 'Preview', 'Checks', 'Build', 'Artifacts')]
    [string]$Mode = 'Help'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
foreach ($required in @('android-app\package.json', 'static\index.html', 'android-app\android\gradlew.bat')) {
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot $required) -PathType Leaf)) {
        throw "Expected project file is missing: $required"
    }
}

function Quote-PowerShellLiteral([string]$Value) {
    return "'" + $Value.Replace("'", "''") + "'"
}

$pythonCandidates = @(
    (Join-Path $repoRoot '.venv\Scripts\python.exe'),
    (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    (Join-Path $repoRoot '..\toolchain\python\python.exe')
)
$pythonExe = $null
foreach ($candidate in $pythonCandidates) {
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $pythonExe = (Resolve-Path -LiteralPath $candidate).Path
        break
    }
}

Write-Output "Repository: $repoRoot"
Write-Output 'PRINT ONLY: no project commands are executed.'
Write-Output ('Set-Location -LiteralPath ' + (Quote-PowerShellLiteral $repoRoot))
if ($pythonExe) {
    Write-Output ('$PythonExe = ' + (Quote-PowerShellLiteral $pythonExe))
} else {
    Write-Output 'Python not located. Set $PythonExe to an installed interpreter before Python commands.'
}

switch ($Mode) {
    'Help' {
        Write-Output 'Modes: Status, Preview, Checks, Build, Artifacts. Each prints commands only.'
        Write-Output 'Read PROJECT_MASTER/SETUP_WINDOWS.md and COMMANDS.md before setup/build.'
        Write-Output 'Current dashcam is disabled; browser paid inference is disabled; no paid calls authorized.'
        Write-Output 'Known Windows/Gradle/device and release-provenance blockers remain open.'
    }
    'Status' {
        Write-Output @'
git rev-parse --show-toplevel
git status --short
git diff --stat
Get-Content -LiteralPath .\PROJECT_MASTER\PROJECT_STATUS.md
Get-Content -LiteralPath .\PROJECT_MASTER\SECURITY_STATUS.md
'@
    }
    'Preview' {
        Write-Output @'
& $PythonExe .\tests\serve_app.py --host 127.0.0.1 --port 8765
'@
        Write-Output 'Open http://127.0.0.1:8765/web-app/ manually. Ctrl+C stops the server.'
        Write-Output 'Native Android plugins and paid inference do not run in browser preview.'
    }
    'Checks' {
        Write-Output @'
$env:PYTHONDONTWRITEBYTECODE = '1'
node --check .\static\standalone.js
node --check .\android-app\www\standalone.js
& $PythonExe .\tests\tender_source_registry_test.py
& $PythonExe .\tests\tender_scope_test.py
& $PythonExe .\tests\sec007_workflow_security_test.py WorkflowSecurityTest
git diff --check
'@
    }
    'Build' {
        Write-Output 'Conditional instructions only: first resolve the recorded blocker and prepare JDK/SDK.'
        Write-Output 'Asset copy regenerates packaged files; build generates artifacts. Not run by this helper.'
        Write-Output 'Stop if web mirrors differ. See COMMANDS.md for readiness and offline-cache limitations.'
        Write-Output @'
Get-FileHash -Algorithm SHA256 -LiteralPath .\static\standalone.js, .\android-app\www\standalone.js, .\docs\standalone.js
Get-FileHash -Algorithm SHA256 -LiteralPath .\static\index.html, .\android-app\www\index.html, .\docs\index.html
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
'@
    }
    'Artifacts' {
        Write-Output @'
Get-ChildItem -LiteralPath .\android-app\android\app\build -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in '.apk', '.aab' } |
    Select-Object FullName, LastWriteTime, Length
'@
        Write-Output 'No build is attempted; existing files do not establish deployment of current fixes.'
    }
}
