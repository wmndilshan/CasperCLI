import { useEffect, useRef } from "react";
import { wsEventsUrl } from "@/api";
import { useStudioStore } from "@/studio/store";

type WsPayload = {
  type: string;
  session_id?: string;
  payload?: Record<string, unknown>;
  ts?: string;
};

export function useWebSocket(enabled: boolean) {
  const appendRuntimeEvent = useStudioStore((s) => s.appendRuntimeEvent);
  const setWsConnected = useStudioStore((s) => s.setWsConnected);
  const ref = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const url = wsEventsUrl();
    const ws = new WebSocket(url);
    ref.current = ws;
    ws.onopen = () => setWsConnected(true);
    ws.onclose = () => setWsConnected(false);
    ws.onerror = () => setWsConnected(false);
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as WsPayload;
        appendRuntimeEvent({
          type: data.type,
          payload: (data.payload ?? {}) as Record<string, unknown>,
          ts: data.ts,
        });
      } catch {
        /* ignore */
      }
    };
    const ping = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, 15000);
    return () => {
      window.clearInterval(ping);
      ws.close();
      ref.current = null;
    };
  }, [appendRuntimeEvent, enabled, setWsConnected]);
}
