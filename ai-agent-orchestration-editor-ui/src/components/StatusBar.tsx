import { useStore } from '../store/store';
import { GitBranch, AlertCircle, AlertTriangle, Bell, Wifi, Check, Circle } from 'lucide-react';

export function StatusBar() {
  const { agents, tabs, diagnostics } = useStore();
  
  const activeAgents = agents.filter(a => a.status === 'working').length;
  const errors = diagnostics.filter(d => d.severity === 'error').length;
  const warnings = diagnostics.filter(d => d.severity === 'warning').length;

  return (
    <div className="h-6 bg-[#007acc] flex items-center justify-between px-2 text-xs text-white">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1 px-2 py-0.5 bg-[#1177bb] rounded cursor-pointer hover:bg-[#1a88cc]">
          <GitBranch size={12} />
          <span>main</span>
        </div>
        
        <div className="flex items-center gap-1">
          <Check size={12} />
          <span>0 Problems</span>
        </div>
        
        <div className="flex items-center gap-3 ml-2 text-white/80">
          <div className="flex items-center gap-1">
            <AlertCircle size={12} />
            <span>{errors}</span>
          </div>
          <div className="flex items-center gap-1">
            <AlertTriangle size={12} />
            <span>{warnings}</span>
          </div>
        </div>
      </div>
      
      <div className="flex items-center gap-3">
        {activeAgents > 0 && (
          <div className="flex items-center gap-1.5 bg-[#1177bb] px-2 py-0.5 rounded">
            <Circle size={6} className="fill-white animate-pulse" />
            <span>{activeAgents} Active</span>
          </div>
        )}
        
        <div className="flex items-center gap-1.5 cursor-pointer hover:bg-[#1177bb] px-2 py-0.5 rounded">
          <span>AI Agents: {agents.length}</span>
        </div>
        
        <div className="flex items-center gap-1">
          <Wifi size={12} />
          <span>Connected</span>
        </div>
        
        <div className="flex items-center gap-1 cursor-pointer hover:bg-[#1177bb] px-2 py-0.5 rounded">
          <Bell size={12} />
        </div>
        
        <div className="cursor-pointer hover:bg-[#1177bb] px-2 py-0.5 rounded">
          UTF-8
        </div>
        
        {tabs.length > 0 && (
          <div className="cursor-pointer hover:bg-[#1177bb] px-2 py-0.5 rounded">
            TypeScript
          </div>
        )}
        
        <div className="cursor-pointer hover:bg-[#1177bb] px-2 py-0.5 rounded">
          Ln 1, Col 1
        </div>
      </div>
    </div>
  );
}
