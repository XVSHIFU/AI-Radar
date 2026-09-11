$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$statePath = Join-Path $projectRoot '.run/processes.json'
if (-not (Test-Path -LiteralPath $statePath)) { Write-Output 'No recorded development processes.'; exit 0 }
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
if ([IO.Path]::GetFullPath($state.project_root) -ne [IO.Path]::GetFullPath($projectRoot)) { throw 'Recorded project path does not match this workspace.' }
foreach ($processId in @($state.api_pid, $state.frontend_pid)) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $([int]$processId)"
    if ($null -eq $process) { continue }
    $belongsToProject = ($process.ExecutablePath -and $process.ExecutablePath.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) -or ($process.CommandLine -and $process.CommandLine.Contains($projectRoot + [IO.Path]::DirectorySeparatorChar))
    if (-not $belongsToProject) { throw "Process $processId no longer belongs to this workspace; refusing to stop it." }
    if ($process.CreationDate -gt ([DateTimeOffset]::Parse($state.started_at)).LocalDateTime.AddSeconds(2)) { throw "Process $processId was replaced; refusing to stop it." }
    Stop-Process -Id $processId
}
Remove-Item -LiteralPath $statePath
Write-Output 'Recorded development processes stopped.'
