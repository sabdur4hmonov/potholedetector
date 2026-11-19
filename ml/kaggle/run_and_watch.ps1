param([switch]$Register, [switch]$Launch)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$python = 'C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
Set-Location -LiteralPath $repoRoot
if ($Register) {
    $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $pythonw = Join-Path (Split-Path $python -Parent) 'pythonw.exe'
    $action = New-ScheduledTaskAction -Execute $pythonw -Argument '-B ml\kaggle\watch.py' -WorkingDirectory $repoRoot
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(15) -RepetitionInterval (New-TimeSpan -Minutes 15)
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName 'PotholeTrainWatch' -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
}
$arguments = @('-B', (Join-Path $PSScriptRoot 'watch.py'))
if ($Launch) { $arguments += '--launch' }
& $python @arguments
exit $LASTEXITCODE
