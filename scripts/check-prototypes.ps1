param([string]$SolUrl = 'http://127.0.0.1:4174', [string]$TerraUrl = 'http://127.0.0.1:4173')
$ErrorActionPreference = 'Stop'
$session = 'radar-acceptance'
function Invoke-BrowserJs([string]$code) {
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code))
    $raw = & agent-browser --session $session eval -b $encoded
    if ($LASTEXITCODE -ne 0) { throw "Browser evaluation failed: $raw" }
    return ($raw | ConvertFrom-Json)
}
$results = @()
try {
    foreach ($candidate in @(@{name='sol';url=$SolUrl}, @{name='terra';url=$TerraUrl})) {
        & agent-browser --session $session open $candidate.url | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Prototype server unavailable' }
        $resultSelector = if ($candidate.name -eq 'sol') { '#result-heading' } else { '[aria-live]' }
        $eventSelector = if ($candidate.name -eq 'sol') { '.event-title' } else { 'article h3 a' }
        $checks = @(
            @{name='initial_total'; query=''; category=''; from=''; to=''; count=32},
            @{name='full_dataset_deepseek'; query='DeepSeek'; category=''; from=''; to=''; count=6},
            @{name='zero_results'; query='not-a-real-event-zz'; category=''; from=''; to=''; count=0},
            @{name='inclusive_dates_category'; query=''; category='agent_tool'; from='2026-09-08'; to='2026-09-10'; count=3}
        )
        foreach ($check in $checks) {
            $inputJson = $check | ConvertTo-Json -Compress
            $js = @"
(async()=>{
const c=$inputJson;
const set=(el,value)=>{if(!el)throw Error('missing control');el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};
set(document.querySelector('input[type=search],input[placeholder]'),c.query);
const select=document.querySelector('select');if(select)set(select,c.category);else document.querySelector('input[type=radio][value="'+c.category+'"]').click();
const dates=[...document.querySelectorAll('input[type=date]')];set(dates[0],c.from);set(dates[1],c.to);
await new Promise(r=>setTimeout(r,1000));
return {text:document.querySelector('$resultSelector').textContent,ids:[...document.querySelectorAll('$eventSelector')].map(e=>e.getAttribute('href').split('/').pop())};
})()
"@
            $actual = Invoke-BrowserJs $js
            $passed = $actual.text -match "(?<!\d)$($check.count)\s*条"
            if ($check.name -eq 'inclusive_dates_category') {
                $expectedIds = @('00000000-0000-4000-8000-000000000013','00000000-0000-4000-8000-000000000019','00000000-0000-4000-8000-000000000025')
                $passed = $passed -and (@(Compare-Object ($actual.ids | Sort-Object) ($expectedIds | Sort-Object)).Count -eq 0)
            }
            $results += [pscustomobject]@{candidate=$candidate.name;check=$check.name;passed=$passed;actual=$actual}
        }
        foreach ($width in @(390,768,1440)) {
            & agent-browser --session $session set viewport $width 1000 | Out-Null
            $actual = Invoke-BrowserJs '({width:innerWidth,scroll:document.documentElement.scrollWidth})'
            $results += [pscustomobject]@{candidate=$candidate.name;check="overflow_$width";passed=($actual.scroll -le $actual.width);actual=$actual}
        }
    }
} finally { & agent-browser --session $session close | Out-Null }
$report = [pscustomobject]@{observed_at=[DateTimeOffset]::UtcNow.ToString('o');layer='synthetic_browser_dom';passed=@($results | Where-Object passed).Count;total=$results.Count;checks=$results}
$target = Join-Path $PSScriptRoot '../docs/prototype-browser-results.json'
[IO.File]::WriteAllText($target, ($report | ConvertTo-Json -Depth 8))
$report | Select-Object passed,total | ConvertTo-Json -Compress
if (@($results | Where-Object { -not $_.passed }).Count -gt 0) { exit 1 }
