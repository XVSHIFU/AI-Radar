import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("container entrypoint wires the content broker used by the deployed runtime", async () => {
  const entry = await readFile(
    new URL("../../../../deploy/containers/runtime-entry.mjs", import.meta.url),
    "utf8",
  );
  const dockerfile = await readFile(
    new URL("../../../../deploy/containers/Runtime.Dockerfile", import.meta.url),
    "utf8",
  );
  assert.match(dockerfile, /COPY deploy\/containers\/runtime-entry\.mjs \.\/container\.mjs/);
  assert.match(dockerfile, /ENTRYPOINT \["node", "container\.mjs"\]/);
  assert.match(entry, /import \{ httpContentBroker \} from '\.\/dist\/src\/content-broker\.js';/);
  assert.match(
    entry,
    /contentBroker:\s*capability\s*=>\s*httpContentBroker\('http:\/\/api:8000',\s*capability\)/,
  );
});
