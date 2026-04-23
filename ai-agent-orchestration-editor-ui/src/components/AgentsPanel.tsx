import { useStore } from '../store/store';
import { cn } from '../utils/cn';
import { Bot, Circle, Sparkles, Zap } from 'lucide-react';

const roleLabels: Record<string, string> = {
  architect: 'Architect',
  developer: 'Developer',
  reviewer: 'Code Reviewer',
  tester: 'Test Engineer',
  designer: 'UI Designer',
};

const statusColors: Record<string, string> = {
  idle: 'bg-[#858585]',
  working: 'bg-[#3b82f6] animate-pulse',
  waiting: 'bg-[#f59e0b]',
  completed: 'bg-[#10b981]',
  error: 'bg-[#ef4444]',
};

export function AgentsPanel() {
  const { agents, selectedAgent, selectAgent, updateAgentStatus, addActivity } = useStore();

  const handleAssignTask = (agentId: string) => {
    updateAgentStatus(agentId, 'working', 'Analyzing code structure...');
    addActivity({
      agentId,
      action: 'Starting new task...',
      type: 'analyze',
    });
    
    // Simulate work completion
    setTimeout(() => {
      updateAgentStatus(agentId, 'completed');
      addActivity({
        agentId,
        action: 'Task completed successfully',
        type: 'complete',
      });
    }, 3000);
  };

  return (
    <div className="text-[#cccccc]">
      <div className="px-4 py-2 text-xs font-semibold uppercase tracking-wide text-[#bbbbbb] flex items-center gap-2">
        <Bot size={14} />
        <span>AI Agents</span>
      </div>
      
      <div className="px-2 pb-2 space-y-1">
        {agents.map(agent => (
          <div
            key={agent.id}
            onClick={() => selectAgent(selectedAgent?.id === agent.id ? null : agent)}
            className={cn(
              "p-2 rounded cursor-pointer transition-all group",
              selectedAgent?.id === agent.id
                ? "bg-[#094771] border border-[#007fd4]"
                : "bg-[#2d2d2d] hover:bg-[#37373d] border border-transparent"
            )}
          >
            <div className="flex items-center gap-2">
              <div 
                className="w-8 h-8 rounded-lg flex items-center justify-center text-lg"
                style={{ backgroundColor: agent.color + '20', border: `1px solid ${agent.color}40` }}
              >
                {agent.avatar}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm">{agent.name}</span>
                  <Circle 
                    size={8} 
                    className={cn("fill-current", statusColors[agent.status])} 
                  />
                </div>
                <div className="text-xs text-[#858585]">
                  {roleLabels[agent.role]}
                </div>
              </div>
            </div>
            
            {agent.status === 'working' && agent.currentTask && (
              <div className="mt-2 text-xs text-[#3b82f6] flex items-center gap-1">
                <Zap size={12} className="animate-pulse" />
                {agent.currentTask}
              </div>
            )}
            
            <div className="mt-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleAssignTask(agent.id);
                }}
                className="flex-1 text-xs bg-[#0e639c] hover:bg-[#1177bb] px-2 py-1 rounded flex items-center justify-center gap-1"
              >
                <Sparkles size={12} />
                Assign Task
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
