"use client";

import Link from "next/link";
import { formatDate } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import type { Scan, ScanStatus } from "@/lib/types";

// Backend uses uppercase status values
const statusVariant: Record<ScanStatus, "default" | "secondary" | "destructive" | "outline"> = {
  COMPLETE: "default",
  RUNNING:  "secondary",
  PENDING:  "outline",
  FAILED:   "destructive",
};

interface RecentScansTableProps {
  scans: Scan[];
  loading: boolean;
}

export function RecentScansTable({ scans, loading }: RecentScansTableProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (scans.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground text-sm">
        No scans yet.{" "}
        <Link href="/scan/new" className="text-primary hover:underline">
          Run your first scan →
        </Link>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Project</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Date</TableHead>
          <TableHead />
        </TableRow>
      </TableHeader>
      <TableBody>
        {scans.map((scan) => (
          <TableRow key={scan.id}>
            {/* API: `name`, not `project_name` */}
            <TableCell className="font-medium">{scan.name ?? "—"}</TableCell>
            <TableCell>
              <Badge variant={statusVariant[scan.status]}>{scan.status}</Badge>
            </TableCell>
            {/* API: `source_type`, not `scan_type` */}
            <TableCell className="text-muted-foreground text-xs uppercase">{scan.source_type}</TableCell>
            <TableCell className="text-muted-foreground text-xs">{formatDate(scan.created_at)}</TableCell>
            <TableCell className="text-right">
              <Link
                href={`/scan/${scan.id}`}
                className="text-xs text-primary hover:underline"
              >
                View →
              </Link>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
