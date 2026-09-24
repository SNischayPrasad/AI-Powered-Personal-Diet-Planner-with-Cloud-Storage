import { apiRequest } from "./apiClient.js";

// POST /api/register → { access_token, token_type, expires_in, user }
export function register({ name, email, password }) {
  return apiRequest("/api/register", { method: "POST", body: { name, email, password }, auth: false });
}

// POST /api/login → { access_token, token_type, expires_in, user }
export function login({ email, password }) {
  return apiRequest("/api/login", { method: "POST", body: { email, password }, auth: false });
}

// POST /api/logout → revokes the current token on the server
export function logout() {
  return apiRequest("/api/logout", { method: "POST" });
}
