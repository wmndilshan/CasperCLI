import { useState } from 'react';
import { useStore } from '../store/store';
import { Users, Plus, X, Check, Circle } from 'lucide-react';
import { cn } from '../utils/cn';

export function TeamsPanel() {
  const { teams, agents, createTeam } = useStore();
  const [isCreating, setIsCreating] = useState(false);
  const [newTeamName, setNewTeamName] = useState('');
  const [selectedMembers, setSelectedMembers] = useState<string[]>([]);

  const handleCreateTeam = () => {
    if (newTeamName.trim() && selectedMembers.length > 0) {
      createTeam(newTeamName, selectedMembers);
      setNewTeamName('');
      setSelectedMembers([]);
      setIsCreating(false);
    }
  };

  const toggleMember = (agentId: string) => {
    setSelectedMembers(prev =>
      prev.includes(agentId)
        ? prev.filter(id => id !== agentId)
        : [...prev, agentId]
    );
  };

  return (
    <div className="text-[#cccccc]">
      <div className="px-4 py-2 text-xs font-semibold uppercase tracking-wide text-[#bbbbbb] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users size={14} />
          <span>Teams</span>
        </div>
        <button
          onClick={() => setIsCreating(true)}
          className="p-1 hover:bg-[#37373d] rounded"
        >
          <Plus size={14} />
        </button>
      </div>

      {isCreating && (
        <div className="mx-2 mb-2 p-3 bg-[#2d2d2d] rounded border border-[#3c3c3c]">
          <input
            type="text"
            placeholder="Team name..."
            value={newTeamName}
            onChange={e => setNewTeamName(e.target.value)}
            className="w-full bg-[#3c3c3c] border border-[#555] rounded px-2 py-1 text-sm mb-2
              focus:outline-none focus:border-[#007fd4]"
            autoFocus
          />
          
          <div className="text-xs text-[#858585] mb-1">Select members:</div>
          <div className="flex flex-wrap gap-1 mb-3">
            {agents.map(agent => (
              <button
                key={agent.id}
                onClick={() => toggleMember(agent.id)}
                className={cn(
                  "flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors",
                  selectedMembers.includes(agent.id)
                    ? "bg-[#0e639c] text-white"
                    : "bg-[#3c3c3c] text-[#cccccc] hover:bg-[#4c4c4c]"
                )}
              >
                <span>{agent.avatar}</span>
                <span>{agent.name}</span>
              </button>
            ))}
          </div>
          
          <div className="flex gap-2">
            <button
              onClick={handleCreateTeam}
              className="flex-1 flex items-center justify-center gap-1 bg-[#0e639c] hover:bg-[#1177bb] px-3 py-1.5 rounded text-sm"
            >
              <Check size={14} />
              Create
            </button>
            <button
              onClick={() => {
                setIsCreating(false);
                setSelectedMembers([]);
                setNewTeamName('');
              }}
              className="flex items-center justify-center gap-1 bg-[#3c3c3c] hover:bg-[#4c4c4c] px-3 py-1.5 rounded text-sm"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      <div className="px-2 pb-2 space-y-2">
        {teams.map(team => (
          <div key={team.id} className="p-3 bg-[#2d2d2d] rounded border border-[#3c3c3c]">
            <div className="font-medium text-sm mb-2">{team.name}</div>
            <div className="flex flex-wrap gap-1">
              {team.members.map(memberId => {
                const agent = agents.find(a => a.id === memberId);
                if (!agent) return null;
                return (
                  <div
                    key={memberId}
                    className="flex items-center gap-1 px-2 py-0.5 bg-[#3c3c3c] rounded-full text-xs"
                  >
                    <span>{agent.avatar}</span>
                    <span>{agent.name}</span>
                    <Circle size={6} className={cn("fill-current", `bg-[${agent.color}]`)} />
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
