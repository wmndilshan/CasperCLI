import { useState } from 'react';
import { ChevronDown, ChevronRight, File, Folder, FolderOpen } from 'lucide-react';
import { useStore } from '../store/store';
import { FileNode } from '../types';

function getFileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase();
  const icons: Record<string, string> = {
    ts: '🔷',
    tsx: '⚛️',
    js: '📜',
    jsx: '⚛️',
    css: '🎨',
    json: '📋',
    md: '📝',
    html: '🌐',
  };
  return icons[ext || ''] || '📄';
}

function FileTreeItem({ node, depth = 0 }: { node: FileNode; depth?: number }) {
  const [isOpen, setIsOpen] = useState(depth < 1);
  const { openFile, tabs, activeTabId } = useStore();
  
  const isFolder = node.type === 'folder';
  const isActive = tabs.some(t => t.id === node.id) && activeTabId === node.id;
  
  const handleClick = () => {
    if (isFolder) {
      setIsOpen(!isOpen);
    } else {
      openFile(node);
    }
  };
  
  return (
    <div>
      <div
        onClick={handleClick}
        className={`flex items-center gap-1 py-[3px] px-2 cursor-pointer text-[13px]
          hover:bg-[#2a2d2e] ${isActive ? 'bg-[#37373d]' : ''}`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {isFolder && (
          <span className="text-[#858585]">
            {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </span>
        )}
        {isFolder ? (
          <span className="text-[#dcb67a]">
            {isOpen ? <FolderOpen size={16} /> : <Folder size={16} />}
          </span>
        ) : (
          <span className="flex items-center">
            <File size={16} className="text-[#858585] mr-1" />
            <span className="text-sm">{getFileIcon(node.name)}</span>
          </span>
        )}
        <span className={`${isActive ? 'text-white' : 'text-[#cccccc]'}`}>
          {node.name}
        </span>
      </div>
      
      {isFolder && isOpen && node.children?.map(child => (
        <FileTreeItem key={child.id} node={child} depth={depth + 1} />
      ))}
    </div>
  );
}

export function FileExplorer() {
  const { files } = useStore();
  
  return (
    <div className="text-[#cccccc]">
      <div className="px-4 py-2 text-xs font-semibold uppercase tracking-wide text-[#bbbbbb] flex items-center justify-between">
        <span>Explorer</span>
        <span className="text-[10px] bg-[#3c3c3c] px-1.5 py-0.5 rounded">PROJECT</span>
      </div>
      <div className="pb-2">
        {files.map(node => (
          <FileTreeItem key={node.id} node={node} />
        ))}
      </div>
    </div>
  );
}
