export type PlanFilters = {
  category?: string;
  date_from?: string;
  date_to?: string;
  entity_ids?: string[];
  entity_match?: "all" | "any";
  event_ids?: string[];
};
export type QueryPlan = {
  intent: string;
  filters: PlanFilters;
  timezone: string;
  business_date: string;
  date_until_exclusive: string | null;
  constraints_origin?: unknown;
  free_text?: string;
  requires_clarification: boolean;
  clarification_candidates: { label: string; entity_id: string | null }[];
  warnings: string[];
  entity_roles?: ("subject" | "product")[];
  data_mode?: string;
  request_id: string;
  history_turns_considered?: number;
  history_user_turns_used?: number;
  event_targets?: { event_id: string; title_zh: string | null; status: "matched" | "filtered_out" | "not_found" }[];
};
const object = (x: unknown): x is Record<string, unknown> =>
  !!x && typeof x === "object" && !Array.isArray(x);
export function queryPlanFrom(value: unknown): QueryPlan | undefined {
  if (!object(value)) return;
  const plan =
    value.query_plan_public ??
    (object(value.details) ? value.details.query_plan_public : undefined);
  if (
    !object(plan) ||
    !object(plan.filters) ||
    typeof plan.timezone !== "string" ||
    typeof plan.business_date !== "string" ||
    typeof plan.requires_clarification !== "boolean" ||
    !Array.isArray(plan.warnings) ||
    !plan.warnings.every((x) => typeof x === "string") ||
    !Array.isArray(plan.clarification_candidates) ||
    !plan.clarification_candidates.every(
      (x) => object(x) && typeof x.label === "string",
    ) ||
    (plan.free_text !== undefined && typeof plan.free_text !== "string") ||
    (plan.entity_roles !== undefined &&
      (!Array.isArray(plan.entity_roles) ||
        !plan.entity_roles.every((x) => x === "subject" || x === "product"))) ||
    (plan.filters.event_ids !== undefined && (!Array.isArray(plan.filters.event_ids) || !plan.filters.event_ids.every((x) => typeof x === "string"))) ||
    (plan.event_targets !== undefined && (!Array.isArray(plan.event_targets) || !plan.event_targets.every((x) => object(x) && typeof x.event_id === "string" && (x.title_zh === null || typeof x.title_zh === "string") && (x.status === "matched" || x.status === "filtered_out" || x.status === "not_found")))) ||
    (plan.history_turns_considered !== undefined && typeof plan.history_turns_considered !== "number") ||
    (plan.history_user_turns_used !== undefined && typeof plan.history_user_turns_used !== "number") ||
    (plan.filters.entity_ids !== undefined &&
      (!Array.isArray(plan.filters.entity_ids) ||
        !plan.filters.entity_ids.every((x) => typeof x === "string")))
  )
    return;
  return plan as unknown as QueryPlan;
}
