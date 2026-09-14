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


 & agent-browser --session $session set viewport 1440 1000|Out-Null
 Open '/ask'
 Check 'insights_today_default_no_model' "await until(()=>t('insights-summary')?.textContent.includes('精确匹配'));return {passed:button('今天').getAttribute('aria-pressed')==='true'&&body().includes('统计由库内事件计算')&&!t('ask-answer')&&!t('insights-error')&&(!t('insights-summary').textContent.includes('精确匹配 0 条')||!t('insights-daily'))};"
 Check 'insights_custom_full_scope_and_pagination' "button('自定义').click();await pause(0);set(document.querySelector('[name=date_from]'),'2026-09-01');set(document.querySelector('[name=date_to]'),'2026-09-30');await until(()=>t('insights-summary')?.textContent.includes('精确匹配 32 条'));await until(()=>t('insights-events').querySelectorAll('article').length===10);const before=t('insights-summary').textContent;button('加载更多').click();await until(()=>t('insights-events').querySelectorAll('article').length===20);return {passed:t('insights-summary').textContent===before&&!t('insights-events').querySelector('.error')&&t('insights-categories').querySelectorAll('[data-category]').length===6};"
 Check 'insights_chart_category_drilldown' "t('insights-categories').querySelector('[data-category=model_release]').click();await until(()=>t('insights-summary')?.textContent.includes('精确匹配 6 条'));return {passed:document.querySelector('.ask-more select').value==='model_release'&&t('insights-events').querySelectorAll('article').length===6&&t('insights-summary').textContent.includes('模型发布')};"
 Check 'insights_chart_day_drilldown' "[...t('insights-daily').querySelectorAll('[data-date-from]')].find(b=>b.dataset.dateFrom==='2026-09-12').click();await until(()=>t('insights-summary')?.textContent.includes('精确匹配 1 条'));return {passed:document.querySelector('[name=date_from]').value==='2026-09-12'&&document.querySelector('[name=date_to]').value==='2026-09-12'};"
 Check 'insights_event_drawer_stays_on_ask' "t('insights-events').querySelector('article a').click();await until(()=>modal()?.querySelector('blockquote'));const path=location.pathname;modal().querySelector('[data-testid=drawer-back]').click();await until(()=>!modal());return {passed:path==='/ask'&&location.pathname==='/ask'&&document.querySelector('[name=date_from]').value==='2026-09-12'&&t('insights-summary').textContent.includes('精确匹配 1 条')};"
 Check 'insights_importance_and_keyword' "set(document.querySelector('.ask-more select'),'');set(document.querySelector('[name=date_from]'),'2026-09-08');set(document.querySelector('[name=date_to]'),'2026-09-12');document.querySelector('.ask-importance input').click();await until(()=>t('insights-summary')?.textContent.includes('精确匹配 13 条'));const high=t('insights-summary').textContent.includes('4');document.querySelector('.ask-importance input').click();set(document.querySelector('.ask-more input[placeholder]'),'DeepSeek');await until(()=>t('insights-summary')?.textContent.includes('精确匹配 4 条'));return {passed:high&&t('insights-summary').textContent.includes('DeepSeek')};"
 Check 'insights_invalid_range_hides_old_counts' "set(document.querySelector('[name=date_from]'),'2026-09-13');await until(()=>body().includes('日期范围无效'));await pause(350);return {passed:!t('insights-daily')&&!t('insights-events').querySelector('article')&&!body().includes('精确匹配 4 条')};"
 Check 'insights_long_range_month_buckets' "set(document.querySelector('.ask-more input[placeholder]'),'');set(document.querySelector('[name=date_from]'),'2026-08-15');set(document.querySelector('[name=date_to]'),'2026-10-15');await until(()=>t('insights-summary')?.textContent.includes('精确匹配 32 条'));const bars=[...t('insights-daily').querySelectorAll('[data-date-from]')];return {passed:bars.length===3&&bars[0].dataset.dateFrom==='2026-08-15'&&bars.at(-1).dataset.dateTo==='2026-10-15'&&t('insights-daily').textContent.includes('月'),buckets:bars.map(b=>[b.dataset.dateFrom,b.dataset.dateTo])};"
 foreach($width in @(390,768,1440,1680)){
  & agent-browser --session $session set viewport $width 1000|Out-Null
  Check ("insights_width_"+$width) "return {passed:document.documentElement.scrollWidth<=innerWidth,width:innerWidth,scroll:document.documentElement.scrollWidth};"
 }
 Check 'insights_month_click_preserves_bucket_boundaries' "const pick=from=>[...(t('insights-daily')?.querySelectorAll('[data-date-from]')||[])].find(b=>b.dataset.dateFrom===from);pick('2026-09-01').click();await until(()=>document.querySelector('[name=date_to]').value==='2026-09-30'&&t('insights-summary')?.textContent.includes('精确匹配 32 条'));const september=document.querySelector('[name=date_from]').value==='2026-09-01';set(document.querySelector('[name=date_from]'),'2026-08-15');set(document.querySelector('[name=date_to]'),'2026-10-15');await until(()=>!!pick('2026-10-01'));pick('2026-10-01').click();await until(()=>t('insights-summary')?.textContent.includes('精确匹配 0 条'));return {passed:september&&document.querySelector('[name=date_from]').value==='2026-10-01'&&document.querySelector('[name=date_to]').value==='2026-10-15'&&!t('insights-error')&&!body().includes('日期范围无效')};"
 Check 'rule_plan_explicit_apply' "set(document.querySelector('textarea'),'最近7天模型发布');await pause(0);const b=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('按问题筛选'));b.click();await until(()=>!!button('应用到总览'));const before=document.querySelector('.ask-more select').value;button('应用到总览').click();await until(()=>document.querySelector('.ask-more select').value==='model_release'&&t('insights-summary')?.textContent.includes('精确匹配 4 条'));return {passed:before===''&&document.querySelector('.ask-more select').value==='model_release'};"
 Check 'ask_real_model_unavailable_keeps_overview' "set(document.querySelector('textarea'),'有哪些进展');await pause(0);button('开始分析').click();await until(()=>!!document.querySelector('.ask-question .error'));return {passed:!t('ask-answer')&&!!t('query-plan')&&t('insights-summary').textContent.includes('精确匹配 4 条')&&body().includes('未配置')};"
 Open '/ask'
 Check 'insights_fault_not_fake_zero_and_retry' "await until(()=>t('insights-summary')?.textContent.includes('精确匹配'));const original=window.fetch;window.fetch=(u,o)=>String(u).includes('/insights/summary')?Promise.resolve(new Response(JSON.stringify({code:'RETRIEVAL_FAILED',message:'合成统计故障'}),{status:503,headers:{'content-type':'application/json'}})):original(u,o);button('近7天').click();await until(()=>!!t('insights-error'));const truthful=!t('insights-summary')?.textContent.includes('精确匹配 0')&&!t('insights-daily');window.fetch=original;t('insights-error').querySelector('button').click();await until(()=>!!t('insights-daily'));return {passed:truthful&&!t('insights-error')};" 'injected_failure_browser'
 Check 'insights_list_failure_keeps_statistics' "const original=window.fetch;window.fetch=(u,o)=>String(u).includes('/api/v1/events?')?Promise.resolve(new Response(JSON.stringify({code:'RETRIEVAL_FAILED',message:'合成列表故障'}),{status:503,headers:{'content-type':'application/json'}})):original(u,o);button('本月').click();await until(()=>!t('insights-summary')?.textContent.includes('正在'));await pause(400);const okay=!!t('insights-daily')&&t('insights-summary').textContent.includes('精确匹配 32 条')&&!!t('insights-events').querySelector('.error');window.fetch=original;return {passed:okay};" 'injected_failure_browser'

}finally{
 $report=[pscustomobject]@{observed_at=[DateTimeOffset]::UtcNow.ToString('o');base_url=$BaseUrl;passed=@($results|Where-Object passed).Count;total=$results.Count;checks=$results}
 [IO.File]::WriteAllText((Join-Path $PSScriptRoot '../docs/reading-insights-browser-results.json'),($report|ConvertTo-Json -Depth 8))
}
$report|Select-Object passed,total|ConvertTo-Json -Compress
if(@($results|Where-Object {-not $_.passed}).Count){exit 1}
