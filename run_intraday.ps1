param(
    [string]$Config = "config/settings.yaml",
    [ValidateSet("DEBUG", "INFO", "WARNING", "ERROR")]
    [string]$LogLevel = "INFO",
    [string]$StartET = "09:25",
    [string]$EndET = "11:00",
    [switch]$ForceRun
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Get-EasternNow {
    $tz = [System.TimeZoneInfo]::FindSystemTimeZoneById("Eastern Standard Time")
    return [System.TimeZoneInfo]::ConvertTime([datetime]::UtcNow, $tz)
}

$nowEt = Get-EasternNow
$todayEt = $nowEt.ToString("yyyy-MM-dd")
$currentMinutes = ($nowEt.Hour * 60) + $nowEt.Minute
$startParts = $StartET.Split(":")
$endParts = $EndET.Split(":")
$startMinutes = ([int]$startParts[0] * 60) + [int]$startParts[1]
$endMinutes = ([int]$endParts[0] * 60) + [int]$endParts[1]

if (-not $ForceRun) {
    if ($nowEt.DayOfWeek -in @([System.DayOfWeek]::Saturday, [System.DayOfWeek]::Sunday)) {
        Write-Host "PulseTrader intraday run skipped: weekend in New York ($($nowEt.ToString("yyyy-MM-dd HH:mm")) ET)."
        exit 0
    }

    if ($currentMinutes -lt $startMinutes -or $currentMinutes -gt $endMinutes) {
        Write-Host "PulseTrader intraday run skipped: outside ET window $StartET-$EndET (current ET: $($nowEt.ToString("HH:mm")))."
        exit 0
    }
}

Write-Host "PulseTrader intraday run starting for $todayEt at $($nowEt.ToString("HH:mm")) ET..."
python .\daily_run.py --date $todayEt --config $Config --log-level $LogLevel
