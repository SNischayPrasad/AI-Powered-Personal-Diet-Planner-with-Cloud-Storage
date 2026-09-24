import { apiRequest } from "./apiClient.js";

// Optional overrides: { dietary_preference, goal, allergies, cuisine_preference }.
export function generatePlan(overrides = {}) {
  return apiRequest("/api/generate-plan", { method: "POST", body: overrides });
}

export function listPlans({ limit = 20, offset = 0 } = {}) {
  return apiRequest(`/api/plans?limit=${limit}&offset=${offset}`);
}

export function getPlan(planId) {
  return apiRequest(`/api/plans/${encodeURIComponent(planId)}`);
}

export function deletePlan(planId) {
  return apiRequest(`/api/plans/${encodeURIComponent(planId)}`, { method: "DELETE" });
}

// Returns { blob, filename } for a JSON or text export of the plan.
export function downloadPlan(planId, format) {
  return apiRequest(`/api/plans/${encodeURIComponent(planId)}/export?format=${format}`, {
    responseType: "blob",
  });
}

// Stores an export in cloud object storage; it then appears on the Cloud files page.
export function savePlanToCloud(planId, format) {
  return apiRequest(`/api/plans/${encodeURIComponent(planId)}/save-to-cloud?format=${format}`, {
    method: "POST",
  });
}
