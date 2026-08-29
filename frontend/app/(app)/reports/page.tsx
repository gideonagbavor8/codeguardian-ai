"use client";

import useSWR from "swr";
import Link from "next/link";
import { reportApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { formatDate, scoreColor, riskLevelColor } from "@/lib/utils";
import type { Report } from "@/lib/types";

export default function ReportsListPage() {
  const { token } = useAuth();

  const { data: reports, isLoading } = useSWR<Report[]>(
    token ? "reports-list" : null,
    () => reportApi.list(token!)
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Reports</h2>
        <p className="text-sm text-muted-foreground">All generated release readiness reports</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">All Reports</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : !reports?.length ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              No reports yet.{" "}
              <Link href="/scan/new" className="text-primary hover:underline">
                Run a scan →
              </Link>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Report ID</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Risk</TableHead>
                  <TableHead>Findings</TableHead>
                  <TableHead>Dep. Vulns</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {reports.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {r.id.slice(0, 8)}…
                    </TableCell>
                    <TableCell>
                      <span className={`font-bold ${scoreColor(r.overall_score)}`}>
                        {Math.round(r.overall_score)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={`text-xs font-semibold uppercase ${riskLevelColor(r.risk_level)}`}>
                        {r.risk_level}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm">{r.total_findings}</TableCell>
                    <TableCell className="text-sm">{r.vulnerable_dependencies}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(r.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Link
                        href={`/reports/${r.id}`}
                        className="text-xs text-primary hover:underline"
                      >
                        View →
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
