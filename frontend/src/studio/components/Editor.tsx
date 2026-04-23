import Editor from "@monaco-editor/react";
import { Circle, Save, X } from "lucide-react";
import { useStudioStore } from "@/studio/store";
import { cn } from "@/studio/utils/cn";
import { apiPut } from "@/api";

const getLanguage = (filename: string): string => {
  const ext = filename.split(".").pop()?.toLowerCase();
  const langMap: Record<string, string> = {
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
  return langMap[ext || ""] || "plaintext";
};

export function EditorArea() {
  const tabs = useStudioStore((s) => s.tabs);
  const activeTabId = useStudioStore((s) => s.activeTabId);
  const setActiveTab = useStudioStore((s) => s.setActiveTab);
  const closeTab = useStudioStore((s) => s.closeTab);
  const updateTabContent = useStudioStore((s) => s.updateTabContent);
  const markTabSaved = useStudioStore((s) => s.markTabSaved);
  const diagnostics = useStudioStore((s) => s.diagnostics);

  const activeTab = tabs.find((t) => t.id === activeTabId);

  const saveActive = async () => {
    if (!activeTab) return;
    const path = activeTab.path ?? activeTab.id;
    await apiPut("/workspace/file", { path, content: activeTab.content });
    markTabSaved(activeTab.id);
  };

  return (
    <div className="flex-1 flex flex-col bg-[#1e1e1e] min-w-0">
      <div className="flex bg-[#252526] border-b border-[#1e1e1e] overflow-x-auto shrink-0">
        {tabs.map((tab) => (
          <div
            key={tab.id}
            className={cn(
              "flex items-center gap-2 px-3 py-2 border-r border-[#252526] cursor-pointer min-w-[120px] max-w-[200px] group",
              activeTabId === tab.id
                ? "bg-[#1e1e1e] border-t-2 border-t-[#007fd4]"
                : "bg-[#2d2d2d] hover:bg-[#2a2d2e]",
            )}
            onClick={() => setActiveTab(tab.id)}
            onKeyDown={(e) => e.key === "Enter" && setActiveTab(tab.id)}
            role="tab"
            tabIndex={0}
          >
            <span className="text-sm truncate flex-1 text-[#cccccc]">{tab.name}</span>
            {tab.isModified && (
              <Circle size={8} className="fill-[#c5c5c5] text-[#c5c5c5] shrink-0" />
            )}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                closeTab(tab.id);
              }}
              className="opacity-0 group-hover:opacity-100 hover:bg-[#3c3c3c] rounded p-0.5 transition-opacity text-[#cccccc]"
            >
              <X size={14} />
            </button>
          </div>
        ))}
        {activeTab && (
          <button
            type="button"
            onClick={() => void saveActive()}
            className="ml-auto mr-2 my-1 flex items-center gap-1 px-2 py-1 rounded text-xs bg-[#0e639c] hover:bg-[#1177bb] text-white shrink-0"
          >
            <Save size={14} />
            Save
          </button>
        )}
      </div>

      {activeTab ? (
        <div className="flex-1 relative min-h-0">
          <Editor
            height="100%"
            path={activeTab.id}
            language={getLanguage(activeTab.name)}
            value={activeTab.content}
            theme="vs-dark"
            onChange={(value) => {
              if (value !== undefined) updateTabContent(activeTab.id, value);
            }}
            options={{
              fontSize: 14,
              fontFamily: '"Cascadia Code", "Fira Code", Consolas, monospace',
              minimap: { enabled: true },
              scrollBeyondLastLine: false,
              automaticLayout: true,
              wordWrap: "on",
              tabSize: 2,
              padding: { top: 8 },
            }}
          />
          {diagnostics.filter((d) => d.file === activeTab.name).length > 0 && (
            <div className="absolute bottom-4 right-4 bg-[#252526] rounded-lg shadow-lg border border-[#3c3c3c] p-2 max-w-xs">
              {diagnostics
                .filter((d) => d.file === activeTab.name)
                .map((d) => (
                  <div key={d.id} className="flex items-start gap-2 text-xs py-1 text-[#cccccc]">
                    <Circle
                      size={8}
                      className={cn(
                        "mt-1 fill-current shrink-0",
                        d.severity === "error" && "text-red-500",
                        d.severity === "warning" && "text-yellow-500",
                        d.severity === "info" && "text-blue-500",
                      )}
                    />
                    <span>
                      Line {d.line}: {d.message}
                    </span>
                  </div>
                ))}
            </div>
          )}
        </div>
      ) : (
        <WelcomeScreen />
      )}
    </div>
  );
}

function WelcomeScreen() {
  return (
    <div className="flex-1 flex items-center justify-center bg-[#1e1e1e] p-8">
      <div className="text-center max-w-lg">
        <h1 className="text-3xl font-light text-[#e8e8e8] mb-2 tracking-tight">
          Casper Hybrid Studio
        </h1>
        <p className="text-[#858585] mb-8 text-sm">
          VS Code–style shell for your multi-agent runtime. Sync the team, run the DAG, watch events
          in the bottom panel.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-left">
          {[
            { icon: "🗂️", t: "Explorer", d: "Browse files from the backend workspace root." },
            { icon: "🧠", t: "Agents", d: "Live agent roster from /team." },
            { icon: "📡", t: "Events", d: "WebSocket stream: tasks, locks, patches." },
          ].map((x) => (
            <div
              key={x.t}
              className="bg-[#252526] rounded-lg p-4 border border-[#3c3c3c] hover:border-[#007fd4]/40 transition-colors"
            >
              <div className="text-2xl mb-2">{x.icon}</div>
              <div className="text-sm font-medium text-[#cccccc]">{x.t}</div>
              <div className="text-xs text-[#858585] mt-1 leading-relaxed">{x.d}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
