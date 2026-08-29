"use client";

import useSWR from "swr";
import Link from "next/link";
import { Plus } from "lucide-react";
import { dashboardApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatsCards } from "@/components/dashboard/StatsCards";
import { RecentScansTable } from "@/components/dashboard/RecentScansTable";
import type { DashboardStats } from "@/lib/types";

export default function DashboardPage() {
  const { token } = useAuth();

  const { data: stats, isLoading } = useSWR<DashboardStats>(
    token ? "dashboard-stats" : null,
    () => dashboardApi.stats(token!)
  );

  const recentScans = stats?.recent_scans ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Dashboard</h2>
          <p className="text-sm text-muted-foreground">Security overview across all your projects</p>
        </div>
        <Button asChild size="sm">
          <Link href="/scan/new">
            <Plus className="h-4 w-4 mr-1" /> New Scan
          </Link>
        </Button>
      </div>

      {/* Stats */}
      <StatsCards stats={stats ?? null} loading={isLoading} />

      {/* Recent scans */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Recent Scans</CardTitle>
          <Link href="/reports" className="text-xs text-primary hover:underline">
            View all
          </Link>
        </CardHeader>
        <CardContent>
          <RecentScansTable scans={recentScans} loading={isLoading} />
        </CardContent>
      </Card>
    </div>
  );
}
