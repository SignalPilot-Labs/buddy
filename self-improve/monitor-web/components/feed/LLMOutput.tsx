"use client";

import { motion } from "framer-motion";
import { clsx } from "clsx";
import {
  SparklesIcon,
  LightBulbIcon,
  BriefcaseIcon,
} from "@heroicons/react/16/solid";

export function LLMTextBlock({
  text,
  agentRole = "worker",
}: {
  text: string;
  agentRole?: "worker" | "ceo";
}) {
  const isCeo = agentRole === "ceo";
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className={clsx(
        "relative border-l-[3px] rounded-r-md px-3 py-2",
        isCeo
          ? "border-l-orange-500/60 bg-orange-500/[0.03]"
          : "border-l-zinc-500/40 bg-white/[0.015]"
      )}
    >
      <div className="flex items-start gap-2">
        {isCeo ? (
          <BriefcaseIcon className="h-3 w-3 text-orange-400 mt-0.5 shrink-0" />
        ) : (
          <SparklesIcon className="h-3 w-3 text-zinc-500 mt-0.5 shrink-0" />
        )}
        <div className="min-w-0">
          {isCeo && (
            <span className="text-[9px] font-bold uppercase tracking-wider text-orange-300 bg-orange-500/15 rounded px-1 py-0.5 mr-1">
              CEO
            </span>
          )}
          <span
            className={clsx(
              "text-[11px] leading-relaxed whitespace-pre-wrap break-words",
              isCeo ? "text-orange-200/80" : "text-zinc-300"
            )}
          >
            {text}
          </span>
          <span
            className={clsx(
              "inline-block w-[6px] h-[13px] ml-0.5 animate-pulse rounded-[1px]",
              isCeo ? "bg-orange-400/60" : "bg-sky-400/60"
            )}
          />
        </div>
      </div>
    </motion.div>
  );
}

export function LLMThinkingBlock({
  text,
  agentRole = "worker",
}: {
  text: string;
  agentRole?: "worker" | "ceo";
}) {
  const isCeo = agentRole === "ceo";
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className={clsx(
        "relative border-l-[3px] rounded-r-md px-3 py-2",
        isCeo
          ? "border-l-orange-700/50 bg-orange-900/10"
          : "border-l-zinc-700/50 bg-zinc-800/20"
      )}
    >
      <div className="flex items-start gap-2">
        <LightBulbIcon
          className={clsx(
            "h-3 w-3 mt-0.5 shrink-0",
            isCeo ? "text-orange-600" : "text-zinc-600"
          )}
        />
        <div className="min-w-0">
          {isCeo && (
            <span className="text-[8px] font-bold uppercase tracking-wider text-orange-400/60 mr-1">
              CEO thinking
            </span>
          )}
          <span
            className={clsx(
              "text-[10px] italic leading-relaxed whitespace-pre-wrap break-words",
              isCeo ? "text-orange-500/60" : "text-zinc-500"
            )}
          >
            {text}
          </span>
          <span
            className={clsx(
              "inline-block w-[5px] h-[11px] ml-0.5 animate-pulse rounded-[1px]",
              isCeo ? "bg-orange-500/30" : "bg-zinc-500/40"
            )}
          />
        </div>
      </div>
    </motion.div>
  );
}
