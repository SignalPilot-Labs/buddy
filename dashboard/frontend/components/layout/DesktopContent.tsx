"use client";

import type { Run, FeedEvent } from "@/lib/types";
import { EventFeed } from "@/components/feed/EventFeed";
import { StatsBar } from "@/components/stats/StatsBar";
import { WorkTree } from "@/components/worktree/WorkTree";

interface DesktopContentProps {
  selectedRun: Run | null;
  selectedRunId: string | null;
  allEvents: FeedEvent[];
  connected: boolean;
}

export function DesktopContent({
  selectedRun,
  selectedRunId,
  allEvents,
  connected,
}: DesktopContentProps): React.ReactElement {
  return (
    <>
      <main className="flex-1 flex flex-col min-h-0 min-w-0">
        <EventFeed events={allEvents} />
        <StatsBar run={selectedRun} connected={connected} events={allEvents} />
      </main>
      <div className="desktop-worktree">
        <WorkTree events={allEvents} runId={selectedRunId} />
      </div>
    </>
  );
}
