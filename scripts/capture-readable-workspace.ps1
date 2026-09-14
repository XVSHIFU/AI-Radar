param([string]$BaseUrl='http://127.0.0.1:5175')
$ErrorActionPreference='Stop'
$session='radar-mvp'
$taskDir=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../.impeccable/review/readable-conversations'))
New-Item -ItemType Directory -Force -Path $taskDir|Out-Null
$taskResults=[Collections.Generic.List[object]]::new()
function Js([string]$code){$raw=& agent-browser --session $session eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)));if($LASTEXITCODE -ne 0){throw $raw};$raw|ConvertFrom-Json}
function Open([string]$path){& agent-browser --session $session open ($BaseUrl+$path)|Out-Null}
function Capture([string]$name){
 Start-Sleep -Milliseconds 350
 & agent-browser --session $session screenshot (Join-Path $taskDir ($name+'.png')) --full|Out-Null
 if($LASTEXITCODE -ne 0){throw 'Screenshot failed'}
 $g=Js "({width:innerWidth,scroll:document.documentElement.scrollWidth,view:document.querySelector('[data-testid=insights-visual]')?.dataset.view,assistant:document.querySelector('[data-testid=global-assistant]')?.getBoundingClientRect().toJSON()})"
 $taskResults.Add([pscustomobject]@{name=$name;passed=$g.scroll -le $g.width;geometry=$g})
}
function Week{
 Js "(async()=>{const b=[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==='近7天');b.click();for(let i=0;i<100&&!document.querySelector('[data-testid=insights-visual]');i++)await new Promise(r=>setTimeout(r,50))})()"|Out-Null
}
foreach($size in @(@{name='desktop';width=1440},@{name='mobile';width=390})){
 & agent-browser --session $session set viewport $size.width 1000|Out-Null
 Open '/ask'
 Week
 foreach($view in @('A','B','C')){Js "document.querySelector('button[data-view=$view]').click();scrollTo(0,0)"|Out-Null;Capture ($size.name+'-'+$view.ToLower())}
}
& agent-browser --session $session set viewport 1440 1000|Out-Null
Open '/?demo=1'
Js "document.querySelector('[data-testid=assistant-toggle]').click();document.querySelector('[data-testid=new-conversation]').click()"|Out-Null
Capture 'desktop-empty-assistant'
Js "(async()=>{const e=document.querySelector('[data-testid=assistant-composer] textarea');e.value='帮我核查当前事件的依据';e.dispatchEvent(new Event('input',{bubbles:true}));await new Promise(r=>setTimeout(r,0));[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='发送').click();await new Promise(r=>setTimeout(r,1000))})()"|Out-Null
Capture 'desktop-conversation'
Js "document.querySelector('[data-testid=history-toggle]').click()"|Out-Null
Capture 'desktop-history'
Js "document.querySelector('[data-testid=history-toggle]').click();document.querySelector('article.timeline-event a').click()"|Out-Null
Capture 'desktop-reader-assistant'
& agent-browser --session $session press Escape|Out-Null
& agent-browser --session $session set viewport 390 1000|Out-Null
Capture 'mobile-conversation'
Js "document.querySelector('[data-testid=history-toggle]').click()"|Out-Null
Capture 'mobile-history'
Js "document.querySelector('[data-testid=history-toggle]').click();document.querySelector('.assistant-close').click();document.querySelector('article.timeline-event a').click()"|Out-Null
Capture 'mobile-reader'
& agent-browser --session $session press Escape|Out-Null
& agent-browser --session $session set viewport 1680 1000|Out-Null
Open '/'
Js "document.querySelector('[data-testid=assistant-toggle]').click();document.querySelector('article.timeline-event a').click()"|Out-Null
Capture 'user-1680-workspace'
[IO.File]::WriteAllText([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../docs/readable-capture-results.json')),($taskResults|ConvertTo-Json -Depth 7))
$taskResults|Select-Object name,passed|ConvertTo-Json -Compress
