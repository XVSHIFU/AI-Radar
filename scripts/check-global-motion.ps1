$ErrorActionPreference='Stop'
function Js([string]$code){$raw=& agent-browser --session radar-mvp eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)));if($LASTEXITCODE -ne 0){throw $raw};$raw|ConvertFrom-Json}
$taskResults=[Collections.Generic.List[object]]::new()
& agent-browser --session radar-mvp set media light|Out-Null
& agent-browser --session radar-mvp open 'http://127.0.0.1:5175/ask'|Out-Null
$taskNormal=Js '(async()=>{const pause=ms=>new Promise(r=>setTimeout(r,ms)),b=t=>[...document.querySelectorAll("button")].find(x=>x.textContent.trim()===t);b("近7天").click();for(let i=0;i<80&&!document.querySelector(".chart-flow");i++)await pause(50);b("播放流动").click();await pause(50);const path=document.querySelector(".chart-flow"),before=getComputedStyle(path).strokeDashoffset;await pause(400);const flowChanged=before!==getComputedStyle(path).strokeDashoffset;b("暂停流动").click();await pause(0);const flowPaused=getComputedStyle(path).animationName==="none";document.querySelector("button[data-view=B]").click();await pause(0);b("播放日期").click();await pause(0);const areas=()=>[...document.querySelectorAll("path.chart-area")].map(x=>x.getAttribute("d")).join("|"),initial=areas();await pause(1100);const revealed=initial!==areas()&&!!document.querySelector(".chart-cursor");b("暂停播放").click();await pause(0);const stopped=areas();await pause(1100);return [{name:"flow_animation_changes_then_pauses",passed:flowChanged&&flowPaused},{name:"area_playback_changes_geometry_then_stops",passed:revealed&&stopped===areas()}];})()'
foreach($row in $taskNormal){$taskResults.Add($row)}
& agent-browser --session radar-mvp set media light reduced-motion|Out-Null
& agent-browser --session radar-mvp open 'http://127.0.0.1:5175/ask?motion-check=1'|Out-Null
$taskReduced=Js '(async()=>{const pause=ms=>new Promise(r=>setTimeout(r,ms)),b=t=>[...document.querySelectorAll("button")].find(x=>x.textContent.trim()===t);b("近7天").click();for(let i=0;i<80&&!document.querySelector(".chart-flow");i++)await pause(50);const flow=!!b("播放流动").disabled&&getComputedStyle(document.querySelector(".chart-flow")).animationName==="none";document.querySelector("button[data-view=B]").click();await pause(0);return {name:"reduced_motion_disables_both_playbacks",passed:matchMedia("(prefers-reduced-motion: reduce)").matches&&flow&&b("播放日期").disabled};})()'
$taskResults.Add($taskReduced)
& agent-browser --session radar-mvp set media light|Out-Null
$taskReport=[pscustomobject]@{observed_at=[DateTimeOffset]::UtcNow.ToString('o');passed=@($taskResults|Where-Object passed).Count;total=$taskResults.Count;checks=$taskResults}
[IO.File]::WriteAllText([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../docs/global-motion-browser-results.json')),($taskReport|ConvertTo-Json -Depth 6))
$taskReport|Select-Object passed,total|ConvertTo-Json -Compress
if($taskReport.passed -ne $taskReport.total){exit 1}
