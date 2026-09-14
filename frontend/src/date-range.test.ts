import assert from "node:assert/strict";
import test from "node:test";
import {addDays,datePreset,validateRange} from "./date-range";
import {demoEvents,demoToday} from "./demo-events";
import {events} from "./api";
import {insights} from "./insights-api";
test("date presets preserve calendar boundaries and inclusive limits",()=>{
 assert.deepEqual(datePreset("month","2026-09-14"),{from:"2026-09-01",to:"2026-09-14"});
 assert.deepEqual(datePreset("week","2026-01-03"),{from:"2025-12-28",to:"2026-01-03"});
 assert.equal(validateRange({from:"2024-02-29",to:"2024-03-01"}),"");
 assert.notEqual(validateRange({from:"2026-02-30",to:"2026-03-01"}),"");
 assert.notEqual(validateRange({from:"2026-09-15",to:"2026-09-14"}),"");
 assert.equal(validateRange({from:"2024-01-01",to:"2024-12-31"}),"");
 assert.notEqual(validateRange({from:"2024-01-01",to:"2025-01-01"}),"");
 assert.equal(validateRange({from:"",to:""},true),"");
 assert.notEqual(validateRange({from:"",to:""}),"");
});
test("rich demo preserves historical fixtures and adds unique 60-day events",()=>{
 const generated=demoEvents.filter(x=>x.id.startsWith("10000000"));
 assert.equal(generated.length,1029);
 assert.equal(new Set(demoEvents.map(x=>x.id)).size,demoEvents.length);
 assert.equal(new Set(generated.map(x=>x.event_date)).size,59);
 assert.equal(generated.at(-1)?.event_date,addDays(demoToday,-59));
 assert.ok(demoEvents.some(x=>x.id==="00000000-0000-4000-8000-000000000002"));
});
test("demo charts, paginated results and details share one filtered event set",async()=>{
 const original=Object.getOwnPropertyDescriptor(globalThis,"location");
 Object.defineProperty(globalThis,"location",{value:{search:"?demo=1"},configurable:true});
 try{
  const query={date_from:addDays(demoToday,-29),date_to:demoToday,category:"research" as const,min_importance:3};
  const overview=await insights(query);
  let cursor:string|undefined,rows:Awaited<ReturnType<typeof events.list>>["items"]=[];
  do{const page=await events.list({...query,limit:7,cursor});assert.equal(page.total,overview.total_events);rows.push(...page.items);cursor=page.next_cursor||undefined}while(cursor);
  assert.equal(rows.length,overview.total_events);
  assert.equal(overview.daily.reduce((n,x)=>n+x.count,0),rows.length);
  assert.equal(overview.daily_categories.reduce((n,x)=>n+x.count,0),rows.length);
  assert.equal(overview.categories.reduce((n,x)=>n+x.count,0),rows.length);
  const detail=await events.one(rows[0]!.id);assert.equal(detail.id,rows[0]!.id);assert.equal(detail.title_zh,rows[0]!.title_zh);
 }finally{if(original)Object.defineProperty(globalThis,"location",original);else Reflect.deleteProperty(globalThis,"location")}
});
