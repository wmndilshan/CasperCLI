import { AlertCircle, AlertTriangle, Bell, Circle, GitBranch, Wifi } from "lucide-react";
import { useStudioStore } from "@/studio/store";

export function StatusBar() {
  const agents = useStudioStore((s) => s.agents);
  const tabs = useStudioStore((s) => s.tabs);
  const diagnostics = useStudioStore((s) => s.diagnostics);
  const wsConnected = useStudioStore((s) => s.wsConnected);
  const runStatus = useStudioStore((s) => s.runStatus);
  const activeTabId = useStudioStore((s) => s.activeTabId);
  const activeTab = tabs.find((t) => t.id === activeTabId);

  const activeAgents = agents.filter((a) => a.status === "working").length;
  const errors = diagnostics.filter((d) => d.severity === "error").length;
  const warnings = diagnostics.filter((d) => d.severity === "warning").length;

  return (
    <div className="h-6 shrink-0 bg-[#007acc] flex items-center justify-between px-2 text-[11px] text-white">
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex items-center gap-1 px-2 py-0.5 bg-[#1177bb] rounded cursor-default shrink-0">
          <GitBranch size={12} />
          <span className="truncate">hybrid</span>
        </div>
        <div className="flex items-center gap-3 text-white/85 truncate">
          <span className="hidden sm:inline">Run: {runStatus}</span>
          <span className="flex items-center gap-1 shrink-0">
            <AlertCircle size={12} />
            {errors}
          </span>
          <span className="flex items-center gap-1 shrink-0">
            <AlertTriangle size={12} />
            {warnings}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {activeAgents > 0 && (
          <div className="flex items-center gap-1.5 bg-[#1177bb] px-2 py-0.5 rounded">
            <Circle size={6} className="fill-white animate-pulse" />
            <span>{activeAgents} active</span>
          </div>
        )}
        <span className="hidden sm:inline">Agents {agents.length}</span>
        <span className="flex items-center gap-1" title="WebSocket">
          <Wifi size={12} className={wsConnected ? "text-[#89d185]" : "text-[#f48771]"} />
        </span>
        <button type="button" className="p-0.5 hover:bg-[#1177bb] rounded">
          <Bell size={12} />
        </button>
        {activeTab && (
          <span className="hidden lg:inline max-w-[100px] truncate">{activeTab.language}</span>
        )}
      </div>
    </div>
  );
}
