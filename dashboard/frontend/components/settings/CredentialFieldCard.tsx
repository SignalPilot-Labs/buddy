"use client";

import { useTranslation } from "@/hooks/useTranslation";
import type { Settings, SettingsStatus } from "@/lib/types";

export interface FieldConfig {
  key: keyof Settings;
  labelKey: "gitToken" | "maxBudgetUsd";
  statusKey?: keyof SettingsStatus;
  secret: boolean;
}

export const FIELDS: FieldConfig[] = [
  {
    key: "git_token",
    labelKey: "gitToken",
    statusKey: "has_git_token",
    secret: true,
  },
  {
    key: "max_budget_usd",
    labelKey: "maxBudgetUsd",
    secret: false,
  },
];

interface CredentialFieldCardProps {
  field: FieldConfig;
  currentValue: string;
  editValue: string | undefined;
  isSet: boolean;
  show: boolean;
  onEditChange: (key: keyof Settings, value: string) => void;
  onCancelEdit: (key: keyof Settings) => void;
  onToggleShow: (key: keyof Settings) => void;
}

export function CredentialFieldCard({
  field,
  currentValue,
  editValue,
  isSet,
  show,
  onEditChange,
  onCancelEdit,
  onToggleShow,
}: CredentialFieldCardProps): React.ReactElement {
  const { t } = useTranslation();
  const isSecret = field.secret;

  return (
    <div className="p-4 bg-white/[0.01] border border-[#1a1a1a] rounded-lg">
      <div className="flex items-center justify-between mb-2">
        <label className="text-[10px] font-semibold text-[#ccc]">
          {t.settings.fieldLabels[field.labelKey]}
        </label>
        {isSet && (
          <span className="flex items-center gap-1 text-[9px] text-[#00ff88]/60">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
              <polyline points="2 5 4 7 8 3" />
            </svg>
            {t.settings.set}
          </span>
        )}
      </div>

      {currentValue && editValue === undefined && (
        <div className="mb-2 px-2.5 py-1.5 bg-black/30 rounded border border-[#1a1a1a] text-[10px] font-mono text-[#666] flex items-center justify-between overflow-hidden">
          <span className="truncate min-w-0">{currentValue}</span>
          <button
            onClick={() => onEditChange(field.key, "")}
            className="text-[9px] text-[#999] hover:text-[#888] transition-colors ml-2"
          >
            {t.settings.change}
          </button>
        </div>
      )}

      {(editValue !== undefined || !currentValue) && (
        <div className="relative">
          <input
            type={isSecret && !show ? "password" : "text"}
            value={editValue || ""}
            onChange={(e) => onEditChange(field.key, e.target.value)}
            placeholder={t.settings.fieldPlaceholders[field.labelKey]}
            className="w-full bg-black/30 border border-[#1a1a1a] rounded px-3 py-2 text-[11px] text-[#ccc] font-mono placeholder-[#666] focus:outline-none focus:border-[#00ff88]/30 transition-all pr-10"
            autoComplete="off"
            spellCheck={false}
          />
          {isSecret && (
            <button
              type="button"
              onClick={() => onToggleShow(field.key)}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-[#999] hover:text-[#888] transition-colors"
              tabIndex={-1}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                {show ? (
                  <>
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </>
                ) : (
                  <>
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </>
                )}
              </svg>
            </button>
          )}
          {editValue !== undefined && currentValue && (
            <button
              onClick={() => onCancelEdit(field.key)}
              className="absolute right-8 top-1/2 -translate-y-1/2 text-[9px] text-[#999] hover:text-[#888]"
            >
              {t.settings.cancel}
            </button>
          )}
        </div>
      )}

      <p className="mt-2 text-[9px] text-[#999] leading-relaxed">
        {t.settings.fieldHelp[field.labelKey]}
      </p>
    </div>
  );
}
