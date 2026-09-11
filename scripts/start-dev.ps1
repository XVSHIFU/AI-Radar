param([switch]$Fixture, [int]$ApiPort = 8000, [int]$FrontendPort = 5173)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$runtimeRoot = Join-Path $projectRoot '.run'
$pythonPath = Join-Path $projectRoot 'backend/.venv/Scripts/python.exe'
$vitePath = Join-Path $projectRoot 'frontend/node_modules/vite/bin/vite.js'
if (-not (Test-Path -LiteralPath $pythonPath) -or -not (Test-Path -LiteralPath $vitePath)) { throw 'Install dependencies first: backend: uv sync --frozen; frontend: pnpm install --frozen-lockfile' }
foreach ($port in @($ApiPort, $FrontendPort)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { throw "Port $port is already in use. Stop the existing service or choose another port." }
}
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$oldMode = $env:RADAR_DATA_MODE
$oldApiTarget = $env:RADAR_API_TARGET
$started = @()
try {
    $env:RADAR_DATA_MODE = if ($Fixture) { 'fixture' } else { 'postgres' }
    $env:RADAR_API_TARGET = "http://127.0.0.1:$ApiPort"
    $api = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$ApiPort") -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeRoot 'api.out.log') -RedirectStandardError (Join-Path $runtimeRoot 'api.err.log') -PassThru
    $started += $api
    $nodePath = (Get-Command node).Source
    $web = Start-Process -FilePath $nodePath -ArgumentList @(('"' + $vitePath + '"'),'--host','127.0.0.1','--port',"$FrontendPort",'--strictPort') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeRoot 'frontend.out.log') -RedirectStandardError (Join-Path $runtimeRoot 'frontend.err.log') -PassThru
    $started += $web
    $state = @{project_root=$projectRoot;api_pid=$api.Id;frontend_pid=$web.Id;api_port=$ApiPort;frontend_port=$FrontendPort;data_mode=$env:RADAR_DATA_MODE;started_at=[DateTimeOffset]::UtcNow.ToString('o')}
    [IO.File]::WriteAllText((Join-Path $runtimeRoot 'processes.json'), ($state | ConvertTo-Json))
    Write-Output "Frontend: http://127.0.0.1:$FrontendPort"
    Write-Output "API: http://127.0.0.1:$ApiPort/docs"
    Write-Output "Mode: $($state.data_mode). Logs: $runtimeRoot. Use scripts/stop-dev.ps1 to stop."
} catch {
    foreach ($process in $started) { if (-not $process.HasExited) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue } }
    throw
} finally { $env:RADAR_DATA_MODE = $oldMode; $env:RADAR_API_TARGET = $oldApiTarget }
