param([switch]$Register, [switch]$Launch)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$python = 'C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
Set-Location -LiteralPath $repoRoot
$env:PYTHONUTF8 = '1'
if ($Register) {
    $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -NonInteractive -File "' + $PSCommandPath + '"') -WorkingDirectory $repoRoot
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(15) -RepetitionInterval (New-TimeSpan -Minutes 15)
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName 'PotholeTrainWatch' -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
}
$arguments = @('-B', (Join-Path $PSScriptRoot 'watch.py'))
if ($Launch) { $arguments += '--launch' }
& $python @arguments
exit $LASTEXITCODE
