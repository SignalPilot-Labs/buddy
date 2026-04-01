"use client";

import { Component, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="flex flex-col items-center justify-center py-16 px-8">
          <AlertTriangle className="w-5 h-5 text-[var(--color-error)] mb-4" strokeWidth={1.5} />
          <h2 className="text-xs tracking-wider mb-2">something went wrong</h2>
          <p className="text-[10px] text-[var(--color-text-dim)] mb-4 max-w-md text-center tracking-wider">
            {this.state.error?.message || "an unexpected error occurred."}
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
            className="flex items-center gap-2 px-4 py-2 bg-[var(--color-text)] text-[var(--color-bg)] text-[10px] tracking-wider uppercase transition-all hover:opacity-90"
          >
            <RefreshCw className="w-3 h-3" />
            reload
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
