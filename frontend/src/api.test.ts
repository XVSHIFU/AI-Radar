import assert from "node:assert/strict";
import test from "node:test";
import { dataMode, updateDataMode } from "./api.js";

test("updates the data-mode banner from successful and error query plans", () => {
  dataMode.value = "live";
  updateDataMode({ details: { query_plan_public: { data_mode: "fixture" } } });
  assert.equal(dataMode.value, "fixture");

  updateDataMode({ data_mode: "postgres" });
  assert.equal(dataMode.value, "live");
});