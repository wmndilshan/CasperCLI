import { Activity, Clock, MessageSquare, X, Zap } from "lucide-react";
import { useStudioStore } from "@/studio/store";
import { cn } from "@/studio/utils/cn";

const statusLabels: Record<string, { label: string; color: string }> = {
  idle: { label: "Idle", color: "text-[#858585]" },
  working: { label: "Working", color: "text-[#3b82f6]" },
  waiting: { label: "Waiting", color: "text-[#f59e0b]" },
  completed: { label: "Completed", color: "text-[#10b981]" },
  error: { label: "Error", color: "text-[#ef4444]" },
};

export function AgentDetailOverlay() {
  const selectedAgent = useStudioStore((s) => s.selectedAgent);
  const selectAgent = useStudioStore((s) => s.selectAgent);
  const agents = useStudioStore((s) => s.agents);
  const activities = useStudioStore((s) => s.activities);
  const addMessage = useStudioStore((s) => s.addMessage);
  const updateAgentStatus = useStudioStore((s) => s.updateAgentStatus);
  const addActivity = useStudioStore((s) => s.addActivity);

  if (!selectedAgent) return null;

  const agent = agents.find((a) => a.id === selectedAgent.id);
  if (!agent) return null;

  const agentActivities = activities.filter((a) => a.agentId === agent.id).slice(-6);
  const st = statusLabels[agent.status] ?? statusLabels.idle;

  const description =
    agent.kind === "llm_worker"
      ? "LLM worker for implementation and reasoning tasks."
      : `${agent.role.replace(/_/g, " ")} — part of the hybrid control plane.`;

  const quickCommands =
    agent.kind === "verification"
      ? ["Lint", "Tests", "Build"]
      : agent.kind === "merge"
        ? ["Merge patches", "Resolve conflicts"]
        : ["Status", "Summarize", "Next step"];

  const handleQuick = (cmd: string) => {
    addMessage({
      content: `@${agent.name} ${cmd}`,
      type: "command",
      mentions: [agent.name.toLowerCase()],
    });
    updateAgentStatus(agent.id, "working", cmd);
    addActivity({ agentId: agent.id, action: cmd, type: "analyze" });
    window.setTimeout(() => {
      updateAgentStatus(agent.id, "idle");
      addActivity({ agentId: agent.id, action: `${cmd} (local)`, type: "complete" });
      addMessage({
        agentId: agent.id,
        content: `Acknowledged: ${cmd}`,
        type: "agent",
      });
    }, 900);
  };

  return (
    <div
      className="fixed inset-0 bg-black/55 flex items-center justify-center z-50 backdrop-blur-[2px]"
      onClick={() => selectAgent(null)}
      onKeyDown={(e) => e.key === "Escape" && selectAgent(null)}
      role="presentation"
    >
      <div
        className="bg-[#252526] rounded-xl shadow-2xl w-[min(480px,94vw)] max-h-[85vh] overflow-hidden border border-[#454545]"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div
          className="p-4 border-b border-[#3c3c3c] relative"
          style={{
            background: `linear-gradient(135deg, ${agent.color}18, transparent)`,
          }}
        >
          <button
            type="button"
            onClick={() => selectAgent(null)}
            className="absolute top-3 right-3 p-1 hover:bg-[#3c3c3c] rounded transition-colors text-[#cccccc]"
          >
            <X size={18} />
          </button>

          <div className="flex items-center gap-4 pr-8">
            <div
              className="w-14 h-14 rounded-xl flex items-center justify-center text-2xl"
              style={{
                backgroundColor: `${agent.color}30`,
                border: `2px solid ${agent.color}66`,
              }}
            >
              {agent.avatar}
            </div>
            <div className="min-w-0">
              <h2 className="text-lg font-semibold text-white truncate">{agent.name}</h2>
              <p className="text-sm text-[#858585] capitalize truncate">{agent.role}</p>
              <div className={cn("flex items-center gap-1.5 mt-1 text-sm", st.color)}>
                <span className="inline-block w-2 h-2 rounded-full bg-current opacity-90" />
                {st.label}
                {agent.currentTask && ` · ${agent.currentTask}`}
              </div>
            </div>
          </div>
        </div>

        <div className="p-4 overflow-y-auto max-h-[48vh]">
          <div className="mb-4">
            <div className="text-[10px] font-semibold uppercase text-[#858585] mb-1">About</div>
            <p className="text-sm text-[#cccccc] leading-relaxed">{description}</p>
          </div>

          <div className="mb-4">
            <div className="text-[10px] font-semibold uppercase text-[#858585] mb-2 flex items-center gap-1">
              <Zap size={12} />
              Quick actions
            </div>
            <div className="flex flex-wrap gap-2">
              {quickCommands.map((cmd) => (
                <button
                  key={cmd}
                  type="button"
                  onClick={() => handleQuick(cmd)}
                  disabled={agent.status === "working"}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-sm transition-colors border border-[#3c3c3c]",
                    agent.status === "working"
                      ? "bg-[#2d2d2d] text-[#858585] cursor-not-allowed"
                      : "bg-[#2d2d2d] hover:bg-[#0e639c] hover:border-[#0e639c] text-[#cccccc]",
                  )}
                >
                  {cmd}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="text-[10px] font-semibold uppercase text-[#858585] mb-2 flex items-center gap-1">
              <Activity size={12} />
              Recent activity
            </div>
            {agentActivities.length > 0 ? (
              <div className="space-y-2">
                {agentActivities.map((activity) => (
                  <div
                    key={activity.id}
                    className="flex items-center gap-2 text-sm bg-[#2d2d2d] rounded p-2"
                  >
                    <Clock size={14} className="text-[#858585] shrink-0" />
                    <span className="text-[#cccccc] flex-1">{activity.action}</span>
                    <span className="text-[10px] text-[#858585] shrink-0">
                      {activity.timestamp.toLocaleTimeString()}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-[#858585] italic">No recent activity</div>
            )}
          </div>
        </div>

        <div className="p-3 border-t border-[#3c3c3c] bg-[#1e1e1e]">
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder={`Message ${agent.name}…`}
              className="flex-1 bg-[#3c3c3c] border border-[#555] rounded-lg px-3 py-2 text-sm text-[#cccccc] focus:outline-none focus:border-[#007fd4]"
              onKeyDown={(e) => {
                const t = e.target as HTMLInputElement;
                if (e.key === "Enter" && t.value.trim()) {
                  handleQuick(t.value);
                  t.value = "";
                }
              }}
            />
            <button
              type="button"
              className="p-2 bg-[#0e639c] hover:bg-[#1177bb] rounded-lg transition-colors text-white"
              aria-label="Send"
            >
              <MessageSquare size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
