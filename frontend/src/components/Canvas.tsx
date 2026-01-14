import React, { useCallback } from 'react';
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Connection,
  useNodesState,
  useEdgesState,
  MiniMap,
  Controls,
  Background,
} from 'reactflow';
import 'reactflow/dist/style.css';
import ComponentNode from './ComponentNode';

interface CanvasProps {
  onNodesChange: (nodes: Node[]) => void;
  onEdgesChange: (edges: Edge[]) => void;
  initialNodes: Node[];
  initialEdges: Edge[];
}

const nodeTypes = {
  component: ComponentNode,
};

const Canvas: React.FC<CanvasProps> = ({
  onNodesChange,
  onEdgesChange,
  initialNodes,
  initialEdges,
}) => {
  const [nodes, setNodes, handleNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, handleEdgesChange] = useEdgesState(initialEdges);

  const handleConnect = useCallback(
    (connection: Connection) => {
      const newEdges = addEdge(connection, edges);
      setEdges(newEdges);
      onEdgesChange(newEdges);
    },
    [edges, setEdges, onEdgesChange]
  );

  const onNodeChange = useCallback(
    (changes: any) => {
      handleNodesChange(changes);
      onNodesChange(nodes);
    },
    [nodes, handleNodesChange, onNodesChange]
  );

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const componentType = event.dataTransfer.getData('componentType');

      if (!componentType) return;

      const newNode: Node = {
        id: `${componentType}_${Date.now()}`,
        data: { label: componentType, type: componentType },
        position: { x: event.clientX - 50, y: event.clientY - 25 },
        type: 'component',
      };

      const newNodes = [...nodes, newNode];
      setNodes(newNodes);
      onNodesChange(newNodes);
    },
    [nodes, setNodes, onNodesChange]
  );

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodeChange}
        onEdgesChange={handleEdgesChange}
        onConnect={handleConnect}
        onDrop={onDrop}
        onDragOver={(e) => e.preventDefault()}
        nodeTypes={nodeTypes}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
};

export default Canvas;
