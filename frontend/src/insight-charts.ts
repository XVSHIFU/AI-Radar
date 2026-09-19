import type { Category } from "./api";
export const chartCategories: Category[] = ["model_release", "agent_tool", "framework_sdk", "research", "product", "industry", "unclassified"];
export type CategoryBucket = { date: string; from: string; to: string; label: string; counts: Record<Category, number>; total: number };
function zeroCounts(): Record<Category, number> { return Object.fromEntries(chartCategories.map((category) => [category, 0])) as Record<Category, number>; }
export function categoryBuckets(rows: { date: string; category: Category; count: number }[], compactByMonth: boolean): CategoryBucket[] {
  const buckets = new Map<string, CategoryBucket>();
  for (const row of rows) {
    const key = compactByMonth ? row.date.slice(0, 7) : row.date;
    let bucket = buckets.get(key);
    if (!bucket) { bucket = { date: key, from: row.date, to: row.date, label: compactByMonth ? key : row.date.slice(5), counts: zeroCounts(), total: 0 }; buckets.set(key, bucket); }
    bucket.to = row.date;
    bucket.counts[row.category] = (bucket.counts[row.category] || 0) + row.count;
    bucket.total += row.count;
  }
  return [...buckets.values()];
}
export function categoryTotal(buckets: CategoryBucket[]) { return buckets.reduce((total, bucket) => total + bucket.total, 0); }
