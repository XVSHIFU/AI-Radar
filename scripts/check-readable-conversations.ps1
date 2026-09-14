param([string]$BaseUrl='http://127.0.0.1:5175')
$ErrorActionPreference='Stop'
$taskSession='radar-mvp'
$taskChecks=[Collections.Generic.List[object]]::new()
function Js([string]$code){$raw=& agent-browser --session $taskSession eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)));if($LASTEXITCODE -ne 0){throw $raw};$raw|ConvertFrom-Json}
function Open([string]$path){& agent-browser --session $taskSession open ($BaseUrl+$path)|Out-Null;if($LASTEXITCODE -ne 0){throw 'Preview unavailable'}}
$taskSetup=@'
const t=id=>document.querySelector('[data-testid="'+id+'"]');
const all=id=>id==='ask-answer'?[...document.querySelectorAll('.conversation-turn.assistant')]:[...document.querySelectorAll('[data-testid="'+id+'"]')];
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const until=async f=>{for(let i=0;i<100;i++){if(f())return;await pause(50)}throw Error('UI timed out')};
const button=text=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===text);
const set=(e,value)=>{if(!e)throw Error('Input missing');e.value=value;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))};
const visible=e=>!!e&&e.getClientRects().length>0;
const send=async text=>{set(t('assistant-composer').querySelector('textarea'),text);await pause(0);(button('发送')||button('开始分析')).click()};
const answerMock=()=>{if(window.__askIntercept)return;window.__askIntercept=true;window.__requests=[];const original=window.fetch;window.fetch=(url,init)=>{if(String(url).endsWith('/ask')){const request=JSON.parse(init.body);window.__requests.push(request);return Promise.resolve(new Response(JSON.stringify({answer:'合成验收回答：'+request.question,citations:[{index:2,title:'合成来源 '+request.question,source_url:'https://example.invalid/fixture',quote_text:'合成引用 '+request.question,paragraph_id:'synthetic-p2'}],execution_status:'completed',answer_status:'answered',scope_total:1,retrieved_count:1,summarized_count:1,citation_count:1,coverage:'complete'}),{status:200,headers:{'content-type':'application/json'}}))}return original(url,init)}};
'@
function Check([string]$name,[string]$code){try{$actual=Js ('(async()=>{'+$taskSetup+$code+'})()');$taskChecks.Add([pscustomobject]@{name=$name;passed=$actual.passed -eq $true;actual=$actual})}catch{$taskChecks.Add([pscustomobject]@{name=$name;passed=$false;error=$_.Exception.Message})};Write-Output ('Checked '+$name)}
& agent-browser --session $taskSession set viewport 1440 1000|Out-Null
Open '/'
Check 'new_conversation' "await until(()=>t('assistant-toggle'));t('assistant-toggle').click();await until(()=>visible(t('global-assistant'))&&t('new-conversation'));t('new-conversation').click();await pause(100);answerMock();return {passed:visible(t('assistant-composer'))&&all('conversation-turn').length===0};"
Check 'first_message' "await send('第一轮验收');await until(()=>all('ask-answer').some(e=>e.textContent.includes('第一轮验收')));return {passed:all('conversation-turn').length===2};"
Check 'second_preserves_first_and_context' "await send('第二轮追问');await until(()=>all('ask-answer').length===2);const r=window.__requests.at(-1);return {passed:all('ask-answer')[0].textContent.includes('第一轮验收')&&r.history.some(m=>m.role==='user'&&m.content.includes('第一轮验收'))&&r.history.length<=6&&r.history.reduce((n,m)=>n+m.content.length,0)<=12000,history:r.history};"
Check 'composer_below_messages' "const c=t('assistant-composer').getBoundingClientRect(),m=t('conversation-messages').getBoundingClientRect();return {passed:c.top>=m.bottom-2&&c.bottom<=innerHeight+1,composer:c.toJSON(),messages:m.toJSON()};"
Check 'citation_ids_unique_per_turn' "const bs=all('ask-answer').flatMap(e=>[...e.querySelectorAll('button')]).filter(b=>b.textContent.includes('[2]'));const ids=[],texts=[];for(const b of bs){b.click();await pause(0);const block=document.getElementById(b.getAttribute('aria-controls'));ids.push(block?.id);texts.push(block?.textContent||'')}return {passed:ids.length===2&&new Set(ids).size===2&&texts[0].includes('第一轮验收')&&texts[1].includes('第二轮追问'),ids};"
Check 'draft_before_reload' "set(t('assistant-composer').querySelector('textarea'),'未发送的草稿');await pause(800);return {passed:true};"
Open '/'
Check 'reload_restores_turns_and_draft' "await until(()=>t('assistant-toggle'));t('assistant-toggle').click();await until(()=>all('ask-answer').length===2);return {passed:all('ask-answer')[0].textContent.includes('第一轮验收')&&all('ask-answer')[1].textContent.includes('第二轮追问')&&t('assistant-composer').querySelector('textarea').value==='未发送的草稿'};"
Check 'history_toggle' "t('history-toggle').click();await until(()=>visible(t('history-panel')));const count=all('history-item').length;t('history-toggle').click();await pause(0);return {passed:count>=1&&!visible(t('history-panel'))};"
Check 'resize_focus' "t('assistant-resizer').focus();return {passed:document.activeElement===t('assistant-resizer')};"
& agent-browser --session $taskSession press End|Out-Null
Check 'resize_half_screen_limit' "await pause(0);const r=t('global-assistant').getBoundingClientRect();return {passed:r.width<=innerWidth/2+1&&r.width>=360,width:r.width,viewport:innerWidth};"
Check 'reader_left_and_assistant_operable' "document.querySelector('article.timeline-event a').click();await until(()=>document.querySelector('dialog[open]'));await pause(300);const d=[...document.querySelectorAll('dialog[open]')].at(-1),r=d.getBoundingClientRect(),a=t('global-assistant').getBoundingClientRect();t('assistant-composer').querySelector('textarea').focus();return {passed:!d.matches(':modal')&&r.right<=a.left+2&&document.activeElement===t('assistant-composer').querySelector('textarea'),reader:r.toJSON(),assistant:a.toJSON()};"
Check 'attach_event_for_next_question' "t('attach-event').click();await until(()=>t('attached-event'));return {passed:visible(t('attached-event'))&&all('ask-answer').length===2};"
& agent-browser --session $taskSession press Escape|Out-Null
Check 'escape_only_reader' "await pause(0);return {passed:!document.querySelector('dialog[open]')&&visible(t('global-assistant'))&&all('ask-answer').length===2};"
Check 'attachment_payload' "answerMock();await send('第三轮附件验收');await until(()=>all('ask-answer').length===3);const r=window.__requests.at(-1);return {passed:r.event_ids.length===1&&r.history.length<=6,event_ids:r.event_ids};"
& agent-browser --session $taskSession set viewport 390 1000|Out-Null
Check 'mobile_controls_visible' "await pause(100);const c=t('assistant-composer').getBoundingClientRect(),r=document.querySelector('.assistant-close').getBoundingClientRect();return {passed:document.documentElement.scrollWidth<=innerWidth&&c.bottom<=innerHeight+1&&r.top>=0&&r.bottom<=innerHeight,composer:c.toJSON(),return:r.toJSON()};"
& agent-browser --session $taskSession set viewport 390 600|Out-Null
Check 'short_viewport_composer_visible' "await pause(100);const c=t('assistant-composer').getBoundingClientRect();return {passed:c.top>=0&&c.bottom<=innerHeight+1,composer:c.toJSON()};"
$taskReport=[pscustomobject]@{observed_at=[DateTimeOffset]::UtcNow.ToString('o');layer='browser_fixture_with_synthetic_ask_response';passed=@($taskChecks|Where-Object passed).Count;total=$taskChecks.Count;checks=$taskChecks}
[IO.File]::WriteAllText([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../docs/readable-conversation-browser-results.json')),($taskReport|ConvertTo-Json -Depth 9))
$taskReport|Select-Object passed,total|ConvertTo-Json -Compress
if($taskReport.passed -ne $taskReport.total){exit 1}
