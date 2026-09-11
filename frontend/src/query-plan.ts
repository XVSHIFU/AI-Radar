export type PlanFilters = {
  category?: string;
  date_from?: string;
  date_to?: string;
  entity_ids?: string[];
  entity_match?: "all" | "any";
};
export type QueryPlan = {
  intent: string;
  filters: PlanFilters;
  timezone: string;
  business_date: string;
  date_until_exclusive: string | null;
  constraints_origin?: unknown;
  free_text?: string[];
  requires_clarification: boolean;
  clarification_candidates: { label: string; entity_id: string | null }[];
  warnings: string[];
  entity_roles?: Record<string, "subject" | "product">;
  data_mode?: string;
  request_id: string;
};
export function queryPlanFrom(value: unknown): QueryPlan | undefined {
  if (!value || typeof value !== "object") return;
  const plan =
    (
      value as {
        query_plan_public?: unknown;
        details?: { query_plan_public?: unknown };
      }
    ).query_plan_public ??
    (value as { details?: { query_plan_public?: unknown } }).details
      ?.query_plan_public;
  if (!plan || typeof plan !== "object") return;
  const p = plan as Partial<QueryPlan>;
  if (
    typeof p.timezone !== "string" ||
    typeof p.business_date !== "string" ||
    !Array.isArray(p.warnings) ||
    typeof p.requires_clarification !== "boolean"
  )
    return;
  return p as QueryPlan;
}
