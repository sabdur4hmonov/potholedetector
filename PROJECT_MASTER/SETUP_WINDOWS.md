# Windows setup

Run PowerShell from the existing repository. These are instructions for a later explicit setup/build; no installation, sync, build, signing, or environment modification was performed for this documentation task.

## Actual requirements and local versions

| Component | Repository requirement / inspected local state |
| --- | --- |
| Node | Installed Capacitor CLI 8.5.0 declares Node `>=22.0.0`; local Node `24.18.0`. |
| npm | Lockfile exists; local npm `11.16.0`. No project-specific npm version pin. |
| JDK | App Java/Kotlin target 21; existing Temurin `21.0.12.1` under the portable toolchain. |
| Gradle | Wrapper pins `8.14.3` with distribution SHA-256. Use `gradlew.bat`, not an invented system Gradle dependency. |
| Android | min SDK 24, compile/target SDK 36; installed `android-36`; installed build-tools `35.0.0` and `36.0.0`. App build file does not explicitly pin build-tools. |
| Build plugins | Android Gradle Plugin `8.13.0`, Kotlin `2.1.0`, KSP `2.1.0-1.0.29`. Retain these; no upgrade instructed. |
| Python | Local pip/venv-capable bundled Python `3.12.14` below; older portable `3.13.7` lacks pip. Repository general Python tooling has no exact interpreter pin. Actions separately pins `3.12.12`. |
| Optional Python packages | Existing general requirements: `playwright>=1.40`, `python-dotenv>=1.0.0`, `Pillow>=10.0.0`. Workflow's hashed Linux-only lock is separate. |

## Enter and prepare this PowerShell session

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\Codex\2026-09-09\bro\work\pothole-reporter'
$toolchainRoot = 'C:\Users\user\Documents\Codex\2026-09-09\bro\work\toolchain'
$env:JAVA_HOME = Join-Path $toolchainRoot 'jdk'
$env:ANDROID_HOME = Join-Path $toolchainRoot 'android-sdk'
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:Path = "$env:JAVA_HOME\bin;$env:ANDROID_HOME\platform-tools;$env:Path"
$PythonExe = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
node --version
npm.cmd --version
& "$env:JAVA_HOME\bin\java.exe" -version
& $PythonExe --version
```

The paths above exist on this laptop. Java/SDK environment variables were unset in the inspected shell; these assignments affect only the session. If the bundled Python is later removed, use another installed Python with pip and venv, then set `$PythonExe` to its actual executable. `py` currently reports no registered installations; do not rely on it here. Do not print environment variables containing credentials.

## Dependencies, only when installation is deliberately needed

Existing Node modules are present. `npm ci` replaces `node_modules`; do not run it just to read docs. To restore exactly the existing lockfile later:

```powershell
Push-Location .\android-app
try { npm.cmd ci } finally { Pop-Location }
```

Offline preview and the small pure-Python checks in the command guide need only the standard library. For the optional general browser/artwork/evaluation tooling, create an ignored local environment using the verified pip/venv-capable Python:

```powershell
& $PythonExe -m venv .\.venv
$PythonExe = (Resolve-Path -LiteralPath '.\.venv\Scripts\python.exe').Path
& $PythonExe -m pip install --no-cache-dir -r .\requirements.txt
& $PythonExe -m playwright install chromium
```

These optional commands install the existing mutable general requirements without changing their source file. They are not the SEC-007 Linux hashed lock, not a remediation of SEC-008, and not required for the print-only helper. No package install was exercised during this task. Do not run evaluation/provider calls with paid-run settings.

## Run / build

For a local UI preview, use the existing server (standard library only):

```powershell
& $PythonExe .\tests\serve_app.py --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/web-app/` manually for the static browser view; `/` serves the Android web asset tree. Stop with Ctrl+C. Pack requests map to the existing hosted pack directory; the server does not expose the entire repository. Native Android plugins do not run in this preview; browser paid inference is disabled.

Build commands and output locations are in [COMMANDS.md](COMMANDS.md). Do not run them until the known Windows/Gradle blocker can be addressed in a separately authorized task. Asset copying/sync changes generated files. Existing `tools/build-apk.sh` also overwrites web mirrors and removes/replaces the debug APK; it is a Bash workflow, not the helper's default. Signed release construction additionally requires private signing configuration; no signing material is included in this center, and NEW-001/NEW-002 remain open.
