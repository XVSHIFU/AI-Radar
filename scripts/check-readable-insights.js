(async()=>{
const checks=[], pause=ms=>new Promise(r=>setTimeout(r,ms));
const t=id=>document.querySelector('[data-testid="'+id+'"]');
const button=text=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===text);
const until=async f=>{for(let i=0;i<100;i++){if(f())return;await pause(50)}throw Error('UI state timed out')};
const set=(e,v)=>{e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))};
const choose=async(lo,hi)=>{button('自定义').click();await pause(0);set(document.querySelector('[name=date_from]'),lo);set(document.querySelector('[name=date_to]'),hi)};
const total=()=>Number(t('insights-summary')?.textContent.match(/精确匹配 (\d+) 条/)?.[1]);
const table=()=>[...(document.querySelectorAll('.ask-data-table tbody tr'))].map(r=>[...r.children].map(c=>c.textContent.trim()));
const check=async(name,fn)=>{try{const actual=await fn();checks.push({name,passed:actual.passed===true,actual})}catch(e){checks.push({name,passed:false,error:String(e)})}};
await until(()=>t('insights-summary'));
let asks=0;const original=window.fetch;window.fetch=(url,init)=>{if(String(url).endsWith('/ask'))asks++;return original(url,init)};
await choose('2026-09-08','2026-09-14');await until(()=>total()===25&&t('insights-visual'));
await check('heat_default_no_motion_switch',async()=>({passed:t('insights-visual').dataset.view==='C'&&!/播放流动|暂停流动|播放日期|暂停播放/.test(t('insights-visual').textContent)}));
await check('full_joint_grid_and_counts',async()=>{const cells=[...document.querySelectorAll('.heat-compact button[data-category]')];return {passed:cells.length===42&&cells.reduce((s,e)=>s+Number(e.textContent),0)===25&&table().reduce((n,r)=>n+Number(r.at(-1)),0)===25}});
await check('heat_has_no_button_rounding',async()=>{const cell=document.querySelector('.heat-compact button[data-category]'),s=getComputedStyle(cell);return {passed:parseFloat(s.borderRadius)===0&&s.boxShadow==='none',radius:s.borderRadius}});
await check('heat_text_contrast_and_zero_encoding',async()=>{const rgb=s=>(s.match(/[\d.]+/g)||[]).slice(0,3).map(Number),luma=a=>a.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);const samples=[...document.querySelectorAll('.heat-compact button')].map(e=>{const s=getComputedStyle(e),a=luma(rgb(s.color)),b=luma(rgb(s.backgroundColor));return {count:Number(e.textContent),contrast:(Math.max(a,b)+.05)/(Math.min(a,b)+.05),background:s.backgroundColor}});return {passed:samples.every(x=>x.contrast>=4.5)&&new Set(samples.filter(x=>!x.count).map(x=>x.background)).size===1,minContrast:Math.min(...samples.map(x=>x.contrast))}});
await check('A_quantity_ranking',async()=>{document.querySelector('[data-view=A]').click();await pause(0);const rows=[...document.querySelectorAll('.rank-row')],counts=rows.map(r=>Number(r.querySelector('b').textContent.match(/\d+/)[0]));return {passed:counts.length===6&&counts.reduce((a,b)=>a+b,0)===25&&counts.every((n,i)=>!i||n<=counts[i-1])&&rows.every(r=>r.textContent.includes('%')),counts}});
await check('B_direct_daily_counts',async()=>{document.querySelector('[data-view=B]').click();await pause(0);const rows=[...document.querySelectorAll('.daily-count')],counts=rows.map(r=>Number(r.querySelector('b').textContent));return {passed:counts.join(',')==='5,5,5,5,5,0,0'&&rows[0].textContent.includes('09-08')&&rows.at(-1).textContent.includes('09-14'),counts}});
await check('day_filter_from_bar',async()=>{document.querySelector('.daily-count[data-date-from="2026-09-12"]').click();await until(()=>total()===5);return {passed:document.querySelector('[name=date_from]').value==='2026-09-12'&&document.querySelector('[name=date_to]').value==='2026-09-12'&&document.querySelector('.ask-chart').textContent.includes('只有一天')}});
await check('month_aggregate_independent_of_pagination',async()=>{await choose('2026-09-01','2026-09-30');await until(()=>total()===32&&table().length===30);return {passed:table().reduce((n,r)=>n+Number(r.at(-1)),0)===32&&t('insights-events').querySelectorAll('article').length===10}});
await check('natural_month_boundaries',async()=>{await choose('2026-08-15','2026-10-15');await until(()=>table().length===3);const rows=table();return {passed:rows[0][0].includes('2026-08-15')&&rows.at(-1)[0].includes('2026-10-15')&&rows.reduce((n,r)=>n+Number(r.at(-1)),0)===32}});
await check('statistics_never_calls_model',async()=>({passed:asks===0,requests:asks}));
window.fetch=original;
return {observed_at:new Date().toISOString(),layer:'fixture_browser_full_aggregate',passed:checks.filter(c=>c.passed).length,total:checks.length,checks};
})()
