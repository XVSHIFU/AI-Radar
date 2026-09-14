param([string]$BaseUrl='http://127.0.0.1:5175')
$ErrorActionPreference='Stop';$session='radar-mvp';$dir=Join-Path (Get-Location) '.impeccable/review/conversation-colors'
New-Item -ItemType Directory -Force $dir|Out-Null
function Js([string]$code){$out=& agent-browser --session $session eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)));if($LASTEXITCODE -ne 0){throw $out}}
function Open([string]$route){& agent-browser --session $session open ($BaseUrl+$route)|Out-Null;Js '(async()=>{for(let i=0;i<100;i++){if(document.querySelector("h1"))break;await new Promise(r=>setTimeout(r,30))}await new Promise(r=>setTimeout(r,450));scrollTo(0,0)})()'|Out-Null}
function Shot([string]$name,[bool]$full=$false){if($full){$out=& agent-browser --session $session screenshot --full}else{$out=& agent-browser --session $session screenshot};$m=[regex]::Match(($out -join "\n"),'Screenshot saved to (.+)');if(!$m.Success){throw $out};Copy-Item -LiteralPath $m.Groups[1].Value.Trim() -Destination (Join-Path $dir ($name+'.png'));Write-Output $name}
& agent-browser --session $session set viewport 1680 1000|Out-Null
Open '/?demo=1'

Js 'localStorage.setItem("assistant-width","520")'|Out-Null
Open '/ask?demo=1'
& agent-browser --session $session click '[data-testid=assistant-toggle]'|Out-Null
& agent-browser --session $session focus '#assistant-question'|Out-Null
Shot 'desktop'
$code=@'
(()=>{
const ratio=(a,b)=>{const lum=c=>{const v=c.match(/[\d.]+/g).slice(0,3).map(Number).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4});return .2126*v[0]+.7152*v[1]+.0722*v[2]};const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
const colors=[[".turn-role[data-role=user]","rgb(255,255,255)"],[".turn-role[data-role=assistant]","rgb(255,255,255)"],[".turn-mode[data-mode=demo]","rgb(255,255,255)"],[".turn-coverage[data-coverage=complete]",null]].map(([selector,bg])=>{const e=document.querySelector(selector);if(!e)return {selector,missing:true};const s=getComputedStyle(e);return {selector,color:s.color,background:bg||s.backgroundColor,contrast:ratio(s.color,bg||s.backgroundColor)}});
const ta=document.querySelector("#assistant-question"),s=getComputedStyle(ta);
return {colors,focus:{width:s.outlineWidth,color:s.outlineColor,contrast:ratio(s.outlineColor,"rgb(255,255,255)")},overflow:document.documentElement.scrollWidth>innerWidth};
})()
'@
& agent-browser --session $session eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)))|Set-Content docs/conversation-colors-verification.json
& agent-browser --session $session set viewport 390 844|Out-Null
Open '/ask?demo=1'
& agent-browser --session $session click '[data-testid=assistant-toggle]'|Out-Null
& agent-browser --session $session focus '#assistant-question'|Out-Null
Shot 'mobile'
