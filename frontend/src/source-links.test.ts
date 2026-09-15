import assert from "node:assert/strict";
import test from "node:test";
import { preferredReadingUrl } from "./source-links.js";
test("DeepSeek news opens its Chinese reading page without changing the stored URL", () => {
  const raw = "https://api-docs.deepseek.com/news/news260910/";
  assert.equal(preferredReadingUrl(raw), "https://api-docs.deepseek.com/zh-cn/news/news260910/");
  assert.equal(preferredReadingUrl("https://example.com/news/news260910/"), "https://example.com/news/news260910/");
});
