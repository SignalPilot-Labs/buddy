"use client";

interface GitHubButtonProps {
  onClick: () => void;
  disabled: boolean;
  label?: string;
}

export default function GitHubButton({
  onClick,
  disabled,
  label = "CONTINUE WITH GITHUB",
}: GitHubButtonProps) {
  return (
    <>
      <button
        onClick={onClick}
        disabled={disabled}
        className="w-full border-2 border-[var(--color-success)] bg-transparent text-[var(--color-text)] font-bold text-sm uppercase tracking-[0.1em] py-4 px-6 cursor-pointer hover:bg-[var(--color-success)] hover:text-[var(--color-bg)] disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {label}
      </button>

      <div className="flex items-center gap-4 my-12">
        <div className="flex-1 h-[2px] bg-[var(--color-text-dim)]" />
        <span className="text-[var(--color-text-dim)] text-xs tracking-[0.15em] uppercase">OR</span>
        <div className="flex-1 h-[2px] bg-[var(--color-text-dim)]" />
      </div>
    </>
  );
}
