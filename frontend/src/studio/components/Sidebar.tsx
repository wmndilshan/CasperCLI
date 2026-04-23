import { Search } from "lucide-react";
import { useStudioStore } from "@/studio/store";
import { ActivityBar } from "./ActivityBar";
import { FileExplorer } from "./FileExplorer";

export function Sidebar() {
  const sidebarView = useStudioStore((s) => s.sidebarView);

  return (
    <div className="flex h-full min-h-0 shrink-0">
      <ActivityBar />
      <div className="w-60 bg-[#252526] border-r border-[#1e1e1e] overflow-y-auto min-h-0">
        {sidebarView === "explorer" && <FileExplorer />}
        {sidebarView === "search" && (
          <div className="p-4 text-[#858585]">
            <div className="flex items-center gap-2 mb-4 text-xs font-semibold uppercase tracking-wide text-[#bbbbbb]">
              <Search size={14} />
              Search
            </div>
            <input
              type="text"
              placeholder="Filter in explorer…"
              className="w-full bg-[#3c3c3c] border border-[#555] rounded px-3 py-1.5 text-sm text-[#cccccc] focus:outline-none focus:border-[#007fd4]"
            />
          </div>
        )}
      </div>
    </div>
  );
}
