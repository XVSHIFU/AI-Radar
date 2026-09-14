param([string]$BaseUrl='http://127.0.0.1:5175')
$ErrorActionPreference='Stop'
& agent-browser --session radar-mvp set viewport 1440 1000|Out-Null
& agent-browser --session radar-mvp open ($BaseUrl+'/ask')|Out-Null
$taskCode=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'check-readable-insights.js'))
$taskRaw=& agent-browser --session radar-mvp eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($taskCode)))
if($LASTEXITCODE -ne 0){throw $taskRaw}
$taskReport=$taskRaw|ConvertFrom-Json
[IO.File]::WriteAllText([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../docs/readable-insights-browser-results.json')),($taskReport|ConvertTo-Json -Depth 7))
$taskReport|Select-Object passed,total|ConvertTo-Json -Compress
if($taskReport.passed -ne $taskReport.total){exit 1}
