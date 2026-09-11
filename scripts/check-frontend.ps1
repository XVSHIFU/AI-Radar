param([string]$BaseUrl = 'http://127.0.0.1:5175')
$ErrorActionPreference = 'Stop'
$session = 'radar-acceptance'
$results = [Collections.Generic.List[object]]::new()
function Js([string]$code) {
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code))
    $raw = & agent-browser --session $session eval -b $encoded
    if ($LASTEXITCODE -ne 0) { throw "Browser evaluation failed: $raw" }
    return ($raw | ConvertFrom-Json)
}
function Open-Page([string]$path) {
    & agent-browser --session $session open ($BaseUrl + $path) | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Page unavailable: $path" }
}
function Check([string]$name, [string]$code, [string]$layer = 'fixture_api_browser') {
    try {
        $actual = Js ("(async()=>{const pause=ms=>new Promise(r=>setTimeout(r,ms));const until=async f=>{for(let i=0;i<60;i++){if(f())return;await pause(50);}throw Error('UI state timed out');};const set=(el,v)=>{if(!el)throw Error('Missing control');el.value=v;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};const button=t=>[...document.querySelectorAll('button')].find(e=>e.textContent.trim()===t);const body=()=>document.body.innerText;" + $code + "})()")
        $results.Add([pscustomobject]@{check=$name;layer=$layer;passed=($actual.passed -eq $true);actual=$actual})
    } catch { $results.Add([pscustomobject]@{check=$name;layer=$layer;passed=$false;error=$_.Exception.Message}) }
}
try {
    & agent-browser --session $session set viewport 1440 1000 | Out-Null
    Open-Page '/'
    Check 'home_initial_total_and_page' "await until(()=>body().includes('精确匹配 32 条'));return {passed:document.querySelectorAll('article.event').length===10};"
    Check 'theme_colors_and_focus_resolve' "await until(()=>!!document.querySelector('.pill'));const b=button('清除');b.focus();const actual={banner:getComputedStyle(document.querySelector('[role=note]')).backgroundColor,pill:getComputedStyle(document.querySelector('.pill')).backgroundColor,focus:getComputedStyle(b).outlineColor};return {passed:actual.banner==='rgb(255, 248, 231)'&&actual.pill==='rgb(232, 245, 243)'&&actual.focus==='rgb(139, 211, 203)',actual};"
    Check 'home_pagination_unique_total' "for(let i=0;i<3;i++){button('加载更多').click();await pause(600);}const ids=[...document.querySelectorAll('article.event a')].map(x=>x.pathname);return {passed:ids.length===32&&new Set(ids).size===32&&body().includes('精确匹配 32 条'),count:ids.length};"
    Check 'home_alias_full_dataset_url' "set(document.querySelector('input[placeholder]'),'深度求索');await until(()=>body().includes('精确匹配 6 条'));return {passed:document.querySelectorAll('article.event').length===6&&new URLSearchParams(location.search).get('q')==='深度求索'};"
    Check 'home_empty_and_clear' "set(document.querySelector('input[placeholder]'),'never-present-synthetic-zz');await until(()=>body().includes('精确匹配 0 条'));const empty=body().includes('这个范围内没有事件');button('清除').click();await until(()=>body().includes('精确匹配 32 条'));return {passed:empty&&document.querySelector('input[placeholder]').value===''};"
    Check 'home_inclusive_date_category_exact_ids' "document.querySelector('input[value=agent_tool]').click();const dates=document.querySelectorAll('input[type=date]');set(dates[0],'2026-09-08');set(dates[1],'2026-09-10');await until(()=>body().includes('精确匹配 3 条'));const ids=[...document.querySelectorAll('article.event a')].map(x=>x.pathname.split('/').pop()).sort();const want=[13,19,25].map(n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0'));return {passed:JSON.stringify(ids)===JSON.stringify(want),ids};"
    Check 'home_invalid_dates' "set(document.querySelectorAll('input[type=date]')[0],'2026-09-11');await until(()=>body().includes('日期范围无效'));return {passed:!document.querySelector('article.event')};"
    foreach ($width in @(390,768,1440)) {
        & agent-browser --session $session set viewport $width 1000 | Out-Null
        if ($width -eq 390) {
            Check 'mobile_navigation_single_line_targets' "const links=[...document.querySelectorAll('nav a')];const rows=links.map(a=>{const r=document.createRange();r.selectNodeContents(a);return {text:a.textContent,lines:[...r.getClientRects()].filter(x=>x.width>0).length,height:a.getBoundingClientRect().height};});return {passed:rows.every(x=>x.lines===1&&x.height>=44),rows};"
        }
        Check "home_width_$width" "return {passed:document.documentElement.scrollWidth<=innerWidth,width:innerWidth,scroll:document.documentElement.scrollWidth};"
    }
    Open-Page '/events/00000000-0000-4000-8000-000000000002'
    Check 'detail_saved_version' "await until(()=>body().includes('展开摘录'));const b=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('展开摘录'));b.focus();return {passed:document.activeElement===b};"
    & agent-browser --session $session press Enter | Out-Null
    Check 'detail_keyboard_evidence' "await until(()=>!!document.querySelector('blockquote'));return {passed:body().includes('synthetic-v1-p1')&&body().includes('30000000-0000-4000-8000-000000000001')};"
    Open-Page '/events/00000000-0000-4000-8000-999999999999'
    Check 'detail_unknown_404' "await until(()=>body().includes('事件不存在'));return {passed:!document.querySelector('main article')};"
    Open-Page '/ask'
    Check 'ask_fixture_api_does_not_fake_model' "set(document.querySelector('textarea'),'有哪些进展');await pause(0);button('开始分析').click();await until(()=>!!document.querySelector('.error'));return {passed:!body().includes('模拟回答')&&!document.querySelector('main article'),error:document.querySelector('.error').innerText};"
    Check 'ask_structured_no_answer' "set(document.querySelectorAll('input[type=date]')[0],'2099-01-01');set(document.querySelectorAll('input[type=date]')[1],'2099-01-01');await pause(0);button('开始分析').click();await until(()=>!!document.querySelector('main article'));return {passed:body().includes('没有可回答的资料')&&body().includes('完整匹配 0'),text:document.querySelector('main article').innerText};"
    Open-Page '/ask?demo=1'
    Check 'ask_slow_demo_completed_index' "set(document.querySelector('textarea'),'演示引用');await pause(0);button('开始分析').click();await until(()=>body().includes('模拟流已完成'));const b=[...document.querySelectorAll('main button')].find(x=>x.textContent.includes('[2]'));return {passed:!!b&&!body().includes('[1]')&&body().includes('完整匹配 1')};" 'synthetic_stream_browser'
    Check 'ask_citation_focus' "const b=[...document.querySelectorAll('main button')].find(x=>x.textContent.includes('[2]'));b.click();await until(()=>!!document.querySelector('blockquote'));return {passed:document.activeElement?.id==='citation-2'&&body().includes('合成段落摘录')};" 'synthetic_stream_browser'
    Check 'ask_cancel_partial_no_completion' "await pause(0);button('开始分析').click();await pause(600);const partial=body().includes('这是');button('取消').click();await pause(1150);return {passed:partial&&body().includes('已取消')&&!body().includes('模拟流已完成')};" 'synthetic_stream_browser'
    Open-Page '/ask'
    Check 'ask_real_json_preserves_explicit_index' "const original=window.fetch;window.fetch=(url,init)=>String(url).endsWith('/ask')?Promise.resolve(new Response(JSON.stringify({answer:'引用示例 [2]',citations:[{index:2,title:'来源二',source_url:'https://example.invalid/two',quote_text:'明确段落'}],execution_status:'completed',answer_status:'answered',scope_total:1,retrieved_count:1,summarized_count:1,citation_count:1,coverage:'complete'}),{status:200,headers:{'content-type':'application/json'}})):original(url,init);set(document.querySelector('textarea'),'引用协议检查');await pause(0);button('开始分析').click();await until(()=>body().includes('[2] 来源二'));return {passed:!body().includes('[1]')&&body().includes('已完成')};" 'synthetic_api_response_browser'
    Check 'ask_malformed_citations_fail_visibly' "window.fetch=()=>Promise.resolve(new Response(JSON.stringify({answer:'不应显示',citations:[{title:'无编号',source_url:'https://example.invalid'}],execution_status:'completed',answer_status:'answered',coverage:'complete'}),{status:200,headers:{'content-type':'application/json'}}));button('开始分析').click();await until(()=>!!document.querySelector('.error'));return {passed:body().includes('引用协议错误')&&!document.querySelector('main article')};" 'synthetic_api_response_browser'
    Check 'ask_many_citations_long_untrusted_answer' "window.fetch=()=>Promise.resolve(new Response(JSON.stringify({answer:'<img src=x onerror=alert(1)> '+('长回答 AI-SDK UUID '.repeat(250)),citations:Array.from({length:12},(_,i)=>({index:i+1,title:'长来源标题 '+('SDK-abcdef'.repeat(12)),source_url:i===0?'javascript:alert(1)':'https://example.invalid/'+i,quote_text:'摘录 '+('q'.repeat(300))})),execution_status:'completed',answer_status:'answered',scope_total:100,retrieved_count:20,summarized_count:12,citation_count:12,coverage:'partial'}),{status:200,headers:{'content-type':'application/json'}}));button('开始分析').click();await until(()=>body().includes('覆盖不完整'));return {passed:document.querySelectorAll('main article button').length===12&&!document.querySelector('main img')&&!document.querySelector('a[href^=javascript]')};" 'synthetic_api_response_browser'
    & agent-browser --session $session set viewport 390 1000 | Out-Null
    Check 'ask_long_answer_mobile_overflow' "return {passed:document.documentElement.scrollWidth<=innerWidth,width:innerWidth,scroll:document.documentElement.scrollWidth};" 'synthetic_api_response_browser'
    Open-Page '/?demo=1'
    Check 'same_route_switch_demo_to_api' "await until(()=>!!document.querySelector('article.event'));const before=document.querySelector('article.event a').getAttribute('href');document.querySelector('a.switch').click();await until(()=>body().includes('后端合成数据'));await pause(600);const after=document.querySelector('article.event a').getAttribute('href');return {passed:!location.search.includes('demo=1')&&before!==after&&after.endsWith('000000000005'),before,after};"
    Open-Page '/'
    Check 'detail_error_retry_real_request' "await until(()=>!!document.querySelector('article.event'));const original=window.fetch;let fail=true;window.fetch=(url,init)=>{if(fail&&String(url).includes('/api/v1/events/')){fail=false;return Promise.resolve(new Response(JSON.stringify({code:'RETRIEVAL_FAILED',message:'合成临时故障',retryable:true}),{status:503,headers:{'content-type':'application/json'}}));}return original(url,init);};document.querySelector('article.event a').click();await until(()=>!!document.querySelector('[role=alert]'));const saw=body().includes('合成临时故障');button('重试').click();await until(()=>!!document.querySelector('main article'));return {passed:saw&&!document.querySelector('[role=alert]')};" 'synthetic_fault_real_retry_browser'
    Open-Page '/ingest'
    Check 'ingest_independent_source_and_runs_failure' "set(document.querySelector('input[type=password]'),'synthetic-not-a-credential');await pause(0);button('读取状态').click();await until(()=>body().includes('运行服务未配置'));return {passed:body().includes('连续失败')&&button('开始采集').disabled&&localStorage.length===0&&sessionStorage.length===0&&!location.search.includes('synthetic-not-a-credential')};"
    foreach ($path in @('/events/00000000-0000-4000-8000-000000000002','/ask?demo=1','/ingest')) {
        Open-Page $path
        foreach ($width in @(390,768,1440)) {
            & agent-browser --session $session set viewport $width 1000 | Out-Null
            Check ("page_width_" + $path.Split('?')[0] + "_$width") "await pause(100);return {passed:document.documentElement.scrollWidth<=innerWidth,width:innerWidth,scroll:document.documentElement.scrollWidth};"
        }
    }
} finally {
    $report=[pscustomobject]@{observed_at=[DateTimeOffset]::UtcNow.ToString('o');base_url=$BaseUrl;passed=@($results|Where-Object passed).Count;total=$results.Count;checks=$results}
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot '../docs/frontend-browser-results.json'),($report|ConvertTo-Json -Depth 8))
}
$report | Select-Object passed,total | ConvertTo-Json -Compress
if (@($results|Where-Object { -not $_.passed }).Count) { exit 1 }
