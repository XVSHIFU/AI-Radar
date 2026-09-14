export type DateRange = { from: string; to: string };
export type DatePreset = "today" | "yesterday" | "week" | "month30" | "month";
export function shanghaiToday() {
 const parts = new Intl.DateTimeFormat("en-CA", { timeZone:"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit" }).formatToParts();
 const get=(type:string)=>parts.find(p=>p.type===type)?.value||"";
 return get("year")+"-"+get("month")+"-"+get("day");
}
export function addDays(date:string,n:number){const d=new Date(date+"T12:00:00Z");d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10)}
export function datePreset(mode:DatePreset,today=shanghaiToday()):DateRange{
 if(mode==="yesterday")return {from:addDays(today,-1),to:addDays(today,-1)};
 return {from:mode==="week"?addDays(today,-6):mode==="month30"?addDays(today,-29):mode==="month"?today.slice(0,8)+"01":today,to:today};
}
export function validateRange(range:DateRange,allowUnbounded=false,maxDays=366){
 const valid=(v:string)=>/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v+"T12:00:00Z"))&&new Date(v+"T12:00:00Z").toISOString().slice(0,10)===v;
 if((range.from&&!valid(range.from))||(range.to&&!valid(range.to)))return "请输入有效日期。";
 if(!allowUnbounded&&(!range.from||!range.to))return "请选择完整的开始和结束日期。";
 if(range.from&&range.to){if(range.from>range.to)return "开始日期不能晚于结束日期。";if((Date.parse(range.to)-Date.parse(range.from))/86400000+1>maxDays)return "日期范围最多 "+maxDays+" 天。"}
 return "";
}
