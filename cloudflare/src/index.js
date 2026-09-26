// Cloudflare Worker: the public front door of the app.
//
//   https://<worker>.workers.dev/            → React build (static assets on Cloudflare's edge)
//   https://<worker>.workers.dev/api/*       → forwarded to the FastAPI service (API_ORIGIN)
//
// Browser and API share one origin, so no CORS setup is needed and the strict
// Content-Security-Policy (connect-src 'self') works unchanged. Hashed files under /assets/*
// never reach this script (see wrangler.jsonc); Cloudflare serves them directly.

// Same policy the FastAPI server sends for the web app (backend/utils/middleware.py).
export const PAGE_SECURITY_HEADERS = {
  "Content-Security-Policy":
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; " +
    "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; " +
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
};

// Hop-by-hop and client-supplied forwarding headers are not passed on as-is.
const STRIPPED_REQUEST_HEADERS = ["host", "connection", "x-forwarded-for", "x-forwarded-proto",
  "x-forwarded-host", "x-real-ip"];

export function isApiPath(pathname) {
  return pathname === "/api" || pathname.startsWith("/api/");
}

function errorResponse(status, code, message) {
  return Response.json({ error: { code, message, request_id: null } }, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

export async function proxyToApi(request, env) {
  if (!env.API_ORIGIN) {
    return errorResponse(503, "api_not_configured", "The API address is not configured.");
  }
  const url = new URL(request.url);
  const target = new URL(url.pathname + url.search, env.API_ORIGIN);

  const headers = new Headers(request.headers);
  for (const name of STRIPPED_REQUEST_HEADERS) headers.delete(name);
  // Cloudflare sets CF-Connecting-IP itself, so it cannot be forged by the visitor. The API
  // uses the first X-Forwarded-For entry for rate limiting (TRUST_PROXY_HEADERS=true).
  const clientIp = request.headers.get("CF-Connecting-IP");
  if (clientIp) headers.set("X-Forwarded-For", clientIp);
  headers.set("X-Forwarded-Proto", url.protocol.replace(":", ""));
  headers.set("X-Forwarded-Host", url.host);

  const hasBody = !["GET", "HEAD"].includes(request.method);
  try {
    return await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      redirect: "manual",
    });
  } catch {
    return errorResponse(502, "api_unreachable",
      "The API could not be reached. It may be waking up; please try again in a minute.");
  }
}

export async function servePage(request, env) {
  const response = await env.ASSETS.fetch(request);
  const secured = new Response(response.body, response);
  for (const [name, value] of Object.entries(PAGE_SECURITY_HEADERS)) {
    secured.headers.set(name, value);
  }
  return secured;
}

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    return isApiPath(pathname) ? proxyToApi(request, env) : servePage(request, env);
  },
};
