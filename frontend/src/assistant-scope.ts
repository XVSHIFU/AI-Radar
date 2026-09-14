import { reactive } from "vue";
import type { Category } from "./api";
import type { PlanFilters } from "./query-plan";
export type AssistantFilters={q?:string;category?:Category;date_from?:string;date_to?:string;min_importance?:number};
export type AssistantScope={label:string;filters:AssistantFilters;snapshot:string};
export const assistantScope=reactive<AssistantScope>({label:"当前阅读范围",filters:{},snapshot:"未设置额外筛选，检索全部已收录事件"});
export function setAssistantScope(scope:AssistantScope){assistantScope.label=scope.label;assistantScope.filters={...scope.filters};assistantScope.snapshot=scope.snapshot;}
