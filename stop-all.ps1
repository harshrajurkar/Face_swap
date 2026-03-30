$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$STATE_DIR = Join-Path $ROOT '.run'
$PID_FILE = Join-Path $STATE_DIR 'pids.json'
$BACKEND_PY = Join-Path $ROOT 'backend\.venv311\Scripts\python.exe'

function Stop-ProcessTreeByPid($pidValue, $label) {
    if (-not $pidValue) { return }
    cmd /c "taskkill /PID $pidValue /T /F" *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Stopped $label tree ($pidValue)"
    }
}

function Stop-ListenersOnPort($port) {
    $lines = netstat -ano -p tcp | Select-String ":$port"
    $pids = @()
    foreach ($line in $lines) {
        $parts = ($line.ToString() -split '\s+') | Where-Object { $_ }
        if ($parts.Length -ge 5) {
            $state = $parts[3]
            $pidValue = $parts[4]
            if ($state -eq 'LISTENING' -and $pidValue -match '^\d+$') {
                $pids += [int]$pidValue
            }
        }
    }
    $pids = $pids | Select-Object -Unique
    foreach ($pidValue in $pids) {
        cmd /c "taskkill /PID $pidValue /T /F" *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Stopped listener on port $port (PID $pidValue)"
        }
    }
}

Write-Host 'Stopping AI Face Swap background services...'

if (Test-Path $PID_FILE) {
    $state = Get-Content -LiteralPath $PID_FILE | ConvertFrom-Json
    foreach ($name in @('frontend_pid', 'worker_pid', 'backend_pid')) {
        Stop-ProcessTreeByPid $state.$name $name
    }
    Remove-Item -LiteralPath $PID_FILE -Force -ErrorAction SilentlyContinue
} else {
    Write-Host 'No PID file found. Skipping saved process tree cleanup.'
}

Stop-ListenersOnPort 3000
Stop-ListenersOnPort 8000

Get-Process python -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path -ieq $BACKEND_PY } |
    ForEach-Object {
        cmd /c "taskkill /PID $($_.Id) /T /F" *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Stopped backend venv python (PID $($_.Id))"
        }
    }

& docker stop ai-face-swap-redis *> $null
Write-Host 'Redis container stopped'
