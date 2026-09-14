param([string]$BaseUrl='http://127.0.0.1:5175',[string[]]$Only=@())
$ErrorActionPreference='Stop'
$taskSession='radar-mvp'
$taskDirectory=Join-Path $PSScriptRoot '../.impeccable/review/global-assistant'
New-Item -ItemType Directory -Force -Path $taskDirectory|Out-Null
function Js([string]$code){$raw=& agent-browser --session $taskSession eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code))); if($LASTEXITCODE -ne 0){throw $raw};$raw|ConvertFrom-Json}
function Open([string]$path){& agent-browser --session $taskSession open ($BaseUrl+$path)|Out-Null}
function Capture([string]$name){
 if ($Only.Count -and $name -notin $Only) { return }
 Js 'scrollTo(0,0)'|Out-Null
 Start-Sleep -Milliseconds 350
 & agent-browser --session $taskSession screenshot ([IO.Path]::GetFullPath((Join-Path $taskDirectory ($name+'.png')))) --full|Out-Null
 if($LASTEXITCODE -ne 0){throw "Capture failed $name"}
 $geometry=Js "({width:innerWidth,scroll:document.documentElement.scrollWidth,title:document.querySelector('h1')?.textContent,view:document.querySelector('[data-testid=insights-visual]')?.dataset.view,assistant:document.querySelector('[data-testid=assistant-toggle]')?.getAttribute('aria-expanded')})"
 $taskResults.Add([pscustomobject]@{name=$name;passed=$geometry.scroll -le $geometry.width;geometry=$geometry})
}
$taskResults=[Collections.Generic.List[object]]::new()
foreach($size in @(@{name='desktop';width=1440},@{name='mobile';width=390})){
 & agent-browser --session $taskSession set viewport $size.width 1000|Out-Null
 Open '/'
 Capture ($size.name+'-home')
 Js "document.querySelector('[data-testid=assistant-toggle]').click()"|Out-Null
 Capture ($size.name+'-assistant')
 Open '/ask'
 Capture ($size.name+'-today')
 Js "(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='近7天').click();for(let i=0;i<80;i++){if(document.querySelector('[data-testid=insights-visual]'))return;await new Promise(r=>setTimeout(r,50));}throw Error('Charts missing')})()"|Out-Null
 foreach($view in @('A','B','C')){
  Js "document.querySelector('button[data-view=$view]').click()"|Out-Null
  Capture ($size.name+'-'+$view.ToLower())
 }
}
& agent-browser --session $taskSession set viewport 1680 1000|Out-Null
Open '/'
Capture 'user-1680-home'
Open '/ask'
Js "(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='近7天').click();for(let i=0;i<80;i++){if(document.querySelector('[data-testid=insights-visual]'))return;await new Promise(r=>setTimeout(r,50));}})()"|Out-Null
Capture 'user-1680-statistics'
[IO.File]::WriteAllText([IO.Path]::GetFullPath((Join-Path $PSScriptRoot ../docs/global-capture-review-results.json)),($taskResults|ConvertTo-Json -Depth 6))
$taskResults|Select-Object name,passed|ConvertTo-Json -Compress
