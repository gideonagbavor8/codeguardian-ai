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

    if (typeof body.detail === "string") {
      detail = body.detail;
    } else if (Array.isArray(body.detail)) {
      detail = body.detail
        .map((item: { msg?: string }) => item.msg ?? "Invalid request")
        .join(", ");
    }
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
  return apiFetch<AuthTokens>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
},

  me(token: string) {
    return apiFetch<User>("/auth/me", { token });
  },
};

// ─── Scans ────────────────────────────────────────────────────────────────────

export const scanApi = {
  list(token: string) {
    // Backend returns ScanListResponse: { items, total, page, limit }
    return apiFetch<{ items: Scan[]; total: number; page: number; limit: number }>("/scans", { token });
  },

  get(token: string, scanId: string) {
    return apiFetch<ScanDetail>(`/scans/${scanId}`, { token });
  },

  uploadFile(token: string, file: File, projectName: string) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("name", projectName);
  return apiUpload<{
    scan_id: string;
    status: string;
    poll_url: string;
  }>("/scans/upload", fd, token);
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
// Backend routes: GET /reports/{scan_id}  (keyed on SCAN id, not report id)
//                 GET /reports/{scan_id}/findings

export const reportApi = {
  // Fetch report by the scan's UUID (backend key)
  getByScanId(token: string, scanId: string) {
    return apiFetch<Report>(`/reports/${scanId}`, { token });
  },

  // Convenience alias kept for call sites that already have the scan_id
  get(token: string, scanId: string) {
    return apiFetch<Report>(`/reports/${scanId}`, { token });
  },
};

// ─── Dashboard ────────────────────────────────────────────────────────────────

export const dashboardApi = {
  stats(token: string) {
    return apiFetch<DashboardStats>("/dashboard/stats", { token });
  },
};
