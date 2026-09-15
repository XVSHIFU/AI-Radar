<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from "vue";
import { activeTheme, changeTheme, themes, themeStorageFailed } from "./themes";
import { locale, setLocale, t, translate as tr } from "./locale";
const open=ref(false),closing=ref(false),trigger=ref<HTMLButtonElement>(),panel=ref<HTMLElement>();
const step=360/themes.length,rotation=ref(-45),dragging=ref(false);
let pointer:number|null=null,startX=0,startY=0,lastAngle=0,moved=false,wheelDelta=0,hadInert=false;
const normalized=(a:number)=>((a+180)%360+360)%360-180;
const items=computed(()=>themes.map((theme,index)=>{
const angle=normalized(index*step+rotation.value),r=angle*Math.PI/180;
return {theme,index,visible:angle>=-86&&angle<=-4,style:{left:Math.cos(r)*81+"%",top:100+Math.sin(r)*81+"%","--swatch":theme.colors.blue,"--swatch-paper":theme.colors.bg}};
}));
const themeNames:Record<string,[string,string]>={mist:["雾白钴蓝","Mist cobalt"],paper:["暖纸松绿","Warm paper pine"],lilac:["雾紫墨蓝","Lilac ink"],oat:["燕麦陶红","Oat terracotta"],glacier:["冰川青","Glacier teal"]};
const themeNotes:Record<string,[string,string]>={mist:["清晰 · 安静","Clear · quiet"],paper:["温暖 · 耐看","Warm · enduring"],lilac:["柔和 · 雅致","Soft · elegant"],oat:["温润 · 质朴","Gentle · grounded"],glacier:["清爽 · 明净","Fresh · clean"]};

