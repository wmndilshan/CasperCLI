import { useEffect } from "react";
import { StudioApp } from "@/studio/StudioApp";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useRefreshRuntime } from "@/hooks/useRefreshRuntime";
import { useStudioStore } from "@/studio/store";

export default function App() {
  useWebSocket(true);
  const { refresh, pollRunStatus } = useRefreshRuntime();
  const runtimeEvents = useStudioStore((s) => s.runtimeEvents);
  const setVerification = useStudioStore((s) => s.setVerification);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const id = window.setInterval(() => {
      if (useStudioStore.getState().runStatus === "running") {
        void refresh();
        void pollRunStatus();
      }
    }, 900);
    return () => window.clearInterval(id);
  }, [refresh, pollRunStatus]);

  useEffect(() => {
    const last = runtimeEvents[runtimeEvents.length - 1];
    if (!last) return;
    if (last.type === "VERIFICATION_RESULT") {
      setVerification(last.payload as Record<string, unknown>);
    }
    if (last.type === "CONFLICT_DETECTED" || last.type === "PATCH_PROPOSED") {
      void refresh();
    }
  }, [runtimeEvents, refresh, setVerification]);

  return <StudioApp />;
}
