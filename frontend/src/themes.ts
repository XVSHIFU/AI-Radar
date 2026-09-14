import { ref } from "vue";
export interface Theme {id:string;name:string;note:string;colors:Record<string,string>}
export function mix(a:string,b:string,w:number){
const parts=(s:string)=>[1,3,5].map(i=>parseInt(s.slice(i,i+2),16));
return "#"+parts(a).map((v,i)=>Math.round(v*(1-w)+parts(b)[i]!*w).toString(16).padStart(2,"0")).join("");
}
export const themes:Theme[]=[
  {
    "id": "mist",
    "name": "雾白钴蓝",
    "note": "清晰 · 安静",
    "colors": {
      "bg": "#f4f5f7",
      "rail": "#eceff3",
      "paper": "#ffffff",
      "ink": "#202c3c",
      "muted": "#5f6d7d",
      "blue": "#315e9e",
      "on-accent": "#ffffff",
      "blue-soft": "#e7edf7",
      "line": "#d1d9e3",
      "focus": "#7893b0",
      "pill-ink": "#316b70",
      "aqua": "#e5f1f0",
      "success": "#267064",
      "success-bg": "#edf6f2",
      "warning": "#86601c",
      "warning-bg": "#fcf7e9",
      "warning-line": "#e7d8ac"
    }
  },
  {
    "id": "paper",
    "name": "暖纸松绿",
    "note": "温暖 · 耐看",
    "colors": {
      "bg": "#f5f2e9",
      "rail": "#eae9de",
      "paper": "#fffdf7",
      "ink": "#29382f",
      "muted": "#626859",
      "blue": "#356752",
      "on-accent": "#ffffff",
      "blue-soft": "#e4ece0",
      "line": "#d4d9c9",
      "focus": "#7e9b7c",
      "pill-ink": "#586629",
      "aqua": "#edf0d9",
      "success": "#356752",
      "success-bg": "#e8efe1",
      "warning": "#875d24",
      "warning-bg": "#faf0de",
      "warning-line": "#e2d1ac"
    }
  },
  {
    "id": "lilac",
    "name": "雾紫墨蓝",
    "note": "柔和 · 雅致",
    "colors": {
      "bg": "#f1eef7",
      "rail": "#e9e5f1",
      "paper": "#fefcff",
      "ink": "#322d43",
      "muted": "#6a6079",
      "blue": "#68518f",
      "on-accent": "#ffffff",
      "blue-soft": "#eae2f4",
      "line": "#d9cfe4",
      "focus": "#9b86b3",
      "pill-ink": "#536782",
      "aqua": "#e8edf6",
      "success": "#357266",
      "success-bg": "#e9f3ef",
      "warning": "#866126",
      "warning-bg": "#fbf4e5",
      "warning-line": "#e8d8b3"
    }
  },
  {
    "id": "oat",
    "name": "燕麦陶红",
    "note": "温润 · 质朴",
    "colors": {
      "bg": "#f6f0e9",
      "rail": "#eee4d9",
      "paper": "#fffaf4",
      "ink": "#403128",
      "muted": "#745f51",
      "blue": "#985239",
      "on-accent": "#ffffff",
      "blue-soft": "#f1e0d4",
      "line": "#e2cfc0",
      "focus": "#aa8066",
      "pill-ink": "#6d643c",
      "aqua": "#eeead7",
      "success": "#486c52",
      "success-bg": "#eaf0e2",
      "warning": "#855b22",
      "warning-bg": "#fbefd9",
      "warning-line": "#e4cfa5"
    }
  },
  {
    "id": "glacier",
    "name": "冰川青",
    "note": "清爽 · 明净",
    "colors": {
      "bg": "#edf5f4",
      "rail": "#e1eeec",
      "paper": "#fbfefd",
      "ink": "#253b3d",
      "muted": "#506b6b",
      "blue": "#17696d",
      "on-accent": "#ffffff",
      "blue-soft": "#dbefeb",
      "line": "#c6ded9",
      "focus": "#688f8c",
      "pill-ink": "#386977",
      "aqua": "#e0f0f2",
      "success": "#2c7058",
      "success-bg": "#e6f2eb",
      "warning": "#835f24",
      "warning-bg": "#faf4e4",
      "warning-line": "#e3d6b2"
    }
  }
];
const additions=[
["slate","雨后灰蓝","沉静 · 理性","#4b607c","#f0f3f7"],
["olive","浅苔橄榄","自然 · 舒缓","#59652c","#f4f4e9"],
["rose","玫瑰豆沙","细腻 · 温柔","#92546a","#faf0f2"],
["apricot","杏纸琥珀","明朗 · 温暖","#925f23","#faf4e8"],
["plum","梅子暮紫","含蓄 · 深邃","#77516f","#f5eff5"],
["sea","海盐湖蓝","轻快 · 通透","#286a89","#eef6f9"],
["jade","玉石竹青","清润 · 平和","#356b5b","#eff6ef"],
["coffee","奶油可可","醇和 · 朴实","#765a45","#f7f3ec"],
["iris","鸢尾靛蓝","知性 · 清朗","#505d96","#f0f2fa"],
["coral","珊瑚浅沙","柔暖 · 活泼","#9a544d","#fcf2ed"],
["graphite","月白石墨","克制 · 专注","#4b5965","#f3f4f5"],
] as const;
for(const [id,name,note,blue,bg] of additions)themes.push({id,name,note,colors:{
bg,blue,rail:mix(bg,blue,.065),paper:mix("#ffffff",bg,.25),ink:mix("#202a31",blue,.17),
muted:mix("#59626a",blue,.10),"blue-soft":mix(bg,blue,.095),line:mix(bg,blue,.23),focus:mix(blue,"#ffffff",.18),
"pill-ink":blue,aqua:mix(bg,blue,.07)}});
for(const theme of themes){
const c=theme.colors;
Object.assign(c,{"composer-focus":c.focus,selection:c["blue-soft"],"hover-line":c.focus,
"primary-hover":mix(c.blue!,"#000000",.14),"quote-bg":mix(c.paper!,c.blue!,.045),"quote-line":c.line,
"plan-bg":c["blue-soft"],"plan-line":c.line,"disabled-bg":c.rail,"disabled-ink":c.muted,
"assistant-answer-ink":c.ink,"conversation-user":c.blue,"conversation-assistant":"#267064",
"conversation-demo":"#86601c","conversation-complete-bg":"#edf6f2","conversation-partial-bg":"#faf2e3",
"demo-bg":"#fcf7e9","demo-ink":"#76521a","demo-line":"#e7d8ac","danger":"#a5342b","danger-bg":"#fff0ef",
"error-line":"#e8b5ae","status-bg":c["blue-soft"]});
}
export const THEME_STORAGE_KEY="ai-radar-theme";
export const activeTheme=ref(themes[0]!);
export const themeStorageFailed=ref(false);
export function resolveTheme(id:string|null){return themes.find(t=>t.id===id)||themes[0]!}
export function applyTheme(theme:Theme,persist=true){
activeTheme.value=theme;
for(const [name,color] of Object.entries(theme.colors))document.documentElement.style.setProperty("--"+name,color);
document.documentElement.dataset.theme=theme.id;
if(persist)try{localStorage.setItem(THEME_STORAGE_KEY,theme.id);themeStorageFailed.value=false}catch{themeStorageFailed.value=true}
}
export function initTheme(){
let id:string|null=null;
try{id=localStorage.getItem(THEME_STORAGE_KEY)}catch{themeStorageFailed.value=true}
applyTheme(resolveTheme(id),false);
window.addEventListener("storage",e=>{if(e.key===THEME_STORAGE_KEY)applyTheme(resolveTheme(e.newValue),false)});
}
type Transition={ready:Promise<void>;finished:Promise<void>;skipTransition:()=>void};
let transition:Transition|undefined,revision=0;
export async function changeTheme(theme:Theme,x:number,y:number){
const own=++revision;transition?.skipTransition();
if(theme.id===activeTheme.value.id){applyTheme(theme);return;}
const start=(document as Document&{startViewTransition?:(callback:()=>void)=>Transition}).startViewTransition;
if(!start||matchMedia("(prefers-reduced-motion: reduce)").matches){applyTheme(theme);return}
try{
const current=start.call(document,()=>{if(own===revision)applyTheme(theme)});transition=current;
await current.ready;if(own!==revision)return;
const radius=Math.hypot(Math.max(x,innerWidth-x),Math.max(y,innerHeight-y));
await document.documentElement.animate({clipPath:[`circle(0px at ${x}px ${y}px)`,`circle(${radius}px at ${x}px ${y}px)`]},
{duration:650,easing:"cubic-bezier(.16,1,.3,1)",pseudoElement:"::view-transition-new(root)",fill:"both"}).finished;
await current.finished;
}catch{if(own===revision)applyTheme(theme)}
finally{if(own===revision)transition=undefined}
}
