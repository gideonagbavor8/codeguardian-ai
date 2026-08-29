import type {
  AuthTokens,
  User,
  Scan,
  ScanDetail,
  Report,
  DashboardStats,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─── Low-level fetch wrapper ──────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options: RequestInit & { token?: string } = {}
): Promise<T> {
  const { token, ...init } = options;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...init, headers });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore parse error
    }
    throw new Error(detail);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// FormData helper (no Content-Type header — browser sets multipart boundary)
async function apiUpload<T>(
  path: string,
  formData: FormData,
  token: string
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const authApi = {
  register(email: string, password: string, fullName: string) {
    return apiFetch<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
  },

  login(email: string, password: string) {
    // FastAPI OAuth2 expects form-encoded body
    const form = new URLSearchParams({ username: email, password });
    return fetch(`${BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    }).then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `HTTP ${res.status}`);
      }
      return res.json() as Promise<AuthTokens>;
    });
  },

  me(token: string) {
    return apiFetch<User>("/auth/me", { token });
  },
};

// ─── Scans ────────────────────────────────────────────────────────────────────

export const scanApi = {
  list(token: string) {
    return apiFetch<Scan[]>("/scans", { token });
  },

  get(token: string, scanId: string) {
    return apiFetch<ScanDetail>(`/scans/${scanId}`, { token });
  },

  uploadFile(token: string, file: File, projectName: string) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("project_name", projectName);
    return apiUpload<Scan>("/scans/upload", fd, token);
  },

  scanGithub(token: string, githubUrl: string, branch: string, projectName: string) {
    return apiFetch<Scan>("/scans/github", {
      method: "POST",
      token,
      body: JSON.stringify({ github_url: githubUrl, branch, project_name: projectName }),
    });
  },

  delete(token: string, scanId: string) {
    return apiFetch<void>(`/scans/${scanId}`, { method: "DELETE", token });
  },
};

// ─── Reports ──────────────────────────────────────────────────────────────────

export const reportApi = {
  list(token: string) {
    return apiFetch<Report[]>("/reports", { token });
  },

  get(token: string, reportId: string) {
    return apiFetch<Report>(`/reports/${reportId}`, { token });
  },

  getByScan(token: string, scanId: string) {
    return apiFetch<Report>(`/reports/scan/${scanId}`, { token });
  },
};

// ─── Dashboard ────────────────────────────────────────────────────────────────

export const dashboardApi = {
  stats(token: string) {
    return apiFetch<DashboardStats>("/dashboard/stats", { token });
  },
};
