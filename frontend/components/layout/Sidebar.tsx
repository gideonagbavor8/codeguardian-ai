"use client";

import { Shield, LayoutDashboard, Search, FileText, LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";

const nav = [
  { href: "/dashboard",  label: "Dashboard",  icon: LayoutDashboard },
  { href: "/scan/new",   label: "New Scan",    icon: Search },
  { href: "/reports",    label: "Reports",     icon: FileText },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="flex h-screen w-56 flex-col border-r border-border bg-card">
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-5 border-b border-border">
        <Shield className="h-5 w-5 text-primary" />
        <span className="font-bold text-sm tracking-tight">CodeGuardian AI</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-1">
        {nav.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
              pathname === href || pathname.startsWith(href + "/")
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>

      {/* User */}
      <div className="p-3 border-t border-border">
        <div className="px-3 py-1 text-xs text-muted-foreground truncate mb-1">
          {user?.email}
        </div>
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
