import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  AlertCircle,
  AtSign,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Edit3,
  Eye,
  FileOutput,
  MessageSquare,
  Radio,
  Send,
  Terminal,
  TestTube,
  XCircle,
} from "lucide-react";
import { useStudioStore } from "@/studio/store";
import { cn } from "@/studio/utils/cn";

const tabs = [
  { id: "events" as const, icon: Radio, label: "Events" },
  { id: "chat" as const, icon: MessageSquare, label: "Chat" },
  { id: "problems" as const, icon: AlertCircle, label: "Problems" },
  { id: "terminal" as const, icon: Terminal, label: "Terminal" },
  { id: "output" as const, icon: FileOutput, label: "Output" },
];

const activityIcons: Record<string, ReactNode> = {
  edit: <Edit3 size={14} className="text-blue-400" />,
  analyze: <Radio size={14} className="text-purple-400" />,
  review: <Eye size={14} className="text-amber-400" />,
  test: <TestTube size={14} className="text-green-400" />,
  complete: <CheckCircle size={14} className="text-green-500" />,
  error: <XCircle size={14} className="text-red-400" />,
  comment: <MessageSquare size={14} className="text-blue-400" />,
};

export function Panel() {
  const panelView = useStudioStore((s) => s.panelView);
  const setPanelView = useStudioStore((s) => s.setPanelView);
  const isPanelOpen = useStudioStore((s) => s.isPanelOpen);
  const togglePanel = useStudioStore((s) => s.togglePanel);
  const messages = useStudioStore((s) => s.messages);
  const activities = useStudioStore((s) => s.activities);
  const commandInput = useStudioStore((s) => s.commandInput);
  const setCommandInput = useStudioStore((s) => s.setCommandInput);
  const addMessage = useStudioStore((s) => s.addMessage);
  const agents = useStudioStore((s) => s.agents);
  const updateAgentStatus = useStudioStore((s) => s.updateAgentStatus);
  const addActivity = useStudioStore((s) => s.addActivity);
  const diagnostics = useStudioStore((s) => s.diagnostics);
  const runtimeEvents = useStudioStore((s) => s.runtimeEvents);

  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [showMentions, setShowMentions] = useState(false);
  const [mentionFilter, setMentionFilter] = useState("");

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, activities]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setCommandInput(value);
    const lastAtIndex = value.lastIndexOf("@");
    if (lastAtIndex !== -1) {
      const afterAt = value.slice(lastAtIndex + 1);
      if (!afterAt.includes(" ")) {
        setShowMentions(true);
        setMentionFilter(afterAt.toLowerCase());
        return;
      }
    }
    setShowMentions(false);
  };

  const handleMentionSelect = (agentName: string) => {
    const lastAtIndex = commandInput.lastIndexOf("@");
    const newInput = commandInput.slice(0, lastAtIndex) + `@${agentName} `;
    setCommandInput(newInput);
    setShowMentions(false);
    inputRef.current?.focus();
  };

  const handleSendCommand = () => {
    if (!commandInput.trim()) return;
    const mentions = [...commandInput.matchAll(/@(\w+)/g)].map((m) => m[1]);
    addMessage({ content: commandInput, type: "command", mentions });
    const mentionedAgents = agents.filter((a) =>
      mentions.some((m) => a.name.toLowerCase().replace(/\s/g, "") === m.toLowerCase()),
    );
    mentionedAgents.forEach((agent) => {
      updateAgentStatus(agent.id, "working", "Command…");
      window.setTimeout(() => {
        addMessage({
          agentId: agent.id,
          content: "Noted (local). Backend runs use the title bar.",
          type: "agent",
        });
        updateAgentStatus(agent.id, "idle");
        addActivity({ agentId: agent.id, action: "Chat command", type: "comment" });
      }, 600);
    });
    setCommandInput("");
  };

  const filteredAgents = agents.filter((a) =>
    a.name.toLowerCase().includes(mentionFilter.replace(/\s/g, "")),
  );

  return (
    <div
      className={`bg-[#1e1e1e] border-t border-[#3c3c3c] flex flex-col shrink-0 ${
        isPanelOpen ? "h-[min(320px,38vh)]" : "h-9"
      }`}
    >
      <div className="flex items-center justify-between bg-[#252526] border-b border-[#3c3c3c] shrink-0">
        <div className="flex overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => {
                setPanelView(tab.id);
                if (!isPanelOpen) togglePanel();
              }}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 text-xs transition-colors whitespace-nowrap",
                panelView === tab.id && isPanelOpen
                  ? "text-white border-b-2 border-[#007fd4] bg-[#1e1e1e]"
                  : "text-[#858585] hover:text-[#cccccc]",
              )}
            >
              <tab.icon size={14} />
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={togglePanel}
          className="p-1.5 text-[#858585] hover:text-white hover:bg-[#3c3c3c] rounded shrink-0"
        >
          {isPanelOpen ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
        </button>
      </div>

      {isPanelOpen && (
        <div className="flex-1 overflow-hidden flex min-h-0">
          <div className="flex-1 overflow-y-auto p-2 min-w-0">
            {panelView === "events" && (
              <div className="font-mono text-[11px] space-y-1.5 text-[#cccccc]">
                {[...runtimeEvents].reverse().map((ev, i) => (
                  <div key={i} className="border-b border-[#333] pb-1.5">
                    <span className="text-[#58a6ff]">{ev.type}</span>
                    {ev.ts && <span className="text-[#858585] ml-2">{ev.ts}</span>}
                    <pre className="text-[#9d9d9d] mt-0.5 whitespace-pre-wrap break-all">
                      {JSON.stringify(ev.payload, null, 0)}
                    </pre>
                  </div>
                ))}
                {runtimeEvents.length === 0 && (
                  <div className="text-[#858585]">Waiting for WebSocket events…</div>
                )}
              </div>
            )}

            {panelView === "terminal" && (
              <div className="font-mono text-sm text-[#cccccc] p-2">
                <div className="text-[#858585]">Hybrid runtime</div>
                <div className="text-[#89d185]">Backend: http://127.0.0.1:8765</div>
                <div className="text-[#858585] mt-2">
                  Use <span className="text-white">Team</span> and <span className="text-white">Run</span>{" "}
                  in the title bar. Patches, locks, and verification are in the right dashboard.
                </div>
              </div>
            )}

            {panelView === "problems" && (
              <div className="space-y-1">
                {diagnostics.length === 0 && (
                  <div className="text-sm text-[#858585] p-2">No problems.</div>
                )}
                {diagnostics.map((d) => (
                  <div
                    key={d.id}
                    className="flex items-start gap-2 p-2 hover:bg-[#2a2d2e] rounded text-sm"
                  >
                    <AlertCircle
                      size={16}
                      className={cn(
                        "mt-0.5 shrink-0",
                        d.severity === "error" && "text-red-500",
                        d.severity === "warning" && "text-yellow-500",
                        d.severity === "info" && "text-blue-500",
                      )}
                    />
                    <span className="text-[#cccccc]">{d.message}</span>
                    <span className="text-[#858585] text-xs ml-auto shrink-0">
                      {d.file}:{d.line}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {panelView === "output" && (
              <div className="font-mono text-sm text-[#cccccc] p-2">
                <div className="text-[#858585]">[studio]</div>
                <div className="text-[#89d185]">UI shell loaded</div>
                <div className="text-[#858585] mt-1">Patches and verification sync from /patches and /run/status.</div>
              </div>
            )}

            {panelView === "chat" && (
              <div className="flex flex-col h-full min-h-[200px]">
                <div className="flex-1 overflow-y-auto space-y-2 p-2">
                  {messages.map((msg) => {
                    const ag = msg.agentId ? agents.find((a) => a.id === msg.agentId) : null;
                    return (
                      <div
                        key={msg.id}
                        className={cn(
                          "flex gap-2",
                          msg.type === "user" || msg.type === "command" ? "flex-row-reverse" : "",
                        )}
                      >
                        {ag && (
                          <div
                            className="w-7 h-7 rounded-lg flex items-center justify-center text-sm shrink-0"
                            style={{ backgroundColor: `${ag.color}33` }}
                          >
                            {ag.avatar}
                          </div>
                        )}
                        {msg.type === "system" && (
                          <div className="w-7 h-7 rounded-lg bg-[#3c3c3c] flex items-center justify-center text-sm shrink-0">
                            ⚙
                          </div>
                        )}
                        {(msg.type === "user" || msg.type === "command") && (
                          <div className="w-7 h-7 rounded-lg bg-[#0e639c] flex items-center justify-center text-sm shrink-0">
                            👤
                          </div>
                        )}
                        <div
                          className={cn(
                            "max-w-[75%] rounded-lg px-3 py-2 text-sm",
                            msg.type === "user" || msg.type === "command"
                              ? "bg-[#0e639c]"
                              : "bg-[#2d2d2d]",
                          )}
                        >
                          {msg.type === "command" && msg.mentions && msg.mentions.length > 0 && (
                            <div className="flex gap-1 mb-1 flex-wrap">
                              {msg.mentions.map((m) => (
                                <span
                                  key={m}
                                  className="text-[10px] bg-[#1e1e1e] px-1.5 py-0.5 rounded text-blue-300"
                                >
                                  @{m}
                                </span>
                              ))}
                            </div>
                          )}
                          <span className="text-[#ececec]">{msg.content}</span>
                          <div className="text-[10px] text-[#c0c0c0]/80 mt-1">
                            {msg.timestamp.toLocaleTimeString()}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  <div ref={messagesEndRef} />
                </div>

                <div className="p-2 relative border-t border-[#333]">
                  {showMentions && filteredAgents.length > 0 && (
                    <div className="absolute bottom-full left-2 right-2 mb-1 bg-[#252526] rounded-lg border border-[#3c3c3c] shadow-lg overflow-hidden z-10 max-h-40 overflow-y-auto">
                      {filteredAgents.map((agent) => (
                        <button
                          key={agent.id}
                          type="button"
                          onClick={() => handleMentionSelect(agent.name.replace(/\s/g, ""))}
                          className="w-full flex items-center gap-2 px-3 py-2 hover:bg-[#094771] text-left"
                        >
                          <span>{agent.avatar}</span>
                          <span className="text-sm text-[#cccccc]">{agent.name}</span>
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="flex items-center gap-2 bg-[#2d2d2d] rounded-lg px-3 py-2">
                    <AtSign size={16} className="text-[#858585]" />
                    <input
                      ref={inputRef}
                      type="text"
                      placeholder="Message… @AgentName"
                      value={commandInput}
                      onChange={handleInputChange}
                      onKeyDown={(e) => e.key === "Enter" && !showMentions && handleSendCommand()}
                      className="flex-1 bg-transparent text-sm text-[#cccccc] focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={handleSendCommand}
                      className="p-1 bg-[#0e639c] hover:bg-[#1177bb] rounded transition-colors text-white"
                    >
                      <Send size={16} />
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {panelView === "chat" && (
            <div className="w-56 border-l border-[#3c3c3c] overflow-y-auto shrink-0 hidden md:block">
              <div className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wide text-[#858585] border-b border-[#3c3c3c]">
                Activity
              </div>
              <div className="p-2 space-y-2">
                {activities
                  .slice(-24)
                  .reverse()
                  .map((activity) => {
                    const agent = agents.find((a) => a.id === activity.agentId);
                    return (
                      <div key={activity.id} className="flex items-start gap-2 text-[11px]">
                        {activityIcons[activity.type] ?? (
                          <MessageSquare size={14} className="text-[#858585]" />
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate" style={{ color: agent?.color }}>
                            {agent?.name ?? "?"}
                          </div>
                          <div className="text-[#858585] truncate">{activity.action}</div>
                          <div className="text-[10px] text-[#555] mt-0.5">
                            {activity.timestamp.toLocaleTimeString()}
                          </div>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
