import assert from "node:assert/strict";
import test from "node:test";
import { setLocale, t, translate } from "./locale.js";
test("locale switches UI dictionary and local pairs without mutating source content", () => { setLocale("en"); assert.equal(t("events"), "Events"); assert.equal(translate("来源", "Source"), "Source"); setLocale("zh"); assert.equal(t("events"), "事件"); });