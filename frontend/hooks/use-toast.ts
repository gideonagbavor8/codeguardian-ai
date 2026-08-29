// Minimal use-toast hook (no external dep)
"use client";

import * as React from "react";
import type { ToastProps } from "@/components/ui/toast";

const TOAST_LIMIT = 5;
const TOAST_REMOVE_DELAY = 4000;

type ToasterToast = ToastProps & {
  id: string;
  title?: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactElement;
};

type Action =
  | { type: "ADD_TOAST"; toast: ToasterToast }
  | { type: "DISMISS_TOAST"; toastId: string }
  | { type: "REMOVE_TOAST"; toastId: string };

interface State {
  toasts: ToasterToast[];
}

const toastTimeouts = new Map<string, ReturnType<typeof setTimeout>>();

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "ADD_TOAST":
      return { toasts: [action.toast, ...state.toasts].slice(0, TOAST_LIMIT) };
    case "DISMISS_TOAST":
      return {
        toasts: state.toasts.map((t) =>
          t.id === action.toastId ? { ...t, open: false } : t
        ),
      };
    case "REMOVE_TOAST":
      return { toasts: state.toasts.filter((t) => t.id !== action.toastId) };
  }
}

let memState: State = { toasts: [] };
const listeners: Array<(state: State) => void> = [];

function dispatch(action: Action) {
  memState = reducer(memState, action);
  listeners.forEach((l) => l(memState));
}

let counter = 0;

export function toast({
  title,
  description,
  variant,
}: {
  title?: string;
  description?: string;
  variant?: "default" | "destructive";
}) {
  const id = String(counter++);
  dispatch({ type: "ADD_TOAST", toast: { id, title, description, variant, open: true } });
  const t = setTimeout(() => {
    dispatch({ type: "DISMISS_TOAST", toastId: id });
    setTimeout(() => dispatch({ type: "REMOVE_TOAST", toastId: id }), 300);
  }, TOAST_REMOVE_DELAY);
  toastTimeouts.set(id, t);
}

export function useToast() {
  const [state, setState] = React.useState<State>(memState);
  React.useEffect(() => {
    listeners.push(setState);
    return () => {
      const idx = listeners.indexOf(setState);
      if (idx > -1) listeners.splice(idx, 1);
    };
  }, []);
  return { toasts: state.toasts };
}
