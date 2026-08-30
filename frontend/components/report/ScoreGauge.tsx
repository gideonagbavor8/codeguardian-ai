"use client";

import { cn, scoreColor, scoreLabel, riskLevelColor } from "@/lib/utils";
import type { Report } from "@/lib/types";

interface ScoreGaugeProps {
  report: Report;
}

export function ScoreGauge({ report }: ScoreGaugeProps) {
  const score = Math.round(report.release_readiness_score);
  const circumference = 2 * Math.PI * 54; // r=54
  const offset = circumference - (score / 100) * circumference;

  const strokeColor =
    score >= 80 ? "#34d399" :
    score >= 60 ? "#fbbf24" :
    score >= 40 ? "#fb923c" : "#f87171";

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="140" height="140" viewBox="0 0 140 140">
        {/* Track */}
        <circle
          cx="70" cy="70" r="54"
          fill="none"
          stroke="hsl(var(--muted))"
          strokeWidth="12"
        />
        {/* Progress */}
        <circle
          cx="70" cy="70" r="54"
          fill="none"
          stroke={strokeColor}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 70 70)"
        />
        {/* Score text */}
        <text
          x="70" y="65"
          textAnchor="middle"
          dominantBaseline="middle"
          className="fill-foreground"
          fontSize="28"
          fontWeight="700"
          fill="currentColor"
        >
          {score}
        </text>
        <text
          x="70" y="88"
          textAnchor="middle"
          fontSize="11"
          fill="hsl(var(--muted-foreground))"
        >
          / 100
        </text>
      </svg>
      <div className={cn("text-sm font-semibold", scoreColor(score))}>
        {scoreLabel(score)}
      </div>
      <div className={cn("text-xs font-medium uppercase tracking-wide", riskLevelColor(report.risk_level))}>
        {report.risk_level} risk
      </div>
    </div>
  );
}
