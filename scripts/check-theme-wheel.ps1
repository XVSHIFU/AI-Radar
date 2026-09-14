$ErrorActionPreference='Stop'
$session='radar-theme'
$dir=Join-Path (Get-Location) '.impeccable/review/theme-wheel'
New-Item -ItemType Directory -Force $dir|Out-Null
function Js([string]$code){$out=& agent-browser --session $session eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)));if($LASTEXITCODE -ne 0){throw ($out -join "`n")};return $out}
function Shot([string]$name){$out=& agent-browser --session $session screenshot;$m=[regex]::Match(($out -join "`n"),'Screenshot saved to (.+)');if(!$m.Success){throw $out};Copy-Item -LiteralPath $m.Groups[1].Value.Trim() -Destination (Join-Path $dir ($name+'.png'))}
Shot 'desktop-wheel'
$code=@'
(async()=>{
const {themes}=await import("/src/themes.ts");
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const lum=hex=>{const c=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return c[0]*.2126+c[1]*.7152+c[2]*.0722};
const ratio=(a,b)=>{const x=lum(a),y=lum(b);return(Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
const low=[];for(const t of themes){for(const bg of ["bg","paper","rail"])for(const fg of ["ink","muted","blue"]){const r=ratio(t.colors[fg],t.colors[bg]);if(r<4.5)low.push({theme:t.id,fg,bg,ratio:r})}}
const key=k=>document.querySelector("#theme-wheel").dispatchEvent(new KeyboardEvent("keydown",{key:k,bubbles:true,cancelable:true}));
key("Home");await pause(40);
const before=document.querySelector(".theme-wheel-count").textContent;
document.querySelector("#theme-wheel").dispatchEvent(new WheelEvent("wheel",{deltaY:80,bubbles:true,cancelable:true}));await pause(40);
const wheelMoved=before!==document.querySelector(".theme-wheel-count").textContent;
const applied=[];key("Home");
for(let i=0;i<themes.length;i++){
await pause(20);key("Enter");await pause(760);
applied.push({id:themes[i].id,applied:document.documentElement.dataset.theme===themes[i].id,stored:localStorage.getItem("ai-radar-theme")===themes[i].id});
key("ArrowRight");
}
key("Home");key("ArrowRight");key("Enter");await pause(760);
key("Escape");await pause(220);
const dismissed=!document.querySelector("#theme-wheel")&&!document.querySelector("#app").inert&&document.activeElement?.matches("[data-testid=theme-toggle]");
return {lowContrast:low,wheelMoved,applied,dismissed,overflow:document.documentElement.scrollWidth>innerWidth};
})()
'@
Js $code|Set-Content docs/theme-wheel-browser-results.json
& agent-browser --session $session open 'http://127.0.0.1:5175/ask?demo=1'|Out-Null
Js '(async()=>{await new Promise(r=>setTimeout(r,350));document.querySelector("[data-testid=assistant-toggle]")?.click();await new Promise(r=>setTimeout(r,200))})()'|Out-Null
Shot 'desktop-paper-assistant'
& agent-browser --session $session set viewport 390 844|Out-Null
& agent-browser --session $session open 'http://127.0.0.1:5175/?demo=1'|Out-Null
Js '(async()=>{await new Promise(r=>setTimeout(r,300));document.querySelector("[data-testid=theme-toggle]").click();await new Promise(r=>setTimeout(r,250))})()'|Out-Null
Shot 'mobile-wheel'
Js '(()=>{const p=document.querySelector("#theme-wheel"),r=p.getBoundingClientRect();return{savedTheme:document.documentElement.dataset.theme,inViewport:r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight,overflow:document.documentElement.scrollWidth>innerWidth}})()'|Set-Content docs/theme-wheel-mobile-results.json
