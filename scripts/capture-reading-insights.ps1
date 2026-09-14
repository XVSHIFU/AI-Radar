param([string]$BaseUrl='http://127.0.0.1:5175',[string]$OutputDir='.impeccable/review/reading-insights/round-1')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$destination=[IO.Path]::GetFullPath((Join-Path $root $OutputDir))
if(-not $destination.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Capture must stay in workspace'}
[IO.Directory]::CreateDirectory($destination)|Out-Null
$session='radar-mvp'
$records=[Collections.Generic.List[object]]::new()
function Js([string]$code) {
 $raw=& agent-browser --session $session eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)))
 if($LASTEXITCODE -ne 0){throw "Capture evaluation failed: $raw"}
 $raw|ConvertFrom-Json
}
function Ready([string]$condition){
 Js ("(async()=>{for(let i=0;i<100;i++){if("+$condition+"){await new Promise(r=>setTimeout(r,300));window.scrollTo(0,0);return true;}await new Promise(r=>setTimeout(r,50));}throw Error('Not ready');})()")|Out-Null
}
function Capture([string]$state,[string]$device,[switch]$Full) {
 $layout=Js "(()=>{const d=[...document.querySelectorAll('dialog:modal')].at(-1),r=d?.getBoundingClientRect();return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,panelLeft:r?.left,panelRight:r?.right,panelOverflow:d?d.scrollWidth>d.clientWidth+1:false,focusInside:d?d.contains(document.activeElement):true,layerCount:document.querySelectorAll('dialog:modal').length,title:document.querySelector('h1')?.textContent,synthetic:document.body.innerText.includes('合成')||document.body.innerText.includes('模拟')};})()"
 Js "(()=>{const s=document.createElement('style');s.textContent='*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}';document.head.append(s);window.scrollTo(0,0);return true;})()"|Out-Null
 $file=Join-Path $destination ($device+'-'+$state+'.png')
 if($Full){& agent-browser --session $session screenshot --full $file|Out-Null}else{& agent-browser --session $session screenshot $file|Out-Null}
 if($LASTEXITCODE -ne 0){throw 'Capture failed'}
 $passed=$layout.scrollWidth -le $layout.width -and -not $layout.panelOverflow -and $layout.focusInside
 if($layout.layerCount){$passed=$passed -and $layout.panelLeft -ge 0 -and $layout.panelRight -le $layout.width+1}
 $records.Add([pscustomobject]@{state=$state;device=$device;passed=$passed;path=$file;layout=$layout})
}
foreach($device in @(@{name='desktop';width=1680},@{name='mobile';width=390})){
 & agent-browser --session $session set viewport $device.width 1000|Out-Null
 & agent-browser --session $session open ($BaseUrl+'/')|Out-Null
 Ready "document.querySelectorAll('article.timeline-event').length===10"
 Capture 'home' $device.name
 & agent-browser --session $session open ($BaseUrl+'/?event=00000000-0000-4000-8000-000000000002')|Out-Null
 Ready "document.querySelector('[data-testid=drawer-event][open] blockquote')"
 Capture 'event' $device.name
 Js "document.querySelector('[data-testid=source-open]').click();true"|Out-Null
 Ready "document.querySelector('[data-testid=drawer-source][open]')"
 Capture 'source' $device.name
 & agent-browser --session $session open ($BaseUrl+'/ask')|Out-Null
 Ready "document.querySelector('[data-testid=insights-summary]')?.textContent.includes('精确匹配')"
 Capture 'ask-today' $device.name
 Js "[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='近7天').click();true"|Out-Null
 Ready "document.querySelector('[data-testid=insights-summary]')?.textContent.includes('精确匹配 25 条')"
 Capture 'ask-week' $device.name
 Capture 'ask-week-full' $device.name -Full
 Js "(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='自定义').click();await new Promise(r=>setTimeout(r,0));for(const [name,value] of [['date_from','2026-08-15'],['date_to','2026-10-15']]){const el=document.querySelector('[name='+name+']');el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));}return true;})()"|Out-Null
 Ready "document.querySelector('[data-testid=insights-daily]')?.querySelectorAll('[data-date-from]').length===3"
 Capture 'ask-months' $device.name
}
$report=[pscustomobject]@{observed_at=[DateTimeOffset]::UtcNow.ToString('o');base_url=$BaseUrl;layer='fixture_api_visual_capture';passed=@($records|Where-Object passed).Count;total=$records.Count;checks=$records}
[IO.File]::WriteAllText((Join-Path $destination 'capture-results.json'),($report|ConvertTo-Json -Depth 8))
$report|Select-Object passed,total|ConvertTo-Json -Compress
if(@($records|Where-Object {-not $_.passed}).Count){exit 1}
