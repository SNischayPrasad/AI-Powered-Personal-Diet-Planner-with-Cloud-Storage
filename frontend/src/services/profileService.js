import { apiRequest } from "./apiClient.js";

export function getProfile() {
  return apiRequest("/api/profile");
}

export function updateProfile(profile) {
  return apiRequest("/api/profile", { method: "PUT", body: profile });
}
