"use client";

import { Bell } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

interface NavbarProps {
  title: string;
}

export function Navbar({ title }: NavbarProps) {
  const { user } = useAuth();
  return (
    <header className="h-14 border-b border-border flex items-center justify-between px-6">
      <h1 className="font-semibold text-sm">{title}</h1>
      <div className="flex items-center gap-4">
        <Bell className="h-4 w-4 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">{user?.full_name || user?.email}</span>
      </div>
    </header>
  );
}
