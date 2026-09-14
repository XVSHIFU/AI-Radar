param([string]$BaseUrl='http://127.0.0.1:5175',[string]$OutputDir='.impeccable/review/simple-mvp/round-1')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$destination=[IO.Path]::GetFullPath((Join-Path $root $OutputDir))
if (-not $destination.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Capture must stay in workspace' }
[IO.Directory]::CreateDirectory($destination)|Out-Null
$session='radar-mvp'
$records=[Collections.Generic.List[object]]::new()
function Js([string]$code) {
  $raw=& agent-browser --session $session eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)))
  if ($LASTEXITCODE -ne 0) {throw "Capture evaluation failed: $raw"}
  $raw|ConvertFrom-Json
}
function Capture([string]$state,[string]$device,[switch]$Full) {
  $layout=Js "(()=>{const d=document.querySelector('dialog[open]');const r=d?.getBoundingClientRect();const e=document.querySelector('[data-testid=preview-event]');return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,panelLeft:r?.left,panelRight:r?.right,panelOverflow:d?d.scrollWidth>d.clientWidth+1:false,focusInside:d?d.contains(document.activeElement):true,firstEventTop:e?.getBoundingClientRect().top,layerCount:document.querySelectorAll('dialog[open]').length,title:document.querySelector('h1')?.textContent,synthetic:document.body.innerText.includes('合成')||document.body.innerText.includes('模拟')};})()"
  Js "(()=>{const s=document.createElement('style');s.textContent='*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}';document.head.append(s);return true;})()"|Out-Null
  $file=Join-Path $destination ($device+'-'+$state+'.png')
  if($Full){ & agent-browser --session $session screenshot --full $file|Out-Null }
  else{ & agent-browser --session $session screenshot $file|Out-Null }
  if($LASTEXITCODE -ne 0){throw 'Capture failed'}
  $passed=$layout.scrollWidth -le $layout.width -and -not $layout.panelOverflow -and $layout.focusInside
  if($layout.layerCount){$passed=$passed -and $layout.panelLeft -ge 0 -and $layout.panelRight -le $layout.width+1}
  $records.Add([pscustomobject]@{state=$state;device=$device;passed=$passed;path=$file;layout=$layout})
}
foreach($device in @(@{name='desktop';width=1440},@{name='mobile';width=390})){
  & agent-browser --session $session set viewport $device.width 1000|Out-Null
  & agent-browser --session $session open ($BaseUrl+'/preview')|Out-Null
  Js "(async()=>{for(let i=0;i<100;i++){if(document.querySelectorAll('[data-testid=preview-event]').length===10){window.scrollTo(0,0);return true;}await new Promise(r=>setTimeout(r,50));}throw Error('Home not ready');})()"|Out-Null
  Capture 'home' $device.name
  Capture 'home-full' $device.name -Full
  Js "(async()=>{const a=[...document.querySelectorAll('[data-testid=preview-event] a')].find(x=>x.pathname.endsWith('000000000002'));a.focus();a.click();for(let i=0;i<100;i++){if(document.querySelector('[data-testid=preview-reader][open] blockquote')){await new Promise(r=>setTimeout(r,300));return true;}await new Promise(r=>setTimeout(r,50));}throw Error('Reader not ready');})()"|Out-Null
  Capture 'reader' $device.name
  & agent-browser --session $session open ($BaseUrl+'/preview/ask')|Out-Null
  Js "(async()=>{for(let i=0;i<100;i++){if(document.querySelector('textarea')){window.scrollTo(0,0);return true;}await new Promise(r=>setTimeout(r,50));}throw Error('Ask not ready');})()"|Out-Null
  Capture 'ask' $device.name
}
$report=[pscustomobject]@{observed_at=[DateTimeOffset]::UtcNow.ToString('o');base_url=$BaseUrl;layer='fixture_api_visual_capture';passed=@($records|Where-Object passed).Count;total=$records.Count;checks=$records}
[IO.File]::WriteAllText((Join-Path $destination 'capture-results.json'),($report|ConvertTo-Json -Depth 8))
$report|Select-Object passed,total|ConvertTo-Json -Compress
if(@($records|Where-Object {-not $_.passed}).Count){exit 1}
