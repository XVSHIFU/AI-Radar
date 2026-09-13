param([string]$BaseUrl='http://127.0.0.1:5175',[string]$OutputDir='.impeccable/review/drawers/round-1')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$destination=[IO.Path]::GetFullPath((Join-Path $root $OutputDir))
if (-not $destination.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Capture destination must be inside workspace' }
[IO.Directory]::CreateDirectory($destination) | Out-Null
$session='radar-acceptance'
$records=[Collections.Generic.List[object]]::new()
function Js([string]$code) {
    $encoded=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code))
    $raw=& agent-browser --session $session eval -b $encoded
    if ($LASTEXITCODE -ne 0) { throw "Capture evaluation failed: $raw" }
    $raw | ConvertFrom-Json
}
function Capture([string]$state,[string]$device,[switch]$Full) {
    $layout=Js "(()=>{const d=[...document.querySelectorAll('dialog[open]')].at(-1);const r=d?.getBoundingClientRect();const toggles=[...document.querySelectorAll('[data-testid^=timeline-][data-testid$=-toggle]')].filter(x=>x.getClientRects().length);return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,layerCount:document.querySelectorAll('dialog[open]').length,panelLeft:r?.left,panelRight:r?.right,panelWidth:r?.width,panelOverflow:d?d.scrollWidth>d.clientWidth+1:false,focusInside:d?d.contains(document.activeElement):true,minimumToggleHeight:Math.min(...toggles.map(x=>x.getBoundingClientRect().height)),title:document.querySelector('h1')?.textContent,synthetic:document.body.innerText.includes('合成数据')||document.body.innerText.includes('合成')};})()"
    Js "(()=>{const s=document.createElement('style');s.textContent='*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}';document.head.append(s);return true;})()" | Out-Null
    $file=Join-Path $destination ($device+'-'+$state+'.png')
    if ($Full) { & agent-browser --session $session screenshot --full $file | Out-Null }
    else { & agent-browser --session $session screenshot $file | Out-Null }
    if ($LASTEXITCODE -ne 0) { throw 'Screenshot failed' }
    $passed=$layout.scrollWidth -le $layout.width -and -not $layout.panelOverflow -and $layout.focusInside
    if ($layout.layerCount) { $passed=$passed -and $layout.panelLeft -ge 0 -and $layout.panelRight -le $layout.width+1 }
    $records.Add([pscustomobject]@{state=$state;device=$device;passed=$passed;path=$file;layout=$layout})
}
foreach ($viewport in @(@{name='desktop';width=1440},@{name='mobile';width=390})) {
    & agent-browser --session $session set viewport $viewport.width 1000 | Out-Null
    & agent-browser --session $session open ($BaseUrl+'/') | Out-Null
    Js "(async()=>{for(let i=0;i<100;i++){if(document.querySelectorAll('article.timeline-event').length===10&&document.querySelector('[data-testid=timeline-month-toggle]')){window.scrollTo(0,0);return true;}await new Promise(r=>setTimeout(r,50));}throw Error('Timeline did not settle');})()" | Out-Null
    Capture 'home' $viewport.name
    Capture 'home-full' $viewport.name -Full
    Js "(async()=>{document.querySelector('[data-testid=timeline-month-toggle]').click();await new Promise(r=>setTimeout(r,300));window.scrollTo(0,0);return true;})()" | Out-Null
    Capture 'month-collapsed' $viewport.name
    Js "(async()=>{document.querySelector('[data-testid=timeline-month-toggle]').click();await new Promise(r=>setTimeout(r,50));const a=[...document.querySelectorAll('article.timeline-event a')].find(a=>a.pathname.endsWith('000000000002'));a.focus();a.click();for(let i=0;i<100;i++){if(document.querySelector('[data-testid=source-open]')){await new Promise(r=>setTimeout(r,300));return true;}await new Promise(r=>setTimeout(r,50));}throw Error('Event drawer did not settle');})()" | Out-Null
    Capture 'event' $viewport.name
    Js "(async()=>{document.querySelector('[data-testid=source-open]').click();for(let i=0;i<100;i++){if(document.querySelector('[data-testid=evidence-open]')){await new Promise(r=>setTimeout(r,300));return true;}await new Promise(r=>setTimeout(r,50));}throw Error('Source drawer did not settle');})()" | Out-Null
    Capture 'source' $viewport.name
    Js "(async()=>{document.querySelector('[data-testid=evidence-open]').click();for(let i=0;i<100;i++){const d=document.querySelector('[data-testid=drawer-evidence]');if(d&&d.textContent.includes('synthetic-v1-p1')){await new Promise(r=>setTimeout(r,300));return true;}await new Promise(r=>setTimeout(r,50));}throw Error('Evidence drawer did not settle');})()" | Out-Null
    Capture 'evidence' $viewport.name
}
$report=[pscustomobject]@{observed_at=[DateTimeOffset]::UtcNow.ToString('o');base_url=$BaseUrl;layer='fixture_api_visual_capture';passed=@($records|Where-Object passed).Count;total=$records.Count;checks=$records}
[IO.File]::WriteAllText((Join-Path $destination 'capture-results.json'),($report|ConvertTo-Json -Depth 8))
$report | Select-Object passed,total | ConvertTo-Json -Compress
if (@($records|Where-Object {-not $_.passed}).Count) {exit 1}
