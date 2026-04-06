"use client";

import Image from "next/image";
import type { RunStatus } from "@/lib/types";

interface LogoMarkProps {
  runStatus: RunStatus | null;
}

export function LogoMark({ runStatus }: LogoMarkProps): React.ReactElement {
  const isRunning = runStatus === "running";
  const ringStroke = isRunning
    ? "rgba(0,255,136,0.2)"
    : "rgba(255,255,255,0.06)";
  const ringStyle: React.CSSProperties | undefined = isRunning
    ? { animation: "spin 8s linear infinite" }
    : undefined;

  return (
    <div className="relative flex items-center justify-center h-7 w-7">
      <svg width="28" height="28" viewBox="0 0 28 28" className="absolute">
        <circle
          cx="14"
          cy="14"
          r="12"
          fill="none"
          stroke={ringStroke}
          strokeWidth="1"
          strokeDasharray="4 3"
          style={ringStyle}
        />
      </svg>
      <Image
        src="/logo.svg"
        alt="AutoFyn"
        width={18}
        height={18}
        className="relative z-[1]"
      />
    </div>
  );
}
