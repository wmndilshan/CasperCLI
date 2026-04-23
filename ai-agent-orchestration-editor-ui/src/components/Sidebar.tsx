import { useStore } from '../store/store';
import { ActivityBar } from './ActivityBar';
import { FileExplorer } from './FileExplorer';
import { AgentsPanel } from './AgentsPanel';
import { TeamsPanel } from './TeamsPanel';
import { Search } from 'lucide-react';

export function Sidebar() {
  const { sidebarView } = useStore();

  return (
    <div className="flex h-full">
      <ActivityBar />
      <div className="w-60 bg-[#252526] border-r border-[#1e1e1e] overflow-y-auto">
        {sidebarView === 'explorer' && <FileExplorer />}
        {sidebarView === 'agents' && <AgentsPanel />}
        {sidebarView === 'teams' && <TeamsPanel />}
        {sidebarView === 'search' && (
          <div className="p-4 text-[#858585]">
            <div className="flex items-center gap-2 mb-4">
              <Search size={14} />
              <span className="text-xs font-semibold uppercase tracking-wide">Search</span>
            </div>
            <input
              type="text"
              placeholder="Search files..."
              className="w-full bg-[#3c3c3c] border border-[#555] rounded px-3 py-1.5 text-sm
                focus:outline-none focus:border-[#007fd4]"
            />
          </div>
        )}
      </div>
    </div>
  );
}
