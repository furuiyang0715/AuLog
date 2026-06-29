const TOKEN_KEY = "aulog_token";

let authToken = localStorage.getItem(TOKEN_KEY) || "";
let onUnauthorized = null;

export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

export function getToken() {
  return authToken;
}

export function setToken(token) {
  authToken = token || "";
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

function parseErrorDetail(data) {
  if (!data || !data.detail) return "请求失败";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail.map((d) => d.msg || String(d)).join("；");
  }
  return String(data.detail);
}

export async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }

  const res = await fetch(`/api${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));

  if (
    res.status === 401 &&
    path !== "/auth/login" &&
    path !== "/auth/register"
  ) {
    setToken("");
    onUnauthorized?.();
    throw new Error(parseErrorDetail(data) || "请重新登录");
  }

  if (!res.ok) {
    throw new Error(parseErrorDetail(data) || res.statusText || "请求失败");
  }

  return data;
}
