const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

export async function api(path, options = {}) {
  const token = localStorage.getItem("stocksense_token");
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) headers.Authorization = "Bearer " + token;

  const response = await fetch(API_BASE + path, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message || "Request failed");
  }
  return response.json();
}

export function setToken(token) {
  localStorage.setItem("stocksense_token", token);
}

export function clearToken() {
  localStorage.removeItem("stocksense_token");
}
