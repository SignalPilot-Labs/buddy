"use client";

import { MotionConfig } from "framer-motion";

interface MotionProviderProps {
  children: React.ReactNode;
}

export function MotionProvider({ children }: MotionProviderProps): React.ReactElement {
  return (
    <MotionConfig reducedMotion="user">
      {children}
    </MotionConfig>
  );
}
