$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND = Join-Path $ROOT 'backend'
$FRONTEND = Join-Path $ROOT 'frontend'
$PY = Join-Path $BACKEND '.venv311\Scripts\python.exe'
$STATE_DIR = Join-Path $ROOT '.run'
$LOG_DIR = Join-Path $ROOT 'logs'
$PID_FILE = Join-Path $STATE_DIR 'pids.json'
$BACKEND_LOG = Join-Path $LOG_DIR 'backend.log'
$WORKER_LOG = Join-Path $LOG_DIR 'worker.log'
$FRONTEND_LOG = Join-Path $LOG_DIR 'frontend.log'

Write-Host 'Starting AI Face Swap in background...'

if (-not (Test-Path $PY)) {
    Write-Error "Backend virtual environment not found at $PY"
    exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error 'Docker is not available on PATH. Start Docker Desktop first.'
    exit 1
}

$npmCmd = (Get-Command 'npm.cmd' -ErrorAction SilentlyContinue).Source
if (-not $npmCmd) {
    Write-Error 'npm.cmd is not available on PATH. Install Node.js first.'
    exit 1
}

New-Item -ItemType Directory -Force -Path $STATE_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null

Set-Content -LiteralPath $BACKEND_LOG -Value ''
Set-Content -LiteralPath $WORKER_LOG -Value ''
Set-Content -LiteralPath $FRONTEND_LOG -Value ''

& docker inspect ai-face-swap-redis *> $null
if ($LASTEXITCODE -ne 0) {
    & docker run -d --name ai-face-swap-redis -p 6379:6379 redis:7-alpine | Out-Null
} else {
    & docker start ai-face-swap-redis | Out-Null
}

Start-Sleep -Seconds 2

$backendCommand = 'cd /d "{0}" && "{1}" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 >> "{2}" 2>&1' -f $BACKEND, $PY, $BACKEND_LOG
$workerCommand = 'cd /d "{0}" && "{1}" -m worker.worker >> "{2}" 2>&1' -f $BACKEND, $PY, $WORKER_LOG

$backend = Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' -ArgumentList @('/c', $backendCommand) -PassThru
$worker = Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' -ArgumentList @('/c', $workerCommand) -PassThru

if (-not (Test-Path (Join-Path $FRONTEND 'node_modules'))) {
    $install = Start-Process -WindowStyle Hidden -FilePath $npmCmd `
        -ArgumentList @('ci') `
        -WorkingDirectory $FRONTEND `
        -RedirectStandardOutput $FRONTEND_LOG `
        -RedirectStandardError (Join-Path $LOG_DIR 'frontend-error.log') `
        -PassThru -Wait
    if ($install.ExitCode -ne 0) {
        Write-Error "Frontend dependency install failed. Check $FRONTEND_LOG and logs\frontend-error.log"
        exit 1
    }
}

$frontend = Start-Process -WindowStyle Hidden -FilePath $npmCmd `
    -ArgumentList @('run', 'dev') `
    -WorkingDirectory $FRONTEND `
    -RedirectStandardOutput $FRONTEND_LOG `
    -RedirectStandardError (Join-Path $LOG_DIR 'frontend-error.log') `
    -PassThru

@{
    backend_pid = $backend.Id
    worker_pid = $worker.Id
    frontend_pid = $frontend.Id
    started_at = (Get-Date).ToString('o')
    backend_log = $BACKEND_LOG
    worker_log = $WORKER_LOG
    frontend_log = $FRONTEND_LOG
    frontend_error_log = (Join-Path $LOG_DIR 'frontend-error.log')
} | ConvertTo-Json | Set-Content -LiteralPath $PID_FILE

Write-Host 'All services running in background'
Write-Host 'Frontend: http://localhost:3000'
Write-Host 'Backend: http://127.0.0.1:8000/docs'
Write-Host "Backend log: $BACKEND_LOG"
Write-Host "Worker log: $WORKER_LOG"
Write-Host "Frontend log: $FRONTEND_LOG"
