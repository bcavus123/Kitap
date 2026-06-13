// API istemcisi: fetch sarmalayıcı + token yönetimi (aynı origin → /api/v1).
const BASE = "/api/v1";

export function getToken() {
  return localStorage.getItem("ky_token") || "";
}
export function setToken(t) {
  if (t) localStorage.setItem("ky_token", t);
  else localStorage.removeItem("ky_token");
}

export async function api(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  const t = getToken();
  if (t) headers.Authorization = "Bearer " + t;

  const res = await fetch(BASE + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  let data = null;
  const txt = await res.text();
  if (txt) {
    try {
      data = JSON.parse(txt);
    } catch {
      data = txt;
    }
  }
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : res.statusText;
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

// WebSocket URL'i (aynı host, ws/wss)
export function wsUrl(projectId) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/api/v1/ws/projects/${projectId}?token=${encodeURIComponent(getToken())}`;
}
