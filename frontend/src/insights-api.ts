import fixture from "../../contracts/prototype-events.json";
import { isDemo, updateDataMode, type Category } from "./api";

export type InsightQuery = {
  q?: string;
  category?: Category;
  date_from: string;
  date_to: string;
  min_importance?: number;
};
export type InsightResult = {
  date_from: string;
  date_to: string;
  timezone: string;
  total_events: number;
  total_relation: "eq";
  daily: { date: string; count: number }[];
  categories: { category: Category; count: number }[];
  as_of: string;
  data_revision: string;
  data_mode: string;
  request_id: string;
};

function fixtureInsights(query: InsightQuery): InsightResult {
  const rows = fixture.items.filter((item) => {
    const haystack = `${item.title_zh} ${item.summary_zh} ${item.entities.join(" ")}`;
    return (
      (!query.q || haystack.toLowerCase().includes(query.q.toLowerCase())) &&
      (!query.category || item.category === query.category) &&
      Boolean(item.event_date) &&
      item.event_date! >= query.date_from &&
      item.event_date! <= query.date_to &&
      (!query.min_importance || item.importance >= query.min_importance)
    );
  });
  const daily = new Map<string, number>();
  const categories = new Map<Category, number>();
  for (const row of rows) {
    if (row.event_date) daily.set(row.event_date, (daily.get(row.event_date) || 0) + 1);
    categories.set(row.category as Category, (categories.get(row.category as Category) || 0) + 1);
  }
  return {
    date_from: query.date_from,
    date_to: query.date_to,
    timezone: "Asia/Shanghai",
    total_events: rows.length,
    total_relation: "eq",
    daily: [...daily].map(([date, count]) => ({ date, count })),
    categories: [...categories].map(([category, count]) => ({ category, count })),
    as_of: "2026-09-12T00:00:00Z",
    data_revision: "synthetic-ui-v1",
    data_mode: "fixture",
    request_id: "demo-insights",
  };
}

export async function insights(
  query: InsightQuery,
  signal?: AbortSignal,
): Promise<InsightResult> {
  if (isDemo()) return fixtureInsights(query);
  const params = new URLSearchParams(
    Object.entries(query).filter(([, value]) => value !== undefined && value !== "") as [string, string][],
  );
  const response = await fetch(`/api/v1/insights?${params}`, { signal });
  if (!response.ok) throw new Error("统计请求失败");
  const value = (await response.json()) as InsightResult;
  updateDataMode(value);
  return value;
}
