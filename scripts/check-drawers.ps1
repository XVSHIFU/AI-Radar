param([string]$BaseUrl = 'http://127.0.0.1:5175')
$ErrorActionPreference = 'Stop'
$session = 'radar-acceptance'
$results = [Collections.Generic.List[object]]::new()
function Js([string]$code) {
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code))
    $raw = & agent-browser --session $session eval -b $encoded
    if ($LASTEXITCODE -ne 0) { throw "Browser evaluation failed: $raw" }
    $raw | ConvertFrom-Json
}
function Open-Page([string]$path) {
    & agent-browser --session $session open ($BaseUrl + $path) | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Page unavailable: $path" }
}
function Check([string]$name,[string]$code,[string]$layer='fixture_api_browser') {
    try {
        $setup = "(async()=>{const pause=ms=>new Promise(r=>setTimeout(r,ms));const until=async f=>{for(let i=0;i<100;i++){if(f())return;await pause(50);}throw Error('UI state timed out');};const test=id=>document.querySelector('[data-testid='+id+']');const visible=x=>!!x&&x.getClientRects().length>0;const shown=()=>[...document.querySelectorAll('article.timeline-event')].filter(visible).length;const toggle=(level,key)=>[...document.querySelectorAll('[data-testid=timeline-'+level+'-toggle]')].find(x=>x.dataset.key===key);const button=t=>[...document.querySelectorAll('button')].find(x=>x.textContent.trim()===t);const top=()=>[...document.querySelectorAll('dialog[open]')].at(-1);"
        $actual=Js ($setup+$code+"})()")
        $results.Add([pscustomobject]@{check=$name;layer=$layer;passed=($actual.passed -eq $true);actual=$actual})
    } catch { $results.Add([pscustomobject]@{check=$name;layer=$layer;passed=$false;error=$_.Exception.Message}) }
}
try {
    & agent-browser --session $session tab new $BaseUrl | Out-Null
    & agent-browser --session $session set viewport 1440 1000 | Out-Null
    Open-Page '/'
    Check 'calendar_three_levels_and_partial_count' "await until(()=>shown()===10);return {passed:!!toggle('year','2026')&&!!toggle('month','2026-09')&&!!toggle('day','2026-09-12')&&document.body.innerText.includes('已加载')&&document.body.innerText.includes('精确匹配 32 条')};"
    Check 'day_month_year_independent_collapse' "const d=toggle('day','2026-09-12'),m=toggle('month','2026-09'),y=toggle('year','2026');toggle('day','2026-09-12').click();await pause(0);const day=shown()===5;toggle('month','2026-09').click();await pause(0);const month=shown()===0;toggle('month','2026-09').click();await pause(0);const retained=shown()===5&&d.getAttribute('aria-expanded')==='false';toggle('year','2026').click();await pause(0);const year=shown()===0;toggle('year','2026').click();await pause(0);const restored=shown()===5;toggle('day','2026-09-12').click();await pause(0);return {passed:day&&month&&retained&&year&&restored&&shown()===10};"
    Check 'append_retains_collapsed_day' "toggle('day','2026-09-12').click();await pause(0);button('加载更多').click();await until(()=>document.body.innerText.includes('精确匹配 32 条')&&!!toggle('day','2026-09-10'));const preserved=toggle('day','2026-09-12').getAttribute('aria-expanded')==='false';toggle('day','2026-09-12').click();await pause(0);return {passed:preserved&&shown()===20,count:shown()};"
    Open-Page '/'
    Check 'event_opens_in_place_and_retains_link' "await until(()=>shown()===10);const a=[...document.querySelectorAll('article.timeline-event a')].find(a=>a.pathname.endsWith('000000000002'));a.scrollIntoView({block:'center'});a.focus();window.__drawerOrigin={scrollY:scrollY,href:a.getAttribute('href')};a.click();await until(()=>!!test('drawer-event')&&test('drawer-event').textContent.includes('DeepSeek'));return {passed:location.pathname==='/'&&new URLSearchParams(location.search).get('event')==='00000000-0000-4000-8000-000000000002'&&window.__drawerOrigin.href.includes('/events/')&&document.querySelectorAll('article.timeline-event').length===10};"
    Check 'source_drawer_stacks' "await until(()=>!!test('source-open'));test('source-open').click();await until(()=>test('drawer-source')?.open&&document.querySelectorAll('dialog[open]').length===2&&top()?.contains(document.activeElement));return {passed:document.querySelectorAll('dialog[open]').length===2&&!!new URLSearchParams(location.search).get('source')};"
    Check 'evidence_drawer_has_saved_anchor' "await until(()=>!!test('evidence-open'));test('evidence-open').click();await until(()=>!!test('drawer-evidence')&&test('drawer-evidence').textContent.includes('synthetic-v1-p1'));window.__drawerDeepLink=location.pathname+location.search;return {passed:document.querySelectorAll('dialog[open]').length===3&&test('drawer-evidence').textContent.includes('30000000-0000-4000-8000-000000000001')&&top().contains(document.activeElement)};"
    & agent-browser --session $session press Tab | Out-Null
    Check 'top_layer_keeps_keyboard_focus' "return {passed:top()?.contains(document.activeElement)&&document.documentElement.scrollWidth<=innerWidth};"
    Check 'drawer_back_control_peels_and_reopens' "top().querySelector('[data-testid=drawer-back]').click();await until(()=>document.querySelectorAll('dialog[open]').length===2&&!new URLSearchParams(location.search).has('evidence'));const source=[...document.querySelectorAll('dialog[open]')].at(-1);source.querySelector('[data-testid=evidence-open]').click();await until(()=>document.querySelectorAll('dialog[open]').length===3);return {passed:top().contains(document.activeElement)};"
    Check 'browser_back_peels_evidence_then_source' "history.back();await until(()=>document.querySelectorAll('dialog[open]').length===2);const sourceFocus=top().contains(document.activeElement);history.back();await until(()=>document.querySelectorAll('dialog[open]').length===1);return {passed:sourceFocus&&top().contains(document.activeElement)&&!new URLSearchParams(location.search).has('source')};"
    Check 'closing_event_restores_focus_and_position' "history.back();await until(()=>document.querySelectorAll('dialog[open]').length===0);await pause(100);return {passed:!new URLSearchParams(location.search).has('event')&&document.activeElement?.getAttribute('href')===window.__drawerOrigin.href&&Math.abs(scrollY-window.__drawerOrigin.scrollY)<4,scroll:scrollY,original:window.__drawerOrigin.scrollY};"
    $deep=Js 'window.__drawerDeepLink'
    Open-Page $deep
    Check 'reloaded_deep_link_restores_stack' "await until(()=>document.querySelectorAll('dialog[open]').length===3&&test('drawer-evidence').textContent.includes('synthetic-v1-p1'));return {passed:top().contains(document.activeElement)};"
    foreach ($width in @(390,768,1440)) {
        & agent-browser --session $session set viewport $width 1000 | Out-Null
        Check "drawer_width_$width" "await pause(100);const d=top(),r=d.getBoundingClientRect();return {passed:r.left>=0&&r.right<=innerWidth+1&&d.scrollWidth<=d.clientWidth+1&&document.documentElement.scrollWidth<=innerWidth,width:innerWidth,panelWidth:r.width};"
    }
    & agent-browser --session $session press Escape | Out-Null
    Check 'escape_closes_only_top_layer' "await until(()=>document.querySelectorAll('dialog[open]').length===2);return {passed:!new URLSearchParams(location.search).has('evidence')&&top().contains(document.activeElement)};"
    Open-Page '/?event=00000000-0000-4000-8000-000000000099'
    Check 'missing_event_has_recovery' "await until(()=>!!test('drawer-event')&&!!test('drawer-event').querySelector('[role=alert]'));return {passed:!!test('drawer-event').querySelector('button')&&location.pathname==='/'};"
    Open-Page '/?q=DeepSeek&event=00000000-0000-4000-8000-000000000002'
    Check 'deep_link_preserves_filtered_list' "await until(()=>document.querySelectorAll('article.timeline-event').length===6&&!!test('source-open'));return {passed:document.querySelector('input[placeholder]').value==='DeepSeek'&&new URLSearchParams(location.search).get('q')==='DeepSeek'};"
    Open-Page '/'
    Check 'prepare_delayed_drawer_request' "await until(()=>shown()===10);const original=window.fetch.bind(window);window.__originalDrawerFetch=original;const payload=await original('/api/v1/events/00000000-0000-4000-8000-000000000002').then(r=>r.json());window.fetch=(input,init)=>String(input)==='/api/v1/events/00000000-0000-4000-8000-000000000002'?new Promise(resolve=>window.__resolveDrawer=()=>resolve(new Response(JSON.stringify(payload),{headers:{'content-type':'application/json'}}))):original(input,init);[...document.querySelectorAll('article.timeline-event a')].find(a=>a.pathname.endsWith('000000000002')).click();await until(()=>!!window.__resolveDrawer&&!!top());return {passed:true};" 'injected_delayed_fixture_response'
    & agent-browser --session $session press Escape | Out-Null
    Check 'late_result_cannot_reopen_closed_drawer' "await until(()=>document.querySelectorAll('dialog[open]').length===0);window.__resolveDrawer();await pause(250);window.fetch=window.__originalDrawerFetch;return {passed:!new URLSearchParams(location.search).has('event')&&document.querySelectorAll('dialog[open]').length===0};" 'injected_delayed_fixture_response'
    Open-Page '/'
    Check 'cross_year_month_and_unknown_dates' "await until(()=>shown()===10);const original=window.fetch.bind(window);const seed=await original('/api/v1/events?limit=10').then(r=>r.json());const dates=['2026-09-12','2026-08-02','2025-12-31',null];const payload={...seed,items:seed.items.slice(0,4).map((x,i)=>({...x,event_date:dates[i]})),total:4,next_cursor:null};window.fetch=(input,init)=>String(input).startsWith('/api/v1/events?')?Promise.resolve(new Response(JSON.stringify(payload),{headers:{'content-type':'application/json'}})):original(input,init);const input=document.querySelector('input[placeholder]');input.value='calendar-structure-fixture';input.dispatchEvent(new Event('input',{bubbles:true}));await until(()=>document.body.innerText.includes('精确匹配 4 条'));return {passed:!!toggle('year','2025')&&!!toggle('year','2026')&&!!toggle('month','2026-08')&&!!toggle('month','2026-09')&&document.body.innerText.includes('日期未知')&&shown()===4};" 'injected_calendar_structure_fixture'

    Open-Page '/?event=00000000-0000-4000-8000-000000000002&source=version:missing'
    Check 'unknown_source_is_not_substituted' "await until(()=>!!test('drawer-source')&&!!test('drawer-source').querySelector('[role=alert]'));return {passed:document.querySelectorAll('dialog[open]').length===2&&!!test('drawer-source').querySelector('button')};"
    Open-Page '/?event=00000000-0000-4000-8000-000000000002&source=30000000-0000-4000-8000-000000000001&evidence=missing'
    Check 'unknown_evidence_is_not_substituted' "await until(()=>!!test('drawer-evidence')&&!!test('drawer-evidence').querySelector('[role=alert]'));return {passed:document.querySelectorAll('dialog[open]').length===3&&!test('drawer-evidence').textContent.includes('合成段落：DeepSeek')};"

    Open-Page '/'
    Check 'prepare_delayed_evidence_request' "await until(()=>shown()===10);const original=window.fetch.bind(window);window.__originalEvidenceFetch=original;const payload=await original('/api/v1/events/00000000-0000-4000-8000-000000000002/evidence').then(r=>r.json());window.fetch=(input,init)=>String(input)==='/api/v1/events/00000000-0000-4000-8000-000000000002/evidence'?new Promise(resolve=>window.__resolveEvidence=()=>resolve(new Response(JSON.stringify(payload),{headers:{'content-type':'application/json'}}))):original(input,init);[...document.querySelectorAll('article.timeline-event a')].find(a=>a.pathname.endsWith('000000000002')).click();await until(()=>!!window.__resolveEvidence);return {passed:true};" 'injected_delayed_fixture_evidence'
    & agent-browser --session $session press Escape | Out-Null
    Check 'old_evidence_cannot_attach_to_new_event' "await until(()=>document.querySelectorAll('dialog[open]').length===0);const a=[...document.querySelectorAll('article.timeline-event a')].find(a=>!a.pathname.endsWith('000000000002'));const title=a.textContent.trim();a.click();await until(()=>!!test('drawer-event')&&test('drawer-event').textContent.includes(title)&&!test('drawer-event').textContent.includes('正在加载'));window.__resolveEvidence();await pause(250);window.fetch=window.__originalEvidenceFetch;return {passed:!test('source-open')&&!test('drawer-event').textContent.includes('合成来源版本 v1')};" 'injected_delayed_fixture_evidence'

} finally {
    $report=[pscustomobject]@{observed_at=[DateTimeOffset]::UtcNow.ToString('o');base_url=$BaseUrl;passed=@($results|Where-Object passed).Count;total=$results.Count;checks=$results}
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot '../docs/drawer-browser-results.json'),($report|ConvertTo-Json -Depth 8))
}
$report | Select-Object passed,total | ConvertTo-Json -Compress
if (@($results|Where-Object { -not $_.passed }).Count) { exit 1 }
