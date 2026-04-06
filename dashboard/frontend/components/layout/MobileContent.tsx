"use client";

import type { Run, FeedEvent } from "@/lib/types";
import { RunList } from "@/components/sidebar/RunList";
import { EventFeed } from "@/components/feed/EventFeed";
import { StatsBar } from "@/components/stats/StatsBar";
import { WorkTree } from "@/components/worktree/WorkTree";

const MOBILE_PADDING_STYLE: React.CSSProperties = {
  paddingBottom: "calc(56px + env(safe-area-inset-bottom, 0px))",
};

type MobilePanel = "feed" | "runs" | "changes";

interface MobileContentProps {
  mobilePanel: MobilePanel;
  runs: Run[];
  selectedRunId: string | null;
  selectedRun: Run | null;
  runsLoading: boolean;
  allEvents: FeedEvent[];
  connected: boolean;
  onSelectRun: (id: string) => void;
}

export function MobileContent({
  mobilePanel,
  runs,
  selectedRunId,
  selectedRun,
  runsLoading,
  allEvents,
  connected,
  onSelectRun,
}: MobileContentProps): React.ReactElement {
  return (
    <div
      className="flex-1 flex flex-col min-h-0 min-w-0"
      style={MOBILE_PADDING_STYLE}
    >
      {mobilePanel === "runs" && (
        <RunList
          runs={runs}
          activeId={selectedRunId}
          onSelect={onSelectRun}
          loading={runsLoading}
          mobile
        />
      )}

      {mobilePanel === "feed" && (
        <main className="flex-1 flex flex-col min-h-0 min-w-0">
          <EventFeed events={allEvents} />
          <StatsBar run={selectedRun} connected={connected} events={allEvents} />
        </main>
      )}

      {mobilePanel === "changes" && (
        <WorkTree events={allEvents} runId={selectedRunId} mobile />
      )}
    </div>
  );
}
