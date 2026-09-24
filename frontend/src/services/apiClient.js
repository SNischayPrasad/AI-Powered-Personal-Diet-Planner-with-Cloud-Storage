// Thin wrapper around fetch() used by every service module.
//
// * Attaches the JWT as `Authorization: Bearer <token>` (the API is stateless — the token
//   is the session).
// * Converts the API's error envelope {error: {code, message, request_id}} into ApiError.
// * Tells the app when a logged-in request is rejected with 401 (expired/revoked session).
//
// Base URL: empty in development (Vite proxies /api to FastAPI) and when the frontend and
// API share a domain; set VITE_API_BASE_URL when the API is hosted separately.

export const API_BASE_URL = (import.meta.env?.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

const TOKEN_KEY = "dietplanner.token";
let memoryToken = null; // fallback when localStorage is unavailable (private mode, tests)

// Security note: localStorage is readable by any script on this origin, so XSS must be
// prevented (React escapes output; the API sends a strict CSP). The token is short-lived
// and can be revoked server-side on logout. See docs/17-security.md for the trade-offs.
export const tokenStore = {
  get() {
    try {
      return globalThis.localStorage?.getItem(TOKEN_KEY) ?? memoryToken;
    } catch {
      return memoryToken;
    }
  },
  set(token) {
    memoryToken = token;
    try {
      globalThis.localStorage?.setItem(TOKEN_KEY, token);
    } catch {
      /* storage blocked: keep the in-memory copy */
    }
  },
  clear() {
    memoryToken = null;
    try {
      globalThis.localStorage?.removeItem(TOKEN_KEY);
    } catch {
      /* nothing to clear */
    }
  },
};

let unauthorizedHandler = null;

export function onUnauthorized(handler) {
  unauthorizedHandler = handler;
}

export class ApiError extends Error {
  constructor({ status, code, message, details = null, requestId = null }) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
    this.fieldErrors = {};
    for (const detail of Array.isArray(details) ? details : []) {
      const field = String(detail.field ?? "").split(".")[0];
      if (field && !this.fieldErrors[field]) this.fieldErrors[field] = detail.message;
    }
  }
}

const FALLBACK_MESSAGES = {
  500: "Something went wrong on the server. Please try again.",
  502: "The service is temporarily unavailable. Please try again shortly.",
  503: "The service is temporarily unavailable. Please try again shortly.",
  504: "The server took too long to respond. Please try again.",
};

async function toApiError(response) {
  let envelope = null;
  try {
    envelope = (await response.json())?.error ?? null;
  } catch {
    /* not JSON (e.g. a proxy error page) */
  }
  return new ApiError({
    status: response.status,
    code: envelope?.code ?? "http_error",
    message: envelope?.message ?? FALLBACK_MESSAGES[response.status] ?? `Request failed (${response.status}).`,
    details: envelope?.details ?? null,
    requestId: envelope?.request_id ?? response.headers.get("X-Request-ID"),
  });
}

export function filenameFromDisposition(header) {
  if (!header) return null;
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(header);
  return match ? decodeURIComponent(match[1]) : null;
}

export async function apiRequest(
  path,
  { method = "GET", body, formData, auth = true, responseType = "json" } = {},
) {
  const headers = {};
  const token = auth ? tokenStore.get() : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  let payload;
  if (formData) {
    payload = formData; // the browser sets the multipart boundary itself
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError({
      status: 0,
      code: "network_error",
      message: "Can't reach the server. Check your connection and that the API is running.",
    });
  }

  if (!response.ok) {
    const error = await toApiError(response);
    if (response.status === 401 && token && unauthorizedHandler) unauthorizedHandler(error.code);
    throw error;
  }
  if (response.status === 204) return null;
  if (responseType === "blob") {
    return {
      blob: await response.blob(),
      filename: filenameFromDisposition(response.headers.get("Content-Disposition")),
    };
  }
  return response.json();
}
