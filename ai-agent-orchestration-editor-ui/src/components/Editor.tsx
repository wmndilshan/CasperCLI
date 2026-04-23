import Editor from '@monaco-editor/react';
import { useStore } from '../store/store';
import { X, Circle } from 'lucide-react';
import { cn } from '../utils/cn';

const getLanguage = (filename: string): string => {
  const ext = filename.split('.').pop()?.toLowerCase();
  const langMap: Record<string, string> = {
    ts: 'typescript',
    tsx: 'typescript',
    js: 'javascript',
    jsx: 'javascript',
    css: 'css',
    json: 'json',
    md: 'markdown',
    html: 'html',
  };
  return langMap[ext || ''] || 'plaintext';
};

export function EditorArea() {
  const { tabs, activeTabId, setActiveTab, closeTab, updateTabContent, diagnostics } = useStore();
  const activeTab = tabs.find(t => t.id === activeTabId);

  return (
    <div className="flex-1 flex flex-col bg-[#1e1e1e] min-w-0">
      {/* Tabs */}
      <div className="flex bg-[#252526] border-b border-[#1e1e1e] overflow-x-auto">
        {tabs.map(tab => (
          <div
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "flex items-center gap-2 px-3 py-2 border-r border-[#252526] cursor-pointer min-w-[120px] group",
              activeTabId === tab.id
                ? "bg-[#1e1e1e] border-t-2 border-t-[#007fd4]"
                : "bg-[#2d2d2d] hover:bg-[#2a2d2e]"
            )}
          >
            <span className="text-sm truncate flex-1">{tab.name}</span>
            {tab.isModified && (
              <Circle size={8} className="fill-[#c5c5c5] text-[#c5c5c5]" />
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                closeTab(tab.id);
              }}
              className="opacity-0 group-hover:opacity-100 hover:bg-[#3c3c3c] rounded p-0.5 transition-opacity"
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>

      {/* Editor or Welcome */}
      {activeTab ? (
        <div className="flex-1 relative">
          <Editor
            height="100%"
            language={getLanguage(activeTab.name)}
            value={activeTab.content}
            theme="vs-dark"
            onChange={(value) => {
              if (value !== undefined) {
                updateTabContent(activeTab.id, value);
              }
            }}
            options={{
              fontSize: 14,
              fontFamily: '"Cascadia Code", "Fira Code", Consolas, monospace',
              minimap: { enabled: true },
              scrollBeyondLastLine: false,
              automaticLayout: true,
              wordWrap: 'on',
              tabSize: 2,
              lineNumbers: 'on',
              renderWhitespace: 'selection',
              cursorBlinking: 'smooth',
              cursorSmoothCaretAnimation: 'on',
              smoothScrolling: true,
              padding: { top: 10 },
            }}
          />
          
          {/* Mini diagnostics */}
          {diagnostics.filter(d => d.file === activeTab.name).length > 0 && (
            <div className="absolute bottom-4 right-4 bg-[#252526] rounded-lg shadow-lg border border-[#3c3c3c] p-2 max-w-xs">
              {diagnostics.filter(d => d.file === activeTab.name).map(d => (
                <div key={d.id} className="flex items-start gap-2 text-xs py-1">
                  <Circle 
                    size={8} 
                    className={cn(
                      "mt-1 fill-current flex-shrink-0",
                      d.severity === 'error' && "text-red-500",
                      d.severity === 'warning' && "text-yellow-500",
                      d.severity === 'info' && "text-blue-500"
                    )} 
                  />
                  <span className="text-[#cccccc]">Line {d.line}: {d.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <WelcomeScreen />
      )}
    </div>
  );
}

function WelcomeScreen() {
  return (
    <div className="flex-1 flex items-center justify-center bg-[#1e1e1e]">
      <div className="text-center">
        <h1 className="text-4xl font-light text-[#cccccc] mb-2">
          AI Code Studio
        </h1>
        <p className="text-[#858585] mb-8">Intelligent Development Environment</p>
        
        <div className="flex gap-4 justify-center">
          <div className="bg-[#252526] rounded-lg p-4 w-48 text-left border border-[#3c3c3c]">
            <div className="text-2xl mb-2">🤖</div>
            <div className="text-sm font-medium text-[#cccccc]">AI Agents</div>
            <div className="text-xs text-[#858585] mt-1">
              Manage your AI team from the sidebar
            </div>
          </div>
          
          <div className="bg-[#252526] rounded-lg p-4 w-48 text-left border border-[#3c3c3c]">
            <div className="text-2xl mb-2">💬</div>
            <div className="text-sm font-medium text-[#cccccc]">Chat & Commands</div>
            <div className="text-xs text-[#858585] mt-1">
              Use @agent to give commands
            </div>
          </div>
          
          <div className="bg-[#252526] rounded-lg p-4 w-48 text-left border border-[#3c3c3c]">
            <div className="text-2xl mb-2">📝</div>
            <div className="text-sm font-medium text-[#cccccc]">Code Editor</div>
            <div className="text-xs text-[#858585] mt-1">
              Full syntax highlighting support
            </div>
          </div>
        </div>
        
        <div className="mt-8 text-xs text-[#858585]">
          Open a file from the Explorer to start editing
        </div>
      </div>
    </div>
  );
}
