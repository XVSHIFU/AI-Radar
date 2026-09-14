import assert from "node:assert/strict";
import test from "node:test";
import { renderMarkdown } from "./markdown";

test("messages and drafts render headings, lists, code, tables and line breaks", () => {
  const html = renderMarkdown("# 结论\n\n**重点**\n换行\n\n- 项目\n\n```js\nconst x = 1;\n```\n\n|类别|数量|\n|---|---|\n|研究|3|");
  for (const tag of ["<h1>", "<strong>", "<br>", "<ul>", "<pre>", "<table>"]) assert.ok(html.includes(tag), tag);
});
test("untrusted messages cannot inject HTML, active links or remote images", () => {
  const html = renderMarkdown('<img src=x onerror=alert(1)>\n\n[危险](javascript:alert%281%29)\n\n![图片](https://example.com/track)\n\n[来源](https://example.com/article)');
  assert.ok(!html.includes("<img"));
  assert.ok(!html.includes('href="javascript:'));
  assert.ok(html.includes("&lt;img"));
  assert.ok(html.includes('rel="noopener noreferrer"'));
});
