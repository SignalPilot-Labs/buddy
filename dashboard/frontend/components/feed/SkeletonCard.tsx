export function SkeletonCard() {
  return (
    <div role="status" aria-label="Loading event" className="rounded-lg p-4 border border-white/[0.04] bg-white/[0.02]">
      {/* Top row: icon placeholder + role label + timestamp */}
      <div className="flex items-center gap-2">
        <div className="h-6 w-6 rounded-md bg-white/[0.06] animate-pulse" />
        <div className="h-3 w-16 rounded bg-white/[0.06] animate-pulse" />
        <div className="h-2.5 w-10 rounded bg-white/[0.04] animate-pulse ml-auto" />
      </div>
      {/* Body: text line placeholders */}
      <div className="space-y-2 mt-2.5">
        <div className="h-2.5 w-full rounded bg-white/[0.04] animate-pulse" />
        <div className="h-2.5 w-3/4 rounded bg-white/[0.04] animate-pulse" />
        <div className="h-2.5 w-1/2 rounded bg-white/[0.04] animate-pulse" />
      </div>
    </div>
  );
}
