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
import { formatDate, severityColor } from "@/lib/utils";
import type { ScanStatus } from "@/lib/types";

const StatusIcon = ({ status }: { status: ScanStatus }) => {
  switch (status) {
    case "completed": return <CheckCircle className="h-5 w-5 text-emerald-400" />;
    case "failed":    return <XCircle className="h-5 w-5 text-red-400" />;
    case "running":   return <Loader2 className="h-5 w-5 text-primary animate-spin" />;
    default:          return <Clock className="h-5 w-5 text-muted-foreground" />;
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

  const isRunning = scan.status === "pending" || scan.status === "running";

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link href="/dashboard" className="text-xs text-muted-foreground hover:text-foreground">
            ← Dashboard
          </Link>
          <h2 className="text-xl font-semibold mt-1">{scan.project_name}</h2>
          <p className="text-xs text-muted-foreground">{formatDate(scan.created_at)}</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <StatusIcon status={scan.status} />
            <Badge
              variant={
                scan.status === "completed" ? "default" :
                scan.status === "failed"    ? "destructive" : "secondary"
              }
            >
              {scan.status}
            </Badge>
          </div>
          {scan.status === "completed" && scan.report && (
            <Button asChild size="sm">
              <Link href={`/reports/${scan.report.id}`}>
                <FileText className="h-4 w-4 mr-1" /> View Report
              </Link>
            </Button>
          )}
        </div>
      </div>

      {/* Running state */}
      {isRunning && (
        <Card>
          <CardContent className="py-10 flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 text-primary animate-spin" />
            <p className="text-sm text-muted-foreground">
              {scan.status === "pending" ? "Queued — starting soon…" : "Running security scan…"}
            </p>
            <p className="text-xs text-muted-foreground">This usually takes 15–60 seconds</p>
          </CardContent>
        </Card>
      )}

      {/* Error */}
      {scan.status === "failed" && scan.error_message && (
        <Card>
          <CardContent className="py-6">
            <p className="text-sm text-destructive font-medium">Scan failed</p>
            <p className="text-xs text-muted-foreground mt-1">{scan.error_message}</p>
          </CardContent>
        </Card>
      )}

      {/* Security findings */}
      {scan.security_findings.length > 0 && (
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
                  <TableHead>Title</TableHead>
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
                      <div className="font-medium text-sm">{f.title}</div>
                      {f.description && (
                        <div className="text-xs text-muted-foreground line-clamp-1 mt-0.5">
                          {f.description}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground font-mono">
                      {f.file_path}
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
      {scan.dependency_findings.length > 0 && (
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
                  <TableHead>CVE / ID</TableHead>
                  <TableHead>Fix</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {scan.dependency_findings.map((d) => (
                  <TableRow key={d.id}>
                    <TableCell className="font-medium text-sm">{d.package_name}</TableCell>
                    <TableCell className="text-xs font-mono text-muted-foreground">
                      {d.installed_version}
                    </TableCell>
                    <TableCell>
                      <span className={`text-xs font-semibold uppercase ${severityColor(d.severity)}`}>
                        {d.severity}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{d.vulnerability_id}</TableCell>
                    <TableCell className="text-xs text-emerald-400 font-mono">
                      {d.fix_version ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Completed but no findings */}
      {scan.status === "completed" &&
        scan.security_findings.length === 0 &&
        scan.dependency_findings.length === 0 && (
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
