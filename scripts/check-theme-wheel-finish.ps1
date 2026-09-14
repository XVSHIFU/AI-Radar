$ErrorActionPreference='Stop'
$session='radar-theme'
function Js([string]$code){$out=& agent-browser --session $session eval -b ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code)));if($LASTEXITCODE -ne 0){throw ($out -join "`n")};return $out}
& agent-browser --session $session open 'http://127.0.0.1:5175/?demo=1'|Out-Null
& agent-browser --session $session set viewport 1680 1000|Out-Null
Js '(async()=>{await new Promise(r=>setTimeout(r,250));document.querySelector("[data-testid=theme-toggle]").click();await new Promise(r=>setTimeout(r,250));window.dragBefore={count:document.querySelector(".theme-wheel-count").textContent,theme:document.documentElement.dataset.theme}})()'|Out-Null
& agent-browser --session $session mouse move 235 695|Out-Null
& agent-browser --session $session mouse down left|Out-Null
& agent-browser --session $session mouse move 285 750|Out-Null
& agent-browser --session $session mouse move 315 805|Out-Null
& agent-browser --session $session mouse up left|Out-Null
Js '({before:window.dragBefore,after:{count:document.querySelector(".theme-wheel-count").textContent,theme:document.documentElement.dataset.theme},dragMoves:window.dragBefore.count!==document.querySelector(".theme-wheel-count").textContent,noAccidentalSelection:window.dragBefore.theme===document.documentElement.dataset.theme})'|Set-Content docs/theme-wheel-drag-results.json
$code=@'
(async()=>{
const {themes,changeTheme,applyTheme,THEME_STORAGE_KEY,themeStorageFailed}=await import("/src/themes.ts");
const pause=ms=>new Promise(r=>setTimeout(r,ms));
let animation=null;const originalAnimate=document.documentElement.animate;
document.documentElement.animate=function(frames,options){animation={frames,options};return originalAnimate.call(this,frames,options)};
await changeTheme(themes[4],200,700);
document.documentElement.animate=originalAnimate;
const animated=animation?.options?.pseudoElement==="::view-transition-new(root)"&&animation?.options?.duration===650;
applyTheme(themes[0]);
const first=changeTheme(themes[2],180,700),second=changeTheme(themes[0],180,700);
await Promise.allSettled([first,second]);await pause(60);
const latestWins=document.documentElement.dataset.theme===themes[0].id;
const media=window.matchMedia;window.matchMedia=q=>q==="(prefers-reduced-motion: reduce)"?{matches:true}:media(q);
await changeTheme(themes[1],100,700);
window.matchMedia=media;
const reducedMotion=document.documentElement.dataset.theme===themes[1].id;
const setter=Storage.prototype.setItem;
Storage.prototype.setItem=function(){throw new Error("test storage unavailable")};
applyTheme(themes[5]);const storageFallback=themeStorageFailed.value&&document.documentElement.dataset.theme===themes[5].id;
Storage.prototype.setItem=setter;applyTheme(themes[1]);
window.dispatchEvent(new StorageEvent("storage",{key:THEME_STORAGE_KEY,newValue:themes[7].id}));
const tabSync=document.documentElement.dataset.theme===themes[7].id;applyTheme(themes[1]);
const panel=document.querySelector("#theme-wheel");
panel.focus();panel.dispatchEvent(new KeyboardEvent("keydown",{key:"Tab",shiftKey:true,bubbles:true,cancelable:true}));
const backwardsFocus=document.activeElement===document.querySelector(".theme-wheel-actions button:last-child");
return {animated,latestWins,reducedMotion,storageFallback,tabSync,backwardsFocus,animation};
})()
'@
Js $code|Set-Content docs/theme-wheel-edge-results.json
Js 'document.querySelector("#theme-wheel").dispatchEvent(new KeyboardEvent("keydown",{key:"Home",bubbles:true}))'|Out-Null
$original=[IO.File]::ReadAllText((Join-Path (Get-Location) 'scripts/check-theme-wheel.ps1'))
$final=$original.Replace("Shot 'desktop-wheel'","Shot 'final-desktop-wheel'").Replace("Shot 'desktop-paper-assistant'","Shot 'final-desktop-paper-assistant'").Replace("Shot 'mobile-wheel'","Shot 'final-mobile-wheel'")
Invoke-Expression $final
