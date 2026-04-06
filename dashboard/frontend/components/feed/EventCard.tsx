"use client";

import type { ReactElement } from "react";
import type { FeedEvent } from "@/lib/types";
import { ToolCallCard } from "@/components/feed/cards/ToolCallCard";
import { AuditCard } from "@/components/feed/cards/AuditCard";
import { UsageCard, ControlCard } from "@/components/feed/cards/SimpleCards";

export function EventCard({ event }: { event: FeedEvent }): ReactElement | null {
  switch (event._kind) {
    case "tool":
      return <ToolCallCard tc={event.data} />;
    case "audit":
      return <AuditCard event={event.data} />;
    case "control":
      return <ControlCard text={event.text} ts={event.ts} />;
    case "usage":
      return <UsageCard usage={event.data} />;
    case "llm_text":
    case "llm_thinking":
      return null;
    default:
      return null;
  }
}
