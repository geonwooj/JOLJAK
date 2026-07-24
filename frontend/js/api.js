const API_BASE = "http://15.164.30.127:8080";

window.ApiClient = {
  token() { return localStorage.getItem("token") || ""; },
  clearSession() {
    localStorage.removeItem("token");
    localStorage.removeItem("userName");
  },
  async request(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const token = this.token();
    if (token && !headers.has("Authorization")) headers.set("Authorization", `Bearer ${token}`);

    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    const type = response.headers.get("content-type") || "";
    const data = type.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      if (response.status === 401) this.clearSession();
      throw new Error(typeof data === "string" ? data : data?.message || "요청 처리에 실패했습니다.");
    }
    return data;
  },
  get(path) { return this.request(path); },
  post(path, body) { return this.request(path, { method: "POST", body: JSON.stringify(body) }); },
  patch(path, body) { return this.request(path, { method: "PATCH", body: JSON.stringify(body) }); },
  delete(path) { return this.request(path, { method: "DELETE" }); },
};
