"use client";

import { Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Report } from "@/lib/types";

export function AISummaryCard({ report }: { report: Report }) {
  if (!report.ai_summary && report.recommendations.length === 0) return null;

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

        {report.key_risks.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              Key Risks
            </p>
            <ul className="space-y-1">
              {report.key_risks.map((risk, i) => (
                <li key={i} className="text-sm flex items-start gap-2">
                  <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-orange-400 shrink-0" />
                  {risk}
                </li>
              ))}
            </ul>
          </div>
        )}

        {report.recommendations.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              Recommendations
            </p>
            <ul className="space-y-1">
              {report.recommendations.map((rec, i) => (
                <li key={i} className="text-sm flex items-start gap-2">
                  <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-emerald-400 shrink-0" />
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
