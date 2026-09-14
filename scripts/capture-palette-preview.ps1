param([string]$BaseUrl='http://127.0.0.1:5175')
$ErrorActionPreference='Stop';$session='radar-palette';$dir=Join-Path (Get-Location) '.impeccable/review/palette-preview'
New-Item -ItemType Directory -Force $dir|Out-Null
function Js([string]$code){$out=& agent-browser --session $session eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)));if($LASTEXITCODE -ne 0){throw $out}}
function Open([string]$route){& agent-browser --session $session open ($BaseUrl+$route)|Out-Null;Js '(async()=>{for(let i=0;i<100;i++){if(document.querySelector("h1"))break;await new Promise(r=>setTimeout(r,30))}await new Promise(r=>setTimeout(r,450));scrollTo(0,0)})()'|Out-Null}
function Shot([string]$name,[bool]$full=$false){if($full){$out=& agent-browser --session $session screenshot --full}else{$out=& agent-browser --session $session screenshot};$m=[regex]::Match(($out -join "\n"),'Screenshot saved to (.+)');if(!$m.Success){throw $out};Copy-Item -LiteralPath $m.Groups[1].Value.Trim() -Destination (Join-Path $dir ($name+'.png'));Write-Output $name}
& agent-browser --session $session set viewport 1680 1000|Out-Null
Open '/?demo=1'

foreach($theme in @('A','B','C','D','E')){
 Open ('/palette-preview.html?theme='+$theme+'&view=home')
 Shot ($theme+'-home')
 Js 'document.querySelector("[data-page=stats]").click()'|Out-Null
 Shot ($theme+'-stats')
}
& agent-browser --session $session set viewport 390 844|Out-Null
Open '/palette-preview.html?theme=B&view=home'
Shot 'mobile-home'
Js 'document.querySelector("[data-page=stats]").click()'|Out-Null
Shot 'mobile-stats'
Js 'document.querySelector("#stats-page .assistant-toggle").click();document.querySelector(".assistant .citation").open=true'|Out-Null
Shot 'mobile-assistant'
