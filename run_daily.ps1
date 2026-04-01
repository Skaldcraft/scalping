param(
    [string]$Date,
    [string]$Config = "config/settings.yaml",
    [ValidateSet("DEBUG", "INFO", "WARNING", "ERROR")]
    [string]$LogLevel = "INFO"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$args = @()
if ($Date) {
    $args += "--date"
    $args += $Date
}
if ($Config) {
    $args += "--config"
    $args += $Config
}
if ($LogLevel) {
    $args += "--log-level"
    $args += $LogLevel
}

python .\daily_run.py @args
