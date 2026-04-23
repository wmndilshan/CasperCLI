import { useStore } from '../store/store';
import { X, Zap, MessageSquare, Activity, Clock } from 'lucide-react';
import { cn } from '../utils/cn';

const roleDescriptions: Record<string, string> = {
  architect: 'Designs system architecture and makes high-level technical decisions',
  developer: 'Implements features, writes code, and fixes bugs',
  reviewer: 'Reviews code for quality, security, and best practices',
  tester: 'Creates and runs tests, identifies issues',
  designer: 'Designs UI/UX components and visual elements',
};

const statusLabels: Record<string, { label: string; color: string }> = {
  idle: { label: 'Idle', color: 'text-[#858585]' },
  working: { label: 'Working', color: 'text-[#3b82f6]' },
  waiting: { label: 'Waiting', color: 'text-[#f59e0b]' },
  completed: { label: 'Completed', color: 'text-[#10b981]' },
  error: { label: 'Error', color: 'text-[#ef4444]' },
};

export function AgentDetailOverlay() {
  const { selectedAgent, selectAgent, agents, activities, addMessage, updateAgentStatus, addActivity } = useStore();

  if (!selectedAgent) return null;

  const agentActivities = activities.filter(a => a.agentId === selectedAgent.id).slice(-5);
  const agent = agents.find(a => a.id === selectedAgent.id);

  if (!agent) return null;

  const handleQuickCommand = (command: string) => {
    addMessage({
      content: `@${agent.name} ${command}`,
      type: 'command',
      mentions: [agent.name.toLowerCase()],
    });
    
    updateAgentStatus(agent.id, 'working', `Processing: ${command}`);
    addActivity({
      agentId: agent.id,
      action: `Received command: ${command}`,
      type: 'analyze',
    });
    
    setTimeout(() => {
      updateAgentStatus(agent.id, 'completed');
      addActivity({
        agentId: agent.id,
        action: `Completed: ${command}`,
        type: 'complete',
      });
      
      addMessage({
        agentId: agent.id,
        content: `✓ ${command} completed successfully!`,
        type: 'agent',
      });
    }, 2500);
  };

  const quickCommands = agent.role === 'developer' 
    ? ['Implement this', 'Refactor code', 'Add tests']
    : agent.role === 'reviewer'
    ? ['Review changes', 'Check security', 'Suggest improvements']
    : agent.role === 'architect'
    ? ['Analyze structure', 'Design API', 'Optimize architecture']
    : agent.role === 'tester'
    ? ['Run tests', 'Generate tests', 'Check coverage']
    : ['Review design', 'Update styles', 'Add animations'];

  return (
    <div 
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={() => selectAgent(null)}
    >
      <div 
        className="bg-[#252526] rounded-xl shadow-2xl w-[480px] max-h-[80vh] overflow-hidden border border-[#3c3c3c]"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div 
          className="p-4 border-b border-[#3c3c3c] relative"
          style={{ 
            background: `linear-gradient(135deg, ${agent.color}20, transparent)` 
          }}
        >
          <button
            onClick={() => selectAgent(null)}
            className="absolute top-3 right-3 p-1 hover:bg-[#3c3c3c] rounded transition-colors"
          >
            <X size={18} />
          </button>
          
          <div className="flex items-center gap-4">
            <div 
              className="w-16 h-16 rounded-xl flex items-center justify-center text-3xl"
              style={{ backgroundColor: agent.color + '30', border: `2px solid ${agent.color}60` }}
            >
              {agent.avatar}
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">{agent.name}</h2>
              <p className="text-sm text-[#858585] capitalize">{agent.role}</p>
              <div className={cn("flex items-center gap-1.5 mt-1 text-sm", statusLabels[agent.status].color)}>
                <div className={cn("w-2 h-2 rounded-full", {
                  'bg-[#858585]': agent.status === 'idle',
                  'bg-[#3b82f6] animate-pulse': agent.status === 'working',
                  'bg-[#f59e0b]': agent.status === 'waiting',
                  'bg-[#10b981]': agent.status === 'completed',
                  'bg-[#ef4444]': agent.status === 'error',
                })} />
                {statusLabels[agent.status].label}
                {agent.currentTask && ` - ${agent.currentTask}`}
              </div>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-4 overflow-y-auto max-h-[50vh]">
          {/* Description */}
          <div className="mb-4">
            <div className="text-xs font-semibold uppercase text-[#858585] mb-1">Description</div>
            <p className="text-sm text-[#cccccc]">{roleDescriptions[agent.role]}</p>
          </div>

          {/* Quick Commands */}
          <div className="mb-4">
            <div className="text-xs font-semibold uppercase text-[#858585] mb-2 flex items-center gap-1">
              <Zap size={12} />
              Quick Commands
            </div>
            <div className="flex flex-wrap gap-2">
              {quickCommands.map(cmd => (
                <button
                  key={cmd}
                  onClick={() => handleQuickCommand(cmd)}
                  disabled={agent.status === 'working'}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-sm transition-colors border border-[#3c3c3c]",
                    agent.status === 'working'
                      ? "bg-[#2d2d2d] text-[#858585] cursor-not-allowed"
                      : "bg-[#2d2d2d] hover:bg-[#0e639c] hover:border-[#0e639c] text-[#cccccc]"
                  )}
                >
                  {cmd}
                </button>
              ))}
            </div>
          </div>

          {/* Recent Activity */}
          <div>
            <div className="text-xs font-semibold uppercase text-[#858585] mb-2 flex items-center gap-1">
              <Activity size={12} />
              Recent Activity
            </div>
            {agentActivities.length > 0 ? (
              <div className="space-y-2">
                {agentActivities.map(activity => (
                  <div key={activity.id} className="flex items-center gap-2 text-sm bg-[#2d2d2d] rounded p-2">
                    <Clock size={14} className="text-[#858585]" />
                    <span className="text-[#cccccc]">{activity.action}</span>
                    <span className="text-xs text-[#858585] ml-auto">
                      {activity.timestamp.toLocaleTimeString()}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-[#858585] italic">No recent activity</div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[#3c3c3c] bg-[#1e1e1e]">
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder={`Message @${agent.name}...`}
              className="flex-1 bg-[#3c3c3c] border border-[#555] rounded-lg px-3 py-2 text-sm
                focus:outline-none focus:border-[#007fd4]"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  const target = e.target as HTMLInputElement;
                  if (target.value.trim()) {
                    handleQuickCommand(target.value);
                    target.value = '';
                  }
                }
              }}
            />
            <button
              className="p-2 bg-[#0e639c] hover:bg-[#1177bb] rounded-lg transition-colors"
              onClick={() => {
                const input = document.querySelector('input[placeholder*="Message"]') as HTMLInputElement;
                if (input?.value.trim()) {
                  handleQuickCommand(input.value);
                  input.value = '';
                }
              }}
            >
              <MessageSquare size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