Object.assign(themeNames, {"slate":["雨后灰蓝","Rain slate"],"olive":["浅苔橄榄","Moss olive"],"rose":["玫瑰豆沙","Dusty rose"],"apricot":["杏纸琥珀","Apricot amber"],"plum":["梅子暮紫","Evening plum"],"sea":["海盐湖蓝","Sea salt blue"],"jade":["玉石竹青","Bamboo jade"],"coffee":["奶油可可","Cream cocoa"],"iris":["鸢尾靛蓝","Iris indigo"],"coral":["珊瑚浅沙","Coral sand"],"graphite":["月白石墨","Moonlit graphite"]});
Object.assign(themeNotes, {"slate":["沉静 · 理性","Calm · considered"],"olive":["自然 · 舒缓","Natural · soothing"],"rose":["细腻 · 温柔","Delicate · gentle"],"apricot":["明朗 · 温暖","Bright · warm"],"plum":["含蓄 · 深邃","Subtle · deep"],"sea":["轻快 · 通透","Light · clear"],"jade":["清润 · 平和","Fresh · peaceful"],"coffee":["醇和 · 朴实","Mellow · grounded"],"iris":["知性 · 清朗","Thoughtful · crisp"],"coral":["柔暖 · 活泼","Soft · lively"],"graphite":["克制 · 专注","Restrained · focused"]});
const themeName=(theme:{id:string;name:string})=>{const value=themeNames[theme.id];return value?tr(value[0],value[1]):theme.name};
const themeNote=(theme:{id:string;note:string})=>{const value=themeNotes[theme.id];return value?tr(value[0],value[1]):theme.note};
const centerIndex=computed(()=>((Math.round((-45-rotation.value)/step)%themes.length)+themes.length)%themes.length);
const browsed=computed(()=>themes[centerIndex.value]!);
let closeAnimation:Animation|undefined,disposed=false;
function release(){pointer=null;dragging.value=false}
async function show(){
if(closing.value)return;
rotation.value=-45-themes.findIndex(t=>t.id===activeTheme.value.id)*step;
open.value=true;hadInert=document.querySelector("#app")?.hasAttribute("inert")||false;window.addEventListener("wheel",captureWheel,{capture:true,passive:false});
document.querySelector("#app")?.setAttribute("inert","");window.addEventListener("keydown",key,true);
await nextTick();panel.value?.focus();
}
async function close(){
if(closing.value||!open.value)return;
closing.value=true;release();
const element=panel.value;
if(element){
const reduced=matchMedia("(prefers-reduced-motion: reduce)").matches;
const current=getComputedStyle(element);
try{
closeAnimation=element.animate([
{opacity:current.opacity,transform:current.transform,transformOrigin:"bottom left"},
{opacity:0,transform:reduced?current.transform:"translate(-10px, 10px) scale(.86)",transformOrigin:"bottom left"}
],{duration:reduced?80:160,easing:"cubic-bezier(.4,0,1,1)",fill:"forwards"});
await closeAnimation.finished;
}catch{/* An interrupted exit still releases the modal state. */}
}
if(disposed)return;
open.value=false;closing.value=false;closeAnimation=undefined;
if(!hadInert)document.querySelector("#app")?.removeAttribute("inert");
window.removeEventListener("keydown",key,true);window.removeEventListener("wheel",captureWheel,true);void nextTick(()=>trigger.value?.focus());
}
function rotate(direction:number){rotation.value-=direction*step}
function onWheel(e:WheelEvent){e.preventDefault();wheelDelta+=e.deltaY||e.deltaX;if(Math.abs(wheelDelta)>=35){rotate(Math.sign(wheelDelta));wheelDelta=0}}
function captureWheel(e:WheelEvent){const rect=panel.value?.getBoundingClientRect();if(!rect||e.clientX<rect.left||e.clientX>rect.right||e.clientY<rect.top||e.clientY>rect.bottom)return;e.preventDefault();e.stopPropagation();if(!closing.value)onWheel(e)}
function angleAt(e:PointerEvent){const r=panel.value!.getBoundingClientRect();return Math.atan2(e.clientY-r.bottom,e.clientX-r.left)*180/Math.PI}
function down(e:PointerEvent){if(e.button!==0||(e.target as HTMLElement).closest(".theme-wheel-controls"))return;pointer=e.pointerId;startX=e.clientX;startY=e.clientY;lastAngle=angleAt(e);moved=false}
function move(e:PointerEvent){
if(pointer!==e.pointerId)return;
if(!moved&&Math.hypot(e.clientX-startX,e.clientY-startY)<6)return;
if(!moved){moved=true;dragging.value=true;panel.value?.setPointerCapture(e.pointerId)}
e.preventDefault();const angle=angleAt(e);rotation.value+=normalized(angle-lastAngle);lastAngle=angle;
}
function up(e:PointerEvent){if(pointer!==e.pointerId)return;const dragged=moved;release();if(dragged){rotation.value=-45-Math.round((-45-rotation.value)/step)*step;setTimeout(()=>{moved=false},0)}}
function select(index:number,e?:MouseEvent){
if(moved)return;
const b=(e?.currentTarget as HTMLElement|undefined)?.getBoundingClientRect()||panel.value!.getBoundingClientRect();
void changeTheme(themes[index]!,b.left+b.width/2,b.top+b.height/2);
}
function key(e:KeyboardEvent){
if(!open.value)return;
if(closing.value){e.preventDefault();e.stopImmediatePropagation();return;}
if(e.key==="Escape"){e.preventDefault();e.stopImmediatePropagation();close();return}
if(["ArrowRight","ArrowDown","ArrowLeft","ArrowUp","Home","End"].includes(e.key)){
e.preventDefault();e.stopImmediatePropagation();
if(e.key==="Home")rotation.value=-45;
else if(e.key==="End")rotation.value=-45-(themes.length-1)*step;
else rotate(["ArrowRight","ArrowDown"].includes(e.key)?1:-1);
panel.value?.focus();return;
}
if(e.key==="Enter"&&e.target===panel.value){e.preventDefault();select(centerIndex.value)}
if(e.key==="Tab"){
const list=[...panel.value!.querySelectorAll<HTMLButtonElement>("button")].filter(b=>!b.hidden&&b.getClientRects().length);
const index=list.indexOf(document.activeElement as HTMLButtonElement);
e.preventDefault();list[index<0?(e.shiftKey?list.length-1:0):(index+(e.shiftKey?-1:1)+list.length)%list.length]?.focus();
}
}
onBeforeUnmount(()=>{disposed=true;closeAnimation?.cancel();if(open.value){if(!hadInert)document.querySelector("#app")?.removeAttribute("inert");window.removeEventListener("keydown",key,true);window.removeEventListener("wheel",captureWheel,true)}release()});
</script>
<template>
<button ref="trigger" class="theme-trigger" data-testid="theme-toggle" :aria-expanded="open" aria-haspopup="dialog" aria-controls="theme-wheel" @click="show">
<span class="theme-trigger-dot" aria-hidden="true"></span><span>{{ t("theme") }}<span class="theme-trigger-name">{{themeName(activeTheme)}}</span></span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 5 7 7-7 7"/></svg>
</button>
<Teleport to="body">
<div v-if="open" class="theme-wheel-dismiss" aria-hidden="true" @pointerdown.prevent="close" @wheel.prevent></div>
<section v-if="open" id="theme-wheel" ref="panel" :inert="closing" class="theme-wheel" :class="{'is-dragging':dragging}" role="dialog" aria-modal="true" :aria-label="tr('主题轮盘', 'Theme wheel')" aria-describedby="theme-wheel-help" tabindex="-1" @pointerdown="down" @pointermove="move" @pointerup="up" @pointercancel="release" @click.capture="e=>{if(moved){e.preventDefault();e.stopPropagation()}}">
<svg class="theme-wheel-track" viewBox="0 0 380 380" aria-hidden="true"><path d="M0 72 A308 308 0 0 1 308 380"/><path d="M0 130 A250 250 0 0 1 250 380"/></svg>
<button v-for="item in items" :key="item.theme.id" :hidden="!item.visible" class="theme-swatch" :style="item.style" :data-theme-id="item.theme.id" :aria-label="themeName(item.theme)+'，'+themeNote(item.theme)" :aria-pressed="item.theme.id===activeTheme.id" @click="select(item.index,$event)">
<span class="theme-swatch-chip"><svg v-if="item.theme.id===activeTheme.id" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 12 4 4 8-8"/></svg></span><span class="theme-swatch-name">{{themeName(item.theme)}}</span>
</button>
<div class="theme-wheel-controls">
<p class="theme-wheel-count">{{ t("themeCount", { current: centerIndex + 1, total: themes.length }) }}</p><strong aria-live="polite">{{themeName(browsed)}}</strong><p class="theme-wheel-note">{{themeNote(browsed)}}</p>
<p id="theme-wheel-help">{{ t("themeHelp") }}</p>
<div class="locale-switch theme-wheel-locale" :aria-label="tr('语言', 'Language')"><button type="button" :aria-pressed="locale === 'zh'" @click="setLocale('zh')">{{ t("localeZh") }}</button><button type="button" :aria-pressed="locale === 'en'" @click="setLocale('en')">{{ t("localeEn") }}</button></div><div class="theme-wheel-actions"><button @click="close">{{ t("close") }}</button></div>
<p class="theme-wheel-status" role="status">{{themeStorageFailed?tr('已应用，本次未能保存偏好','Applied, but this preference could not be saved.'):tr('已应用 · {name}', 'Applied · {name}', { name: themeName(activeTheme) })}}</p>
</div>
</section>
</Teleport>
</template>
