import type { AskResult, Citation } from "./api";
export type AskView = {
  citations: Citation[];
  status: string;
  noAnswer: boolean;
  partial: boolean;
};
export function askView(result: AskResult): AskView {
  const seen = new Set<number>();
  for (const citation of result.citations) {
    if (
      !Number.isInteger(citation.index) ||
      citation.index < 1 ||
      seen.has(citation.index)
    )
      throw new Error("引用协议错误：index 必须唯一正整数");
    seen.add(citation.index);
  }
  const noAnswer = result.answer_status === "no_answer";
  const partial = result.coverage === "partial";
  const status =
    result.execution_status === "completed"
      ? noAnswer
        ? "没有可回答的资料。"
        : "已完成"
      : result.execution_status === "cancelled"
        ? "已取消。"
        : `执行失败：${result.execution_status}`;
  return { citations: result.citations, status, noAnswer, partial };
}
