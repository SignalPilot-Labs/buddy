"use client";

import React from "react";
import type { GroupedEvent } from "@/lib/groupEvents";
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

interface GroupedEventCardProps {
  event: GroupedEvent;
  isLast?: boolean;
  runActive?: boolean;
  runPaused?: boolean;
}

function GroupedEventCardInner({
  event,
  isLast = false,
  runActive = false,
  runPaused = false,
}: GroupedEventCardProps) {
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
      return (
        <ControlMessage
          text={event.text}
          ts={event.ts}
          retryAction={event.retryAction}
        />
      );
    case "user_prompt":
      return (
        <UserPromptCard
          prompt={event.prompt}
          ts={event.ts}
          pending={event.pending}
          failed={event.failed}
        />
      );
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

function areEqual(
  prev: GroupedEventCardProps,
  next: GroupedEventCardProps
): boolean {
  if (prev.isLast !== next.isLast) return false;
  if (prev.runActive !== next.runActive) return false;
  if (prev.runPaused !== next.runPaused) return false;

  const pe = prev.event;
  const ne = next.event;

  if (pe.id !== ne.id) return false;
  if (pe.type !== ne.type) return false;

  switch (pe.type) {
    case "llm_message": {
      if (ne.type !== "llm_message") return false;
      return pe.text.length === ne.text.length && pe.thinking.length === ne.thinking.length;
    }
    case "tool_group":
    case "edit_group":
    case "bash_group":
    case "playwright_group": {
      if (ne.type !== pe.type) return false;
      const pTools = (pe as { tools: { id: number }[] }).tools;
      const nTools = (ne as { tools: { id: number }[] }).tools;
      if (pTools.length !== nTools.length) return false;
      if (pTools.length === 0) return true;
      return pTools[pTools.length - 1].id === nTools[nTools.length - 1].id;
    }
    case "agent_run": {
      if (ne.type !== "agent_run") return false;
      if (pe.childTools.length !== ne.childTools.length) return false;
      if (pe.finalText?.length !== ne.finalText?.length) return false;
      if (pe.tool.phase !== ne.tool.phase) return false;
      if (pe.tool.id !== ne.tool.id) return false;
      return true;
    }
    case "single_tool": {
      if (ne.type !== "single_tool") return false;
      return pe.tool.id === ne.tool.id && pe.tool.phase === ne.tool.phase;
    }
    default:
      // For control, milestone, user_prompt, divider — id + type comparison above is sufficient
      return true;
  }
}

export const GroupedEventCard = React.memo(GroupedEventCardInner, areEqual);
