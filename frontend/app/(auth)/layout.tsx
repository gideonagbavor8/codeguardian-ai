import type { Metadata } from "next";
import { Shield } from "lucide-react";
import Link from "next/link";

export const metadata: Metadata = { title: "CodeGuardian AI — Auth" };

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background px-4">
      <Link href="/" className="flex items-center gap-2 mb-8">
        <Shield className="h-6 w-6 text-primary" />
        <span className="font-bold text-lg tracking-tight">CodeGuardian AI</span>
      </Link>
      <div className="w-full max-w-sm">{children}</div>
      <p className="mt-8 text-xs text-muted-foreground">
        Secured by IBM watsonx.ai
      </p>
    </div>
  );
}
