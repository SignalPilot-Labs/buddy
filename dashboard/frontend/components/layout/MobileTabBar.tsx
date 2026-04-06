"use client";

import type { LocaleDict } from "@/lib/i18n/types";
import { MobileTab } from "@/components/mobile/MobileTab";

type MobilePanel = "feed" | "runs" | "changes";

interface MobileTabBarProps {
  mobilePanel: MobilePanel;
  controlsOpen: boolean;
  runsCount: number;
  eventsCount: number;
  onPanelChange: (panel: MobilePanel) => void;
  onControlsToggle: () => void;
  t: LocaleDict;
}

export function MobileTabBar({
  mobilePanel,
  controlsOpen,
  runsCount,
  eventsCount,
  onPanelChange,
  onControlsToggle,
  t,
}: MobileTabBarProps): React.ReactElement {
  return (
    <nav className="mobile-bottom-bar">
      <MobileTab
        icon={
          <svg
            width="18"
            height="18"
            viewBox="0 0 18 18"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          >
            <rect x="2" y="2" width="14" height="14" rx="2" />
            <line x1="2" y1="6" x2="16" y2="6" />
            <line x1="2" y1="10" x2="16" y2="10" />
          </svg>
        }
        label={t.nav.runs}
        active={mobilePanel === "runs"}
        onClick={() => onPanelChange("runs")}
        badge={runsCount || null}
      />
      <MobileTab
        icon={
          <svg
            width="18"
            height="18"
            viewBox="0 0 18 18"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          >
            <path d="M3 9h12" />
            <path d="M3 5h8" />
            <path d="M3 13h10" />
          </svg>
        }
        label={t.nav.feed}
        active={mobilePanel === "feed"}
        onClick={() => onPanelChange("feed")}
        badge={eventsCount || null}
      />
      <MobileTab
        icon={
          <svg
            width="18"
            height="18"
            viewBox="0 0 18 18"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          >
            <path d="M9 2v14M9 2L5 6M9 2l4 4" />
            <circle cx="5" cy="10" r="1.5" />
            <circle cx="13" cy="12" r="1.5" />
            <line x1="5" y1="10" x2="9" y2="10" />
            <line x1="13" y1="12" x2="9" y2="12" />
          </svg>
        }
        label={t.nav.changes}
        active={mobilePanel === "changes"}
        onClick={() => onPanelChange("changes")}
      />
      <MobileTab
        icon={
          <svg
            width="18"
            height="18"
            viewBox="0 0 18 18"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          >
            <circle cx="9" cy="6" r="2" />
            <path d="M5 14h8" />
            <path d="M4 10h10" />
          </svg>
        }
        label={t.nav.controls}
        active={controlsOpen}
        onClick={onControlsToggle}
      />
    </nav>
  );
}
