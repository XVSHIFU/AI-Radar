import test from "node:test";
import assert from "node:assert/strict";
import { computed } from "vue";
import { setLocale } from "./locale";
import { at, adminMessage, adminError, adminUsageValue, adminRecordedUsage } from "./admin-locale";

test("existing admin notices react to language changes without changing source names", () => {
  const sourceName = "来源 {message} / OpenAI";
  const notice = adminMessage("{name}：{message}{items}", {
    name: sourceName,
    message: adminMessage("RSS 订阅可访问"),
    items: adminMessage("（发现 {count} 项）", { count: 3 }),
  });
  const rendered = computed(() => at(notice));
  setLocale("zh");
  assert.equal(rendered.value, `${sourceName}：RSS 订阅可访问（发现 3 项）`);
  setLocale("en");
  assert.equal(rendered.value, `${sourceName}: RSS feed is accessible (found 3 items)`);
  setLocale("zh");
  assert.equal(rendered.value, `${sourceName}：RSS 订阅可访问（发现 3 项）`);
});

test("admin errors and unavailable usage respond to locale changes", () => {
  setLocale("en");
  assert.equal(adminError({ code: "SOURCE_COOLDOWN", message: "Source is cooling down" }), "The source is cooling down. Try again later.");
  assert.equal(adminError({ code: "UNAUTHORIZED", message: "会话已过期，请重新输入管理口令。" }), "Your session has expired. Enter the admin passphrase again.");
  assert.equal(adminUsageValue(null), "Unknown");
  assert.equal(adminUsageValue(0), "0");
  assert.equal(adminRecordedUsage(0), "0 recorded calls");
  setLocale("zh");
  assert.equal(adminError({ code: "SOURCE_COOLDOWN", message: "Source is cooling down" }), "来源正在冷却，请稍后再试。");
  assert.equal(adminUsageValue(null), "未知");
  assert.equal(adminRecordedUsage(0), "已记录 0 次");
});

test("unknown diagnostics remain verbatim, including interpolation-like content", () => {
  const raw = 'provider/model https://example.test/{id} 原始 {message} $&';
  for (const locale of ["en", "zh"] as const) {
    setLocale(locale);
    assert.equal(at(raw), raw);
    assert.equal(adminError({ code: "UNKNOWN_PROVIDER_ERROR", message: raw }), raw);
  }
});
