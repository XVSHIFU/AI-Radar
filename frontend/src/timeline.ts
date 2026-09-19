import type { Event, FeedItem } from "./api";

export type TimelineEntry = Event | FeedItem;
export type TimelineDay<T extends TimelineEntry = Event> = { key: string; label: string; events: T[] };
export type TimelineMonth<T extends TimelineEntry = Event> = {
  key: string;
  label: string;
  days: TimelineDay<T>[];
};
export type TimelineYear<T extends TimelineEntry = Event> = {
  key: string;
  label: string;
  months: TimelineMonth<T>[];
  unknown?: boolean;
};
export type TimelineState = Record<string, boolean>;

const dateParts = (date: string | null) => {
  const match = date?.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return match
    ? { year: match[1], month: `${match[1]}-${match[2]}`, day: match[0] }
    : undefined;
};

/** Builds date headings from loaded rows only; it never claims calendar-wide counts. */
export function buildTimeline<T extends TimelineEntry>(items: T[]): TimelineYear<T>[] {
  const known = new Map<string, Map<string, Map<string, T[]>>>();
  const unknown: T[] = [];
  for (const item of items) {
    const parts = dateParts("display_date" in item ? item.display_date?.slice(0, 10) ?? null : item.event_date);
    if (!parts) {
      unknown.push(item);
      continue;
    }
    const months = known.get(parts.year) || new Map();
    const days = months.get(parts.month) || new Map();
    const rows = days.get(parts.day) || [];
    rows.push(item);
    days.set(parts.day, rows);
    months.set(parts.month, days);
    known.set(parts.year, months);
  }
  const years: TimelineYear<T>[] = [...known.entries()]
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([year, months]) => ({
      key: year,
      label: `${year} 年`,
      months: [...months.entries()]
        .sort(([a], [b]) => b.localeCompare(a))
        .map(([month, days]) => ({
          key: month,
          label: `${Number(month.slice(5))} 月`,
          days: [...days.entries()]
            .sort(([a], [b]) => b.localeCompare(a))
            .map(([day, events]) => ({ key: day, label: `${Number(day.slice(-2))} 日`, events })),
        })),
    }));
  if (unknown.length) {
    years.push({
      key: "unknown",
      label: "日期未知",
      unknown: true,
      months: [
        {
          key: "unknown-month",
          label: "未提供日期",
          days: [{ key: "unknown-day", label: "日期未知", events: unknown }],
        },
      ],
    });
  }
  return years;
}

const allKeys = (timeline: TimelineYear<TimelineEntry>[]) =>
  timeline.flatMap((year) => [
    year.key,
    ...year.months.flatMap((month) => [
      month.key,
      ...month.days.map((day) => day.key),
    ]),
  ]);

/** Preserves an author's open/closed choices while pages append new date groups. */
export function reconcileTimelineState(
  current: TimelineState,
  timeline: TimelineYear<TimelineEntry>[],
): TimelineState {
  return Object.fromEntries(
    allKeys(timeline).map((key) => [key, current[key] ?? true]),
  );
}

export function setTimelineGranularity(
  timeline: TimelineYear<TimelineEntry>[],
  open: boolean,
): TimelineState {
  return Object.fromEntries(allKeys(timeline).map((key) => [key, open]));
}
