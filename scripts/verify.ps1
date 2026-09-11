$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
function Invoke-Checked([string]$Executable, [string[]]$CommandArguments) {
    & $Executable @CommandArguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable failed with exit code $LASTEXITCODE" }
}
Push-Location (Join-Path $projectRoot 'backend')
try {
    Invoke-Checked uv @('run','--frozen','ruff','check','.')
    Invoke-Checked uv @('run','--frozen','mypy','src')
    Invoke-Checked uv @('run','--frozen','pytest','-q')
    Invoke-Checked uv @('run','--frozen','alembic','upgrade','head','--sql')
} finally { Pop-Location }
Push-Location (Join-Path $projectRoot 'frontend')
try {
    Invoke-Checked pnpm @('typecheck')
    Invoke-Checked pnpm @('test')
    Invoke-Checked pnpm @('build')
} finally { Pop-Location }
Write-Output 'Local checks passed. PostgreSQL/live models are only validated if their dedicated integration checks actually ran.'
