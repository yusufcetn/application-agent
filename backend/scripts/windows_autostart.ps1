<#
Starts the Apply Agent backend when you sign in to Windows, keeps it running, and wakes
the computer from sleep shortly before the daily search.

Install (once, in PowerShell from the repo root):
  powershell -ExecutionPolicy Bypass -File backend\scripts\windows_autostart.ps1
Remove:
  powershell -ExecutionPolicy Bypass -File backend\scripts\windows_autostart.ps1 -Remove

Output goes to data\backend.log. Waking from sleep needs "Allow wake timers" enabled in the
Windows power options; a computer that is shut down is not started.
#>
param(
    [switch]$Remove,
    # A few minutes before the search time in Settings (08:00 by default).
    [string]$WakeAt = "07:55",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$TaskName = "Apply Agent"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "'$TaskName' görevi kaldırıldı."
    return
}

$backend = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$data = Join-Path (Split-Path $backend -Parent) "data"
New-Item -ItemType Directory -Force $data | Out-Null
$log = Join-Path $data "backend.log"
$uv = (Get-Command uv).Source

$command = "& '$uv' run uvicorn app.main:app --port $Port *>> '$log'"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -Command `"$command`"" `
    -WorkingDirectory $backend
$triggers = @(
    (New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"),
    # Wakes the computer; if the backend is already running this start is skipped.
    (New-ScheduledTaskTrigger -Daily -At $WakeAt)
)
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings `
    -Principal $principal -Description "Apply Agent backend (http://127.0.0.1:$Port)" -Force | Out-Null
Write-Host "'$TaskName' görevi kuruldu: oturum açılınca başlar, her gün $WakeAt'te bilgisayarı uyandırır."
Write-Host "Şimdi başlatmak için: Start-ScheduledTask -TaskName '$TaskName'"
