"use client";

import useSWR from "swr";
import Link from "next/link";
import { scanApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { formatDate } from "@/lib/utils";
import type { Scan } from "@/lib/types";

export default function ReportsListPage() {
  const { token } = useAuth();

  // Backend has no GET /reports list endpoint.
  // Reports are fetched individually via GET /reports/{scan_id}.
  // Here we list COMPLETE scans — each links to /reports/{scan.id}.
  const { data, isLoading } = useSWR(
    token ? "scans-complete" : null,
    () => scanApi.list(token!)
  );

  const completedScans: Scan[] = (data?.items ?? []).filter(
    (s) => s.status === "COMPLETE"
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Reports</h2>
        <p className="text-sm text-muted-foreground">All generated release readiness reports</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Completed Scans</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : completedScans.length === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              No completed scans yet.{" "}
              <Link href="/scan/new" className="text-primary hover:underline">
                Run a scan →
              </Link>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Project</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Completed</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {completedScans.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="font-medium text-sm">{s.name ?? "—"}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs uppercase">
                        {s.source_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {s.completed_at ? formatDate(s.completed_at) : formatDate(s.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      {/* Route uses scan id — backend: GET /reports/{scan_id} */}
                      <Link
                        href={`/reports/${s.id}`}
                        className="text-xs text-primary hover:underline"
                      >
                        View report →
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
