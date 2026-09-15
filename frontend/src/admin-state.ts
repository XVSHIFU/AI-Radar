export function adminRequestGeneration() {
  let generation = 0;
  return {
    capture: () => generation,
    invalidate: () => { generation += 1; },
    current: (candidate: number) => candidate === generation,
  };
}
export function usageValue(value: number | null | undefined) {
  return value === null || value === undefined ? "未知" : String(value);
}
export function recordedUsage(value: number | null | undefined) {
  return value === null || value === undefined ? "记录次数未知" : `已记录 ${value} 次`;
}