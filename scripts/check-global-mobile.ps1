param([string]$BaseUrl='http://127.0.0.1:5175')
$ErrorActionPreference='Stop'
$taskChecks=[Collections.Generic.List[object]]::new()
function Js([string]$code){$raw=& agent-browser --session radar-mvp eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)));if($LASTEXITCODE -ne 0){throw $raw};$raw|ConvertFrom-Json}
function Check([string]$name,[string]$code){try{$actual=Js ("(async()=>{const pause=ms=>new Promise(r=>setTimeout(r,ms));const until=async f=>{for(let i=0;i<80;i++){if(f())return;await pause(50);}throw Error('UI timeout')};const p=()=>document.querySelector('[data-testid=global-assistant]');const entry=()=>document.querySelector('[data-testid=assistant-toggle]');"+$code+"})()");$taskChecks.Add([pscustomobject]@{name=$name;passed=$actual.passed -eq $true;actual=$actual})}catch{$taskChecks.Add([pscustomobject]@{name=$name;passed=$false;error=$_.Exception.Message})}}
& agent-browser --session radar-mvp set viewport 390 1000|Out-Null
& agent-browser --session radar-mvp open ($BaseUrl+'/')|Out-Null
Check 'mobile_open_focus_and_background_lock' "entry().click();await pause(100);const bg=document.querySelector('.app-shell');return {passed:p().contains(document.activeElement)&&p().getBoundingClientRect().width===390&&(document.querySelector('.app-content main').inert&&document.querySelector('.app-rail').inert)&&(getComputedStyle(document.body).overflow==='hidden'||getComputedStyle(document.documentElement).overflow==='hidden'||getComputedStyle(document.body).position==='fixed')};"
& agent-browser --session radar-mvp press Shift+Tab|Out-Null
Check 'mobile_focus_cycles_inside' "return {passed:p().contains(document.activeElement)};"
Check 'long_answer_return_stays_visible' "const old=window.fetch;window.fetch=(u,o)=>String(u).endsWith('/ask')?Promise.resolve(new Response(JSON.stringify({answer:'合成滚动验收。'.repeat(700),citations:[],execution_status:'completed',answer_status:'answered',scope_total:1,retrieved_count:1,summarized_count:1,citation_count:0,coverage:'complete'}),{status:200,headers:{'content-type':'application/json'}})):old(u,o);const area=p().querySelector('textarea');area.value='长回答滚动';area.dispatchEvent(new Event('input',{bubbles:true}));await pause(0);[...p().querySelectorAll('button')].find(b=>b.textContent.trim()==='开始分析').click();await until(()=>p().querySelector('[data-testid=ask-answer]'));p().scrollTop=p().scrollHeight;const scroller=p().querySelector('.assistant-body');if(scroller)scroller.scrollTop=scroller.scrollHeight;await pause(0);const r=p().querySelector('.assistant-close').getBoundingClientRect();window.fetch=old;return {passed:r.top>=0&&r.bottom<=innerHeight&&document.documentElement.scrollWidth<=innerWidth,returnTop:r.top,returnBottom:r.bottom};"
& agent-browser --session radar-mvp press Escape|Out-Null
Check 'mobile_close_restores_background_and_focus' "const bg=document.querySelector('.app-shell');return {passed:p().getClientRects().length===0&&!document.querySelector('.app-content main').inert&&!document.querySelector('.app-rail').inert&&document.activeElement===entry()};"
& agent-browser --session radar-mvp set viewport 1440 1000|Out-Null
& agent-browser --session radar-mvp open ($BaseUrl+'/')|Out-Null
Check 'desktop_assistant_and_reader_both_open' "entry().click();await until(()=>document.querySelector('article.timeline-event a'));document.querySelector('article.timeline-event a').click();await until(()=>document.querySelector('dialog:modal'));return {passed:p().getClientRects().length>0&&!!document.querySelector('dialog:modal')};"
& agent-browser --session radar-mvp press Escape|Out-Null
Check 'escape_only_closes_top_reader' "await pause(0);return {passed:!document.querySelector('dialog:modal')&&p().getClientRects().length>0};"
$taskReport=[pscustomobject]@{observed_at=[DateTimeOffset]::UtcNow.ToString('o');layer='browser_with_synthetic_long_answer';passed=@($taskChecks|Where-Object passed).Count;total=$taskChecks.Count;checks=$taskChecks}
[IO.File]::WriteAllText([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../docs/global-mobile-browser-results.json')),($taskReport|ConvertTo-Json -Depth 7))
$taskReport|Select-Object passed,total|ConvertTo-Json -Compress
if($taskReport.passed -ne $taskReport.total){exit 1}
