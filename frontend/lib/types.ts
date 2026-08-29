// ─── Auth ────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  token_type: string;
}

// ─── Scans ───────────────────────────────────────────────────────────────────

export type ScanStatus = "pending" | "running" | "completed" | "failed";
export type ScanType = "upload" | "github";

export interface Scan {
  id: string;
  user_id: string;
  scan_type: ScanType;
  status: ScanStatus;
  project_name: string;
  github_url: string | null;
  branch: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScanDetail extends Scan {
  security_findings: SecurityFinding[];
  dependency_findings: DependencyFinding[];
  report: Report | null;
}

// ─── Findings ────────────────────────────────────────────────────────────────

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface SecurityFinding {
  id: string;
  scan_id: string;
  tool: string;
  rule_id: string;
  severity: Severity;
  title: string;
  description: string;
  file_path: string;
  line_number: number | null;
  code_snippet: string | null;
  fix_suggestion: string | null;
}

export interface DependencyFinding {
  id: string;
  scan_id: string;
  package_name: string;
  installed_version: string;
  severity: Severity;
  vulnerability_id: string;
  description: string;
  fix_version: string | null;
  ecosystem: string;
}

// ─── Reports ─────────────────────────────────────────────────────────────────

export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface Report {
  id: string;
  scan_id: string;
  overall_score: number;
  risk_level: RiskLevel;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  total_findings: number;
  dependency_risk_score: number;
  vulnerable_dependencies: number;
  total_dependencies: number;
  ai_summary: string | null;
  key_risks: string[];
  recommendations: string[];
  release_recommendation: string;
  created_at: string;
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

export interface DashboardStats {
  total_scans: number;
  completed_scans: number;
  average_score: number | null;
  critical_findings: number;
  recent_scans: Scan[];
}

// ─── API helpers ─────────────────────────────────────────────────────────────

export interface ApiError {
  detail: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
