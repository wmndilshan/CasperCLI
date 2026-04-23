import { Files, Search, Settings } from "lucide-react";
import { useStudioStore } from "@/studio/store";

const icons = [
  { id: "explorer" as const, icon: Files, tooltip: "Explorer" },
  { id: "search" as const, icon: Search, tooltip: "Search" },
];

export function ActivityBar() {
  const sidebarView = useStudioStore((s) => s.sidebarView);
  const setSidebarView = useStudioStore((s) => s.setSidebarView);

  return (
    <div className="w-12 bg-[#333333] flex flex-col items-center py-2 border-r border-[#252526] shrink-0">
      <div className="flex-1 flex flex-col gap-1">
        {icons.map(({ id, icon: Icon, tooltip }) => (
          <button
            key={id}
            type="button"
            onClick={() => setSidebarView(id)}
            title={tooltip}
            className={`relative w-10 h-10 flex items-center justify-center rounded transition-colors ${
              sidebarView === id
                ? "text-white bg-[#37373d]"
                : "text-[#858585] hover:text-white hover:bg-[#2a2d2e]"
            }`}
          >
            <Icon size={22} strokeWidth={1.75} />
            {sidebarView === id && (
              <div className="absolute left-0 top-1 bottom-1 w-0.5 bg-white rounded-r" />
            )}
          </button>
        ))}
      </div>
      <button
        type="button"
        title="Settings"
        className="w-10 h-10 flex items-center justify-center rounded text-[#858585] hover:text-white hover:bg-[#2a2d2e] mt-2"
      >
        <Settings size={22} strokeWidth={1.75} />
      </button>
    </div>
  );
}
