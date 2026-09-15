import type { Category } from "./api";
import { formatDate, locale, t, translate } from "./locale";

export { formatDate, locale, t, translate };

const categories: Record<Category, [string, string]> = {
  model_release: ["模型发布", "Model releases"],
  agent_tool: ["智能体工具", "Agent tools"],
  framework_sdk: ["框架与 SDK", "Frameworks & SDKs"],
  research: ["研究", "Research"],
  product: ["产品", "Products"],
  industry: ["产业", "Industry"],
};

export function categoryLabel(category: Category): string {
  const [zh, en] = categories[category];
  return translate(zh, en);
}

export function precisionLabel(value: string): string {
  if (value === "day") return translate("日精度", "Day precision");
  if (value === "month") return translate("月精度", "Month precision");
  return translate("精度未知", "Unknown precision");
}

export function countLabel(count: number, zhUnit: string, enSingular: string, enPlural = `${enSingular}s`): string {
  return locale.value === "zh" ? `${count} ${zhUnit}` : `${count} ${count === 1 ? enSingular : enPlural}`;
}
