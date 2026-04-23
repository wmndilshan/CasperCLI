import { 
  Files, 
  Users, 
  UserCircle2, 
  Search, 
  Settings,
  Bug,
  GitBranch,
  Puzzle
} from 'lucide-react';
import { useStore } from '../store/store';

const icons = [
  { id: 'explorer' as const, icon: Files, tooltip: 'Explorer' },
  { id: 'agents' as const, icon: UserCircle2, tooltip: 'AI Agents' },
  { id: 'teams' as const, icon: Users, tooltip: 'Teams' },
  { id: 'search' as const, icon: Search, tooltip: 'Search' },
];

const bottomIcons = [
  { icon: GitBranch, tooltip: 'Source Control' },
  { icon: Bug, tooltip: 'Run & Debug' },
  { icon: Puzzle, tooltip: 'Extensions' },
  { icon: Settings, tooltip: 'Settings' },
];

export function ActivityBar() {
  const { sidebarView, setSidebarView } = useStore();

  return (
    <div className="w-12 bg-[#333333] flex flex-col items-center py-2 border-r border-[#252526]">
      <div className="flex-1 flex flex-col gap-1">
        {icons.map(({ id, icon: Icon, tooltip }) => (
          <button
            key={id}
            onClick={() => setSidebarView(id)}
            className={`w-10 h-10 flex items-center justify-center rounded relative group
              ${sidebarView === id 
                ? 'text-white bg-[#37373d]' 
                : 'text-[#858585] hover:text-white hover:bg-[#2a2d2e]'}`}
          >
            <Icon size={22} />
            {sidebarView === id && (
              <div className="absolute left-0 top-1 bottom-1 w-0.5 bg-white rounded-r" />
            )}
            <div className="absolute left-full ml-2 px-2 py-1 bg-[#252526] text-white text-xs 
              rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50
              border border-[#454545] pointer-events-none">
              {tooltip}
            </div>
          </button>
        ))}
      </div>
      
      <div className="flex flex-col gap-1">
        {bottomIcons.map(({ icon: Icon, tooltip }, i) => (
          <button
            key={i}
            className="w-10 h-10 flex items-center justify-center rounded text-[#858585] 
              hover:text-white hover:bg-[#2a2d2e] relative group"
          >
            <Icon size={22} />
            <div className="absolute left-full ml-2 px-2 py-1 bg-[#252526] text-white text-xs 
              rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50
              border border-[#454545] pointer-events-none">
              {tooltip}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
