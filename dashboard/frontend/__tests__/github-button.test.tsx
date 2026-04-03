import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import GitHubButton from "@/components/auth/GitHubButton";

describe("GitHubButton", () => {
  it("renders with default label", () => {
    render(<GitHubButton onClick={vi.fn()} disabled={false} />);
    expect(screen.getByRole("button", { name: "CONTINUE WITH GITHUB" })).toBeInTheDocument();
  });

  it("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<GitHubButton onClick={onClick} disabled={false} />);
    fireEvent.click(screen.getByRole("button", { name: "CONTINUE WITH GITHUB" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("renders custom label when provided", () => {
    render(<GitHubButton onClick={vi.fn()} disabled={false} label="LOGIN WITH GITHUB" />);
    expect(screen.getByRole("button", { name: "LOGIN WITH GITHUB" })).toBeInTheDocument();
  });

  it("is disabled when disabled=true", () => {
    render(<GitHubButton onClick={vi.fn()} disabled={true} />);
    expect(screen.getByRole("button", { name: "CONTINUE WITH GITHUB" })).toBeDisabled();
  });

  it("does not call onClick when disabled", () => {
    const onClick = vi.fn();
    render(<GitHubButton onClick={onClick} disabled={true} />);
    fireEvent.click(screen.getByRole("button", { name: "CONTINUE WITH GITHUB" }));
    expect(onClick).not.toHaveBeenCalled();
  });

  it("renders the OR divider", () => {
    render(<GitHubButton onClick={vi.fn()} disabled={false} />);
    expect(screen.getByText("OR")).toBeInTheDocument();
  });
});
