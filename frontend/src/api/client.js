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

export async function apiDownload(path, fallbackFilename = "aulog-backup.json") {
  const headers = {};
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }

  const res = await fetch(`/api${path}`, { headers });
  if (res.status === 401) {
    setToken("");
    onUnauthorized?.();
    throw new Error("请重新登录");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(parseErrorDetail(data) || res.statusText || "下载失败");
  }

  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] || fallbackFilename;

  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function apiUpload(path, file) {
  const form = new FormData();
  form.append("file", file);

  const headers = {};
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }

  const res = await fetch(`/api${path}`, { method: "POST", headers, body: form });
  const data = await res.json().catch(() => ({}));

  if (res.status === 401) {
    setToken("");
    onUnauthorized?.();
    throw new Error(parseErrorDetail(data) || "请重新登录");
  }
  if (!res.ok) {
    throw new Error(parseErrorDetail(data) || res.statusText || "上传失败");
  }

  return data;
}
