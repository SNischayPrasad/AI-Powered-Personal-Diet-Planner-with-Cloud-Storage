// Unit tests for the Cloudflare Worker (plain Node, no Cloudflare account needed):
//   node --test "cloudflare/test/*.test.js"
import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import worker, { PAGE_SECURITY_HEADERS, isApiPath } from "../src/index.js";

const API_ORIGIN = "https://api.example.test";
const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; });

function fakeAssets(body = "<!doctype html><div id=root></div>") {
  const calls = [];
  return {
    calls,
    fetch: async (request) => {
      calls.push(new URL(request.url).pathname);
      return new Response(body, { headers: { "Content-Type": "text/html" } });
    },
  };
}

function captureFetch(response = Response.json({ status: "ok" })) {
  const seen = [];
  globalThis.fetch = async (url, init) => {
    seen.push({ url: String(url), init });
    return response;
  };
  return seen;
}

test("only /api and /api/... are API paths", () => {
  assert.ok(isApiPath("/api"));
  assert.ok(isApiPath("/api/plans/1"));
  assert.ok(!isApiPath("/apiary"));
  assert.ok(!isApiPath("/dashboard"));
});

test("pages come from static assets with the security headers added", async () => {
  const assets = fakeAssets();
  const response = await worker.fetch(new Request("https://app.test/dashboard"),
    { ASSETS: assets, API_ORIGIN });

  assert.deepEqual(assets.calls, ["/dashboard"]);
  assert.equal(response.status, 200);
  for (const [name, value] of Object.entries(PAGE_SECURITY_HEADERS)) {
    assert.equal(response.headers.get(name), value);
  }
});

test("API calls keep path, query, method, body and token, and go to API_ORIGIN", async () => {
  const seen = captureFetch();
  const request = new Request("https://app.test/api/plans?limit=5", {
    method: "POST",
    headers: { Authorization: "Bearer abc", "Content-Type": "application/json" },
    body: JSON.stringify({ goal: "fitness" }),
  });

  const response = await worker.fetch(request, { ASSETS: fakeAssets(), API_ORIGIN });

  assert.equal(response.status, 200);
  assert.equal(seen[0].url, "https://api.example.test/api/plans?limit=5");
  assert.equal(seen[0].init.method, "POST");
  assert.equal(seen[0].init.headers.get("Authorization"), "Bearer abc");
  assert.equal(await new Response(seen[0].init.body).text(), '{"goal":"fitness"}');
});

test("the visitor IP comes from Cloudflare, never from a forged header", async () => {
  const seen = captureFetch();
  const request = new Request("https://app.test/api/login", {
    method: "POST",
    headers: { "CF-Connecting-IP": "203.0.113.7", "X-Forwarded-For": "6.6.6.6" },
    body: "{}",
  });

  await worker.fetch(request, { ASSETS: fakeAssets(), API_ORIGIN });

  assert.equal(seen[0].init.headers.get("X-Forwarded-For"), "203.0.113.7");
  assert.equal(seen[0].init.headers.get("X-Forwarded-Proto"), "https");
});

test("an unreachable API gives a JSON 502 in the app's error format", async () => {
  globalThis.fetch = async () => { throw new TypeError("network down"); };

  const response = await worker.fetch(new Request("https://app.test/api/health"),
    { ASSETS: fakeAssets(), API_ORIGIN });

  assert.equal(response.status, 502);
  assert.equal((await response.json()).error.code, "api_unreachable");
});

test("a missing API_ORIGIN is reported instead of failing silently", async () => {
  const response = await worker.fetch(new Request("https://app.test/api/health"),
    { ASSETS: fakeAssets() });

  assert.equal(response.status, 503);
  assert.equal((await response.json()).error.code, "api_not_configured");
});
