param([string]$BaseUrl='http://127.0.0.1:5175')
$ErrorActionPreference='Stop'
$session='radar-mvp'
$dir=Join-Path (Get-Location) '.impeccable/review/compact-controls'
function Js([string]$code){$out=& agent-browser --session $session eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)));if($LASTEXITCODE -ne 0){throw $out};return $out}
function Shot([string]$name,[bool]$full=$false){if($full){$out=& agent-browser --session $session screenshot --full}else{$out=& agent-browser --session $session screenshot};$match=[regex]::Match(($out -join "\n"),'Screenshot saved to (.+)');if(!$match.Success){throw $out};Copy-Item -LiteralPath $match.Groups[1].Value.Trim() -Destination (Join-Path $dir ($name+'.png'));Write-Output $name}
& agent-browser --session $session set viewport 1680 1000|Out-Null
& agent-browser --session $session open ($BaseUrl+'/controls-preview.html')|Out-Null
Js '(()=>{const ok=active().draft===''保留这份草稿''&&active().messages.length===4;return {reload_preserves_conversation:ok}})()' | Set-Content (Join-Path $dir 'reload-results.json')
Shot 'desktop-conversation'
& agent-browser --session $session set viewport 390 844|Out-Null
Js 'showAssistant()'|Out-Null
Shot 'mobile-conversation'
Js '$(''#collapse-assistant'').click()'|Out-Null
& agent-browser --session $session set viewport 1680 1000|Out-Null
Js 'showAssistant()'|Out-Null
Js '$(''#new-chat'').click();historyOpen=true;syncHistory();scrollTo(0,0)'|Out-Null
Shot 'desktop' $true
Js 'openDate()'|Out-Null
Shot 'desktop-date'
Js 'closeDate()'|Out-Null
& agent-browser --session $session set viewport 390 844|Out-Null
Js 'scrollTo(0,0)'|Out-Null
Shot 'mobile' $true
Js 'openDate()'|Out-Null
Shot 'mobile-date'
Js '(()=>{const r=$(''#date-popover'').getBoundingClientRect();return {popover_in_view:r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight,page_no_horizontal_overflow:document.documentElement.scrollWidth<=innerWidth}})()' | Set-Content (Join-Path $dir 'mobile-results.json')
Js 'closeDate();showAssistant()'|Out-Null
Shot 'mobile-assistant'
Js 'historyOpen=true;syncHistory()'|Out-Null
Shot 'mobile-history'
Js 'historyOpen=false;syncHistory();$(''#collapse-assistant'').click()'|Out-Null
& agent-browser --session $session set viewport 1024 768|Out-Null
Js 'scrollTo(0,0);openDate()'|Out-Null
Shot 'tablet-date'
Js '(()=>{const r=$(''#date-popover'').getBoundingClientRect();return {popover_in_view:r.top>=0&&r.bottom<=innerHeight}})()' | Set-Content (Join-Path $dir 'tablet-results.json')
Js 'closeDate()'|Out-Null
& agent-browser --session $session set viewport 1680 1000|Out-Null
Js 'showAssistant();historyOpen=true;syncHistory();scrollTo(0,0)'|Out-Null
