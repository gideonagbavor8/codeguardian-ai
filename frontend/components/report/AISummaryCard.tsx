"use client";

import { Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Report } from "@/lib/types";

export function AISummaryCard({ report }: { report: Report }) {
  // ai_fix_suggestions is the backend field; key_risks/recommendations don't exist
  const hasSummary = Boolean(report.ai_summary);
  if (!hasSummary) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          AI Analysis Summary
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {report.ai_summary && (
          <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-line">
            {report.ai_summary}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
