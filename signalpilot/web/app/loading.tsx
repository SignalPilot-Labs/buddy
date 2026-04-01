export default function Loading() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="text-center">
        {/* Animated loading SVG */}
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none" className="mx-auto mb-4">
          {/* Outer frame */}
          <rect x="1" y="1" width="46" height="46" stroke="var(--color-border)" strokeWidth="1" fill="none">
            <animate attributeName="stroke" values="var(--color-border);var(--color-border-hover);var(--color-border)" dur="2s" repeatCount="indefinite" />
          </rect>
          {/* Spinning inner square */}
          <rect x="14" y="14" width="20" height="20" stroke="var(--color-text-dim)" strokeWidth="1" fill="none" opacity="0.5">
            <animateTransform
              attributeName="transform"
              type="rotate"
              from="0 24 24"
              to="360 24 24"
              dur="4s"
              repeatCount="indefinite"
            />
          </rect>
          {/* Center dot */}
          <circle cx="24" cy="24" r="2" fill="var(--color-success)" opacity="0.6">
            <animate attributeName="r" values="1.5;3;1.5" dur="1.5s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.6;0.2;0.6" dur="1.5s" repeatCount="indefinite" />
          </circle>
          {/* Corner markers */}
          <path d="M1 6V1H6" stroke="var(--color-border-hover)" strokeWidth="1" />
          <path d="M42 1H47V6" stroke="var(--color-border-hover)" strokeWidth="1" />
          <path d="M47 42V47H42" stroke="var(--color-border-hover)" strokeWidth="1" />
          <path d="M6 47H1V42" stroke="var(--color-border-hover)" strokeWidth="1" />
        </svg>

        <p className="text-[10px] text-[var(--color-text-dim)] tracking-[0.2em] uppercase">
          loading
        </p>
      </div>
    </div>
  );
}
