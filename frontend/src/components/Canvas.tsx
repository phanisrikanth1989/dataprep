import React, { useCallback, useRef, useEffect } from 'react';
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
  useReactFlow,
  ReactFlowProvider,
  NodeChange,
  EdgeChange,
} from 'reactflow';
import 'reactflow/dist/style.css';
import ComponentNode from './ComponentNode.tsx';

interface CanvasProps {
  onNodesChange: (nodes: Node[]) => void;
  onEdgesChange: (edges: Edge[]) => void;
  onNodeSelect?: (node: Node | null) => void;
  initialNodes: Node[];
  initialEdges: Edge[];
}

const nodeTypes = {
  component: ComponentNode,
};

const CanvasInner: React.FC<CanvasProps> = ({
  onNodesChange,
  onEdgesChange,
  onNodeSelect,
  initialNodes,
  initialEdges,
}) => {
  const [nodes, setNodes, handleNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, handleEdgesChange] = useEdgesState(initialEdges);
  const reactFlowInstance = useReactFlow();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  // Sync initial nodes/edges when they change externally
  useEffect(() => {
    if (initialNodes.length > 0 || nodes.length === 0) {
      setNodes(initialNodes);
    }
  }, [initialNodes, setNodes]);

  useEffect(() => {
    if (initialEdges.length > 0 || edges.length === 0) {
      setEdges(initialEdges);
    }
  }, [initialEdges, setEdges]);

  const handleConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => {
        const newEdges = addEdge(connection, eds);
        onEdgesChange(newEdges);
        return newEdges;
      });
    },
    [setEdges, onEdgesChange]
  );

  const onNodeChangeHandler = useCallback(
    (changes: NodeChange[]) => {
      handleNodesChange(changes);
      // Use functional update to get latest state
      setNodes((currentNodes) => {
        // Schedule the callback to run after state update
        setTimeout(() => onNodesChange(currentNodes), 0);
        return currentNodes;
      });
    },
    [handleNodesChange, setNodes, onNodesChange]
  );

  const onEdgeChangeHandler = useCallback(
    (changes: EdgeChange[]) => {
      handleEdgesChange(changes);
      setEdges((currentEdges) => {
        setTimeout(() => onEdgesChange(currentEdges), 0);
        return currentEdges;
      });
    },
    [handleEdgesChange, setEdges, onEdgesChange]
  );

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      onNodeSelect?.(node);
    },
    [onNodeSelect]
  );

  const onPaneClick = useCallback(() => {
    onNodeSelect?.(null);
  }, [onNodeSelect]);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const componentType = event.dataTransfer.getData('componentType');

      if (!componentType || !reactFlowWrapper.current) return;

      // Get the correct position using React Flow's coordinate system
      const bounds = reactFlowWrapper.current.getBoundingClientRect();
      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX - bounds.left,
        y: event.clientY - bounds.top,
      });

      const newNode: Node = {
        id: `${componentType}_${Date.now()}`,
        data: { label: componentType, type: componentType, config: {} },
        position,
        type: 'component',
      };

      setNodes((nds) => {
        const newNodes = [...nds, newNode];
        onNodesChange(newNodes);
        return newNodes;
      });
    },
    [reactFlowInstance, setNodes, onNodesChange]
  );

  return (
    <div ref={reactFlowWrapper} style={{ width: '100%', height: '100%' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodeChangeHandler}
        onEdgesChange={onEdgeChangeHandler}
        onConnect={handleConnect}
        onDrop={onDrop}
        onDragOver={(e) => e.preventDefault()}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
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

// Wrap with ReactFlowProvider to use useReactFlow hook
const Canvas: React.FC<CanvasProps> = (props) => {
  return (
    <ReactFlowProvider>
      <CanvasInner {...props} />
    </ReactFlowProvider>
  );
};

export default Canvas;
