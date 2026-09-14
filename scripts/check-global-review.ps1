$ErrorActionPreference='Stop'
$taskChecks=[Collections.Generic.List[object]]::new()
function Js([string]$code){$raw=& agent-browser --session radar-mvp eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)));if($LASTEXITCODE -ne 0){throw $raw};$raw|ConvertFrom-Json}
function HoverCheck([string]$name,[string]$selector){Js ("document.querySelector('"+$selector+"').scrollIntoView({block:'center',behavior:'instant'})")|Out-Null;& agent-browser --session radar-mvp hover $selector|Out-Null;if($LASTEXITCODE -ne 0){throw "Hover failed: $selector"};$taskResult=Js ("(()=>{const e=document.querySelector('"+$selector+"'),s=getComputedStyle(e);return {decoration:s.textDecorationLine,hover:e.matches(':hover'),passed:e.matches(':hover')&&!s.textDecorationLine.includes('underline')};})()");$taskChecks.Add([pscustomobject]@{name=$name;passed=$taskResult.passed;actual=$taskResult})}
& agent-browser --session radar-mvp set viewport 1440 1000|Out-Null
& agent-browser --session radar-mvp open 'http://127.0.0.1:5175/?q=DeepSeek'|Out-Null
Js '(async()=>{for(let i=0;i<80&&!document.querySelector(".timeline-month__toggle");i++)await new Promise(r=>setTimeout(r,50));})()'|Out-Null
HoverCheck 'month_hover_no_underline' '.timeline-month__toggle'
HoverCheck 'event_hover_no_underline' '.timeline-event__title a'
HoverCheck 'clear_no_underline' '.filter-clear'
& agent-browser --session radar-mvp open 'http://127.0.0.1:5175/ask'|Out-Null
Js '(async()=>{[...document.querySelectorAll("button")].find(b=>b.textContent.trim()==="近7天").click();for(let i=0;i<80&&!document.querySelector(".ask-events h3 a");i++)await new Promise(r=>setTimeout(r,50));})()'|Out-Null
HoverCheck 'statistics_event_hover_no_underline' '.ask-events h3 a'
& agent-browser --session radar-mvp set viewport 390 1000|Out-Null
foreach($view in @('A','B','C')){
 Js "document.querySelector('button[data-view=$view]').click()"|Out-Null
 $selector=if($view -eq 'C'){'.heatmap'}else{'.chart-scroll'}
 Js ("(()=>{const e=document.querySelector('"+$selector+"');e.scrollLeft=0;e.focus();return true})()")|Out-Null
 & agent-browser --session radar-mvp press ArrowRight|Out-Null
 Start-Sleep -Milliseconds 250
 $taskResult=Js ("(()=>{const e=document.querySelector('"+$selector+"');return {passed:document.activeElement===e&&e.scrollLeft>0,scroll:e.scrollLeft,hint:document.querySelector('.chart-mobile-hint')?.textContent};})()")
 $taskChecks.Add([pscustomobject]@{name=("keyboard_scroll_"+$view);passed=$taskResult.passed;actual=$taskResult})
}
$taskReport=[pscustomobject]@{observed_at=[DateTimeOffset]::UtcNow.ToString('o');passed=@($taskChecks|Where-Object passed).Count;total=$taskChecks.Count;checks=$taskChecks}
[IO.File]::WriteAllText([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../docs/global-review-browser-results.json')),($taskReport|ConvertTo-Json -Depth 6))
$taskReport|Select-Object passed,total|ConvertTo-Json -Compress
if($taskReport.passed -ne $taskReport.total){exit 1}
