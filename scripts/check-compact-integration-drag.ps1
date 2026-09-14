param([string]$BaseUrl='http://127.0.0.1:5175')
$ErrorActionPreference='Stop'
function Js([string]$code){$out=& agent-browser --session radar-mvp eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)));if($LASTEXITCODE -ne 0){throw $out};$out|ConvertFrom-Json}
& agent-browser --session radar-mvp set viewport 1680 1000|Out-Null
& agent-browser --session radar-mvp open ($BaseUrl+'/ask?demo=1')|Out-Null
Js '(async()=>{for(let i=0;i<100;i++){if(document.querySelector("[data-testid=assistant-toggle]"))break;await new Promise(r=>setTimeout(r,30))}document.querySelector("[data-testid=assistant-toggle]").click();await new Promise(r=>setTimeout(r,100));document.querySelector("[data-testid=history-toggle]").click();await new Promise(r=>setTimeout(r,100))})()'|Out-Null
$a=Js 'document.querySelector("#global-assistant").getBoundingClientRect().toJSON()'
& agent-browser --session radar-mvp mouse move ([int]$a.left+2) 340|Out-Null
& agent-browser --session radar-mvp mouse down|Out-Null
& agent-browser --session radar-mvp mouse move ([int]$a.left-78) 340|Out-Null
& agent-browser --session radar-mvp mouse up|Out-Null
$b=Js 'document.querySelector("#global-assistant").getBoundingClientRect().toJSON()'
$h=Js 'document.querySelector(".history-panel").getBoundingClientRect().toJSON()'
$hit=Js '(()=>{const r=document.querySelector(".history-panel").getBoundingClientRect();return document.elementFromPoint(r.left+2,340).className})()'
& agent-browser --session radar-mvp mouse move ([int]$h.left+2) 340|Out-Null
& agent-browser --session radar-mvp mouse down|Out-Null
& agent-browser --session radar-mvp mouse move ([int]$h.left-18) 340|Out-Null
& agent-browser --session radar-mvp mouse up|Out-Null
$h2=Js 'document.querySelector(".history-panel").getBoundingClientRect().toJSON()'
$r=[pscustomobject]@{assistant_drag=$b.width -gt $a.width;half_limit=$b.width -le 840;history_drag=$h2.width -gt $h.width;before=$a.width;after=$b.width;history_before=$h.width;history_after=$h2.width;pointer_target=$hit}
$r|ConvertTo-Json|Set-Content docs/compact-integration-drag-results.json
$r|ConvertTo-Json -Compress
if(!$r.assistant_drag -or !$r.half_limit -or !$r.history_drag){exit 1}
