import { apiRequest } from "./apiClient.js";

export function listFiles() {
  return apiRequest("/api/files");
}

export function uploadFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest("/api/upload", { method: "POST", formData });
}

// Files are private, so they are fetched with the auth header and returned as a blob
// (used for image previews and downloads) instead of being linked directly.
export function downloadFile(fileId) {
  return apiRequest(`/api/files/${encodeURIComponent(fileId)}/download`, { responseType: "blob" });
}

export function deleteFile(fileId) {
  return apiRequest(`/api/files/${encodeURIComponent(fileId)}`, { method: "DELETE" });
}
