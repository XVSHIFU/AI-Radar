$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$checks = [Collections.Generic.List[object]]::new()
$startedAt = [DateTimeOffset]::UtcNow
function Invoke-Checked([string]$Executable, [string[]]$CommandArguments) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $exitCode = -1
    try {
        & $Executable @CommandArguments
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) { throw "$Executable failed with exit code $exitCode" }
    } finally {
        $timer.Stop()
        $checks.Add([pscustomobject]@{command=(@($Executable)+$CommandArguments)-join ' ';exit_code=$exitCode;passed=($exitCode -eq 0);elapsed_ms=$timer.ElapsedMilliseconds})
    }
}
try {
    Push-Location (Join-Path $projectRoot 'backend')
    try {
        Invoke-Checked uv @('run','--frozen','ruff','check','.')
        Invoke-Checked uv @('run','--frozen','mypy','src','app')
        Invoke-Checked uv @('run','--frozen','pytest','-q')
        Invoke-Checked uv @('run','--frozen','python','../scripts/check-database-unavailable.py')
        Invoke-Checked uv @('run','--frozen','python','../scripts/check-structure.py')
        Invoke-Checked uv @('run','--frozen','python','../scripts/check-query-plan.py')
        Invoke-Checked uv @('run','--frozen','python','../scripts/freeze-openapi.py')
        Invoke-Checked uv @('run','--frozen','alembic','upgrade','head','--sql')
    } finally { Pop-Location }
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        Invoke-Checked pnpm @('typecheck')
        Invoke-Checked pnpm @('test')
        Invoke-Checked pnpm @('build')
    } finally { Pop-Location }
} finally {
    $report=[pscustomobject]@{started_at=$startedAt.ToString('o');finished_at=[DateTimeOffset]::UtcNow.ToString('o');layer='local_static_unit_offline_migration_build';postgres_integration_executed=$false;live_model_executed=$false;passed=@($checks|Where-Object passed).Count;expected_steps=11;checks=$checks}
    [IO.File]::WriteAllText((Join-Path $projectRoot 'docs/local-checks.json'),($report|ConvertTo-Json -Depth 6))
}
Write-Output 'Local checks passed. This runner does not execute PostgreSQL or live model integration acceptance.'
