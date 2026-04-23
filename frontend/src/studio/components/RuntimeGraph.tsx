import { useEffect, useMemo } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useStudioStore } from "@/studio/store";
import type { RuntimeTask } from "@/studio/types";

const statusColor: Record<string, string> = {
  pending: "#8b949e",
  running: "#58a6ff",
  blocked: "#d29922",
  completed: "#3fb950",
  failed: "#f85149",
};

function buildGraph(tasks: Record<string, RuntimeTask>): { nodes: Node[]; edges: Edge[] } {
  const ids = Object.keys(tasks);
  const depth = new Map<string, number>();

  function computeDepth(id: string): number {
    if (depth.has(id)) return depth.get(id)!;
    const deps = tasks[id]?.dependencies ?? [];
    if (deps.length === 0) {
      depth.set(id, 0);
      return 0;
    }
    const v = 1 + Math.max(...deps.map((d) => computeDepth(d)), 0);
    depth.set(id, v);
    return v;
  }
  ids.forEach((id) => computeDepth(id));

  const byLevel = new Map<number, string[]>();
  for (const id of ids) {
    const lv = depth.get(id) ?? 0;
    if (!byLevel.has(lv)) byLevel.set(lv, []);
    byLevel.get(lv)!.push(id);
  }

  const nodes: Node[] = [];
  const sortedLevels = [...byLevel.entries()].sort((a, b) => a[0] - b[0]);
  for (const [lv, row] of sortedLevels) {
    row.forEach((id, i) => {
      const t = tasks[id];
      const st = t?.status ?? "pending";
      nodes.push({
        id,
        position: { x: lv * 220, y: i * 88 },
        data: { label: `${id}\n${st}` },
        style: {
          border: `1px solid ${statusColor[st] ?? "#30363d"}`,
          borderRadius: 8,
          padding: 8,
          background: "#252526",
          color: "#e6edf3",
          fontSize: 11,
          minWidth: 100,
        },
      });
    });
  }

  const edges: Edge[] = [];
  for (const id of ids) {
    for (const dep of tasks[id]?.dependencies ?? []) {
      edges.push({
        id: `${dep}->${id}`,
        source: dep,
        target: id,
        animated: tasks[id]?.status === "running",
      });
    }
  }
  return { nodes, edges };
}

function GraphInner({ heightClass }: { heightClass: string }) {
  const runtimeTasks = useStudioStore((s) => s.runtimeTasks);
  const { nodes: bn, edges: be } = useMemo(() => buildGraph(runtimeTasks), [runtimeTasks]);
  const [nodes, setNodes, onNodesChange] = useNodesState(bn);
  const [edges, setEdges, onEdgesChange] = useEdgesState(be);

  useEffect(() => {
    setNodes(bn);
    setEdges(be);
  }, [bn, be, setNodes, setEdges]);

  if (Object.keys(runtimeTasks).length === 0) {
    return (
      <div className="p-4 text-xs text-[#858585]">
        No tasks yet. Run the hybrid DAG from the title bar.
      </div>
    );
  }

  return (
    <div className={`${heightClass} w-full bg-[#1e1e1e] min-h-[200px]`}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} color="#333" />
        <MiniMap className="!bg-[#252526]" />
        <Controls className="!bg-[#252526] !border-[#454545]" />
      </ReactFlow>
    </div>
  );
}

export function RuntimeGraph({ compact }: { compact?: boolean }) {
  const heightClass = compact ? "h-72" : "h-[min(420px,calc(100vh-220px))]";
  return (
    <ReactFlowProvider>
      <GraphInner heightClass={heightClass} />
    </ReactFlowProvider>
  );
}
