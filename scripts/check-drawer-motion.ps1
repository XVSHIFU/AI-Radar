param([string]$BaseUrl='http://127.0.0.1:5175')
$ErrorActionPreference='Stop'
$session='radar-acceptance'
$records=[Collections.Generic.List[object]]::new()
function Js([string]$code) {
  $encoded=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code))
  $raw=& agent-browser --session $session eval -b $encoded
  if ($LASTEXITCODE -ne 0) { throw "Browser evaluation failed: $raw" }
  $raw | ConvertFrom-Json
}
try {
  & agent-browser --session $session set viewport 1440 1000 | Out-Null
  foreach ($reduced in @($false,$true)) {
    if ($reduced) { & agent-browser --session $session set media light reduced-motion | Out-Null }
    else { & agent-browser --session $session set media light | Out-Null }
    & agent-browser --session $session open ($BaseUrl+'/?event=00000000-0000-4000-8000-000000000002') | Out-Null
    $actual=Js "(async()=>{const pause=ms=>new Promise(r=>setTimeout(r,ms));const until=async f=>{for(let i=0;i<100;i++){if(f())return;await pause(10);}throw Error('Drawer not ready');};const top=()=>[...document.querySelectorAll('dialog[open]')].at(-1);await until(()=>!!document.querySelector('[data-testid=source-open]'));await pause(250);const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;document.querySelector('[data-testid=source-open]').click();await until(()=>top()?.dataset.testid==='drawer-source');const source=top();const enter={name:getComputedStyle(source).animationName,start:source.getBoundingClientRect().left};const rear=document.querySelector('[data-testid=drawer-event]');const rearHidden=getComputedStyle(rear.querySelector('.drawer-body')).visibility==='hidden'&&[...rear.querySelector('.drawer-header').children].every(x=>getComputedStyle(x).visibility==='hidden');await pause(250);enter.end=source.getBoundingClientRect().left;source.querySelector('[data-testid=drawer-back]').click();await until(()=>document.querySelectorAll('dialog[open]').length===1);const event=top();const back={name:getComputedStyle(event).animationName,start:event.getBoundingClientRect().left};await pause(250);back.end=event.getBoundingClientRect().left;const motion=m=>reduced?m.name==='none'&&Math.abs(m.start-m.end)<0.5:m.name!=='none'&&m.start-m.end>0.1;return {passed:motion(enter)&&motion(back)&&rearHidden&&getComputedStyle(event.querySelector('.drawer-body')).visibility==='visible'&&event.contains(document.activeElement),reduced,enter,back,rearHidden};})()"
    $records.Add([pscustomobject]@{check="drawer_motion_reduced_$reduced";passed=$actual.passed;actual=$actual})
  }
} finally {
  & agent-browser --session $session set media light | Out-Null
}
$report=[pscustomobject]@{observed_at=[DateTimeOffset]::UtcNow.ToString('o');layer='fixture_api_browser_motion';passed=@($records|Where-Object passed).Count;total=$records.Count;checks=$records}
[IO.File]::WriteAllText((Join-Path $PSScriptRoot '../docs/drawer-motion-results.json'),($report|ConvertTo-Json -Depth 8))
$report | ConvertTo-Json -Depth 8
if (@($records|Where-Object {-not $_.passed}).Count) { exit 1 }
