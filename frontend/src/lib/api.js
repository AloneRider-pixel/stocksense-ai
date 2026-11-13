const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

export async function api(path, options = {}) {
  const token = localStorage.getItem("stocksense_token");
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) headers.Authorization = "Bearer " + token;

  let response;
  try {
    response = await fetch(API_BASE + path, {
      ...options, headers,
      signal: options.signal || AbortSignal.timeout(20000),
    });
  } catch (err) {
    if (err.name === "TimeoutError") throw new Error("The server took too long to respond. Please retry.");
    throw err;
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const error = new Error(body?.error?.message || "Request failed");
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export function setToken(token) {
  localStorage.setItem("stocksense_token", token);
}

export function clearToken() {
  localStorage.removeItem("stocksense_token");
}
