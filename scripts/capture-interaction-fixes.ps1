param([string]$BaseUrl='http://127.0.0.1:5175')
$ErrorActionPreference='Stop';$session='radar-mvp';$dir=Join-Path (Get-Location) '.impeccable/review/interaction-fixes'
New-Item -ItemType Directory -Force $dir|Out-Null
function Js([string]$code){$out=& agent-browser --session $session eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)));if($LASTEXITCODE -ne 0){throw $out}}
function Open([string]$route){& agent-browser --session $session open ($BaseUrl+$route)|Out-Null;Js '(async()=>{for(let i=0;i<100;i++){if(document.querySelector("h1"))break;await new Promise(r=>setTimeout(r,30))}await new Promise(r=>setTimeout(r,450));scrollTo(0,0)})()'|Out-Null}
function Shot([string]$name,[bool]$full=$false){if($full){$out=& agent-browser --session $session screenshot --full}else{$out=& agent-browser --session $session screenshot};$m=[regex]::Match(($out -join "\n"),'Screenshot saved to (.+)');if(!$m.Success){throw $out};Copy-Item -LiteralPath $m.Groups[1].Value.Trim() -Destination (Join-Path $dir ($name+'.png'));Write-Output $name}
& agent-browser --session $session set viewport 1680 1000|Out-Null
Open '/?demo=1'

Open '/?demo=1'
& agent-browser --session $session click '[data-testid=date-range-trigger]'|Out-Null
Shot 'desktop-calendar'
& agent-browser --session $session press Escape|Out-Null
& agent-browser --session $session click '[data-testid=assistant-toggle]'|Out-Null
& agent-browser --session $session click '[data-testid=new-conversation]'|Out-Null
Shot 'desktop-empty'
& agent-browser --session $session fill '#assistant-question' '请整理 **模型发布** 的主要变化。'|Out-Null
& agent-browser --session $session press Enter|Out-Null
Js '(async()=>{await new Promise(r=>setTimeout(r,850))})()'|Out-Null
& agent-browser --session $session fill '#assistant-question' '## 继续核查
- 有哪些来源？
- 哪些结论有证据？'|Out-Null
& agent-browser --session $session press Enter|Out-Null
Js '(async()=>{await new Promise(r=>setTimeout(r,850))})()'|Out-Null
Shot 'desktop-thread'
Js 'document.querySelector(".assistant-scope-menu").open=true'|Out-Null
Shot 'desktop-scope'
Js 'document.querySelector(".assistant-scope-menu").open=false;document.querySelector(".timeline-event__title a").click()'|Out-Null
Js '(async()=>{await new Promise(r=>setTimeout(r,250))})()'|Out-Null
Shot 'desktop-reader'
& agent-browser --session $session set viewport 390 844|Out-Null
Open '/?demo=1'
& agent-browser --session $session click '[data-testid=assistant-toggle]'|Out-Null
Js '(async()=>{await new Promise(r=>setTimeout(r,250))})()'|Out-Null
Shot 'mobile-thread'
