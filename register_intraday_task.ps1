param(
    [string]$TaskName = "PulseTrader Intraday 15m",
    [int]$RepeatMinutes = 15,
    [string]$Config = "config/settings.yaml",
    [ValidateSet("DEBUG", "INFO", "WARNING", "ERROR")]
    [string]$LogLevel = "INFO",
    [string]$StartET = "09:25",
    [string]$EndET = "11:00"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $root "run_intraday.ps1"

if (-not (Test-Path $scriptPath)) {
    throw "Missing script: $scriptPath"
}

$powershellPath = (Get-Command powershell.exe).Source
$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -Config `"$Config`" -LogLevel `"$LogLevel`" -StartET `"$StartET`" -EndET `"$EndET`""

$action = New-ScheduledTaskAction -Execute $powershellPath -Argument $arguments
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes $RepeatMinutes) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Write-Host "Creating scheduled task '$TaskName'..."
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "Scheduled task created. It runs every $RepeatMinutes minutes and only executes inside the ET window $StartET-$EndET."
Write-Host "Inspect: Get-ScheduledTask -TaskName `"$TaskName`" | Format-List *"
Write-Host "Remove : Unregister-ScheduledTask -TaskName `"$TaskName`" -Confirm:`$false"
