import Link from "next/link";
import { Shield, Zap, Eye, FileCheck } from "lucide-react";

const features = [
  {
    icon: Shield,
    title: "Security Scanning",
    desc: "Bandit + Semgrep detect vulnerabilities across your entire codebase in seconds.",
  },
  {
    icon: Eye,
    title: "Dependency Audit",
    desc: "pip-audit and npm audit surface vulnerable packages with fix guidance.",
  },
  {
    icon: Zap,
    title: "AI Code Review",
    desc: "IBM watsonx.ai synthesises findings into actionable developer summaries.",
  },
  {
    icon: FileCheck,
    title: "Release Readiness",
    desc: "Composite risk score tells you instantly whether your code is ship-ready.",
  },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-background flex flex-col">
      {/* Nav */}
      <nav className="border-b border-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="h-6 w-6 text-primary" />
          <span className="font-bold text-lg tracking-tight">CodeGuardian AI</span>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Sign in
          </Link>
          <Link
            href="/register"
            className="text-sm bg-primary text-primary-foreground px-4 py-2 rounded-md hover:bg-primary/90 transition-colors"
          >
            Get started
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="flex-1 flex flex-col items-center justify-center text-center px-6 py-24 gap-6">
        <div className="inline-flex items-center gap-2 bg-primary/10 text-primary text-xs font-medium px-3 py-1 rounded-full border border-primary/20">
          Powered by IBM watsonx.ai
        </div>
        <h1 className="text-5xl font-bold tracking-tight max-w-3xl leading-tight">
          AI-powered security analysis for{" "}
          <span className="text-primary">every commit</span>
        </h1>
        <p className="text-muted-foreground text-lg max-w-xl">
          Scan your code, audit dependencies, and get an AI-generated release
          readiness report — in under 60 seconds.
        </p>
        <div className="flex items-center gap-4 mt-2">
          <Link
            href="/register"
            className="bg-primary text-primary-foreground px-6 py-3 rounded-md font-medium hover:bg-primary/90 transition-colors"
          >
            Start scanning free
          </Link>
          <Link
            href="/login"
            className="text-muted-foreground hover:text-foreground text-sm transition-colors"
          >
            Sign in →
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="border-t border-border px-6 py-16">
        <div className="max-w-5xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map(({ icon: Icon, title, desc }) => (
            <div
              key={title}
              className="bg-card border border-border rounded-lg p-5 flex flex-col gap-3"
            >
              <Icon className="h-5 w-5 text-primary" />
              <h3 className="font-semibold text-sm">{title}</h3>
              <p className="text-muted-foreground text-xs leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border px-6 py-4 text-center text-xs text-muted-foreground">
        CodeGuardian AI — Built with Next.js + FastAPI + IBM watsonx.ai
      </footer>
    </main>
  );
}
