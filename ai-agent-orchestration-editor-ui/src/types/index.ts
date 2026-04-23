export interface Agent {
  id: string;
  name: string;
  avatar: string;
  role: 'architect' | 'developer' | 'reviewer' | 'tester' | 'designer';
  status: 'idle' | 'working' | 'waiting' | 'completed' | 'error';
  currentTask?: string;
  color: string;
}

export interface AgentTeam {
  id: string;
  name: string;
  members: string[];
  createdAt: Date;
}

export interface Message {
  id: string;
  agentId?: string;
  content: string;
  timestamp: Date;
  type: 'agent' | 'user' | 'system' | 'command';
  mentions?: string[];
}

export interface Activity {
  id: string;
  agentId: string;
  action: string;
  timestamp: Date;
  type: 'edit' | 'analyze' | 'review' | 'test' | 'comment' | 'complete' | 'error';
  details?: string;
}

export interface FileNode {
  id: string;
  name: string;
  type: 'file' | 'folder';
  children?: FileNode[];
  content?: string;
  language?: string;
}

export interface Tab {
  id: string;
  name: string;
  content: string;
  language: string;
  isModified: boolean;
}

export interface Diagnostic {
  id: string;
  line: number;
  column: number;
  message: string;
  severity: 'error' | 'warning' | 'info';
  file: string;
}
