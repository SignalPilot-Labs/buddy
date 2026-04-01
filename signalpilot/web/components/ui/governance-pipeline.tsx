"use client";

import {
  Shield,
  FileSearch,
  Gauge,
  Filter,
  Eye,
  ScrollText,
  CheckCircle2,
  XCircle,
  ArrowRight,
} from "lucide-react";

interface PipelineStep {
  id: string;
  label: string;
  icon: React.ElementType;
  description: string;
  status: "active" | "passed" | "blocked" | "idle";
}

const PIPELINE_STEPS: PipelineStep[] = [
  {
    id: "parse",
    label: "SQL Parse",
    icon: FileSearch,
    description: "AST validation via sqlglot — blocks DDL/DML, stacking",
    status: "idle",
  },
  {
    id: "policy",
    label: "Policy Check",
    icon: Shield,
    description: "Blocked tables, schema annotations, read-only enforcement",
    status: "idle",
  },
  {
    id: "cost",
    label: "Cost Estimate",
    icon: Gauge,
    description: "EXPLAIN-based pre-estimation, budget check",
    status: "idle",
  },
  {
    id: "limit",
    label: "Row Limit",
    icon: Filter,
    description: "LIMIT injection/clamping to prevent context overflow",
    status: "idle",
  },
  {
    id: "pii",
    label: "PII Redaction",
    icon: Eye,
    description: "Hash/mask/drop flagged columns before returning results",
    status: "idle",
  },
  {
    id: "audit",
    label: "Audit Log",
    icon: ScrollText,
    description: "Append-only JSONL with full query chain for compliance",
    status: "idle",
  },
];

const statusColors = {
  active: "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]",
  passed: "border-[var(--color-success)] bg-[var(--color-success)]/10 text-[var(--color-success)]",
  blocked: "border-[var(--color-error)] bg-[var(--color-error)]/10 text-[var(--color-error)]",
  idle: "border-[var(--color-border)] bg-[var(--color-bg-card)] text-[var(--color-text-muted)]",
};

export function GovernancePipeline() {
  return (
    <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <Shield className="w-4 h-4 text-[var(--color-success)]" />
        <h3 className="text-sm font-medium">Query Governance Pipeline</h3>
      </div>
      <div className="flex items-center gap-1 overflow-x-auto pb-2">
        {PIPELINE_STEPS.map((step, i) => {
          const Icon = step.icon;
          return (
            <div key={step.id} className="flex items-center gap-1 flex-shrink-0">
              <div
                className={`flex flex-col items-center gap-1.5 px-3 py-2 rounded-lg border ${statusColors[step.status]} transition-all min-w-[90px]`}
                title={step.description}
              >
                <Icon className="w-4 h-4" />
                <span className="text-[10px] font-medium whitespace-nowrap">{step.label}</span>
              </div>
              {i < PIPELINE_STEPS.length - 1 && (
                <ArrowRight className="w-3 h-3 text-[var(--color-text-dim)] flex-shrink-0" />
              )}
            </div>
          );
        })}
      </div>
      <p className="text-[10px] text-[var(--color-text-dim)] mt-2">
        Every query passes through this 6-stage governance pipeline before results reach the agent.
      </p>
    </div>
  );
}
