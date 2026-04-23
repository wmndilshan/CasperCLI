import { useCallback } from "react";
import { apiGet, apiPost } from "@/api";
import { useStudioStore } from "@/studio/store";
import type { RuntimeTask } from "@/studio/types";

type TeamSpecApi = {
  project_root: string;
  agents: Array<{
    id: string;
    kind: string;
    role: string;
    status: string;
    current_tasks?: string[];
  }>;
};

export function useRefreshRuntime() {
  const syncAgentsFromBackend = useStudioStore((s) => s.syncAgentsFromBackend);
  const setProjectRoot = useStudioStore((s) => s.setProjectRoot);
  const setRuntimeTasks = useStudioStore((s) => s.setRuntimeTasks);
  const setLocks = useStudioStore((s) => s.setLocks);
  const setPatches = useStudioStore((s) => s.setPatches);
  const setConflicts = useStudioStore((s) => s.setConflicts);
  const setVerification = useStudioStore((s) => s.setVerification);
  const setResources = useStudioStore((s) => s.setResources);

  const refresh = useCallback(async () => {
    try {
      const team = await apiGet<TeamSpecApi>("/team");
      syncAgentsFromBackend(team.agents);
      setProjectRoot(team.project_root);
    } catch {
      /* no team yet */
    }
    try {
      const tasksRes = await apiGet<{ tasks: Record<string, RuntimeTask> }>("/tasks");
      setRuntimeTasks(tasksRes.tasks ?? {});
    } catch {
      setRuntimeTasks({});
    }
    try {
      const locks = await apiGet<{ locks: Array<Record<string, unknown>> }>("/locks");
      setLocks(locks.locks ?? []);
    } catch {
      setLocks([]);
    }
    try {
      const patches = await apiGet<{ patches: Array<Record<string, unknown>> }>("/patches");
      setPatches(patches.patches ?? []);
    } catch {
      setPatches([]);
    }
    try {
      const conflicts = await apiGet<{ conflicts: Array<Record<string, unknown>> }>(
        "/conflicts",
      );
      setConflicts(conflicts.conflicts ?? []);
    } catch {
      setConflicts([]);
    }
    try {
      const res = await apiGet<{ resources: Array<Record<string, unknown>> }>("/resources");
      setResources(res.resources ?? []);
    } catch {
      setResources([]);
    }
  }, [
    setConflicts,
    setLocks,
    setPatches,
    setProjectRoot,
    setResources,
    setRuntimeTasks,
    syncAgentsFromBackend,
  ]);

  const pollRunStatus = useCallback(async () => {
    const st = await apiGet<{
      status: string;
      result?: { verification?: Record<string, unknown> };
    }>("/run/status");
    useStudioStore.getState().setRunStatus(st.status);
    if (st.status === "completed" && st.result?.verification) {
      setVerification(st.result.verification);
    }
    if (st.status === "failed") {
      setVerification({ error: "run failed" });
    }
  }, [setVerification]);

  return { refresh, pollRunStatus };
}

export async function synthesizeTeam(goal: string, projectRoot: string, teamSize: number) {
  return apiPost("/team/synthesize", {
    goal,
    project_root: projectRoot,
    team_size: teamSize,
    strict: true,
    project_context: "",
  });
}

export async function startRun(goal: string, projectRoot: string) {
  return apiPost("/run", {
    goal,
    project_root: projectRoot,
    team_size: 6,
    strict: true,
    parallel: true,
    max_parallel_tasks: 4,
  });
}

export async function approvePatch(patchId: string) {
  return apiPost("/patch/approve", { patch_id: patchId });
}

export async function rejectPatch(patchId: string) {
  return apiPost("/patch/reject", { patch_id: patchId });
}

export async function resolveConflict(conflictId: string, resolution: string) {
  return apiPost("/conflict/resolve", { conflict_id: conflictId, resolution });
}

export async function commitPatches() {
  return apiPost<{ written: string[] }>("/patch/commit", {});
}
