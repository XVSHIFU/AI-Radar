import assert from "node:assert/strict";
import test from "node:test";
import { buildTimeline, reconcileTimelineState } from "./timeline";
import type { Event } from "./api";

const event = (id: string, event_date: string | null) =>
  ({ id, event_date } as Event);

test("buildTimeline keeps cross-year and cross-month date rhythm", () => {
  const timeline = buildTimeline([
    event("old", "2025-12-31"),
    event("sep", "2026-09-12"),
    event("aug", "2026-08-31"),
  ]);
  assert.deepEqual(
    timeline.map((year) => [year.key, year.months.map((month) => month.key)]),
    [["2026", ["2026-09", "2026-08"]], ["2025", ["2025-12"]]],
  );
});

test("buildTimeline gives undated events an explicit final group", () => {
  const timeline = buildTimeline([event("known", "2026-09-12"), event("none", null)]);
  assert.equal(timeline.at(-1)?.label, "日期未知");
  assert.equal(timeline.at(-1)?.months[0].days[0].events[0].id, "none");
});

test("reconcileTimelineState keeps closed groups closed after append", () => {
  const first = buildTimeline([event("first", "2026-09-12")]);
  const closed = { ...reconcileTimelineState({}, first), "2026": false, "2026-09": false };
  const appended = buildTimeline([
    event("first", "2026-09-12"),
    event("second", "2026-08-20"),
  ]);
  const state = reconcileTimelineState(closed, appended);
  assert.equal(state["2026"], false);
  assert.equal(state["2026-09"], false);
  assert.equal(state["2026-08"], true);
});
