'use strict';
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const cats=['模型发布','智能体工具','框架与 SDK','研究','产品','产业'];
const iso=d=>d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
const parse=s=>new Date(s+'T12:00:00');
const offset=(s,n)=>{const d=parse(s);d.setDate(d.getDate()+n);return iso(d)};
const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date()),first=offset(today,-59),days=Array.from({length:60},(_,i)=>offset(first,i));
const themes=['推理能力评估','工作流协作','开发接口更新','长上下文实验','团队空间体验','应用生态观察'];
const records=[];
days.forEach((date,i)=>cats.forEach((category,c)=>{const wave=(i*7+c*11+i*c*3+Math.floor(i/5)*c*2)%13;const count=wave<3?0:Math.min(12,Math.floor(wave/2)+((i===44||i===53)&&c<3?6:0));for(let k=0;k<count;k++)records.push({id:date+'-'+c+'-'+k,date,category,title:'示例 · '+themes[c]+' '+(i+1)+'.'+(k+1)})}));
let range={start:offset(today,-29),end:today},draft={...range},calendarMonth=parse(today),selectingEnd=false,selected=null,limit=12;
const palette=['#e8edf1','#f7eeeb','#f2dcd5','#eac7bd','#e4b4a6','#dba08e','#ce8673','#c2725d','#b65e49','#a94b3b','#9d3c2e','#8f3027','#822a23'];
const escapeHTML=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon=name=>'<svg><use href="#i-'+name+'"/></svg>';
function current(){return records.filter(e=>e.date>=range.start&&e.date<=range.end)}
function selection(){return current().filter(e=>!selected||(e.date===selected.date&&e.category===selected.category))}
function preset(key){if(key==='today')return{start:today,end:today};if(key==='yesterday')return{start:offset(today,-1),end:offset(today,-1)};if(key==='week')return{start:offset(today,-6),end:today};if(key==='month')return{start:today.slice(0,8)+'01',end:today};if(key==='all')return{start:first,end:today};return{start:offset(today,-29),end:today}}
function setRange(value){range={...value};selected=null;limit=12;renderStats();$$('[data-range]').forEach(b=>b.setAttribute('aria-pressed',JSON.stringify(preset(b.dataset.range))===JSON.stringify(range)))}
function renderStats(){
 const data=current(),chartDays=[];for(let d=range.start;d<=range.end;d=offset(d,1))chartDays.push(d);
 $('#range-label').textContent=range.start.replaceAll('-','/')+' — '+range.end.replaceAll('-','/');
 $('#assistant-scope').textContent=range.start+' 至 '+range.end+' · '+data.length+' 条事件';
 const totals=cats.map(c=>({name:c,count:data.filter(e=>e.category===c).length})).sort((a,b)=>b.count-a.count);
 $('#summary').innerHTML='<b>'+data.length+'</b> 条事件 · '+chartDays.length+' 天'+(data.length?' · '+totals[0].name+'最多，'+totals[0].count+' 条':' · 当前范围暂无样本');
 $('#chart-caption').textContent='横向看日期，纵向看分类。灰色为 0；红色越深，事件越多。';
 const grid=$('#heatmap');grid.style.setProperty('--day-count',chartDays.length);grid.style.gridTemplateColumns='88px repeat('+chartDays.length+',minmax(26px,1fr))';
 let html='<span></span>'+chartDays.map(d=>'<span class="date">'+d.slice(5).replace('-','/')+'</span>').join('');
 cats.forEach(c=>{html+='<span class="category">'+c+'</span>';chartDays.forEach((d,i)=>{const n=data.filter(e=>e.date===d&&e.category===c).length;html+='<button class="heat-cell" data-date="'+d+'" data-category="'+c+'" data-count="'+n+'" aria-pressed="'+Boolean(selected&&selected.date===d&&selected.category===c)+'" aria-label="'+d+' '+c+'，'+n+' 条事件" title="'+d+' · '+c+' · '+n+' 条" style="--cell:'+palette[Math.min(12,n)]+';--cell-ink:'+(n>=8?'#fff':'#201511')+';--delay:'+Math.min(i*7,180)+'ms">'+n+'</button>'})});
 grid.innerHTML=html;renderEvents();
}
function renderEvents(){const data=selection();$('#events-title').textContent=selected?selected.date+' · '+selected.category:'所选范围的事件';$('#list-count').textContent='共 '+data.length+' 条';$('#reset-cell').hidden=!selected;
 const sorted=[...data].sort((a,b)=>b.date.localeCompare(a.date));
 $('#events').innerHTML=sorted.length?sorted.slice(0,limit).map(e=>'<article class="event-row"><time>'+e.date.slice(5)+'</time><div class="event-copy"><p>'+e.title+'</p><span>'+e.category+' · 合成演示事件</span></div><button class="quiet small-button" data-ask-event="'+e.id+'">向助手提问</button></article>').join(''):'<p class="empty">这段范围没有演示事件，可以切换日期或选择其他色块。</p>';$('#load-more').hidden=data.length<=limit;
}
$('#heatmap').onclick=e=>{const b=e.target.closest('.heat-cell');if(!b)return;selected={date:b.dataset.date,category:b.dataset.category};limit=12;$$('.heat-cell').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));renderEvents()};
$('#reset-cell').onclick=()=>{selected=null;$$('.heat-cell').forEach(x=>x.setAttribute('aria-pressed','false'));renderEvents()};
$('#load-more').onclick=()=>{limit+=12;renderEvents()};
$$('[data-range]').forEach(b=>b.onclick=()=>setRange(preset(b.dataset.range)));
$('#compare-week').onclick=()=>{setRange(preset('week'));toast('已切换到近7天')};$('#clear').onclick=()=>{setRange(preset('month30'));toast('已恢复近30天、全部分类')};
function openDate(){draft={...range};calendarMonth=parse(draft.end);selectingEnd=false;$('#date-popover').hidden=false;$('#range-trigger').setAttribute('aria-expanded','true');$('#date-error').hidden=true;syncDate();if(innerWidth>900){const p=$('#date-popover'),r=$('#range-trigger').getBoundingClientRect();p.style.top=Math.max(8,Math.min(r.bottom+8,innerHeight-p.offsetHeight-12))+'px';p.style.left=Math.max(8,Math.min(r.left,innerWidth-p.offsetWidth-12))+'px'}else{$('#date-popover').style.top='';$('#date-popover').style.left=''}$('#start-date').focus()}
function closeDate(){ $('#date-popover').hidden=true;$('#range-trigger').setAttribute('aria-expanded','false');$('#range-trigger').focus()}
function syncDate(){$('#start-date').value=draft.start;$('#end-date').value=draft.end;$$('[data-preset]').forEach(b=>b.setAttribute('aria-pressed',JSON.stringify(preset(b.dataset.preset))===JSON.stringify(draft)));renderCalendar()}
function renderCalendar(){
 const y=calendarMonth.getFullYear(),m=calendarMonth.getMonth(),one=new Date(y,m,1,12),start=offset(iso(one),-((one.getDay()+6)%7));
 $('#calendar-title').textContent=y+'年 '+(m+1)+'月';
 $('#calendar-days').innerHTML=Array.from({length:42},(_,i)=>{const d=offset(start,i),day=parse(d);return '<button class="calendar-day '+(day.getMonth()!==m?'outside ':'')+(d>=draft.start&&d<=draft.end?'in-range ':'')+(d===draft.start||d===draft.end?'endpoint':'')+'" data-day="'+d+'" aria-label="'+d+'" aria-pressed="'+(d===draft.start||d===draft.end)+'">'+day.getDate()+'</button>'}).join('');
 $('#date-hint').textContent=selectingEnd?'请选择结束日期':'先选开始日期，再选结束日期';
}
$('#range-trigger').onclick=()=>$('#date-popover').hidden?openDate():closeDate();
$('#cancel-date').onclick=closeDate;
$('#prev-month').onclick=()=>{calendarMonth=new Date(calendarMonth.getFullYear(),calendarMonth.getMonth()-1,1,12);renderCalendar()};
$('#next-month').onclick=()=>{calendarMonth=new Date(calendarMonth.getFullYear(),calendarMonth.getMonth()+1,1,12);renderCalendar()};
$('#calendar-days').onclick=e=>{const d=e.target.closest('[data-day]')?.dataset.day;if(!d)return;if(!selectingEnd){draft={start:d,end:d};selectingEnd=true}else{draft={start:d<draft.start?d:draft.start,end:d<draft.start?draft.start:d};selectingEnd=false}syncDate()};
$$('[data-preset]').forEach(b=>b.onclick=()=>{draft=preset(b.dataset.preset);calendarMonth=parse(draft.end);selectingEnd=false;syncDate()});
['start','end'].forEach(k=>$('#'+k+'-date').onchange=e=>{draft[k]=e.target.value;if(draft[k])calendarMonth=parse(draft[k]);renderCalendar()});
$('#apply-date').onclick=()=>{const span=(parse(draft.end)-parse(draft.start))/86400000;if(!draft.start||!draft.end||span<0||span>365){$('#date-error').textContent='请选择有效的起止日期，范围不超过366天。';$('#date-error').hidden=false;return}setRange(draft);closeDate()};
document.addEventListener('pointerdown',e=>{if(!$('#date-popover').hidden&&!e.target.closest('.range-anchor'))closeDate();if(!$('#chat-menu').hidden&&!e.target.closest('#chat-menu')&&!e.target.closest('[data-menu]')&&!e.target.closest('#compare-more'))$('#chat-menu').hidden=true});
let toastTimer;function toast(s){$('#toast').textContent=s;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,2800)}
const storageKey='radar-controls-preview-chats-v1';
let chats=[],activeId='',menuId='',historyOpen=innerWidth>1200,panelWidth=Math.min(560,innerWidth*.5),historyWidth=180;
const uid=()=>globalThis.crypto?.randomUUID?.()||'chat-'+Date.now()+'-'+Math.random().toString(36).slice(2);
const active=()=>chats.find(c=>c.id===activeId);
function save(){try{localStorage.setItem(storageKey,JSON.stringify({chats,activeId}))}catch{$('#storage-notice').textContent='浏览器存储不可用，本次会话暂存于内存。'}}
try{const v=JSON.parse(localStorage.getItem(storageKey)||'null');if(v&&Array.isArray(v.chats)){chats=v.chats.filter(c=>typeof c.id==='string'&&typeof c.title==='string'&&Array.isArray(c.messages));activeId=v.activeId}}catch{}
if(!chats.length){chats=[{id:uid(),title:'新的研究会话',draft:'',messages:[]},{id:uid(),title:'示例 · 模型方向观察',draft:'',messages:[{role:'user',text:'这个示例会话可以如何管理？'},{role:'assistant',text:'点击会话右侧的更多按钮，可以重命名、导出或删除。此处只展示本地会话交互，不连接 AI 模型。'}]},{id:uid(),title:'示例 · 本周产品进展',draft:'',messages:[{role:'assistant',text:'这是用于体验历史切换的示例会话。你也可以新建自己的预览会话。'}]}];activeId=chats[0].id}
if(!active())activeId=chats[0].id;
function renderHistory(){$('#history-list').innerHTML=chats.map(c=>'<div class="history-item '+(c.id===activeId?'active':'')+'"><button class="history-title" data-chat="'+c.id+'" title="'+escapeHTML(c.title)+'" '+(c.id===activeId?'aria-current="true"':'')+'>'+escapeHTML(c.title)+'</button><button class="icon quiet" data-menu="'+c.id+'" aria-label="'+escapeHTML(c.title)+'的更多操作">'+icon('more')+'</button></div>').join('')}
function renderChat(){const c=active();$('#messages').innerHTML=c.messages.length?c.messages.map(m=>'<article class="message '+m.role+'"><strong>'+(m.role==='user'?'你':'助手 · 脚本演示')+'</strong>'+escapeHTML(m.text)+'</article>').join(''):'<div class="welcome"><h3>从一个问题开始</h3><p>看图时有了疑问，就在这里继续。你的问题和历史会话会保留在本机。</p><button class="soft" id="suggestion">这段时间哪个方向最活跃？</button></div>';
 $('#question').value=c.draft||'';$('#send').disabled=!$('#question').value.trim();$('#suggestion')?.addEventListener('click',()=>{$('#question').value='这段时间哪个方向最活跃？';active().draft=$('#question').value;$('#send').disabled=false;$('#question').focus();save()});renderHistory();$('#messages').scrollTop=$('#messages').scrollHeight}
