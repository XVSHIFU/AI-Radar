import test from "node:test";
import assert from "node:assert/strict";
import { queryPlanFrom } from "./query-plan.js";
const plan = {
  intent: "search",
  filters: { category: "agent_tool" },
  timezone: "Asia/Shanghai",
  business_date: "2026-09-12",
  date_until_exclusive: null,
  requires_clarification: false,
  clarification_candidates: [],
  warnings: ["日期条件冲突"],
  request_id: "r",
};
test("reads plan from success and error details", () => {
  assert.equal(
    queryPlanFrom({ query_plan_public: plan })?.timezone,
    "Asia/Shanghai",
  );
  assert.equal(
    queryPlanFrom({ details: { query_plan_public: plan } })?.warnings[0],
    "日期条件冲突",
  );
});
