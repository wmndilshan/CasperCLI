/**
 * Right rail: agent/runtime dashboard (spec: IDE layout with explorer | editor | agent panel).
 */
import { useState } from "react";
import {
  Bot,
  Circle,
  GitBranch,
  HardDrive,
  Layers,
  ListTodo,
  ShieldAlert,
  TestTube2,
  Users,
} from "lucide-react";
import { useStudioStore } from "@/studio/store";
import { cn } from "@/studio/utils/cn";
import { RuntimeGraph } from "./RuntimeGraph";
import { TeamsPanel } from "./TeamsPanel";
import {
  approvePatch,
  commitPatches,
  rejectPatch,
  resolveConflict,
  useRefreshRuntime,
} from "@/hooks/useRefreshRuntime";

const dashTabs = [
  { id: "agents" as const, label: "Agents", icon: Bot },
  { id: "dag" as const, label: "DAG", icon: GitBranch },
  { id: "tasks" as const, label: "Tasks", icon: ListTodo },
  { id: "locks" as const, label: "Locks", icon: Layers },
  { id: "resources" as const, label: "Resources", icon: HardDrive },
  { id: "patches" as const, label: "Patches", icon: Layers },
  { id: "conflicts" as const, label: "Conflicts", icon: ShieldAlert },
  { id: "verify" as const, label: "Verify", icon: TestTube2 },
  { id: "teams" as const, label: "Teams", icon: Users },
];

const statusDot: Record<string, string> = {
  idle: "bg-[#858585]",
  working: "bg-[#3b82f6] animate-pulse",
  waiting: "bg-[#f59e0b]",
  completed: "bg-[#10b981]",
  error: "bg-[#ef4444]",
};

