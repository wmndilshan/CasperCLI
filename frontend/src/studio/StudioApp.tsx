import { TitleBar } from "./components/TitleBar";
import { Sidebar } from "./components/Sidebar";
import { EditorArea } from "./components/Editor";
import { RightDashboard } from "./components/RightDashboard";
import { Panel } from "./components/Panel";
import { StatusBar } from "./components/StatusBar";
import { AgentDetailOverlay } from "./components/AgentDetailOverlay";

/**
 * IDE layout: left explorer | center Monaco | right agent/runtime dashboard | bottom console.
 */
export function StudioApp() {
  return (
    <div className="h-screen flex flex-col bg-[#1e1e1e] text-[#cccccc] overflow-hidden">
      <TitleBar />
      <div className="flex-1 flex overflow-hidden min-h-0">
        <Sidebar />
        <EditorArea />
        <RightDashboard />
      </div>
      <Panel />
      <StatusBar />
      <AgentDetailOverlay />
    </div>
  );
}
