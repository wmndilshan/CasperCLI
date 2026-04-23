import { useCallback, useEffect } from "react";
import { ChevronRight, File, Folder } from "lucide-react";
import { apiBase } from "@/api";
import { useStudioStore } from "@/studio/store";

function langFromName(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase();
  const m: Record<string, string> = {
    ts: "typescript",
    tsx: "typescript",
    js: "javascript",
    jsx: "javascript",
    css: "css",
    json: "json",
    md: "markdown",
    html: "html",
    py: "python",
  };
  return m[ext || ""] || "plaintext";
}

export function FileExplorer() {
  const explorerPath = useStudioStore((s) => s.explorerPath);
  const setExplorerPath = useStudioStore((s) => s.setExplorerPath);
  const explorerEntries = useStudioStore((s) => s.explorerEntries);
  const setExplorerEntries = useStudioStore((s) => s.setExplorerEntries);
  const openWorkspaceFile = useStudioStore((s) => s.openWorkspaceFile);
  const projectRoot = useStudioStore((s) => s.projectRoot);

  const load = useCallback(async () => {
    const u = new URL(`${apiBase}/workspace/list`);
    u.searchParams.set("path", explorerPath);
    try {
      const res = await fetch(u);
      if (!res.ok) return;
      const data = (await res.json()) as {
        entries: Array<{ name: string; path: string; is_dir: boolean }>;
      };
      setExplorerEntries(data.entries ?? []);
    } catch {
      setExplorerEntries([]);
    }
  }, [explorerPath, setExplorerEntries]);

  useEffect(() => {
    void load();
  }, [load, projectRoot]);

  return (
    <div className="text-[#cccccc]">
      <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-[#bbbbbb] border-b border-[#333] flex items-center justify-between gap-2">
        <span>Explorer</span>
        <span className="text-[10px] font-normal text-[#858585] truncate" title={explorerPath}>
          {explorerPath}
        </span>
      </div>
      <div className="py-1">
        {explorerPath !== "." && (
          <button
            type="button"
            onClick={() => {
              const parts = explorerPath.split("/").filter(Boolean);
              parts.pop();
              setExplorerPath(parts.length ? parts.join("/") : ".");
            }}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-[13px] text-[#858585] hover:bg-[#2a2d2e] text-left"
          >
            <ChevronRight size={14} className="rotate-[-90deg]" />
            ..
          </button>
        )}
        {explorerEntries.map((e) => (
          <button
            key={e.path}
            type="button"
            onClick={async () => {
              if (e.is_dir) {
                setExplorerPath(e.path);
                return;
              }
              const u = new URL(`${apiBase}/workspace/file`);
              u.searchParams.set("path", e.path);
              const res = await fetch(u);
              if (!res.ok) return;
              const data = (await res.json()) as { content: string; path: string };
              openWorkspaceFile(data.path, e.name, data.content, langFromName(e.name));
            }}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-[13px] text-left hover:bg-[#2a2d2e] text-[#cccccc]"
          >
            {e.is_dir ? (
              <Folder size={16} className="text-[#dcb67a] shrink-0" />
            ) : (
              <File size={16} className="text-[#858585] shrink-0" />
            )}
            <span className="truncate">{e.name}</span>
          </button>
        ))}
        {explorerEntries.length === 0 && (
          <p className="px-3 py-4 text-xs text-[#858585]">
            Synthesize a team or run the backend so the workspace root is set. Then open folders
            here.
          </p>
        )}
      </div>
    </div>
  );
}
