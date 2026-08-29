import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import type { Severity, RiskLevel } from "./types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateShort(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

export function severityColor(severity: Severity | string): string {
  switch (severity.toLowerCase()) {
    case "critical": return "text-red-400";
    case "high":     return "text-orange-400";
    case "medium":   return "text-yellow-400";
    case "low":      return "text-blue-400";
    default:         return "text-slate-400";
  }
}

export function severityBadgeVariant(
  severity: Severity | string
): "destructive" | "secondary" | "outline" | "default" {
  switch (severity.toLowerCase()) {
    case "critical": return "destructive";
    case "high":     return "destructive";
    case "medium":   return "secondary";
    default:         return "outline";
  }
}

export function riskLevelColor(risk: RiskLevel | string): string {
  switch (risk.toLowerCase()) {
    case "critical": return "text-red-400";
    case "high":     return "text-orange-400";
    case "medium":   return "text-yellow-400";
    case "low":      return "text-emerald-400";
    default:         return "text-slate-400";
  }
}

export function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-400";
  if (score >= 60) return "text-yellow-400";
  if (score >= 40) return "text-orange-400";
  return "text-red-400";
}

export function scoreLabel(score: number): string {
  if (score >= 80) return "Excellent";
  if (score >= 60) return "Good";
  if (score >= 40) return "Needs Work";
  return "Critical";
}

export function truncate(str: string, maxLen: number): string {
  return str.length > maxLen ? str.slice(0, maxLen) + "…" : str;
}
