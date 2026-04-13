"use client";

import type { GroupedEvent } from "@/lib/groupEventTypes";
import {
  LLMMessageCard,
  ControlMessage,
  UserPromptCard,
  MilestoneCard,
  DividerCard,
} from "@/components/feed/MessageCards";
import {
  ReadGroupCard,
  EditGroupCard,
} from "@/components/feed/GroupCards";
import {
  BashGroupCard,
  PlaywrightGroupCard,
  SingleToolCard,
} from "@/components/feed/ToolGroupCards";
import { AgentRunCard } from "@/components/feed/AgentRunCard";

export function GroupedEventCard({
  event,
  isLast,
  runActive,
  runPaused,
}: {
  event: GroupedEvent;
  isLast: boolean;
  runActive: boolean;
  runPaused: boolean;
}) {
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
      return (
        <EditGroupCard
          tools={event.tools}
          ts={event.ts}
          totalDuration={event.totalDuration}
        />
      );
    case "bash_group":
      return (
        <BashGroupCard
          tools={event.tools}
          ts={event.ts}
          totalDuration={event.totalDuration}
        />
      );
    case "playwright_group":
      return (
        <PlaywrightGroupCard
          tools={event.tools}
          ts={event.ts}
          totalDuration={event.totalDuration}
        />
      );
    case "agent_run":
      return (
        <AgentRunCard
          tool={event.tool}
          childTools={event.childTools}
          finalText={event.finalText}
          agentType={event.agentType}
          ts={event.ts}
          runActive={runActive}
          runPaused={runPaused}
        />
      );
    case "single_tool":
      return <SingleToolCard tool={event.tool} />;
    case "control":
      return <ControlMessage text={event.text} ts={event.ts} retryAction={event.retryAction} />;
    case "user_prompt":
      return <UserPromptCard prompt={event.prompt} ts={event.ts} pending={event.pending} failed={event.failed} />;
    case "milestone":
      return (
        <MilestoneCard
          label={event.label}
          detail={event.detail}
          color={event.color}
          ts={event.ts}
        />
      );
    case "divider":
      return <DividerCard label={event.label} />;
    default:
      return (
        <div className="text-[9px] text-[#555] px-3 py-1.5 rounded border border-[#1a1a1a] bg-white/[0.01]">
          Unknown event: {(event as { type: string }).type}
        </div>
      );
  }
}
