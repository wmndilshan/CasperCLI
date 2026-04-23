import { create } from "zustand";
import type {
  Activity,
  Agent,
  AgentTeam,
  Diagnostic,
  FileNode,
  Message,
  RuntimeTask,
  Tab,
} from "./types";

const KIND_EMOJI: Record<string, string> = {
  llm_worker: "🧠",
  rule_based: "📐",
  boundary: "🛡️",
  scheduler: "📅",
  execution: "⚡",
  conflict_detection: "⚠️",
  merge: "🔀",
  verification: "✅",
  integrator: "🧩",
};

function hueFromString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360;
  return h;
}

function colorForId(id: string): string {
  const h = hueFromString(id);
  return `hsl(${h} 55% 42%)`;
}

function displayName(role: string, id: string): string {
  const short = id.replace(/^agent_/, "").slice(0, 12);
  return role === "llm_worker" ? `LLM ${short}` : role.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function mapBackendAgent(a: {
  id: string;
  kind: string;
  role: string;
  status: string;
  current_tasks?: string[];
}): Agent {
  const statusMap: Record<string, Agent["status"]> = {
    idle: "idle",
    running: "working",
    blocked: "waiting",
    completed: "completed",
    error: "error",
  };
  return {
    id: a.id,
    name: displayName(a.role, a.id),
    avatar: KIND_EMOJI[a.kind] ?? "🤖",
    role: a.role,
    backendRole: a.role,
    kind: a.kind,
    status: statusMap[a.status] ?? (a.status as Agent["status"]) ?? "idle",
    currentTask: a.current_tasks?.length ? a.current_tasks.join(", ") : undefined,
    color: colorForId(a.id),
  };
}

interface StudioStore {
  agents: Agent[];
  teams: AgentTeam[];
  selectedAgent: Agent | null;

  files: FileNode[];
  tabs: Tab[];
  activeTabId: string | null;
  diagnostics: Diagnostic[];

  messages: Message[];
  activities: Activity[];
  commandInput: string;

  sidebarView: "explorer" | "search";
  panelView: "events" | "chat" | "problems" | "terminal" | "output";
  isPanelOpen: boolean;

  explorerPath: string;
  explorerEntries: Array<{ name: string; path: string; is_dir: boolean }>;
  projectRoot: string;
  goal: string;
  wsConnected: boolean;
  runStatus: string;

  runtimeTasks: Record<string, RuntimeTask>;
  locks: Array<Record<string, unknown>>;
  patches: Array<Record<string, unknown>>;
  conflicts: Array<Record<string, unknown>>;
  verification: Record<string, unknown> | null;
  runtimeEvents: Array<{ type: string; payload: Record<string, unknown>; ts?: string }>;
  resources: Array<Record<string, unknown>>;

  setActiveTab: (tabId: string) => void;
  closeTab: (tabId: string) => void;
  updateTabContent: (tabId: string, content: string) => void;
  openFile: (file: FileNode) => void;
  openWorkspaceFile: (relPath: string, fileName: string, content: string, language: string) => void;
  markTabSaved: (tabId: string) => void;

  setSidebarView: (view: StudioStore["sidebarView"]) => void;
  setPanelView: (view: StudioStore["panelView"]) => void;
  togglePanel: () => void;

  selectAgent: (agent: Agent | null) => void;
  createTeam: (name: string, members: string[]) => void;

  addMessage: (message: Omit<Message, "id" | "timestamp">) => void;
  addActivity: (activity: Omit<Activity, "id" | "timestamp">) => void;
  setCommandInput: (input: string) => void;

  updateAgentStatus: (agentId: string, status: Agent["status"], task?: string) => void;

  setExplorerPath: (p: string) => void;
  setExplorerEntries: (e: StudioStore["explorerEntries"]) => void;
  setProjectRoot: (p: string) => void;
  setGoal: (g: string) => void;
  setWsConnected: (v: boolean) => void;
  setRunStatus: (s: string) => void;

  setRuntimeTasks: (t: Record<string, RuntimeTask>) => void;
  setLocks: (l: Array<Record<string, unknown>>) => void;
  setPatches: (p: Array<Record<string, unknown>>) => void;
  setConflicts: (c: Array<Record<string, unknown>>) => void;
  setVerification: (v: Record<string, unknown> | null) => void;
  appendRuntimeEvent: (e: StudioStore["runtimeEvents"][0]) => void;
  setResources: (r: Array<Record<string, unknown>>) => void;

  syncAgentsFromBackend: (
    rows: Array<{ id: string; kind: string; role: string; status: string; current_tasks?: string[] }>,
  ) => void;
}

export const useStudioStore = create<StudioStore>((set) => ({
  agents: [],
  teams: [],
  selectedAgent: null,

  files: [],
  tabs: [],
  activeTabId: null,
  diagnostics: [],

  messages: [
    {
      id: "welcome",
      content:
        "Casper Hybrid Studio — connect to the backend, synthesize a team, then run the DAG. Live events stream below.",
      timestamp: new Date(),
      type: "system",
    },
  ],
  activities: [],
  commandInput: "",

  sidebarView: "explorer",
  panelView: "events",
  isPanelOpen: true,

  explorerPath: ".",
  explorerEntries: [],
  projectRoot: ".",
  goal: "Ship the hybrid multi-agent runtime",
  wsConnected: false,
  runStatus: "idle",

  runtimeTasks: {},
  locks: [],
  patches: [],
  conflicts: [],
  verification: null,
  runtimeEvents: [],
  resources: [],

  setActiveTab: (tabId) => set({ activeTabId: tabId }),

  closeTab: (tabId) =>
    set((state) => {
      const newTabs = state.tabs.filter((t) => t.id !== tabId);
      const newActiveId =
        state.activeTabId === tabId
          ? newTabs.length > 0
            ? newTabs[newTabs.length - 1].id
            : null
          : state.activeTabId;
      return { tabs: newTabs, activeTabId: newActiveId };
    }),

  updateTabContent: (tabId, content) =>
    set((state) => ({
      tabs: state.tabs.map((t) => (t.id === tabId ? { ...t, content, isModified: true } : t)),
    })),

  openFile: (file) =>
    set((state) => {
      if (file.type === "folder") return state;
      const existingTab = state.tabs.find((t) => t.id === file.id);
      if (existingTab) return { activeTabId: file.id };
      const newTab: Tab = {
        id: file.id,
        name: file.name,
        content: file.content || "",
        language: file.language || "plaintext",
        isModified: false,
      };
      return { tabs: [...state.tabs, newTab], activeTabId: file.id };
    }),

  openWorkspaceFile: (relPath, fileName, content, language) =>
    set((state) => {
      const id = relPath;
      const existingTab = state.tabs.find((t) => t.id === id);
      if (existingTab) return { activeTabId: id };
      const newTab: Tab = {
        id,
        name: fileName,
        content,
        language,
        isModified: false,
        path: relPath,
      };
      return { tabs: [...state.tabs, newTab], activeTabId: id };
    }),

  markTabSaved: (tabId) =>
    set((state) => ({
      tabs: state.tabs.map((t) => (t.id === tabId ? { ...t, isModified: false } : t)),
    })),

  setSidebarView: (view) => set({ sidebarView: view }),
  setPanelView: (view) => set({ panelView: view }),
  togglePanel: () => set((state) => ({ isPanelOpen: !state.isPanelOpen })),

  selectAgent: (agent) => set({ selectedAgent: agent }),

  createTeam: (name, members) =>
    set((state) => ({
      teams: [...state.teams, { id: crypto.randomUUID(), name, members, createdAt: new Date() }],
    })),

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, { ...message, id: crypto.randomUUID(), timestamp: new Date() }],
    })),

  addActivity: (activity) =>
    set((state) => ({
      activities: [...state.activities, { ...activity, id: crypto.randomUUID(), timestamp: new Date() }],
    })),

  setCommandInput: (input) => set({ commandInput: input }),

  updateAgentStatus: (agentId, status, task) =>
    set((state) => ({
      agents: state.agents.map((a) =>
        a.id === agentId ? { ...a, status, currentTask: task } : a,
      ),
    })),

  setExplorerPath: (explorerPath) => set({ explorerPath }),
  setExplorerEntries: (explorerEntries) => set({ explorerEntries }),
  setProjectRoot: (projectRoot) => set({ projectRoot }),
  setGoal: (goal) => set({ goal }),
  setWsConnected: (wsConnected) => set({ wsConnected }),
  setRunStatus: (runStatus) => set({ runStatus }),

  setRuntimeTasks: (runtimeTasks) => set({ runtimeTasks }),
  setLocks: (locks) => set({ locks }),
  setPatches: (patches) => set({ patches }),
  setConflicts: (conflicts) => set({ conflicts }),
  setVerification: (verification) => set({ verification }),
  appendRuntimeEvent: (e) =>
    set((state) => ({
      runtimeEvents: [...state.runtimeEvents, e].slice(-400),
    })),

  setResources: (resources) => set({ resources }),

  syncAgentsFromBackend: (rows) => set({ agents: rows.map(mapBackendAgent) }),
}));
