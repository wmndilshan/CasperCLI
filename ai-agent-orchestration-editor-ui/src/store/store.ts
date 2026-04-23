import { create } from 'zustand';
import { Agent, AgentTeam, Message, Activity, Tab, Diagnostic, FileNode } from '../types';

const initialAgents: Agent[] = [
  { id: '1', name: 'Atlas', avatar: '🤖', role: 'architect', status: 'idle', color: '#3b82f6' },
  { id: '2', name: 'Coder', avatar: '💻', role: 'developer', status: 'idle', color: '#10b981' },
  { id: '3', name: 'Reyna', avatar: '👁️', role: 'reviewer', status: 'idle', color: '#f59e0b' },
  { id: '4', name: 'TestBot', avatar: '🧪', role: 'tester', status: 'idle', color: '#8b5cf6' },
  { id: '5', name: 'Pixel', avatar: '🎨', role: 'designer', status: 'idle', color: '#ec4899' },
];

const initialTeams: AgentTeam[] = [
  { id: '1', name: 'Full Stack Team', members: ['1', '2', '3'], createdAt: new Date() },
  { id: '2', name: 'Frontend Squad', members: ['2', '5'], createdAt: new Date() },
];

const initialFiles: FileNode[] = [
  {
    id: '1',
    name: 'src',
    type: 'folder',
    children: [
      { id: '2', name: 'App.tsx', type: 'file', language: 'typescript', content: `import React from 'react';

function App() {
  const [count, setCount] = React.useState(0);
  
  return (
    <div className="app">
      <h1>Hello World</h1>
      <p>Count: {count}</p>
      <button onClick={() => setCount(c => c + 1)}>
        Increment
      </button>
    </div>
  );
}

export default App;` },
      { id: '3', name: 'index.css', type: 'file', language: 'css', content: `.app {
  font-family: sans-serif;
  padding: 2rem;
}

h1 {
  color: #333;
}

button {
  background: #3b82f6;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}` },
      { id: '4', name: 'utils.ts', type: 'file', language: 'typescript', content: `export function formatDate(date: Date): string {
  return date.toLocaleDateString();
}

export function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout>;
  return (...args) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delay);
  };
}` },
    ],
  },
  {
    id: '5',
    name: 'components',
    type: 'folder',
    children: [
      { id: '6', name: 'Button.tsx', type: 'file', language: 'typescript', content: `interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary';
}

export function Button({ children, onClick, variant = 'primary' }: ButtonProps) {
  return (
    <button
      className={\`btn btn-\${variant}\`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}` },
      { id: '7', name: 'Card.tsx', type: 'file', language: 'typescript', content: `interface CardProps {
  title: string;
  children: React.ReactNode;
}

export function Card({ title, children }: CardProps) {
  return (
    <div className="card">
      <h3 className="card-title">{title}</h3>
      <div className="card-content">
        {children}
      </div>
    </div>
  );
}` },
    ],
  },
  { id: '8', name: 'package.json', type: 'file', language: 'json', content: `{
  "name": "my-project",
  "version": "1.0.0",
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  }
}` },
  { id: '9', name: 'README.md', type: 'file', language: 'markdown', content: `# My Project

A sample project for demonstrating the AI team orchestration editor.

## Getting Started

\`\`\`bash
npm install
npm run dev
\`\`\`

## Features

- React 18
- TypeScript
- Tailwind CSS
` },
];

const initialDiagnostics: Diagnostic[] = [
  { id: '1', line: 5, column: 10, message: 'Unused variable: temp', severity: 'warning', file: 'App.tsx' },
  { id: '2', line: 12, column: 5, message: 'Missing return type on function', severity: 'info', file: 'utils.ts' },
];

interface Store {
  // Agents
  agents: Agent[];
  teams: AgentTeam[];
  selectedAgent: Agent | null;
  
  // Files & Editor
  files: FileNode[];
  tabs: Tab[];
  activeTabId: string | null;
  diagnostics: Diagnostic[];
  
  // Communication
  messages: Message[];
  activities: Activity[];
  commandInput: string;
  
  // UI State
  sidebarView: 'explorer' | 'agents' | 'teams' | 'search';
  panelView: 'terminal' | 'problems' | 'output' | 'chat';
  isPanelOpen: boolean;
  
