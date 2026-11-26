param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location -LiteralPath $repoRoot
$python = 'C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$androidRoot = Join-Path $repoRoot 'android-app/android'
$env:JAVA_HOME = Join-Path $androidRoot '.gradle/toolchain/jdk'
$env:ANDROID_HOME = Join-Path $androidRoot '.gradle/toolchain/android-sdk'
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:GRADLE_USER_HOME = Join-Path $androidRoot '.gradle/codex-home'
$env:ANDROID_USER_HOME = Join-Path $androidRoot '.gradle/android-home'
$socketDir = if ($env:POTHOLE_JAVA_SOCKET_DIR) { $env:POTHOLE_JAVA_SOCKET_DIR } else { Join-Path $androidRoot '.gradle' }
$env:JDK_JAVA_OPTIONS = '-Djdk.net.unixdomain.tmpdir="' + $socketDir + '"'
$env:PYTHONUTF8 = '1'
& $python -B tools/sync-web-assets.py
if ($LASTEXITCODE) { throw 'Web synchronization failed' }
Push-Location android-app
try { & .\node_modules\.bin\cap.cmd copy android; if ($LASTEXITCODE) { throw 'Capacitor copy failed' } }
finally { Pop-Location }
Push-Location $androidRoot
$previousErrorAction = $ErrorActionPreference
try {
    $testStarted = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    # Windows PowerShell wraps native stderr (including Java's startup note) as
    # NativeCommandError. Use Gradle's exit code and let its complete log be written.
    $ErrorActionPreference = 'Continue'
    & .\gradlew.bat --offline --no-daemon --console=plain '-Pkotlin.incremental=false' --continue :app:assembleDebug :app:testDebugUnitTest --rerun *> (Join-Path $OutputDirectory 'build.log')
    $buildExit = $LASTEXITCODE
}
finally { $ErrorActionPreference = $previousErrorAction; Pop-Location }
& $python -B (Join-Path $PSScriptRoot 'verify_build.py') --output $OutputDirectory --gradle-exit $buildExit --since $testStarted
exit $LASTEXITCODE
