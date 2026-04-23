import { Sidebar } from './components/Sidebar';
import { EditorArea } from './components/Editor';
import { Panel } from './components/Panel';
import { StatusBar } from './components/StatusBar';
import { AgentDetailOverlay } from './components/AgentDetailOverlay';

function App() {
  return (
    <div className="h-screen flex flex-col bg-[#1e1e1e] text-[#cccccc] overflow-hidden">
      {/* Title Bar */}
      <div className="h-8 bg-[#323233] flex items-center px-3 text-sm select-none border-b border-[#252526]">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <span className="text-lg">🤖</span>
            <span className="font-medium text-[#cccccc]">AI Code Studio</span>
          </div>
          <span className="text-[#858585] text-xs ml-2">- Intelligent Development Environment</span>
        </div>
        
        {/* Window Controls */}
        <div className="ml-auto flex items-center gap-1">
          <div className="w-3 h-3 rounded-full bg-[#f1fa8c] cursor-pointer hover:brightness-110" title="Minimize" />
          <div className="w-3 h-3 rounded-full bg-[#50fa7b] cursor-pointer hover:brightness-110" title="Maximize" />
          <div className="w-3 h-3 rounded-full bg-[#ff5555] cursor-pointer hover:brightness-110" title="Close" />
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <EditorArea />
      </div>

      {/* Bottom Panel */}
      <Panel />

      {/* Status Bar */}
      <StatusBar />
      
      {/* Agent Detail Overlay */}
      <AgentDetailOverlay />
    </div>
  );
}

export default App;
