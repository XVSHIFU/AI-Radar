param([string]$BaseUrl = 'http://127.0.0.1:5175', [string]$OutputDir = '.impeccable/review')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$destination = [IO.Path]::GetFullPath((Join-Path $projectRoot $OutputDir))
if (-not $destination.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Capture directory must be inside the project' }
[IO.Directory]::CreateDirectory($destination) | Out-Null
$session = 'radar-acceptance'
function Js([string]$code) {
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code))
    $raw = & agent-browser --session $session eval -b $encoded
    if ($LASTEXITCODE -ne 0) { throw "Browser evaluation failed: $raw" }
    return ($raw | ConvertFrom-Json)
}
$records = [Collections.Generic.List[object]]::new()
$pages = @(
    @{name='home';path='/';ready="document.querySelectorAll('article.timeline-event').length===10"},
    @{name='detail';path='/events/00000000-0000-4000-8000-000000000002';ready="!![...document.querySelectorAll('button')].find(b=>b.textContent.includes('展开')&&b.textContent.includes('摘录'))"},
    @{name='ask';path='/ask?demo=1';ready="!!document.querySelector('textarea')"},
    @{name='ingest';path='/ingest';ready="!!document.querySelector('input[type=password]')"}
)
foreach ($page in $pages) {
    foreach ($viewport in @(@{name='desktop';width=1440;height=1000},@{name='mobile';width=390;height=1000})) {
        & agent-browser --session $session set viewport $viewport.width $viewport.height | Out-Null
        & agent-browser --session $session open ($BaseUrl + $page.path) | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Failed to open capture page' }
        $ready = Js ("(async()=>{for(let i=0;i<100;i++){if(" + $page.ready + ")return true;await new Promise(r=>setTimeout(r,50));}throw Error('Capture page did not settle');})()")
        if ($page.name -eq 'detail') {
            Js "(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent.includes('展开')&&b.textContent.includes('摘录')).click();await new Promise(r=>setTimeout(r,300));return !!document.querySelector('blockquote');})()" | Out-Null
        }
        if ($page.name -eq 'ask') {
            Js "(async()=>{const t=document.querySelector('textarea');t.value='DeepSeek';t.dispatchEvent(new Event('input',{bubbles:true}));await new Promise(r=>setTimeout(r,0));[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='开始分析').click();for(let i=0;i<100;i++){if(document.body.innerText.includes('模拟流已完成')){const b=[...document.querySelectorAll('main button')].find(x=>x.textContent.includes('[2]'));if(b)b.click();await new Promise(r=>setTimeout(r,300));return true;}await new Promise(r=>setTimeout(r,50));}throw Error('Demo answer did not finish');})()" | Out-Null
        }
        $layout = Js "(()=>{window.scrollTo(0,0);const h=document.querySelector('h1');const rail=document.querySelector('.app-rail');const search=document.querySelector('input[placeholder]');const context=document.querySelector('.context-panel');const nav=[...document.querySelectorAll('nav a')].filter(x=>x.getBoundingClientRect().height);const main=document.querySelector('main');return {title:h?.textContent.trim(),firstEventTop:document.querySelector('article.timeline-event')?.getBoundingClientRect().top,categorySelectWidth:document.querySelector('select')?.getBoundingClientRect().width,headingTop:h?.getBoundingClientRect().top,railTop:rail?.getBoundingClientRect().top,searchWidth:search?.getBoundingClientRect().width,contextHeight:context?.getBoundingClientRect().height,width:innerWidth,scrollWidth:document.documentElement.scrollWidth,mainWidth:main?.getBoundingClientRect().width,headingCount:document.querySelectorAll('main h1').length,articleCount:document.querySelectorAll('article.timeline-event').length,navTargets:nav.map(x=>({text:x.textContent.trim(),height:x.getBoundingClientRect().height})),bodyFont:getComputedStyle(document.body).fontFamily,bodySize:getComputedStyle(document.body).fontSize,syntheticNotice:document.body.innerText.includes('合成数据')||document.body.innerText.includes('前端模拟'),textLength:main?.innerText.length};})()"
        Js "(()=>{window.scrollTo(0,0);const s=document.createElement('style');s.textContent='*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}';document.head.append(s);return true;})()" | Out-Null
        $stem = if ($page.name -eq 'home') { $viewport.name } else { $page.name + '-' + $viewport.name }
        $fullPath = Join-Path $destination ($stem + '.png')
        & agent-browser --session $session screenshot --full $fullPath | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Screenshot failed' }
        if ($page.name -eq 'home') {
            & agent-browser --session $session screenshot (Join-Path $destination ($stem + '-viewport.png')) | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'Viewport screenshot failed' }
        }
        $passed = $layout.scrollWidth -le $layout.width -and $layout.headingCount -eq 1 -and $layout.textLength -gt 40 -and @($layout.navTargets | Where-Object { $_.height -lt 44 }).Count -eq 0
        if ($viewport.name -eq 'desktop') { $passed = $passed -and $layout.railTop -ge 0 -and $layout.railTop -le 32 }
        if ($viewport.name -eq 'mobile') { $passed = $passed -and $layout.headingTop -le 360 }
        if ($page.name -eq 'home' -and $viewport.name -eq 'desktop') { $passed = $passed -and $layout.searchWidth -ge 300 -and $layout.contextHeight -le 1000 }
        if ($page.name -eq 'home') { $passed = $passed -and $layout.firstEventTop -lt 500 }
        if ($page.name -eq 'ask' -and $viewport.name -eq 'desktop') { $passed = $passed -and $layout.categorySelectWidth -ge 120 }
        $records.Add([pscustomobject]@{page=$page.name;viewport=$viewport.name;path=$page.path;passed=$passed;screenshot=$fullPath;layout=$layout})
    }
}
$report = [pscustomobject]@{observed_at=[DateTimeOffset]::UtcNow.ToString('o');base_url=$BaseUrl;layer='fixture_and_explicit_demo_visual_capture';passed=@($records|Where-Object passed).Count;total=$records.Count;checks=$records}
[IO.File]::WriteAllText((Join-Path $destination 'capture-results.json'),($report | ConvertTo-Json -Depth 10))
$report | Select-Object passed,total | ConvertTo-Json -Compress
if (@($records | Where-Object { -not $_.passed }).Count) { exit 1 }
