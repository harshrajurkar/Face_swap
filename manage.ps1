param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'stop', 'logs', 'status')]
    [string]$Action = 'status',

    [Parameter(Position = 1)]
    [ValidateSet('backend', 'worker', 'frontend', 'all')]
    [string]$Service = 'all'
)

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$startScript = Join-Path $ROOT 'start-all.ps1'
$stopScript = Join-Path $ROOT 'stop-all.ps1'
$watchScript = Join-Path $ROOT 'watch-logs.ps1'
$stateFile = Join-Path $ROOT '.run\pids.json'

switch ($Action) {
    'start' {
        & powershell -ExecutionPolicy Bypass -File $startScript
        break
    }
    'stop' {
        & powershell -ExecutionPolicy Bypass -File $stopScript
        break
    }
    'logs' {
        & powershell -ExecutionPolicy Bypass -File $watchScript -Service $Service
        break
    }
    'status' {
        Write-Host 'AI Face Swap manager'
        Write-Host "Workspace: $ROOT"
        if (Test-Path $stateFile) {
            $state = Get-Content -LiteralPath $stateFile | ConvertFrom-Json
            Write-Host 'Status: running'
            Write-Host "Backend PID: $($state.backend_pid)"
            Write-Host "Worker PID: $($state.worker_pid)"
            Write-Host "Frontend PID: $($state.frontend_pid)"
        } else {
            Write-Host 'Status: stopped or not started with start-all.ps1'
        }

        Write-Host ''
        Write-Host 'Commands:'
        Write-Host '  .\manage.ps1 start'
        Write-Host '  .\manage.ps1 stop'
        Write-Host '  .\manage.ps1 logs'
        Write-Host '  .\manage.ps1 logs backend'
        Write-Host '  .\manage.ps1 logs worker'
        Write-Host '  .\manage.ps1 logs frontend'
        Write-Host '  .\manage.ps1 status'
        break
    }
}
