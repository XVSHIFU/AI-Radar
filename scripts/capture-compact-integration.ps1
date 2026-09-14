param([string]$BaseUrl='http://127.0.0.1:5175')
$ErrorActionPreference='Stop';$session='radar-mvp';$dir=Join-Path (Get-Location) '.impeccable/review/compact-integration'
New-Item -ItemType Directory -Force $dir|Out-Null
function Js([string]$code){$out=& agent-browser --session $session eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)));if($LASTEXITCODE -ne 0){throw $out}}
function Open([string]$route){& agent-browser --session $session open ($BaseUrl+$route)|Out-Null;Js '(async()=>{for(let i=0;i<100;i++){if(document.querySelector("h1"))break;await new Promise(r=>setTimeout(r,30))}await new Promise(r=>setTimeout(r,450));scrollTo(0,0)})()'|Out-Null}
function Shot([string]$name,[bool]$full=$false){if($full){$out=& agent-browser --session $session screenshot --full}else{$out=& agent-browser --session $session screenshot};$m=[regex]::Match(($out -join "\n"),'Screenshot saved to (.+)');if(!$m.Success){throw $out};Copy-Item -LiteralPath $m.Groups[1].Value.Trim() -Destination (Join-Path $dir ($name+'.png'));Write-Output $name}
& agent-browser --session $session set viewport 1680 1000|Out-Null
Open '/?demo=1'
Shot 'desktop-home' $true
& agent-browser --session $session click '[data-testid=date-range-trigger]'|Out-Null
Shot 'desktop-date'
& agent-browser --session $session press Escape|Out-Null
Open '/ask?demo=1'
Js '([...document.querySelectorAll("button")].find(b=>b.textContent.trim()==="近30天")).click()'|Out-Null
Js '(async()=>{await new Promise(r=>setTimeout(r,500))})()'|Out-Null
Shot 'desktop-heat' $true
& agent-browser --session $session click '[data-testid=assistant-toggle]'|Out-Null
& agent-browser --session $session click '[data-testid=history-toggle]'|Out-Null
Js 'document.querySelectorAll("[data-testid=history-item]").forEach(b=>{if(b.textContent==="B 集成验证会话")b.click()})'|Out-Null
Js '(async()=>{await new Promise(r=>setTimeout(r,150))})()'|Out-Null
Shot 'desktop-assistant'
Js 'document.querySelector(".ask-events h3 a").click()'|Out-Null
Js '(async()=>{await new Promise(r=>setTimeout(r,200))})()'|Out-Null
Shot 'desktop-reader'
Open '/ingest?demo=1'
Shot 'desktop-ingest' $true
& agent-browser --session $session set viewport 390 844|Out-Null
Open '/?demo=1'
Shot 'mobile-home' $true
Open '/ask?demo=1'
Js '([...document.querySelectorAll("button")].find(b=>b.textContent.trim()==="近30天")).click()'|Out-Null
Js '(async()=>{await new Promise(r=>setTimeout(r,500))})()'|Out-Null
Shot 'mobile-heat' $true
& agent-browser --session $session click '[data-testid=date-range-trigger]'|Out-Null
Shot 'mobile-date'
& agent-browser --session $session press Escape|Out-Null
& agent-browser --session $session click '[data-testid=assistant-toggle]'|Out-Null
Shot 'mobile-assistant'
& agent-browser --session $session click '[data-testid=history-toggle]'|Out-Null
Shot 'mobile-history'
& agent-browser --session $session set viewport 1680 1000|Out-Null
