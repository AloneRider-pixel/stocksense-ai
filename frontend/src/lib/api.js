const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

function validationMessage(body) {
  const details = body?.error?.details;
  if (body?.error?.code !== "VALIDATION_ERROR" || !Array.isArray(details) || !details.length) return "";
  const parts = details.slice(0, 3).map((d) => {
    const field = Array.isArray(d.loc) ? d.loc.filter((x) => x !== "body" && x !== "query").join(".") : "";
    const msg = String(d.msg || "is invalid").replace(/^Value error, /, "");
    return field ? field + ": " + msg : msg;
  });
  return "Please fix: " + parts.join("; ") + ".";
}

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
      // Bound each attempt even when a cold start takes several minutes.
      signal: options.signal || AbortSignal.timeout(path === "/auth/login" || path === "/auth/register" ? 75000 : 20000),
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    if (path === "/auth/register") {
      throw new Error("We could not confirm account creation. The request may have reached the server. Try signing in before creating the account again.");
    }
    if (path === "/auth/login") {
      throw new Error("We could not finish signing you in. The server may still be starting, which can take several minutes. Wait a moment and try Sign in again; no automatic retry was sent.");
    }
    if (err.name === "TimeoutError") throw new Error("The server took too long to respond. Please retry.");
    throw err;
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const error = new Error(validationMessage(body) || body?.error?.message || "Request failed");
    error.status = response.status;
    error.code = body?.error?.code || body?.detail?.code || "";
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
