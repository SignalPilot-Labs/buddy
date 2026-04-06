"use client";

import type { ReactElement } from "react";
import type { GroupedEvent } from "@/lib/groupEvents";
import { LLMMessageCard } from "@/components/feed/cards/LLMMessageCard";
import { ReadGroupCard } from "@/components/feed/cards/ReadGroupCard";
import { EditGroupCard } from "@/components/feed/cards/EditGroupCard";
import { BashGroupCard } from "@/components/feed/cards/BashGroupCard";
import { PlaywrightGroupCard } from "@/components/feed/cards/PlaywrightGroupCard";
import { SingleToolCard } from "@/components/feed/cards/SingleToolCard";
import { AgentRunCard } from "@/components/feed/cards/AgentRunCard";
import {
  UsageTick,
  ControlMessage,
  UserPromptCard,
  MilestoneCard,
  DividerCard,
} from "@/components/feed/cards/SimpleCards";

export function GroupedEventCard({
  event,
  isLast = false,
}: {
  event: GroupedEvent;
  isLast?: boolean;
}): ReactElement | null {
  switch (event.type) {
    case "llm_message":
      return (
        <LLMMessageCard
          role={event.role}
          text={event.text}
          thinking={event.thinking}
          ts={event.ts}
          isLast={isLast}
        />
      );
    case "tool_group":
      return (
        <ReadGroupCard
          tools={event.tools}
          ts={event.ts}
          totalDuration={event.totalDuration}
          label={event.label}
        />
      );
    case "edit_group":
      return <EditGroupCard tools={event.tools} ts={event.ts} totalDuration={event.totalDuration} />;
    case "bash_group":
      return <BashGroupCard tools={event.tools} ts={event.ts} totalDuration={event.totalDuration} />;
    case "playwright_group":
      return (
        <PlaywrightGroupCard tools={event.tools} ts={event.ts} totalDuration={event.totalDuration} />
      );
    case "agent_run":
      return (
        <AgentRunCard
          tool={event.tool}
          childTools={event.childTools}
          finalText={event.finalText}
          agentType={event.agentType}
          ts={event.ts}
        />
      );
    case "single_tool":
      return <SingleToolCard tool={event.tool} />;
    case "usage_tick":
      return <UsageTick data={event.data} ts={event.ts} />;
    case "control":
      return <ControlMessage text={event.text} ts={event.ts} />;
    case "user_prompt":
      return <UserPromptCard prompt={event.prompt} ts={event.ts} />;
    case "milestone":
      return <MilestoneCard label={event.label} detail={event.detail} color={event.color} ts={event.ts} />;
    case "divider":
      return <DividerCard label={event.label} />;
    default:
      return null;
  }
}
