param([string]$BaseUrl='http://127.0.0.1:5175')
$ErrorActionPreference='Stop'
$session='radar-mvp'
$results=[Collections.Generic.List[object]]::new()
function Js([string]$code) {
 $raw=& agent-browser --session $session eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)))
 if($LASTEXITCODE -ne 0){throw "Browser evaluation failed: $raw"}
 $raw|ConvertFrom-Json
}
function Open([string]$path) { & agent-browser --session $session open ($BaseUrl+$path)|Out-Null }
function Check([string]$name,[string]$code,[string]$layer='fixture_api_browser') {
 try {
  $setup="(async()=>{const pause=ms=>new Promise(r=>setTimeout(r,ms));const until=async f=>{for(let i=0;i<100;i++){if(f())return;await pause(50);}throw Error('UI state timed out');};const t=id=>document.querySelector('[data-testid='+id+']');const body=()=>document.body.innerText;const rows=()=>[...document.querySelectorAll('article.timeline-event')].filter(x=>x.getClientRects().length);const modal=()=>[...document.querySelectorAll('dialog:modal')].at(-1);const set=(el,v)=>{if(!el)throw Error('Missing input');el.value=v;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};const button=x=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===x);"
  $actual=Js ($setup+$code+"})()")
  $results.Add([pscustomobject]@{check=$name;layer=$layer;passed=$actual.passed -eq $true;actual=$actual})
 }catch{$results.Add([pscustomobject]@{check=$name;layer=$layer;passed=$false;error=$_.Exception.Message})}
 Write-Output ("Checked "+$name)
}
try {
 & agent-browser --session $session tab new ($BaseUrl+'/')|Out-Null
 & agent-browser --session $session set viewport 1680 1000|Out-Null
 Open '/'
 Check 'home_only_month_folds' "await until(()=>rows().length===10);return {passed:body().includes('精确匹配 32 条')&&!document.querySelector('.timeline-year button')?.classList.contains('timeline-year__toggle')&&!document.querySelector('[data-testid=timeline-day-toggle]')&&!document.querySelector('.filter-clear')&&!button('展开')&&!button('折叠'),rows:rows().length};"
 Check 'home_month_fold_and_restore' "const m=document.querySelector('.timeline-month__toggle');m.click();await pause(0);const hidden=rows().length===0;m.click();await pause(0);return {passed:hidden&&rows().length===10};"
 & agent-browser --session $session click 'label:has(input[value=industry])'|Out-Null
 Check 'home_pointer_selection_no_outer_ring' "await until(()=>rows().length===5);const r=document.querySelector('input[value=industry]');const s=getComputedStyle(r);return {passed:r.checked&&(s.outlineStyle==='none'||parseFloat(s.outlineWidth)===0)&&!!document.querySelector('.filter-clear'),outline:s.outlineWidth};"
 & agent-browser --session $session press Tab|Out-Null
 Check 'home_keyboard_focus_remains_visible' "const a=document.activeElement,s=getComputedStyle(a);return {passed:a.matches(':focus-visible')&&parseFloat(s.outlineWidth)>=2,tag:a.tagName,outline:s.outlineWidth};"
 Check 'home_search_clear_recovers_full_scope' "document.querySelector('.filter-clear').click();await until(()=>rows().length===10);set(document.querySelector('input[placeholder]'),'DeepSeek');await until(()=>rows().length===6);const filtered=body().includes('精确匹配 6 条');document.querySelector('.filter-clear').click();await until(()=>rows().length===10);return {passed:filtered&&body().includes('精确匹配 32 条')&&!document.querySelector('.filter-clear')};"
 foreach($width in @(390,768,1440,1680)){
  & agent-browser --session $session set viewport $width 1000|Out-Null
  Check ("home_width_"+$width) "return {passed:document.documentElement.scrollWidth<=innerWidth,width:innerWidth,scroll:document.documentElement.scrollWidth};"
 }

 & agent-browser --session $session set viewport 1680 1000|Out-Null
 Open '/?q=DeepSeek'
 Check 'reader_direct_evidence_and_no_page_exit' "await until(()=>rows().length===6);const a=rows()[0].querySelector('a');a.focus();a.click();await until(()=>modal()?.querySelector('blockquote'));return {passed:location.pathname==='/'&&modal().innerText.includes('synthetic-v1-p1')===false&&!!modal().querySelector('details')&&!modal().innerText.includes('打开完整事件页')&&![...modal().querySelectorAll('button')].some(x=>x.textContent.trim()==='关闭')&&modal().contains(document.activeElement)};"
 Check 'reader_provenance_visible_on_demand' "modal().querySelector('details summary').click();await pause(0);return {passed:modal().innerText.includes('synthetic-v1-p1')&&modal().innerText.includes('30000000-0000-4000-8000-000000000001')};"
 Check 'reader_internal_blank_keeps_open' "const d=modal(),r=d.getBoundingClientRect();d.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:r.left+10,clientY:r.top+150}));await pause(0);return {passed:modal()===d};"
 Check 'source_child_right_parent_left' "t('source-open').click();await until(()=>modal()?.dataset.testid==='drawer-source');await pause(250);const p=t('drawer-event').getBoundingClientRect(),c=modal().getBoundingClientRect();return {passed:p.left<c.left&&Math.abs(c.right-(innerWidth-24))<2&&modal().contains(document.activeElement),parentLeft:p.left,childLeft:c.left,right:c.right};"
 & agent-browser --session $session mouse move 100 200|Out-Null
 & agent-browser --session $session mouse down|Out-Null
 & agent-browser --session $session mouse up|Out-Null
 Check 'source_outside_click_closes_top_only' "await until(()=>modal()?.dataset.testid==='drawer-event');return {passed:!!new URLSearchParams(location.search).get('event')&&!new URLSearchParams(location.search).has('source')};"
 & agent-browser --session $session press Escape|Out-Null
 Check 'event_escape_preserves_filter_focus' "await until(()=>!modal());return {passed:new URLSearchParams(location.search).get('q')==='DeepSeek'&&rows().length===6&&document.activeElement?.tagName==='A'&&document.body.style.position!=='fixed'};"
 Open '/?event=00000000-0000-4000-8000-000000000002'
 Check 'reader_deeplink_modal_focus' "await until(()=>modal()?.querySelector('blockquote'));return {passed:modal().contains(document.activeElement)};"
 & agent-browser --session $session mouse move 100 200|Out-Null
 & agent-browser --session $session mouse down|Out-Null
 & agent-browser --session $session mouse up|Out-Null
 Check 'event_outside_click_closes' "await until(()=>!modal());return {passed:!new URLSearchParams(location.search).has('event')};"
 & agent-browser --session $session set viewport 390 1000|Out-Null
 Open '/?event=00000000-0000-4000-8000-000000000002'
 Check 'mobile_event_and_source_fullscreen_return' "await until(()=>modal()?.querySelector('blockquote'));await pause(250);const a=modal().getBoundingClientRect();t('source-open').click();await until(()=>modal()?.dataset.testid==='drawer-source');await pause(250);const b=modal().getBoundingClientRect();modal().querySelector('[data-testid=drawer-back]').click();await until(()=>modal()?.dataset.testid==='drawer-event');modal().querySelector('[data-testid=drawer-back]').click();await until(()=>!modal());return {passed:a.left===0&&a.width===390&&b.left===0&&b.width===390,first:a.width,second:b.width};"
 Open '/preview?event=00000000-0000-4000-8000-000000000002'
 Check 'preview_reader_parity' "await until(()=>modal()?.querySelector('blockquote'));const okay=!modal().innerText.includes('打开完整事件页')&&![...modal().querySelectorAll('button')].some(b=>b.textContent.trim()==='关闭');modal().querySelector('header button').click();await until(()=>!modal());return {passed:okay&&location.pathname==='/preview'};"


} finally {
 $report=[pscustomobject]@{observed_at=[DateTimeOffset]::UtcNow.ToString('o');base_url=$BaseUrl;passed=@($results|Where-Object passed).Count;total=$results.Count;checks=$results}
 [IO.File]::WriteAllText((Join-Path $PSScriptRoot '../docs/global-home-browser-results.json'),($report|ConvertTo-Json -Depth 8))
}
$report | Select-Object passed,total | ConvertTo-Json -Compress
if (@($results|Where-Object { -not $_.passed }).Count) { exit 1 }
