"use client";

import { useEffect, useRef, useState } from "react";
import { scanApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import type { ScanDetail } from "@/lib/types";

export function useScanStatus(scanId: string) {
  const { token } = useAuth();
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!token || !scanId) return;

    const poll = async () => {
      try {
        const data = await scanApi.get(token, scanId);
        setScan(data);
        if (data.status === "COMPLETE" || data.status === "FAILED") {
          if (intervalRef.current) clearInterval(intervalRef.current);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to fetch scan");
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 3000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [token, scanId]);

  return { scan, error };
}