export function RightDashboard() {
  const [tab, setTab] = useState<(typeof dashTabs)[number]["id"]>("agents");
  const agents = useStudioStore((s) => s.agents);
  const runtimeTasks = useStudioStore((s) => s.runtimeTasks);
  const locks = useStudioStore((s) => s.locks);
  const resources = useStudioStore((s) => s.resources);
  const patches = useStudioStore((s) => s.patches);
  const conflicts = useStudioStore((s) => s.conflicts);
  const verification = useStudioStore((s) => s.verification);
  const selectAgent = useStudioStore((s) => s.selectAgent);
  const { refresh } = useRefreshRuntime();
  const [conflictNotes, setConflictNotes] = useState<Record<string, string>>({});

  const tasksForAgent = (agentId: string) =>
    Object.values(runtimeTasks).filter((t) => t.assigned_agent_id === agentId);

  return (
    <div className="w-[22rem] min-w-[18rem] max-w-[28rem] flex flex-col bg-[#252526] border-l border-[#1e1e1e] shrink-0">
      <div className="px-2 py-1.5 border-b border-[#333] text-[10px] font-semibold uppercase tracking-wide text-[#bbbbbb] shrink-0">
        Runtime dashboard
      </div>
      <div className="flex flex-wrap gap-0.5 p-1 border-b border-[#333] shrink-0 max-h-[72px] overflow-y-auto">
        {dashTabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            title={label}
            className={cn(
              "flex items-center gap-1 px-1.5 py-1 rounded text-[10px] transition-colors",
              tab === id
                ? "bg-[#094771] text-white"
                : "text-[#858585] hover:bg-[#2a2d2e] hover:text-[#cccccc]",
            )}
          >
            <Icon size={12} />
            <span className="hidden xl:inline">{label}</span>
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto min-h-0 text-xs text-[#cccccc] p-2">
        {tab === "agents" && (
          <div className="space-y-2">
            {agents.length === 0 && (
              <p className="text-[#858585]">Synthesize a team to see agents here.</p>
            )}
            {agents.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => selectAgent(a)}
                className="w-full text-left p-2 rounded border border-[#3c3c3c] bg-[#2d2d2d] hover:border-[#007fd4]/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg">{a.avatar}</span>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{a.name}</div>
                    <div className="text-[10px] text-[#858585] truncate">{a.role}</div>
                  </div>
                  <Circle size={8} className={cn("fill-current shrink-0", statusDot[a.status])} />
                </div>
                {tasksForAgent(a.id).length > 0 && (
                  <div className="mt-1.5 text-[10px] text-[#58a6ff] space-y-0.5">
                    {tasksForAgent(a.id).map((t) => (
                      <div key={t.id} className="truncate">
                        {t.id}: {t.status}
                      </div>
                    ))}
                  </div>
                )}
              </button>
            ))}
          </div>
        )}

        {tab === "dag" && (
          <div>
            <RuntimeGraph compact />
          </div>
        )}

        {tab === "tasks" && (
          <ul className="space-y-1.5">
            {Object.values(runtimeTasks).length === 0 && (
              <li className="text-[#858585]">No tasks (run DAG first).</li>
            )}
            {Object.values(runtimeTasks).map((t) => (
              <li
                key={t.id}
                className="p-2 rounded bg-[#2d2d2d] border border-[#3c3c3c] text-[11px]"
              >
                <div className="font-medium text-[#e8e8e8]">{t.title}</div>
                <div className="text-[#858585] mt-0.5">
                  {t.id} · <span className="text-[#89d185]">{t.status}</span>
                </div>
                <div className="text-[#6b6b6b] mt-0.5 truncate">→ {t.assigned_agent_id}</div>
                {t.dependencies?.length > 0 && (
                  <div className="text-[10px] text-[#858585] mt-1">
                    deps: {t.dependencies.join(", ")}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}

        {tab === "locks" && (
          <ul className="space-y-1">
            {locks.length === 0 && <li className="text-[#858585]">No active file locks.</li>}
            {locks.map((l, i) => (
              <li key={i} className="p-2 rounded bg-[#2d2d2d] border border-[#3c3c3c]">
                <div className="truncate font-mono text-[11px]">{String(l.path)}</div>
                <div className="text-[#858585] text-[10px]">
                  {String(l.lock_type)} · {String(l.agent_id)}
                </div>
              </li>
            ))}
          </ul>
        )}

        {tab === "resources" && (
          <ul className="space-y-1">
            {resources.length === 0 && (
              <li className="text-[#858585]">No exclusive resources claimed (e.g. merge_lane).</li>
            )}
            {resources.map((r, i) => (
              <li key={i} className="p-2 rounded bg-[#2d2d2d] border border-[#3c3c3c]">
                <span className="text-[#89d185]">{String(r.resource)}</span>
                <span className="text-[#858585]"> → </span>
                <span className="font-mono text-[10px]">{String(r.agent_id)}</span>
              </li>
            ))}
          </ul>
        )}

        {tab === "patches" && (
          <div className="space-y-2">
            <div className="flex gap-2">
              <button
                type="button"
                onClick={async () => {
                  await commitPatches();
                  await refresh();
                }}
                className="px-2 py-1 rounded bg-[#388a26] text-white text-[11px]"
              >
                Commit approved
              </button>
            </div>
            {patches.length === 0 && <p className="text-[#858585]">No patches.</p>}
            {patches.map((p) => (
              <div key={String(p.id)} className="p-2 rounded bg-[#2d2d2d] border border-[#3c3c3c]">
                <div className="font-mono text-[11px]">{String(p.id)}</div>
                <div className="text-[#858585] text-[10px]">{String(p.status)}</div>
                {String(p.status) === "proposed" && (
                  <div className="flex gap-1 mt-1">
                    <button
                      type="button"
                      className="px-2 py-0.5 rounded bg-[#0e639c] text-white text-[10px]"
                      onClick={async () => {
                        await approvePatch(String(p.id));
                        await refresh();
                      }}
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      className="px-2 py-0.5 rounded bg-[#a31515] text-white text-[10px]"
                      onClick={async () => {
                        await rejectPatch(String(p.id));
                        await refresh();
                      }}
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {tab === "conflicts" && (
          <div className="space-y-2">
            {conflicts.length === 0 && <p className="text-[#858585]">No conflicts.</p>}
            {conflicts.map((c) => (
              <div key={String(c.id)} className="p-2 rounded bg-[#2d2d2d] border border-[#3c3c3c]">
                <p className="text-[11px]">{String(c.description)}</p>
                <input
                  className="mt-1 w-full bg-[#3c3c3c] border border-[#555] rounded px-2 py-1 text-[11px] text-[#cccccc]"
                  placeholder="Resolution"
                  value={conflictNotes[String(c.id)] ?? ""}
                  onChange={(e) =>
                    setConflictNotes((m) => ({ ...m, [String(c.id)]: e.target.value }))
                  }
                />
                <button
                  type="button"
                  className="mt-1 px-2 py-1 rounded bg-[#0e639c] text-white text-[10px]"
                  onClick={async () => {
                    await resolveConflict(String(c.id), conflictNotes[String(c.id)] || "resolved");
                    await refresh();
                  }}
                >
                  Resolve
                </button>
              </div>
            ))}
          </div>
        )}

        {tab === "verify" && (
          <div>
            {!verification && <p className="text-[#858585]">No verification result yet.</p>}
            {verification && (
              <div className="space-y-2">
                <div className="flex gap-3 text-[11px]">
                  <span
                    className={
                      verification.lint_ok === true ? "text-[#89d185]" : "text-[#f48771]"
                    }
                  >
                    lint {String(verification.lint_ok)}
                  </span>
                  <span
                    className={
                      verification.test_ok === true ? "text-[#89d185]" : "text-[#f48771]"
                    }
                  >
                    tests {String(verification.test_ok)}
                  </span>
                  <span
                    className={
                      verification.build_ok === true ? "text-[#89d185]" : "text-[#f48771]"
                    }
                  >
                    build {String(verification.build_ok)}
                  </span>
                </div>
                <pre className="text-[10px] text-[#9d9d9d] whitespace-pre-wrap break-all max-h-64 overflow-y-auto bg-[#1e1e1e] p-2 rounded border border-[#333]">
                  {JSON.stringify(verification, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}

        {tab === "teams" && <TeamsPanel />}
      </div>
    </div>
  );
}