  // Actions
  setActiveTab: (tabId: string) => void;
  closeTab: (tabId: string) => void;
  updateTabContent: (tabId: string, content: string) => void;
  openFile: (file: FileNode) => void;
  
  setSidebarView: (view: 'explorer' | 'agents' | 'teams' | 'search') => void;
  setPanelView: (view: 'terminal' | 'problems' | 'output' | 'chat') => void;
  togglePanel: () => void;
  
  selectAgent: (agent: Agent | null) => void;
  createTeam: (name: string, members: string[]) => void;
  
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void;
  addActivity: (activity: Omit<Activity, 'id' | 'timestamp'>) => void;
  setCommandInput: (input: string) => void;
  
  updateAgentStatus: (agentId: string, status: Agent['status'], task?: string) => void;
}

export const useStore = create<Store>((set) => ({
  agents: initialAgents,
  teams: initialTeams,
  selectedAgent: null,
  
  files: initialFiles,
  tabs: [],
  activeTabId: null,
  diagnostics: initialDiagnostics,
  
  messages: [
    { id: '1', content: 'Welcome to AI Code Studio! Use @agent-name to mention agents.', timestamp: new Date(), type: 'system' },
    { id: '2', agentId: '1', content: 'Atlas ready. I can help with architecture decisions.', timestamp: new Date(), type: 'agent' },
    { id: '3', agentId: '2', content: 'Coder online. Ready to implement features.', timestamp: new Date(), type: 'agent' },
  ],
  activities: [
    { id: '1', agentId: '2', action: 'Modified App.tsx', timestamp: new Date(Date.now() - 60000), type: 'edit' },
    { id: '2', agentId: '3', action: 'Completed code review', timestamp: new Date(Date.now() - 120000), type: 'review', details: 'Found 2 suggestions' },
    { id: '3', agentId: '4', action: 'Running tests...', timestamp: new Date(Date.now() - 30000), type: 'test' },
  ],
  commandInput: '',
  
  sidebarView: 'explorer',
  panelView: 'chat',
  isPanelOpen: true,
  
  setActiveTab: (tabId) => set({ activeTabId: tabId }),
  
  closeTab: (tabId) => set((state) => {
    const newTabs = state.tabs.filter(t => t.id !== tabId);
    const newActiveId = state.activeTabId === tabId 
      ? (newTabs.length > 0 ? newTabs[newTabs.length - 1].id : null)
      : state.activeTabId;
    return { tabs: newTabs, activeTabId: newActiveId };
  }),
  
  updateTabContent: (tabId, content) => set((state) => ({
    tabs: state.tabs.map(t => t.id === tabId ? { ...t, content, isModified: true } : t)
  })),
  
  openFile: (file) => set((state) => {
    const existingTab = state.tabs.find(t => t.id === file.id);
    if (existingTab) {
      return { activeTabId: file.id };
    }
    const newTab: Tab = {
      id: file.id,
      name: file.name,
      content: file.content || '',
      language: file.language || 'plaintext',
      isModified: false,
    };
    return {
      tabs: [...state.tabs, newTab],
      activeTabId: file.id,
    };
  }),
  
  setSidebarView: (view) => set({ sidebarView: view }),
  setPanelView: (view) => set({ panelView: view }),
  togglePanel: () => set((state) => ({ isPanelOpen: !state.isPanelOpen })),
  
  selectAgent: (agent) => set({ selectedAgent: agent }),
  
  createTeam: (name, members) => set((state) => ({
    teams: [...state.teams, { id: Date.now().toString(), name, members, createdAt: new Date() }]
  })),
  
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, { ...message, id: Date.now().toString(), timestamp: new Date() }]
  })),
  
  addActivity: (activity) => set((state) => ({
    activities: [...state.activities, { ...activity, id: Date.now().toString(), timestamp: new Date() }]
  })),
  
  setCommandInput: (input) => set({ commandInput: input }),
  
  updateAgentStatus: (agentId, status, task) => set((state) => ({
    agents: state.agents.map(a => a.id === agentId ? { ...a, status, currentTask: task } : a)
  })),
}));
