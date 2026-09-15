import assert from "node:assert/strict";
import { createServer as httpServer } from "node:http";
import { once } from "node:events";
import test from "node:test";
import { createServer, type ProxyOptions } from "vite";
import config from "../vite.config";

test("edge proxy replaces spoofed forwarding identity with socket peer", async () => {
  const backend = httpServer((req, res) => {
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify(req.headers));
  });
  backend.listen(0, "127.0.0.1");
  await once(backend, "listening");
  const address = backend.address();
  assert(address && typeof address === "object");
  const options = config.server?.proxy?.["/api"] as ProxyOptions;
  const edge = await createServer({
    configFile: false, logLevel: "silent",
    server: { host: "127.0.0.1", port: 0, proxy: {
      "/api": { ...options, target: `http://127.0.0.1:${address.port}` },
    } },
  });
  try {
    await edge.listen();
    const target = edge.httpServer?.address();
    assert(target && typeof target === "object");
    const response = await fetch(`http://127.0.0.1:${target.port}/api/probe`, { headers: {
      "x-forwarded-for": "203.0.113.9", "x-real-ip": "203.0.113.8",
      "forwarded": "for=203.0.113.7", "x-forwarded-proto": "https",
      "x-forwarded-host": "forged.invalid",
    } });
    const headers = await response.json();
    assert.equal(headers["x-forwarded-for"], "127.0.0.1");
    assert.equal(headers["x-forwarded-proto"], "http");
    for (const key of ["forwarded", "x-real-ip", "x-forwarded-host"]) assert.equal(headers[key], undefined);
  } finally {
    await edge.close();
    backend.close();
    await once(backend, "close");
  }
});
