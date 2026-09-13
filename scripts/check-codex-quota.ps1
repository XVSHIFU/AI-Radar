param([double]$StopBelow = 80)
$ErrorActionPreference = 'Stop'
$sessionRoot = Join-Path $env:USERPROFILE '.codex/sessions'
# A resumed session can continue writing yesterday's file. Select by freshness,
# not the local calendar directory (which can also differ from UTC).
$recentFiles = @(Get-ChildItem -LiteralPath $sessionRoot -Recurse -File -Filter '*.jsonl' |
    Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 12)
$observations = foreach ($sessionFile in $recentFiles) {
    $records = @(& rg --no-heading --no-filename '"type"\s*:\s*"token_count"' $sessionFile.FullName | Select-Object -Last 8)
    foreach ($line in $records) {
        try { $entry = $line | ConvertFrom-Json } catch { continue }
        if ($entry.type -ne 'event_msg' -or $entry.payload.type -ne 'token_count' -or $entry.payload.rate_limits.limit_id -ne 'codex') { continue }
        foreach ($window in @($entry.payload.rate_limits.primary, $entry.payload.rate_limits.secondary)) {
            if ($null -ne $window) {
                [pscustomobject]@{observed_at=$entry.timestamp; window_minutes=$window.window_minutes; remaining_percent=(100 - $window.used_percent); stop_at_or_below=$StopBelow}
            }
        }
    }
}
$latest = @($observations | Group-Object window_minutes | ForEach-Object { $_.Group | Sort-Object observed_at -Descending | Select-Object -First 1 })
if ($latest.Count -eq 0) { Write-Output '{"status":"unknown","action":"pause_paid_work"}'; exit 2 }
$latest | ConvertTo-Json -Compress
if ($latest | Where-Object { $_.remaining_percent -le $StopBelow }) { exit 3 }
$stale = $latest | Where-Object { ([DateTimeOffset]::UtcNow - ([DateTimeOffset]$_.observed_at)).TotalMinutes -gt 10 }
if ($stale) { Write-Output '{"status":"stale","action":"refresh_before_paid_work"}'; exit 2 }
