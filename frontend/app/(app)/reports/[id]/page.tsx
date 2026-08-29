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
import { formatDate, riskLevelColor, scoreColor } from "@/lib/utils";
import type { Report, ScanDetail } from "@/lib/types";

function SeverityRow({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border last:border-0">
      <span className={`text-xs font-semibold uppercase ${color}`}>{label}</span>
      <span className="text-sm font-bold">{count}</span>
    </div>
  );
}

export default function ReportDetailPage({ params }: { params: { id: string } }) {
  const { token } = useAuth();

  const { data: report, isLoading: loadingReport } = useSWR<Report>(
    token ? `report-${params.id}` : null,
    () => reportApi.get(token!, params.id)
  );

  const { data: scan } = useSWR<ScanDetail>(
    token && report ? `scan-${report.scan_id}` : null,
    () => scanApi.get(token!, report!.scan_id)
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
          {scan?.project_name ?? "Security Report"}
        </h2>
        <p className="text-xs text-muted-foreground">{formatDate(report.created_at)}</p>
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
            <SeverityRow label="Critical" count={report.critical_count}     color="text-red-400" />
            <SeverityRow label="High"     count={report.high_count}         color="text-orange-400" />
            <SeverityRow label="Medium"   count={report.medium_count}       color="text-yellow-400" />
            <SeverityRow label="Low"      count={report.low_count}          color="text-blue-400" />
            <div className="mt-3 pt-3 border-t border-border flex justify-between text-xs text-muted-foreground">
              <span>Total findings</span>
              <span className="font-bold text-foreground">{report.total_findings}</span>
            </div>
          </CardContent>
        </Card>

        {/* Dependency risk */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Dependency Risk</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="text-3xl font-bold">
              {report.vulnerable_dependencies}
              <span className="text-sm font-normal text-muted-foreground">
                {" "}/ {report.total_dependencies}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">vulnerable packages</p>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Dep. risk score</span>
              <span className={`text-sm font-bold ${scoreColor(100 - report.dependency_risk_score)}`}>
                {Math.round(report.dependency_risk_score)}
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
              Release recommendation
            </p>
            <p className="text-sm font-semibold">{report.release_recommendation}</p>
          </div>
          <Badge
            className="ml-auto"
            variant={
              report.risk_level === "low"      ? "default" :
              report.risk_level === "medium"   ? "secondary" : "destructive"
            }
          >
            {report.risk_level} risk
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
