import fixture from "../../contracts/prototype-events.json";
import type { Event, Category } from "./api";
import {addDays,shanghaiToday} from "./date-range";
const categories:Category[]=["model_release","agent_tool","framework_sdk","research","product","industry"];
const titles=["推理能力评估","工作流协作","开发接口更新","长上下文实验","团队空间体验","应用生态观察"];
export const demoToday=shanghaiToday();
const generated:Event[]=[];
for(let i=0;i<60;i++)for(let c=0;c<categories.length;c++){
 const wave=(i*7+c*11+i*c*3+Math.floor(i/5)*c*2)%13;
 const count=wave<3?0:Math.min(12,Math.floor(wave/2)+((i===44||i===53)&&c<3?6:0));
 const date=addDays(demoToday,i-59);
 for(let k=0;k<count;k++)generated.push({id:"10000000-0000-4000-8000-"+String(i*100+c*12+k).padStart(12,"0"),title_zh:"示例 · "+titles[c]+" "+(i+1)+"."+(k+1),summary_zh:"用于观察日期分布和分类变化的合成事件，不代表真实新闻。可在抽屉核对演示来源，并加入研究会话。",category:categories[c]!,importance:1+(i+c+k)%5,event_date:date,date_precision:"day",source_count:1,evidence_count:1,entities:["示例研究团队"],content_version:1,articles:[{title:"合成演示来源",source_url:"https://example.invalid/demo",language:"zh"}]});
}
export const demoEvents:Event[]=[...(fixture.items as Event[]),...generated].sort((a,b)=>(b.event_date||"").localeCompare(a.event_date||"")||a.id.localeCompare(b.id));
export const demoRevision="synthetic-rich-ui-v2";
