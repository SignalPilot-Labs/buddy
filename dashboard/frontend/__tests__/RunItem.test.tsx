/**
 * RunItem component tests.
 *
 * Covers: rendering run details, active state indicator, error preview,
 * click handler, and status badge.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { RunItem } from "@/components/sidebar/RunItem";
import type { Run } from "@/lib/types";
import { PROMPT_LABEL_MAX_LEN } from "@/lib/constants";

function makeRun(overrides: Partial<Run> = {}): Run {
  return {
    id: "abc-123",
    branch_name: "autofyn/2026-04-06-abc123",
    status: "running",
    started_at: new Date().toISOString(),
    total_tool_calls: 5,
    total_cost_usd: 1.25,
    total_input_tokens: 10000,
    total_output_tokens: 5000,
    pr_url: null,
    error_message: null,
    base_branch: "main",
    github_repo: "owner/repo",
    custom_prompt: null,
    duration_minutes: 30,
    rate_limit_resets_at: null,
    ...overrides,
  } as Run;
}

describe("RunItem", () => {
  it("renders branch name without prefix when custom_prompt is null", () => {
    render(<RunItem run={makeRun({ custom_prompt: null })} active={false} onClick={vi.fn()} />);
    expect(screen.getByText(/abc123/)).toBeInTheDocument();
  });

  it("shows custom_prompt as the label when set", () => {
    render(
      <RunItem
        run={makeRun({ custom_prompt: "Fix the login button on mobile" })}
        active={false}
        onClick={vi.fn()}
      />
    );
    expect(screen.getByText("Fix the login button on mobile")).toBeInTheDocument();
  });

  it("truncates long custom_prompt to PROMPT_LABEL_MAX_LEN characters", () => {
    const longPrompt = "A".repeat(PROMPT_LABEL_MAX_LEN * 2);
    render(
      <RunItem
        run={makeRun({ custom_prompt: longPrompt })}
        active={false}
        onClick={vi.fn()}
      />
    );
    expect(screen.getByText("A".repeat(PROMPT_LABEL_MAX_LEN))).toBeInTheDocument();
  });

  it("shows tool call count when nonzero", () => {
    render(<RunItem run={makeRun({ total_tool_calls: 12 })} active={false} onClick={vi.fn()} />);
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("shows cost when nonzero", () => {
    render(<RunItem run={makeRun({ total_cost_usd: 2.5 })} active={false} onClick={vi.fn()} />);
    expect(screen.getByText(/2\.50/)).toBeInTheDocument();
  });

  it("shows truncated error message", () => {
    const longError = "x".repeat(200);
    render(<RunItem run={makeRun({ error_message: longError })} active={false} onClick={vi.fn()} />);
    const errorEl = screen.getByText(/xxx/);
    expect(errorEl.textContent!.length).toBeLessThan(100);
  });

  it("calls onClick when clicked", async () => {
    const onClick = vi.fn();
    render(<RunItem run={makeRun()} active={false} onClick={onClick} />);
    await userEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("shows active indicator when active", () => {
    const { container } = render(<RunItem run={makeRun()} active={true} onClick={vi.fn()} />);
    const indicator = container.querySelector(".bg-\\[\\#00ff88\\]");
    expect(indicator).toBeInTheDocument();
  });

  it("renders different statuses correctly", () => {
    const statuses = ["running", "completed", "crashed", "starting", "paused"] as const;
    statuses.forEach((status) => {
      const { unmount } = render(
        <RunItem run={makeRun({ status })} active={false} onClick={vi.fn()} />
      );
      // Just verify it renders without crashing
      unmount();
    });
  });
});
