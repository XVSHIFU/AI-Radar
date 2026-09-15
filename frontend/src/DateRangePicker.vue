<script setup lang="ts">
import { translate as tr } from "./locale";
import {computed,nextTick,onBeforeUnmount,onMounted,ref,useId} from "vue";
import {addDays,datePreset,shanghaiToday,validateRange,type DatePreset,type DateRange} from "./date-range";
const props=withDefaults(defineProps<{from:string;to:string;allowUnbounded?:boolean;maxDays?:number}>(),{allowUnbounded:false,maxDays:366});
const emit=defineEmits<{change:[DateRange]}>();
const id=useId(),open=ref(false),trigger=ref<HTMLButtonElement>(),panel=ref<HTMLElement>(),startInput=ref<HTMLInputElement>(),draftFrom=ref(""),draftTo=ref(""),month=ref(""),choosingEnd=ref(false),error=ref(""),position=ref({left:"12px",top:"100px"});
const presets:{value:DatePreset;label:string}[]=[{value:"today",label:"今天"},{value:"yesterday",label:"昨天"},{value:"week",label:"近7天"},{value:"month30",label:"近30天"},{value:"month",label:"本月"}];
const label=computed(()=>!props.from&&!props.to?"不限日期":(props.from||"不限")+" — "+(props.to||"不限"));
const monthLabel=computed(()=>month.value?month.value.slice(0,4)+"年 "+Number(month.value.slice(5,7))+"月":"");
const days=computed(()=>{if(!month.value)return [];const first=month.value+"-01",weekday=new Date(first+"T12:00:00Z").getUTCDay();return Array.from({length:42},(_,i)=>addDays(first,i-(weekday+6)%7))});
function place(){if(!trigger.value||!panel.value)return;const rect=trigger.value.getBoundingClientRect(),mobile=innerWidth<=900;position.value={left:mobile?"12px":Math.max(12,Math.min(rect.left,innerWidth-panel.value.offsetWidth-12))+"px",top:Math.max(12,Math.min(mobile?80:rect.bottom+8,innerHeight-panel.value.offsetHeight-12))+"px"}}
async function show(){draftFrom.value=props.from||shanghaiToday();draftTo.value=props.to||shanghaiToday();month.value=draftTo.value.slice(0,7);choosingEnd.value=false;error.value="";open.value=true;await nextTick();place();startInput.value?.focus()}
function close(returnFocus=true){open.value=false;if(returnFocus)trigger.value?.focus()}
function choosePreset(mode:DatePreset){const r=datePreset(mode);draftFrom.value=r.from;draftTo.value=r.to;month.value=r.to.slice(0,7);choosingEnd.value=false;error.value=""}
function moveMonth(delta:number){const d=new Date(month.value+"-01T12:00:00Z");d.setUTCMonth(d.getUTCMonth()+delta);month.value=d.toISOString().slice(0,7)}
async function chooseDay(day:string){if(!choosingEnd.value){draftFrom.value=day;draftTo.value=day;choosingEnd.value=true}else{const start=draftFrom.value;draftFrom.value=day<start?day:start;draftTo.value=day<start?start:day;choosingEnd.value=false}error.value="";await nextTick();panel.value?.querySelector<HTMLButtonElement>('[data-day="'+day+'"]')?.focus()}
function apply(){const range={from:draftFrom.value,to:draftTo.value};error.value=validateRange(range,props.allowUnbounded,props.maxDays);if(error.value)return;emit("change",range);close()}
function clear(){emit("change",{from:"",to:""});close()}
function outside(e:PointerEvent){if(open.value&&!panel.value?.contains(e.target as Node)&&!trigger.value?.contains(e.target as Node))close(false)}
function onKey(e:KeyboardEvent){if(!open.value)return;if(e.key==="Escape"){e.preventDefault();e.stopImmediatePropagation();close()}}
onMounted(()=>{document.addEventListener("pointerdown",outside);document.addEventListener("keydown",onKey,true);window.addEventListener("resize",place)});
onBeforeUnmount(()=>{document.removeEventListener("pointerdown",outside);document.removeEventListener("keydown",onKey,true);window.removeEventListener("resize",place)});
</script>
<template>
 <div class="range-picker">
  <button ref="trigger" type="button" class="range-trigger" data-testid="date-range-trigger" :aria-expanded="open" :aria-controls="id" @click="open?close():show()"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18"/></svg><span>{{label}}</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 10 5 5 5-5"/></svg></button>
  <Teleport to="body"><section v-if="open" :id="id" ref="panel" class="range-popover" data-testid="date-range-popover" :style="position" aria-label="选择日期范围">
   <div class="range-fields"><label>{{ tr("开始日期", "Start date") }}<input ref="startInput" v-model="draftFrom" type="text" inputmode="numeric" placeholder="YYYY-MM-DD" maxlength="10" autocomplete="off" name="date_from" @focus="choosingEnd=false" @change="error=''" /></label><span>至</span><label>{{ tr("结束日期", "End date") }}<input v-model="draftTo" type="text" inputmode="numeric" placeholder="YYYY-MM-DD" maxlength="10" autocomplete="off" name="date_to" @focus="choosingEnd=true" @change="error=''" /></label></div>
   <div class="range-body"><div class="range-presets"><button v-for="p in presets" :key="p.value" :data-preset="p.value" :aria-pressed="datePreset(p.value).from===draftFrom&&datePreset(p.value).to===draftTo" @click="choosePreset(p.value)">{{p.label}}</button></div>
   <div class="range-calendar"><div class="range-calendar-heading"><button class="icon-button" aria-label="上个月" @click="moveMonth(-1)"><svg viewBox="0 0 24 24"><path d="m14 6-6 6 6 6"/></svg></button><strong>{{monthLabel}}</strong><button class="icon-button" aria-label="下个月" @click="moveMonth(1)"><svg viewBox="0 0 24 24"><path d="m10 6 6 6-6 6"/></svg></button></div>
   <div class="range-weekdays"><span v-for="d in ['一','二','三','四','五','六','日']" :key="d">{{d}}</span></div>
   <div class="range-days"><button v-for="day in days" :key="day" :data-day="day" :aria-label="day" :aria-pressed="day===draftFrom||day===draftTo" :class="{outside:!day.startsWith(month),between:day>=draftFrom&&day<=draftTo,endpoint:day===draftFrom||day===draftTo}" @click="chooseDay(day)">{{Number(day.slice(-2))}}</button></div></div></div>
   <div class="range-footer"><span>{{choosingEnd?'请选择结束日期':'先选开始日期，再选结束日期'}}</span><button v-if="allowUnbounded" class="quiet-button" @click="clear">{{ tr("不限日期", "Any date") }}</button><button class="quiet-button" @click="close()">{{ tr("取消", "Cancel") }}</button><button class="primary" data-testid="apply-date-range" @click="apply">{{ tr("应用", "Apply") }}</button></div><p v-if="error" class="error" role="alert">{{error}}</p>
  </section></Teleport>
 </div>
</template>
