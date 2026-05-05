/**Shared animated list row used in settings sections for tokens, repos, sandboxes.*/

"use client";

import { motion } from "framer-motion";
import { IconTrash } from "@/components/ui/icons";

interface ListRowProps {
  layoutId: string;
  onDelete: () => void;
  deleteTitle: string;
  children: React.ReactNode;
}

export function ListRow({ layoutId, onDelete, deleteTitle, children }: ListRowProps): React.ReactElement {
  return (
    <motion.div
      key={layoutId}
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      className="flex items-center gap-2 px-2.5 py-2 bg-black/30 rounded border border-border group"
    >
      {children}
      <button
        onClick={onDelete}
        className="text-text-secondary hover:text-[#ff4444] transition-colors opacity-0 group-hover:opacity-100 focus-visible:opacity-100 shrink-0"
        title={deleteTitle}
      >
        <IconTrash size={11} />
      </button>
    </motion.div>
  );
}
