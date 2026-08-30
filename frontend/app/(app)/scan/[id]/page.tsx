"use client";

import Link from "next/link";
import { Loader2, CheckCircle, XCircle, Clock, FileText } from "lucide-react";
import { useScanStatus } from "@/hooks/use-scan-status";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { formatDate, severityColor, scoreColor, riskLevelColor } from "@/lib/utils";
import type { ScanStatus } from "@/lib/types";

// Backend uses uppercase status values
const StatusIcon = ({ status }: { status: ScanStatus }) => {
  switch (status) {
    case "COMPLETE": return <CheckCircle className="h-5 w-5 text-emerald-400" />;
    case "FAILED":   return <XCircle className="h-5 w-5 text-red-400" />;
    case "RUNNING":  return <Loader2 className="h-5 w-5 text-primary animate-spin" />;
    default:         return <Clock className="h-5 w-5 text-muted-foreground" />;
  }
};

const statusBadgeVariant = (status: ScanStatus) => {
  switch (status) {
    case "COMPLETE": return "default" as const;
    case "FAILED":   return "destructive" as const;
    default:         return "secondary" as const;
  }
};

export default function ScanDetailPage({ params }: { params: { id: string } }) {
  const { scan, error } = useScanStatus(params.id);

  if (error) {
    return (
      <div className="max-w-3xl mx-auto py-12 text-center">
        <p className="text-destructive text-sm">{error}</p>
        <Button asChild variant="outline" size="sm" className="mt-4">
          <Link href="/dashboard">← Back</Link>
        </Button>
      </div>
    );
  }

  if (!scan) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const isRunning = scan.status === "PENDING" || scan.status === "RUNNING";
  const isComplete = scan.status === "COMPLETE";
  const isFailed = scan.status === "FAILED";

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link href="/dashboard" className="text-xs text-muted-foreground hover:text-foreground">
            ← Dashboard
          </Link>
          {/* API returns `name`, not `project_name` */}
          <h2 className="text-xl font-semibold mt-1">{scan.name ?? "Unnamed scan"}</h2>
          <p className="text-xs text-muted-foreground">
            {formatDate(scan.created_at)}
            {scan.language && (
              <span className="ml-2 uppercase text-muted-foreground/60">{scan.language}</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <StatusIcon status={scan.status} />
            <Badge variant={statusBadgeVariant(scan.status)}>
              {scan.status}
            </Badge>
          </div>
          {isComplete && scan.report && (
            <Button asChild size="sm">
              {/* Backend route is keyed on scan_id, not report.id */}
              <Link href={`/reports/${scan.id}`}>
                <FileText className="h-4 w-4 mr-1" /> View Report
              </Link>
            </Button>
          )}
        </div>
      </div>

      {/* Report summary card — shown when complete */}
      {isComplete && scan.report && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Report Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-muted-foreground mb-1">Score</p>
                {/* API: release_readiness_score */}
                <p className={`text-2xl font-bold ${scoreColor(scan.report.release_readiness_score)}`}>
                  {scan.report.release_readiness_score}
                  <span className="text-sm font-normal text-muted-foreground">/100</span>
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Risk level</p>
                {/* API: risk_level is uppercase e.g. "SAFE", "HIGH" */}
                <p className={`text-sm font-semibold ${riskLevelColor(scan.report.risk_level)}`}>
                  {scan.report.risk_level}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Security issues</p>
                {/* API: total_security_issues */}
                <p className="text-2xl font-bold">{scan.report.total_security_issues}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Dep. issues</p>
                {/* API: total_dep_issues */}
                <p className="text-2xl font-bold">{scan.report.total_dep_issues}</p>
              </div>
            </div>

            {scan.report.ai_summary && (
              <div className="mt-4 pt-4 border-t border-border">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                  AI Summary
                </p>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {scan.report.ai_summary}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Running state */}
      {isRunning && (
        <Card>
          <CardContent className="py-10 flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 text-primary animate-spin" />
            <p className="text-sm text-muted-foreground">
              {scan.status === "PENDING" ? "Queued — starting soon…" : "Running security scan…"}
            </p>
            <p className="text-xs text-muted-foreground">This usually takes 15–60 seconds</p>
          </CardContent>
        </Card>
      )}

      {/* Error */}
      {isFailed && scan.error_message && (
        <Card>
          <CardContent className="py-6">
            <p className="text-sm text-destructive font-medium">Scan failed</p>
            <p className="text-xs text-muted-foreground mt-1">{scan.error_message}</p>
          </CardContent>
        </Card>
      )}

      {/* Security findings */}
      {(scan.security_findings?.length ?? 0) > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Security Findings ({scan.security_findings.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Severity</TableHead>
                  <TableHead>Message</TableHead>
                  <TableHead>File</TableHead>
                  <TableHead>Tool</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {scan.security_findings.map((f) => (
                  <TableRow key={f.id}>
                    <TableCell>
                      <span className={`text-xs font-semibold uppercase ${severityColor(f.severity)}`}>
                        {f.severity}
                      </span>
                    </TableCell>
                    <TableCell>
                      {/* API returns `message`, not `title`/`description` */}
                      <div className="text-sm">{f.message}</div>
                      {f.cwe_id && (
                        <div className="text-xs text-muted-foreground mt-0.5">{f.cwe_id}</div>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground font-mono">
                      {f.file_path ?? "—"}
                      {f.line_number ? `:${f.line_number}` : ""}
                    </TableCell>
                    <TableCell className="text-xs uppercase text-muted-foreground">{f.tool}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Dependency findings */}
      {(scan.dependency_findings?.length ?? 0) > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Vulnerable Dependencies ({scan.dependency_findings.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Package</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>CVEs</TableHead>
                  <TableHead>Fix</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {scan.dependency_findings.map((d) => (
                  <TableRow key={d.id}>
                    <TableCell className="font-medium text-sm">{d.package_name}</TableCell>
                    <TableCell className="text-xs font-mono text-muted-foreground">
                      {d.installed_version ?? "—"}
                    </TableCell>
                    <TableCell>
                      <span className={`text-xs font-semibold uppercase ${severityColor(d.severity)}`}>
                        {d.severity}
                      </span>
                    </TableCell>
                    {/* API: cve_ids is string[], not a single vulnerability_id */}
                    <TableCell className="text-xs text-muted-foreground">
                      {d.cve_ids?.join(", ") ?? "—"}
                    </TableCell>
                    {/* API: fixed_version, not fix_version */}
                    <TableCell className="text-xs text-emerald-400 font-mono">
                      {d.fixed_version ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Completed but no findings */}
      {isComplete &&
        (scan.security_findings?.length ?? 0) === 0 &&
        (scan.dependency_findings?.length ?? 0) === 0 && (
          <Card>
            <CardContent className="py-10 text-center">
              <CheckCircle className="h-8 w-8 text-emerald-400 mx-auto mb-3" />
              <p className="text-sm font-medium">No issues found</p>
              <p className="text-xs text-muted-foreground mt-1">
                Your code passed all security checks.
              </p>
            </CardContent>
          </Card>
        )}
    </div>
  );
}
