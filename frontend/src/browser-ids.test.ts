import assert from "node:assert/strict";
import test from "node:test";
import { secureUuid } from "./browser-ids.js";

test("secureUuid falls back to getRandomValues when HTTP omits randomUUID", () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, "crypto");
  let calls = 0;
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: { getRandomValues(bytes: Uint8Array) { calls++; bytes.forEach((_, index) => { bytes[index] = index; }); return bytes; } } });
  try { assert.match(secureUuid(), /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/); assert.equal(calls, 1); }
  finally { if (original) Object.defineProperty(globalThis, "crypto", original); else delete (globalThis as { crypto?: Crypto }).crypto; }
});
