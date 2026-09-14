param([string]$BaseUrl='http://127.0.0.1:5175')
$ErrorActionPreference='Stop';$session='radar-mvp';$checks=[Collections.Generic.List[object]]::new()
function Js([string]$code){$raw=& agent-browser --session $session eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)));if($LASTEXITCODE -ne 0){throw $raw};$raw|ConvertFrom-Json}
function Open([string]$path){& agent-browser --session $session open ($BaseUrl+$path)|Out-Null}
$setup=@'
const t=id=>document.querySelector('[data-testid="'+id+'"]'),pause=ms=>new Promise(r=>setTimeout(r,ms)),until=async f=>{for(let i=0;i<100;i++){if(f())return;await pause(40)}throw Error('Timed out')},rect=e=>e.getBoundingClientRect(),button=s=>[...document.querySelectorAll('button')].find(e=>e.textContent.trim()===s);
'@
function Check([string]$name,[string]$code){try{$v=Js ('(async()=>{'+$setup+$code+'})()');$checks.Add([pscustomobject]@{name=$name;passed=$v.passed -eq $true;actual=$v})}catch{$checks.Add([pscustomobject]@{name=$name;passed=$false;error=$_.Exception.Message})};Write-Output ('Checked '+$name)}
foreach($taskWidth in @(1440,1680)){
 & agent-browser --session $session set viewport $taskWidth 1000|Out-Null
 Js "localStorage.setItem('assistant-width','340');localStorage.setItem('history-width','180')"|Out-Null
 Open '/'
 Check ('history_readable_from_saved_340_at_'+$taskWidth) "await until(()=>t('assistant-toggle'));await pause(250);t('assistant-toggle').click();await pause(50);t('history-toggle').click();await pause(200);const panel=rect(t('global-assistant')),main=rect(document.querySelector('.assistant-main')),history=rect(t('history-panel'));const first=main.width>=338&&history.width>=180&&panel.width<=innerWidth/2+1;const h=t('history-resizer');h.dispatchEvent(new PointerEvent('pointerdown',{clientX:history.left,clientY:200,bubbles:true}));window.dispatchEvent(new PointerEvent('pointermove',{clientX:history.left-250,clientY:200,bubbles:true}));window.dispatchEvent(new PointerEvent('pointerup',{bubbles:true}));await pause(100);return {passed:first&&rect(document.querySelector('.assistant-main')).width>=338&&rect(t('global-assistant')).width<=innerWidth/2+1,panel:panel.toJSON(),main:main.toJSON(),history:history.toJSON()};"
}
& agent-browser --session $session set viewport 390 1000|Out-Null
Open '/ask'
Check 'mobile_entry_has_own_navigation_space' "await until(()=>t('assistant-toggle'));const entry=t('assistant-toggle'),rail=document.querySelector('.app-rail');return {passed:!!entry.closest('.app-rail')&&getComputedStyle(entry).position==='static'&&rect(entry).height>=44&&rect(entry).right<=innerWidth&&getComputedStyle(rail).position==='sticky',entry:rect(entry).toJSON(),rail:rect(rail).toJSON()};"
Check 'ABC_scroll_has_no_entry_overlap' "button('近7天').click();await until(()=>t('insights-visual'));const bad=[];for(const view of ['A','B','C']){document.querySelector('button[data-view='+view+']').click();await pause(50);scrollTo(0,0);const visual=t('insights-visual'),start=rect(visual).top+scrollY,end=start+rect(visual).height;for(let y=Math.max(0,start-600);y<=end;y+=44){scrollTo(0,y);await pause(20);const e=rect(t('assistant-toggle')),rail=rect(document.querySelector('.app-rail'));for(const label of visual.querySelectorAll('.rank-row b,.daily-count b,.daily-count small,.heat-compact button,.heat-legend,.ask-data-table summary')){const r=rect(label);if(r.top<rail.bottom||r.bottom>innerHeight)continue;if(r.left<e.right&&r.right>e.left&&r.top<e.bottom&&r.bottom>e.top)bad.push({view,label:label.textContent})}}}scrollTo(0,0);return {passed:bad.length===0,overlaps:bad};"
$report=[pscustomobject]@{observed_at=[DateTimeOffset]::UtcNow.ToString('o');layer='finish_review_layout_regression';passed=@($checks|Where-Object passed).Count;total=$checks.Count;checks=$checks}
[IO.File]::WriteAllText([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../docs/readable-finish-layout-results.json')),($report|ConvertTo-Json -Depth 8))
$report|Select-Object passed,total|ConvertTo-Json -Compress
if($report.passed -ne $report.total){exit 1}
