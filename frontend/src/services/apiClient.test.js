import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiRequest, filenameFromDisposition, onUnauthorized, tokenStore } from "./apiClient.js";

function jsonResponse(status, body, headers = {}) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

describe("apiRequest", () => {
  let fetchMock;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    tokenStore.clear();
    onUnauthorized(null);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends JSON bodies and parses JSON responses", async () => {
    fetchMock.mockResolvedValue(jsonResponse(201, { id: "p1" }));

    const result = await apiRequest("/api/generate-plan", { method: "POST", body: { goal: "fitness" } });

    expect(result).toEqual({ id: "p1" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/generate-plan");
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ goal: "fitness" });
  });

  it("attaches the stored bearer token", async () => {
    tokenStore.set("abc.def.ghi");
    fetchMock.mockResolvedValue(jsonResponse(200, {}));

    await apiRequest("/api/profile");

    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer abc.def.ghi");
  });

  it("does not attach a token to public requests", async () => {
    tokenStore.set("abc.def.ghi");
    fetchMock.mockResolvedValue(jsonResponse(200, {}));

    await apiRequest("/api/login", { method: "POST", body: {}, auth: false });

    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined();
  });

  it("turns the API error envelope into an ApiError", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(409, {
        error: {
          code: "email_already_registered",
          message: "An account with this email already exists.",
          request_id: "req-123",
        },
      }),
    );

    const error = await apiRequest("/api/register", { method: "POST", body: {} }).catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(409);
    expect(error.code).toBe("email_already_registered");
    expect(error.message).toBe("An account with this email already exists.");
    expect(error.requestId).toBe("req-123");
  });

  it("keeps field-level validation details", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(422, {
        error: {
          code: "validation_error",
          message: "Invalid value for 'age'",
          details: [{ field: "age", message: "Input should be greater than or equal to 18" }],
        },
      }),
    );

    const error = await apiRequest("/api/profile", { method: "PUT", body: {} }).catch((e) => e);

    expect(error.fieldErrors).toEqual({ age: "Input should be greater than or equal to 18" });
  });

  it("reports network failures with a helpful message", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    const error = await apiRequest("/api/health").catch((e) => e);

    expect(error.code).toBe("network_error");
    expect(error.status).toBe(0);
  });

  it("returns null for 204 No Content", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    expect(await apiRequest("/api/plans/p1", { method: "DELETE" })).toBeNull();
  });

  it("notifies the app when a logged-in request comes back 401", async () => {
    const handler = vi.fn();
    onUnauthorized(handler);
    tokenStore.set("expired.token.value");
    fetchMock.mockResolvedValue(
      jsonResponse(401, { error: { code: "token_expired", message: "Your session has expired." } }),
    );

    await apiRequest("/api/profile").catch(() => {});

    expect(handler).toHaveBeenCalledWith("token_expired");
  });

  it("returns a blob and the server-provided filename for downloads", async () => {
    fetchMock.mockResolvedValue(
      new Response("plan text", {
        status: 200,
        headers: { "Content-Disposition": 'attachment; filename="diet-plan-2026-09-24-3ef00471.txt"' },
      }),
    );

    const { blob, filename } = await apiRequest("/api/plans/p1/export?format=txt", { responseType: "blob" });

    expect(await blob.text()).toBe("plan text");
    expect(filename).toBe("diet-plan-2026-09-24-3ef00471.txt");
  });
});

describe("filenameFromDisposition", () => {
  it("extracts quoted filenames and tolerates missing headers", () => {
    expect(filenameFromDisposition('attachment; filename="my lunch.png"')).toBe("my lunch.png");
    expect(filenameFromDisposition(null)).toBeNull();
  });
});
