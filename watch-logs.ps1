param(
    [ValidateSet('backend', 'worker', 'frontend', 'all')]
    [string]$Service = 'all'
)

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$LOG_DIR = Join-Path $ROOT 'logs'
$files = switch ($Service) {
    'backend' { @('backend.log') }
    'worker' { @('worker.log') }
    'frontend' { @('frontend.log', 'frontend-error.log') }
    default { @('backend.log', 'worker.log', 'frontend.log', 'frontend-error.log') }
}

if (-not (Test-Path $LOG_DIR)) {
    Write-Error "Log directory not found at $LOG_DIR"
    exit 1
}

$targets = @()
foreach ($file in $files) {
    $path = Join-Path $LOG_DIR $file
    if (-not (Test-Path $path)) {
        New-Item -ItemType File -Path $path -Force | Out-Null
    }
    $targets += $path
}

Write-Host 'Watching logs. Press Ctrl+C to stop.'
Get-Content -LiteralPath $targets -Wait -Tail 50