$('#question').oninput=()=>{active().draft=$('#question').value;$('#send').disabled=!$('#question').value.trim();save()};
function showAssistant(){document.body.classList.remove('assistant-closed');if(innerWidth<=900){$('#assistant').classList.add('mobile-open');document.body.classList.add('mobile-chat-open');historyOpen=false;syncHistory()}$('#question').focus()}
$('#open-assistant').onclick=showAssistant;$('#compare-send').onclick=showAssistant;
$('#collapse-assistant').onclick=()=>{document.body.classList.add('assistant-closed');document.body.classList.remove('mobile-chat-open');$('#assistant').classList.remove('mobile-open');$('#open-assistant').focus()};
$('#new-chat').onclick=()=>{const c={id:uid(),title:'新的研究会话',draft:'',messages:[]};chats.unshift(c);activeId=c.id;renderChat();save();$('#question').focus()};
function syncHistory(){$('#history').hidden=!historyOpen;$('#toggle-history').setAttribute('aria-expanded',String(historyOpen));widths()}
$('#toggle-history').onclick=()=>{historyOpen=!historyOpen;syncHistory()};$('#hide-history').onclick=()=>{historyOpen=false;syncHistory();$('#toggle-history').focus()};
$('#compare-history').onclick=()=>{showAssistant();historyOpen=true;syncHistory()};
function openMenu(id,anchor){menuId=id;const r=anchor.getBoundingClientRect(),m=$('#chat-menu');m.hidden=false;m.style.left=Math.max(8,Math.min(innerWidth-145,r.right-135))+'px';m.style.top=Math.max(8,Math.min(innerHeight-140,r.bottom+5))+'px';m.querySelector('button').focus()}
$('#history-list').onclick=e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.menu){openMenu(b.dataset.menu,b);return}if(b.dataset.chat){activeId=b.dataset.chat;renderChat();save();if(innerWidth<=1200){historyOpen=false;syncHistory()}}};
$('#compare-more').onclick=e=>openMenu(activeId,e.currentTarget);
$('#chat-menu').onclick=e=>{const action=e.target.dataset.action,c=chats.find(c=>c.id===menuId);if(!action||!c)return;$('#chat-menu').hidden=true;
 if(action==='rename'){$('#rename-input').value=c.title;$('#rename-dialog').showModal();$('#rename-input').select()}
 if(action==='export'){const url=URL.createObjectURL(new Blob([JSON.stringify(c,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='radar-preview-conversation.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('已导出会话')}
 if(action==='delete'){chats=chats.filter(x=>x.id!==c.id);if(!chats.length){$('#new-chat').click()}else{if(activeId===c.id)activeId=chats[0].id;renderChat();save()}toast('已删除预览会话')}
};
$('#rename-form').onsubmit=e=>{if(e.submitter?.value!=='save')return;const c=chats.find(c=>c.id===menuId),name=$('#rename-input').value.trim();if(!name){e.preventDefault();return}if(c){c.title=name;renderHistory();save()}};
$('#composer').onsubmit=e=>{e.preventDefault();const q=$('#question').value.trim();if(!q)return;const c=active(),data=current(),totals=cats.map(name=>({name,count:data.filter(x=>x.category===name).length})).sort((a,b)=>b.count-a.count);c.messages.push({role:'user',text:q});
 const text=data.length?'当前范围（'+range.start+' 至 '+range.end+'）有 '+data.length+' 条合成事件。'+totals[0].name+'最多，为 '+totals[0].count+' 条，占 '+Math.round(totals[0].count/data.length*100)+'%。\n\n这是脚本对当前范围的固定统计回复，用于体验连续对话；尚未理解问题或调用 AI 模型。':'这个范围没有演示事件。试试近30天，或选取样本覆盖的 '+first+' 至 '+today+'。\n\n这是脚本演示回复。';
 c.messages.push({role:'assistant',text});if(c.title==='新的研究会话')c.title=q.slice(0,24);c.draft='';renderChat();save()};
$('#events').onclick=e=>{const id=e.target.closest('[data-ask-event]')?.dataset.askEvent;if(!id)return;const event=records.find(x=>x.id===id);showAssistant();active().draft='请分析「'+event.title+'」（'+event.date+'，'+event.category+'）';renderChat();save();$('#question').focus()};
function widths(){const min=historyOpen&&innerWidth>1200?510:330;panelWidth=Math.min(innerWidth/2,Math.max(min,panelWidth));historyWidth=Math.max(160,Math.min(240,panelWidth-330,historyWidth));document.documentElement.style.setProperty('--assistant-width',panelWidth+'px');document.documentElement.style.setProperty('--history-width',historyWidth+'px');$('.outer-edge').setAttribute('aria-valuenow',Math.round(panelWidth));$('.history-edge').setAttribute('aria-valuenow',Math.round(historyWidth))}
$$('.resize-edge').forEach(edge=>{edge.onpointerdown=e=>{e.preventDefault();const outer=edge.classList.contains('outer-edge'),start=e.clientX,width=outer?panelWidth:historyWidth;edge.setPointerCapture(e.pointerId);const move=p=>{if(outer)panelWidth=width+start-p.clientX;else historyWidth=width+start-p.clientX;widths()};const up=()=>{edge.removeEventListener('pointermove',move);edge.removeEventListener('pointerup',up);edge.removeEventListener('pointercancel',up)};edge.addEventListener('pointermove',move);edge.addEventListener('pointerup',up);edge.addEventListener('pointercancel',up)};edge.onkeydown=e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();const d=e.key==='ArrowLeft'?20:-20;if(edge.classList.contains('outer-edge'))panelWidth+=d;else historyWidth+=d;widths()}});
window.addEventListener('resize',()=>{widths();if(innerWidth>900){document.body.classList.remove('mobile-chat-open');$('#assistant').classList.remove('mobile-open')}});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){if(!$('#chat-menu').hidden){$('#chat-menu').hidden=true}else if(!$('#date-popover').hidden){closeDate()}else if(!$('#rename-dialog').open&&historyOpen){historyOpen=false;syncHistory()}else if(!$('#rename-dialog').open){$('#collapse-assistant').click()}}});
renderStats();renderChat();syncHistory();save();
