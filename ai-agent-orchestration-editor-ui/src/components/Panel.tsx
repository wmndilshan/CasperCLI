import { useState, useRef, useEffect } from 'react';
import { useStore } from '../store/store';
import { cn } from '../utils/cn';
import { 
  Terminal, 
  AlertCircle, 
  FileOutput, 
  MessageSquare, 
  ChevronUp, 
  ChevronDown,
  Send,
  AtSign,
  Sparkles,
  Edit3,
  Eye,
  TestTube,
  CheckCircle,
  XCircle
} from 'lucide-react';

const tabs = [
  { id: 'terminal' as const, icon: Terminal, label: 'Terminal' },
  { id: 'problems' as const, icon: AlertCircle, label: 'Problems' },
  { id: 'output' as const, icon: FileOutput, label: 'Output' },
  { id: 'chat' as const, icon: MessageSquare, label: 'AI Chat' },
];

const activityIcons: Record<string, React.ReactNode> = {
  edit: <Edit3 size={14} className="text-blue-400" />,
  analyze: <Sparkles size={14} className="text-purple-400" />,
  review: <Eye size={14} className="text-amber-400" />,
  test: <TestTube size={14} className="text-green-400" />,
  complete: <CheckCircle size={14} className="text-green-500" />,
  error: <XCircle size={14} className="text-red-400" />,
  comment: <MessageSquare size={14} className="text-blue-400" />,
};

