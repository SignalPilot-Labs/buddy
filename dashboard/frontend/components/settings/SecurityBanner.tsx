export function SecurityBanner() {
  return (
    <div className="border border-border rounded bg-bg overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-1.5 bg-bg-card border-b border-border">
        <div className="flex gap-1">
          <span className="h-2 w-2 rounded-full bg-[#ff4444]/30" />
          <span className="h-2 w-2 rounded-full bg-[#ffaa00]/30" />
          <span className="h-2 w-2 rounded-full bg-[#00ff88]/30" />
        </div>
        <span className="text-[10px] text-text-secondary font-mono">security</span>
      </div>
      <div className="flex items-start gap-3 px-4 py-3">
        <svg width="44" height="44" viewBox="0 0 32 32" fill="none" className="shrink-0">
          <path
            d="M16 2L4 8v8c0 7.2 5.1 13.2 12 15 6.9-1.8 12-7.8 12-15V8L16 2z"
            stroke="#00ff88" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" opacity="0.4"
          />
          <path
            d="M16 5L7 9.5v6.5c0 5.6 3.8 10.2 9 11.5 5.2-1.3 9-5.9 9-11.5V9.5L16 5z"
            fill="#00ff88" opacity="0.03"
          />
          <rect x="12" y="15" width="8" height="6" rx="1" stroke="#00ff88" strokeWidth="1" opacity="0.6" />
          <path d="M13.5 15v-2.5a2.5 2.5 0 015 0V15" stroke="#00ff88" strokeWidth="1" strokeLinecap="round" opacity="0.6" />
          <circle cx="16" cy="18" r="1" fill="#00ff88" opacity="0.5" />
          <text x="5" y="7" fontSize="3" fill="#00ff88" opacity="0.15" fontFamily="monospace">01</text>
          <text x="24" y="7" fontSize="3" fill="#00ff88" opacity="0.15" fontFamily="monospace">10</text>
          <text x="3" y="28" fontSize="3" fill="#00ff88" opacity="0.15" fontFamily="monospace">11</text>
          <text x="26" y="28" fontSize="3" fill="#00ff88" opacity="0.15" fontFamily="monospace">00</text>
        </svg>
        <div className="space-y-1.5 min-w-0">
          <div className="font-mono text-[10px] leading-relaxed">
            <span className="text-[#00ff88]/60">$</span>{" "}
            <span className="text-accent-hover">Credentials encrypted with</span>{" "}
            <span className="text-[#00ff88]">AES-128 (Fernet)</span>{" "}
            <span className="text-accent-hover">before storage.</span>
          </div>
          <div className="font-mono text-[10px] leading-relaxed">
            <span className="text-[#00ff88]/60">$</span>{" "}
            <span className="text-accent-hover">Decrypted</span>{" "}
            <span className="text-[#ffcc44]">in-memory only</span>{" "}
            <span className="text-accent-hover">when starting a run.</span>
          </div>
          <div className="font-mono text-[10px] leading-relaxed">
            <span className="text-[#00ff88]/60">$</span>{" "}
            <span className="text-accent-hover">Master key on Docker volume &mdash;</span>{" "}
            <span className="text-text-secondary">never leaves host.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
