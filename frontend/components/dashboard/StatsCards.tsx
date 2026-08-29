"use client";

import { Shield, Scan, TrendingUp, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { DashboardStats } from "@/lib/types";

interface StatsCardsProps {
  stats: DashboardStats | null;
  loading: boolean;
}

const cards = [
  {
    key: "total_scans" as const,
    label: "Total Scans",
    icon: Scan,
    format: (s: DashboardStats) => s.total_scans,
    sub: (s: DashboardStats) => `${s.completed_scans} completed`,
  },
  {
    key: "avg_score" as const,
    label: "Average Score",
    icon: TrendingUp,
    format: (s: DashboardStats) =>
      s.average_score !== null ? `${Math.round(s.average_score)}` : "—",
    sub: () => "out of 100",
  },
  {
    key: "critical" as const,
    label: "Critical Findings",
    icon: AlertTriangle,
    format: (s: DashboardStats) => s.critical_findings,
    sub: () => "across all scans",
  },
  {
    key: "shield" as const,
    label: "Projects Protected",
    icon: Shield,
    format: (s: DashboardStats) => s.completed_scans,
    sub: () => "successfully analysed",
  },
];

export function StatsCards({ stats, loading }: StatsCardsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map(({ label, icon: Icon, format, sub }) =>
        loading || !stats ? (
          <Card key={label}>
            <CardHeader className="pb-2">
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-16 mb-1" />
              <Skeleton className="h-3 w-28" />
            </CardContent>
          </Card>
        ) : (
          <Card key={label}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                {label}
              </CardTitle>
              <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{format(stats)}</div>
              <p className="text-xs text-muted-foreground mt-0.5">{sub(stats)}</p>
            </CardContent>
          </Card>
        )
      )}
    </div>
  );
}
