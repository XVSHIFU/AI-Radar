param([string]$BaseUrl='http://127.0.0.1:5175')
$ErrorActionPreference='Stop'
$session='radar-mvp'
$results=[Collections.Generic.List[object]]::new()
function Js([string]$code) {
  $raw=& agent-browser --session $session eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)))
  if ($LASTEXITCODE -ne 0) { throw "Browser evaluation failed: $raw" }
  $raw | ConvertFrom-Json
}
function Open([string]$path) {
  & agent-browser --session $session open ($BaseUrl+$path) | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Page unavailable: $path" }
}
function Check([string]$name,[string]$code,[string]$layer='fixture_api_browser') {
  try {
    $setup="(async()=>{const pause=ms=>new Promise(r=>setTimeout(r,ms));const until=async f=>{for(let i=0;i<100;i++){if(f())return;await pause(50);}throw Error('UI state timed out');};const test=id=>document.querySelector('[data-testid='+id+']');const rows=()=>[...document.querySelectorAll('[data-testid=preview-event]')].filter(x=>x.getClientRects().length);const reader=()=>document.querySelector('[data-testid=preview-reader][open]');const set=(el,v)=>{if(!el)throw Error('Missing input');el.value=v;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};const toggle=(level,key)=>[...document.querySelectorAll('[data-testid=timeline-'+level+'-toggle]')].find(x=>x.dataset.key===key);"
    $actual=Js ($setup+$code+"})()")
    $results.Add([pscustomobject]@{check=$name;layer=$layer;passed=$actual.passed -eq $true;actual=$actual})
  } catch {$results.Add([pscustomobject]@{check=$name;layer=$layer;passed=$false;error=$_.Exception.Message})}
}
try {
  & agent-browser --session $session tab new ($BaseUrl+'/preview') | Out-Null
  & agent-browser --session $session set viewport 1440 1000 | Out-Null
  Open '/preview'
  Check 'preview_initial_fixture_and_precise_total' "await until(()=>rows().length===10);return {passed:document.body.innerText.includes('32')&&document.body.innerText.includes('合成')&&[...document.querySelectorAll('a')].some(a=>a.getAttribute('href')==='/'),firstEventTop:rows()[0].getBoundingClientRect().top};"
  Check 'search_filters_without_submit_and_updates_url' "set(test('preview-search'),'DeepSeek');await until(()=>rows().length===6);return {passed:new URLSearchParams(location.search).get('q')==='DeepSeek'&&rows().every(x=>x.textContent.includes('DeepSeek'))};"
  Open '/preview'
  Check 'category_filters_with_one_action' "await until(()=>rows().length===10);[...document.querySelectorAll('[data-testid=preview-category]')].find(x=>x.dataset.category==='agent_tool').click();await until(()=>rows().length===6);return {passed:new URLSearchParams(location.search).get('category')==='agent_tool'};"
  Open '/preview'
  Check 'date_range_is_inclusive_and_visible' "await until(()=>rows().length===10);test('preview-date-toggle').click();await pause(0);set(document.querySelector('input[name=date_from]'),'2026-09-12');set(document.querySelector('input[name=date_to]'),'2026-09-12');await until(()=>rows().length===5);return {passed:new URLSearchParams(location.search).get('date_from')==='2026-09-12'&&new URLSearchParams(location.search).get('date_to')==='2026-09-12'};"
  Check 'invalid_date_range_has_feedback' "set(document.querySelector('input[name=date_from]'),'2026-09-13');await pause(450);return {passed:!!document.querySelector('[role=alert]')&&rows().length===0};"
  Open '/preview'
  Check 'calendar_independent_folding' "await until(()=>rows().length===10);toggle('day','2026-09-12').click();await pause(0);const day=rows().length===5;toggle('month','2026-09').click();await pause(0);const month=rows().length===0;toggle('month','2026-09').click();await pause(0);const kept=rows().length===5;toggle('year','2026').click();await pause(0);const year=rows().length===0;toggle('year','2026').click();await pause(0);return {passed:day&&month&&kept&&year&&rows().length===5};"
  Check 'pagination_keeps_closed_day' "test('preview-load-more').click();await until(()=>!!toggle('day','2026-09-10'));const kept=toggle('day','2026-09-12').getAttribute('aria-expanded')==='false';toggle('day','2026-09-12').click();await pause(0);return {passed:kept&&rows().length===20};"
  Open '/preview'
  Check 'one_click_opens_saved_evidence' "await until(()=>rows().length===10);const a=rows().flatMap(x=>[...x.querySelectorAll('a')]).find(x=>x.pathname.endsWith('000000000002'));a.scrollIntoView({block:'center'});a.focus();window.__mvpOrigin={href:a.getAttribute('href'),scroll:scrollY};a.click();await until(()=>reader()?.querySelector('blockquote')?.textContent.includes('DeepSeek'));return {passed:document.querySelectorAll('dialog[open]').length===1&&new URLSearchParams(location.search).get('event')==='00000000-0000-4000-8000-000000000002'&&reader().querySelector('blockquote').getClientRects().length>0&&!reader().querySelector('[data-testid=preview-source-info]').open};"
  Check 'provenance_disclosure_keeps_exact_anchors' "const info=reader().querySelector('[data-testid=preview-source-info]');info.querySelector('summary').click();await pause(0);return {passed:info.open&&info.textContent.includes('30000000-0000-4000-8000-000000000001')&&info.textContent.includes('synthetic-v1-p1')};"
  Check 'browser_back_and_forward_keep_reading_context' "history.back();await until(()=>!reader());const kept=rows().length===10;history.forward();await until(()=>reader()?.querySelector('blockquote'));return {passed:kept&&document.querySelectorAll('dialog[open]').length===1};"
  & agent-browser --session $session press Tab | Out-Null
  Check 'reader_traps_keyboard_focus' "return {passed:reader()?.matches(':modal')&&reader()?.contains(document.activeElement)};"
  & agent-browser --session $session press Escape | Out-Null
  Check 'escape_restores_origin' "await until(()=>!reader());await pause(250);return {passed:!new URLSearchParams(location.search).has('event')&&document.activeElement?.getAttribute('href')===window.__mvpOrigin.href&&Math.abs(scrollY-window.__mvpOrigin.scroll)<4};"
  Open '/preview?q=DeepSeek&event=00000000-0000-4000-8000-000000000002'
  Check 'deep_link_restores_reader_and_filter' "await until(()=>reader()?.querySelector('blockquote')&&rows().length===6);return {passed:test('preview-search').value==='DeepSeek'&&document.querySelectorAll('dialog[open]').length===1&&reader().contains(document.activeElement)};"
  foreach($width in @(390,768,1440)) {
    & agent-browser --session $session set viewport $width 1000 | Out-Null
    Check "reader_width_$width" "await pause(250);const d=reader(),r=d.getBoundingClientRect();return {passed:r.left>=0&&r.right<=innerWidth+1&&d.scrollWidth<=d.clientWidth+1&&document.documentElement.scrollWidth<=innerWidth,width:innerWidth,panelWidth:r.width};"
  }
  Check 'close_keeps_filtered_results' "test('preview-close').click();await until(()=>!reader());return {passed:rows().length===6&&new URLSearchParams(location.search).get('q')==='DeepSeek'};"
  Open '/preview?event=00000000-0000-4000-8000-000000000099'
  Check 'unknown_event_recovery' "await until(()=>reader()?.querySelector('[role=alert]'));return {passed:!!test('preview-close')};"
  Open '/preview'
  Check 'late_response_does_not_reopen_reader' "await until(()=>rows().length===10);const original=window.fetch.bind(window);const payload=await original('/api/v1/events/00000000-0000-4000-8000-000000000002').then(r=>r.json());let resolveLate;window.fetch=(input,init)=>String(input)==='/api/v1/events/00000000-0000-4000-8000-000000000002'?new Promise(resolve=>resolveLate=()=>resolve(new Response(JSON.stringify(payload),{headers:{'content-type':'application/json'}}))):original(input,init);rows().flatMap(x=>[...x.querySelectorAll('a')]).find(x=>x.pathname.endsWith('000000000002')).click();await until(()=>!!resolveLate&&!!reader());test('preview-close').click();await until(()=>!reader());resolveLate();await pause(250);window.fetch=original;return {passed:!reader()&&!new URLSearchParams(location.search).has('event')};" 'injected_delayed_fixture_response'
  foreach($width in @(390,768,1440)) {
    & agent-browser --session $session set viewport $width 1000 | Out-Null
    Open '/preview'
    Check "home_width_$width" "await until(()=>rows().length===10);const a=rows()[0].getBoundingClientRect();const day=document.querySelector('.timeline-day-toggle');const label=day.querySelector('.preview-day-label');const offset=label.getBoundingClientRect().left-day.getBoundingClientRect().left;return {passed:document.documentElement.scrollWidth<=innerWidth&&offset<44,width:innerWidth,firstEventTop:a.top,dateOffset:offset};"
  }
  Open '/preview'
  Check 'empty_search_can_be_cleared' "await until(()=>rows().length===10);set(test('preview-search'),'no-such-event-fixture-927');await until(()=>rows().length===0&&!document.body.innerText.includes('正在更新'));const empty=document.body.innerText.includes('没有事件');[...document.querySelectorAll('button')].find(x=>x.textContent.includes('清除条件')).click();await until(()=>rows().length===10);return {passed:empty&&!new URLSearchParams(location.search).has('q')};"
  Open '/preview'
  Check 'event_list_error_has_working_retry' "await until(()=>rows().length===10);const original=window.fetch.bind(window);let failed=false;window.fetch=(input,init)=>{if(!failed&&String(input).startsWith('/api/v1/events?')){failed=true;return Promise.resolve(new Response(JSON.stringify({code:'TEMPORARY_FAILURE',message:'合成故障：暂时不可用',data_mode:'fixture'}),{status:503,headers:{'content-type':'application/json'}}));}return original(input,init);};set(test('preview-search'),'DeepSeek');await until(()=>!!document.querySelector('[role=alert]'));const alert=document.querySelector('[role=alert]');const shown=alert.textContent.includes('合成故障');alert.querySelector('button').click();await until(()=>rows().length===6);window.fetch=original;return {passed:shown&&rows().every(x=>x.textContent.includes('DeepSeek'))};" 'injected_fixture_http_failure'
  Open '/preview'
  Check 'late_evidence_does_not_attach_to_another_event' "await until(()=>rows().length===10);const original=window.fetch.bind(window);const payload=await original('/api/v1/events/00000000-0000-4000-8000-000000000002/evidence').then(r=>r.json());let resolveLate;window.fetch=(input,init)=>String(input)==='/api/v1/events/00000000-0000-4000-8000-000000000002/evidence'?new Promise(resolve=>resolveLate=()=>resolve(new Response(JSON.stringify(payload),{headers:{'content-type':'application/json'}}))):original(input,init);const links=()=>rows().flatMap(x=>[...x.querySelectorAll('a')]);links().find(x=>x.pathname.endsWith('000000000002')).click();await until(()=>!!resolveLate&&!!reader());test('preview-close').click();await until(()=>!reader());const other=links().find(x=>!x.pathname.endsWith('000000000002'));const title=other.textContent.trim();other.click();await until(()=>reader()?.textContent.includes(title));resolveLate();await pause(250);window.fetch=original;return {passed:reader().textContent.includes(title)&&!reader().querySelector('blockquote')};" 'injected_delayed_fixture_evidence'
  Open '/preview/ask?demo=1'
  Check 'ask_conditions_are_optional_but_available' "await until(()=>!!document.querySelector('textarea'));const d=[...document.querySelectorAll('details')].find(x=>x.textContent.includes('分类'));const closed=!!d&&!d.open;d?.querySelector('summary').click();await pause(0);return {passed:closed&&d.open&&!!d.querySelector('input[type=date]')};"
  Check 'ask_demo_still_works' "set(document.querySelector('textarea'),'DeepSeek');await pause(0);[...document.querySelectorAll('button')].find(x=>x.textContent.includes('开始分析')).click();await until(()=>document.body.innerText.includes('模拟流已完成'));return {passed:!!document.querySelector('[data-testid=ask-answer]')&&document.body.innerText.includes('模拟')};" 'frontend_simulated_sse'
} finally {
  $report=[pscustomobject]@{observed_at=[DateTimeOffset]::UtcNow.ToString('o');base_url=$BaseUrl;passed=@($results|Where-Object passed).Count;total=$results.Count;checks=$results}
  [IO.File]::WriteAllText((Join-Path $PSScriptRoot '../docs/simple-mvp-browser-results.json'),($report|ConvertTo-Json -Depth 8))
}
$report | Select-Object passed,total | ConvertTo-Json -Compress
if (@($results|Where-Object {-not $_.passed}).Count) { exit 1 }
