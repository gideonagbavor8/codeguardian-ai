"use client";

import useSWR from "swr";
import Link from "next/link";
import { reportApi, scanApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { ScoreGauge } from "@/components/report/ScoreGauge";
import { AISummaryCard } from "@/components/report/AISummaryCard";
import { formatDate, riskLevelColor } from "@/lib/utils";
import type { Report, ScanDetail } from "@/lib/types";

function SeverityRow({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border last:border-0">
      <span className={`text-xs font-semibold uppercase ${color}`}>{label}</span>
      <span className="text-sm font-bold">{count}</span>
    </div>
  );
}

// Map uppercase backend risk levels to badge variants
function riskBadgeVariant(risk: string): "default" | "secondary" | "destructive" | "outline" {
  switch (risk.toUpperCase()) {
    case "SAFE":
    case "LOW":    return "default";
    case "MEDIUM": return "secondary";
    default:       return "destructive";
  }
}

export default function ReportDetailPage({ params }: { params: { id: string } }) {
  const { token } = useAuth();

  // params.id is the SCAN id — the backend route is GET /reports/{scan_id}
  const { data: report, isLoading: loadingReport } = useSWR<Report>(
    token ? `report-scan-${params.id}` : null,
    () => reportApi.get(token!, params.id)
  );

  // Load the scan so we can show its name in the header
  const { data: scan } = useSWR<ScanDetail>(
    token ? `scan-${params.id}` : null,
    () => scanApi.get(token!, params.id)
  );

  if (loadingReport) {
    return (
      <div className="max-w-5xl mx-auto space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-48" />)}
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="max-w-5xl mx-auto py-12 text-center">
        <p className="text-muted-foreground text-sm">Report not found.</p>
        <Link href="/reports" className="text-xs text-primary hover:underline mt-2 block">
          ← All reports
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <Link href="/reports" className="text-xs text-muted-foreground hover:text-foreground">
          ← All reports
        </Link>
        <h2 className="text-xl font-semibold mt-1">
          {/* API: scan.name, not scan.project_name */}
          {scan?.name ?? "Security Report"}
        </h2>
        {/* API: report.generated_at, not report.created_at */}
        <p className="text-xs text-muted-foreground">{formatDate(report.generated_at)}</p>
      </div>

      {/* Score + breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Gauge */}
        <Card className="flex flex-col items-center justify-center py-6">
          <ScoreGauge report={report} />
        </Card>

        {/* Severity breakdown */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Finding Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <SeverityRow label="Critical" count={report.critical_count} color="text-red-400" />
            <SeverityRow label="High"     count={report.high_count}     color="text-orange-400" />
            <SeverityRow label="Medium"   count={report.medium_count}   color="text-yellow-400" />
            <SeverityRow label="Low"      count={report.low_count}      color="text-blue-400" />
            <div className="mt-3 pt-3 border-t border-border flex justify-between text-xs text-muted-foreground">
              <span>Total security issues</span>
              {/* API: total_security_issues */}
              <span className="font-bold text-foreground">{report.total_security_issues}</span>
            </div>
          </CardContent>
        </Card>

        {/* Dependency risk */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Dependency Risk</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* API: total_dep_issues */}
            <div className="text-3xl font-bold">{report.total_dep_issues}</div>
            <p className="text-xs text-muted-foreground">vulnerable packages</p>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Model used</span>
              <span className="text-xs text-muted-foreground font-mono">
                {report.model_used ?? "—"}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Release recommendation */}
      <Card>
        <CardContent className="py-4 flex items-center gap-4">
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wide font-medium mb-1">
              Risk level
            </p>
            {/* API: risk_level is uppercase e.g. "SAFE", "HIGH" */}
            <p className={`text-sm font-semibold ${riskLevelColor(report.risk_level)}`}>
              {report.risk_level}
            </p>
          </div>
          <Badge className="ml-auto" variant={riskBadgeVariant(report.risk_level)}>
            {report.risk_level}
          </Badge>
        </CardContent>
      </Card>

      {/* AI Summary */}
      <AISummaryCard report={report} />

      {/* Link to full scan */}
      {scan && (
        <div className="text-right">
          <Link href={`/scan/${scan.id}`} className="text-xs text-primary hover:underline">
            View raw scan findings →
          </Link>
        </div>
      )}
    </div>
  );
}
