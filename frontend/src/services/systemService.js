import { API_BASE_URL, apiRequest } from "./apiClient.js";

// Which database, storage and AI providers this deployment uses (public, no secrets).
export function getSystemStatus() {
  return apiRequest("/api/system/status", { auth: false });
}

// Readiness answers 503 with a body when a dependency is down, so read the body either way.
export async function getReadiness() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/health/ready`);
    return await response.json();
  } catch {
    return { status: "unreachable", checks: {} };
  }
}