export function Panel() {
  const { 
    panelView, 
    setPanelView, 
    isPanelOpen, 
    togglePanel,
    messages,
    activities,
    commandInput,
    setCommandInput,
    addMessage,
    agents,
    updateAgentStatus,
    addActivity,
    diagnostics
  } = useStore();
  
  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [showMentions, setShowMentions] = useState(false);
  const [mentionFilter, setMentionFilter] = useState('');

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activities]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setCommandInput(value);
    
    // Check for @ mentions
    const lastAtIndex = value.lastIndexOf('@');
    if (lastAtIndex !== -1 && lastAtIndex === value.length - 1) {
      setShowMentions(true);
      setMentionFilter('');
    } else if (lastAtIndex !== -1) {
      const afterAt = value.slice(lastAtIndex + 1);
      if (!afterAt.includes(' ')) {
        setShowMentions(true);
        setMentionFilter(afterAt.toLowerCase());
      } else {
        setShowMentions(false);
      }
    } else {
      setShowMentions(false);
    }
  };

  const handleMentionSelect = (agentName: string) => {
    const lastAtIndex = commandInput.lastIndexOf('@');
    const newInput = commandInput.slice(0, lastAtIndex) + `@${agentName} `;
    setCommandInput(newInput);
    setShowMentions(false);
    inputRef.current?.focus();
  };

  const handleSendCommand = () => {
    if (!commandInput.trim()) return;
    
    // Parse mentions
    const mentions = [...commandInput.matchAll(/@(\w+)/g)].map(m => m[1]);
    
    addMessage({
      content: commandInput,
      type: 'command',
      mentions,
    });
    
    // Simulate agent response
    const mentionedAgents = agents.filter(a => 
      mentions.some(m => a.name.toLowerCase() === m.toLowerCase())
    );
    
    mentionedAgents.forEach(agent => {
      updateAgentStatus(agent.id, 'working', 'Processing command...');
      
      setTimeout(() => {
        const responses = [
          `Got it! Working on that now.`,
          `I'll handle that for you.`,
          `Starting analysis...`,
          `On it! Give me a moment.`,
        ];
        
        addMessage({
          agentId: agent.id,
          content: responses[Math.floor(Math.random() * responses.length)],
          type: 'agent',
        });
        
        addActivity({
          agentId: agent.id,
          action: `Processing: "${commandInput.slice(0, 50)}..."`,
          type: 'analyze',
        });
        
        setTimeout(() => {
          updateAgentStatus(agent.id, 'completed');
          addActivity({
            agentId: agent.id,
            action: 'Task completed',
            type: 'complete',
          });
        }, 2000);
      }, 1000);
    });
    
    setCommandInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !showMentions) {
      handleSendCommand();
    }
  };

  const filteredAgents = agents.filter(a =>
    a.name.toLowerCase().includes(mentionFilter)
  );

  return (
    <div className="bg-[#1e1e1e] border-t border-[#3c3c3c] flex flex-col" style={{ height: isPanelOpen ? '280px' : '35px' }}>
      {/* Panel Header */}
      <div className="flex items-center justify-between bg-[#252526] border-b border-[#3c3c3c]">
        <div className="flex">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => {
                setPanelView(tab.id);
                if (!isPanelOpen) togglePanel();
              }}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 text-xs transition-colors",
                panelView === tab.id && isPanelOpen
                  ? "text-white border-b-2 border-[#007fd4] bg-[#1e1e1e]"
                  : "text-[#858585] hover:text-[#cccccc]"
              )}
            >
              <tab.icon size={14} />
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
        
        <button
          onClick={togglePanel}
          className="p-1.5 text-[#858585] hover:text-white hover:bg-[#3c3c3c] rounded"
        >
          {isPanelOpen ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
        </button>
      </div>

      {/* Panel Content */}
      {isPanelOpen && (
        <div className="flex-1 overflow-hidden flex">
          {/* Main Content Area */}
          <div className="flex-1 overflow-y-auto p-2">
            {panelView === 'terminal' && (
              <div className="font-mono text-sm text-[#cccccc] p-2">
                <div className="text-[#858585]">PS C:\Projects\ai-code-studio&gt;</div>
                <div className="text-green-400">npm run dev</div>
                <div className="text-[#858585] mt-1">Starting development server...</div>
                <div className="text-green-400 mt-1">✓ Ready in 1.2s</div>
                <div className="text-cyan-400">➜ Local: http://localhost:5173/</div>
              </div>
            )}

            {panelView === 'problems' && (
              <div className="space-y-1">
                {diagnostics.map(d => (
                  <div key={d.id} className="flex items-start gap-2 p-2 hover:bg-[#2a2d2e] rounded text-sm">
                    <AlertCircle 
                      size={16} 
                      className={cn(
                        "mt-0.5 flex-shrink-0",
                        d.severity === 'error' && "text-red-500",
                        d.severity === 'warning' && "text-yellow-500",
                        d.severity === 'info' && "text-blue-500"
                      )} 
                    />
                    <span className="text-[#cccccc]">{d.message}</span>
                    <span className="text-[#858585] text-xs ml-auto">
                      {d.file}:{d.line}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {panelView === 'output' && (
              <div className="font-mono text-sm text-[#cccccc] p-2">
                <div className="text-[#858585]">[Extension Host]</div>
                <div className="text-green-400">AI Agent extension activated</div>
                <div className="text-[#858585] mt-1">[Agent: Atlas]</div>
                <div className="text-blue-400">Architecture analysis complete</div>
                <div className="text-[#858585] mt-1">[Agent: Coder]</div>
                <div className="text-blue-400">Code generation ready</div>
              </div>
            )}

            {panelView === 'chat' && (
              <div className="flex flex-col h-full">
                {/* Messages */}
                <div className="flex-1 overflow-y-auto space-y-2 p-2">
                  {messages.map(msg => {
                    const agent = msg.agentId ? agents.find(a => a.id === msg.agentId) : null;
                    return (
                      <div
                        key={msg.id}
                        className={cn(
                          "flex gap-2",
                          msg.type === 'user' || msg.type === 'command' ? "flex-row-reverse" : ""
                        )}
                      >
                        {agent && (
                          <div 
                            className="w-7 h-7 rounded-lg flex items-center justify-center text-sm flex-shrink-0"
                            style={{ backgroundColor: agent.color + '30' }}
                          >
                            {agent.avatar}
                          </div>
                        )}
                        {msg.type === 'system' && (
                          <div className="w-7 h-7 rounded-lg bg-[#3c3c3c] flex items-center justify-center text-sm flex-shrink-0">
                            ⚙️
                          </div>
                        )}
                        {(msg.type === 'user' || msg.type === 'command') && (
                          <div className="w-7 h-7 rounded-lg bg-[#0e639c] flex items-center justify-center text-sm flex-shrink-0">
                            👤
                          </div>
                        )}
                        <div className={cn(
                          "max-w-[70%] rounded-lg px-3 py-2 text-sm",
                          msg.type === 'user' || msg.type === 'command'
                            ? "bg-[#0e639c]"
                            : "bg-[#2d2d2d]"
                        )}>
                          {msg.type === 'command' && msg.mentions && msg.mentions.length > 0 && (
                            <div className="flex gap-1 mb-1 flex-wrap">
                              {msg.mentions.map(m => (
                                <span key={m} className="text-xs bg-[#1e1e1e] px-1.5 py-0.5 rounded text-blue-400">
                                  @{m}
                                </span>
                              ))}
                            </div>
                          )}
                          <span className="text-[#cccccc]">{msg.content}</span>
                          <div className="text-[10px] text-[#858585] mt-1">
                            {msg.timestamp.toLocaleTimeString()}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input */}
                <div className="p-2 relative">
                  {showMentions && (
                    <div className="absolute bottom-full left-2 right-2 mb-1 bg-[#252526] rounded-lg border border-[#3c3c3c] shadow-lg overflow-hidden">
                      {filteredAgents.map(agent => (
                        <button
                          key={agent.id}
                          onClick={() => handleMentionSelect(agent.name)}
                          className="w-full flex items-center gap-2 px-3 py-2 hover:bg-[#094771] text-left"
                        >
                          <span>{agent.avatar}</span>
                          <span className="text-sm text-[#cccccc]">{agent.name}</span>
                          <span className="text-xs text-[#858585] ml-auto">
                            {agent.role}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="flex items-center gap-2 bg-[#2d2d2d] rounded-lg px-3 py-2">
                    <AtSign size={16} className="text-[#858585]" />
                    <input
                      ref={inputRef}
                      type="text"
                      placeholder="Type @ to mention an agent..."
                      value={commandInput}
                      onChange={handleInputChange}
                      onKeyDown={handleKeyDown}
                      className="flex-1 bg-transparent text-sm text-[#cccccc] focus:outline-none"
                    />
                    <button
                      onClick={handleSendCommand}
                      className="p-1 bg-[#0e639c] hover:bg-[#1177bb] rounded transition-colors"
                    >
                      <Send size={16} />
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Activity Feed (only for chat view) */}
          {panelView === 'chat' && (
            <div className="w-64 border-l border-[#3c3c3c] overflow-y-auto">
              <div className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-[#858585] border-b border-[#3c3c3c]">
                Agent Activity
              </div>
              <div className="p-2 space-y-2">
                {activities.slice(-20).reverse().map(activity => {
                  const agent = agents.find(a => a.id === activity.agentId);
                  return (
                    <div key={activity.id} className="flex items-start gap-2 text-xs">
                      {activityIcons[activity.type]}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1">
                          <span className="font-medium" style={{ color: agent?.color }}>
                            {agent?.name}
                          </span>
                        </div>
                        <div className="text-[#858585] truncate">{activity.action}</div>
                        {activity.details && (
                          <div className="text-[#666]">{activity.details}</div>
                        )}
                        <div className="text-[10px] text-[#555] mt-0.5">
                          {activity.timestamp.toLocaleTimeString()}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
