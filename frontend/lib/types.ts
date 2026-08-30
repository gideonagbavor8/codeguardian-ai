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

// Backend uses uppercase status values
export type ScanStatus = "PENDING" | "RUNNING" | "COMPLETE" | "FAILED";
export type SourceType = "SNIPPET" | "UPLOAD" | "GITHUB";

export interface Scan {
  id: string;
  user_id: string;
  name: string | null;
  source_type: SourceType;
  status: ScanStatus;
  language: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface ScanDetail extends Scan {
  security_findings: SecurityFinding[];
  dependency_findings: DependencyFinding[];
  report: Report | null;
}

// ─── Findings ────────────────────────────────────────────────────────────────

export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";

export interface SecurityFinding {
  id: string;
  scan_id: string;
  tool: string;
  rule_id: string | null;
  severity: Severity;
  confidence: string | null;
  file_path: string | null;
  line_number: number | null;
  code_snippet: string | null;
  message: string;           // backend field name
  cwe_id: string | null;
  owasp_category: string | null;
  ai_fix: string | null;
  created_at: string;
}

export interface DependencyFinding {
  id: string;
  scan_id: string;
  package_name: string;
  installed_version: string | null;
  severity: Severity;
  cve_ids: string[] | null;  // backend field name (array)
  description: string | null;
  fixed_version: string | null; // backend field name
  ecosystem: string;
  created_at: string;
}

// ─── Reports ─────────────────────────────────────────────────────────────────

// Backend uses uppercase risk levels
export type RiskLevel = "SAFE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface Report {
  id: string;
  scan_id: string;
  release_readiness_score: number; // backend field name
  risk_level: RiskLevel;
  ai_summary: string | null;
  ai_fix_suggestions: Array<{ index: number; suggestion: string }> | null;
  ai_review_narrative: string | null;
  model_used: string | null;
  total_security_issues: number;   // backend field name
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  total_dep_issues: number;        // backend field name
  generated_at: string;            // backend field name
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
