import { Loader2, Play, RefreshCw, Sparkles, Wifi, WifiOff } from "lucide-react";
import { useStudioStore } from "@/studio/store";
import { useRefreshRuntime, startRun, synthesizeTeam } from "@/hooks/useRefreshRuntime";

export function TitleBar() {
  const projectRoot = useStudioStore((s) => s.projectRoot);
  const setProjectRoot = useStudioStore((s) => s.setProjectRoot);
  const goal = useStudioStore((s) => s.goal);
  const setGoal = useStudioStore((s) => s.setGoal);
  const wsConnected = useStudioStore((s) => s.wsConnected);
  const runStatus = useStudioStore((s) => s.runStatus);
  const setRunStatus = useStudioStore((s) => s.setRunStatus);
  const { refresh, pollRunStatus } = useRefreshRuntime();

  const busy = runStatus === "running";

  return (
    <div className="h-9 shrink-0 bg-[#323233] flex items-center px-3 gap-3 text-sm select-none border-b border-[#252526]">
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-lg shrink-0" aria-hidden>
          👻
        </span>
        <span className="font-medium text-[#e8e8e8] truncate">Casper Hybrid Studio</span>
        <span className="text-[#858585] text-xs hidden sm:inline truncate">
          Multi-agent orchestration
        </span>
      </div>

      <div className="flex items-center gap-2 flex-1 min-w-0 justify-center max-w-3xl mx-auto">
        <input
          type="text"
          title="Project root"
          placeholder="Project root"
          value={projectRoot}
          onChange={(e) => setProjectRoot(e.target.value)}
          className="w-40 sm:w-48 bg-[#3c3c3c] border border-[#454545] rounded px-2 py-1 text-xs text-[#cccccc] focus:outline-none focus:border-[#007fd4]"
        />
        <input
          type="text"
          title="Goal"
          placeholder="Goal…"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          className="flex-1 min-w-[120px] bg-[#3c3c3c] border border-[#454545] rounded px-2 py-1 text-xs text-[#cccccc] focus:outline-none focus:border-[#007fd4]"
        />
        <button
          type="button"
          onClick={() => void refresh()}
          className="flex items-center gap-1 px-2 py-1 rounded bg-[#3c3c3c] hover:bg-[#4a4a4a] text-xs text-[#cccccc] border border-[#454545]"
        >
          <RefreshCw size={14} />
          <span className="hidden md:inline">Sync</span>
        </button>
        <button
          type="button"
          onClick={async () => {
            await synthesizeTeam(goal, projectRoot, 6);
            await refresh();
          }}
          className="flex items-center gap-1 px-2 py-1 rounded bg-[#0e639c] hover:bg-[#1177bb] text-xs text-white"
        >
          <Sparkles size={14} />
          Team
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={async () => {
            try {
              setRunStatus("running");
              await startRun(goal, projectRoot);
              await pollRunStatus();
              await refresh();
            } catch {
              setRunStatus("idle");
            }
          }}
          className="flex items-center gap-1 px-2 py-1 rounded bg-[#388a26] hover:bg-[#3f9b2d] disabled:opacity-50 text-xs text-white"
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          Run
        </button>
      </div>

      <div className="flex items-center gap-2 shrink-0 text-xs">
        <span
          className={`flex items-center gap-1 px-2 py-0.5 rounded ${
            wsConnected ? "text-[#89d185]" : "text-[#f48771]"
          }`}
        >
          {wsConnected ? <Wifi size={14} /> : <WifiOff size={14} />}
          {wsConnected ? "Live" : "WS"}
        </span>
        <span className="text-[#858585] capitalize hidden sm:inline">{runStatus}</span>
      </div>
    </div>
  );
}
