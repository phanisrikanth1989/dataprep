import { useCallback, useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Node,
  Edge,
  BackgroundVariant,
  Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Button, message, Drawer, Tabs, Modal } from 'antd';
import { ArrowLeftOutlined, SaveOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { useStore } from '../store';
import { v4 as uuidv4 } from 'uuid';
import type { JobNode, JobEdge, ComponentMetadata, SchemaColumn } from '../types';
import ComponentPalette from '../components/ComponentPalette';
import ConfigPanel from '../components/ConfigPanel';
import SchemaEditor from '../components/SchemaEditor';
import MapEditor from '../components/MapEditor';
import ETLNode from '../components/ETLNode';
import './JobDesigner.css';

// Custom node types
const nodeTypes = { etlNode: ETLNode };

// Input components that support schema definition
const INPUT_COMPONENTS = ['FileInputDelimited', 'DatabaseInput', 'FileInputExcel', 'FileInputJSON'];

// Components that need the Map Editor
const MAP_COMPONENTS = ['Map'];

export default function JobDesigner() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const { currentJob, loadJob, updateJob, components, loadComponents } = useStore();

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('config');
  const [saving, setSaving] = useState(false);
  const [mapEditorOpen, setMapEditorOpen] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [executionTaskId, setExecutionTaskId] = useState<string | null>(null);

  // Load job and components
  useEffect(() => {
    if (jobId) loadJob(jobId);
    if (components.length === 0) loadComponents();
  }, [jobId, loadJob, loadComponents, components.length]);

  // Convert job data to React Flow format
  useEffect(() => {
    if (currentJob) {
      const flowNodes: Node[] = currentJob.nodes.map((n) => ({
        id: n.id,
        type: 'etlNode',
        position: { x: n.x, y: n.y },
        data: { 
          label: n.label, 
          type: n.type, 
          name: n.name,
          config: n.config,
        },
      }));
      const flowEdges: Edge[] = currentJob.edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: 'smoothstep',
        animated: e.edge_type === 'trigger',
        style: { stroke: e.edge_type === 'reject' ? '#ff4d4f' : '#1890ff', strokeWidth: 2 },
      }));
      setNodes(flowNodes);
      setEdges(flowEdges);
    }
  }, [currentJob, setNodes, setEdges]);

  // Handle edge connections
  const onConnect = useCallback(
    (connection: Connection) => {
      const newEdge: Edge = {
        ...connection,
        id: `edge-${uuidv4()}`,
        source: connection.source || '',
        target: connection.target || '',
        type: 'smoothstep',
        style: { stroke: '#1890ff', strokeWidth: 2 },
      };
      setEdges((eds) => [...eds, newEdge]);
    },
    [setEdges]
  );

  // Handle node click
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
    const nodeType = (node.data as any).type;
    
    // Open Map Editor for Map components
    if (MAP_COMPONENTS.includes(nodeType)) {
      setMapEditorOpen(true);
    } else {
      setActiveTab('config');
      setDrawerOpen(true);
    }
  }, []);

  // Handle drop from palette
  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const componentType = event.dataTransfer.getData('application/reactflow');
      if (!componentType) return;

      const component = components.find((c) => c.type === componentType);
      if (!component) return;

      const bounds = (event.target as HTMLElement).getBoundingClientRect();
      const position = {
        x: event.clientX - bounds.left - 75,
        y: event.clientY - bounds.top - 30,
      };

      const newNode: Node = {
        id: `node-${uuidv4()}`,
        type: 'etlNode',
        position,
        data: {
          label: component.label,
          type: component.type,
          name: '',
          config: {},
        },
      };

      setNodes((nds) => [...nds, newNode]);
      message.success(`Added ${component.label}`);
    },
    [components, setNodes]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  // Save job
  const handleSave = async () => {
    if (!currentJob || !jobId) return;
    setSaving(true);

    const jobNodes: JobNode[] = nodes.map((n) => ({
      id: n.id,
      type: (n.data as any).type,
      label: (n.data as any).label,
      name: (n.data as any).name,
      x: n.position.x,
      y: n.position.y,
      config: (n.data as any).config || {},
    }));

    const jobEdges: JobEdge[] = edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      edge_type: 'flow',
    }));

    try {
      await updateJob(jobId, {
        ...currentJob,
        nodes: jobNodes,
        edges: jobEdges,
      });
      message.success('Job saved!');
      return true;
    } catch (error) {
      message.error('Failed to save job');
      return false;
    } finally {
      setSaving(false);
    }
  };

  // Execute job
  const handleExecute = async () => {
    if (!jobId) return;

    // Save first
    const saved = await handleSave();
    if (!saved) return;

    setExecuting(true);
    try {
      const { startExecution, pollExecution } = useStore.getState();
      const taskId = await startExecution(jobId);
      setExecutionTaskId(taskId);
      message.info(`Execution started: ${taskId}`);

      // Poll for status
      const pollInterval = setInterval(async () => {
        try {
          const status = await pollExecution(taskId);
          if (status.status === 'success') {
            clearInterval(pollInterval);
            setExecuting(false);
            message.success('Job executed successfully!');
          } else if (status.status === 'error') {
            clearInterval(pollInterval);
            setExecuting(false);
            message.error(`Execution failed: ${status.error_message || 'Unknown error'}`);
          }
        } catch (err) {
          clearInterval(pollInterval);
          setExecuting(false);
        }
      }, 1000);

      // Auto-stop polling after 5 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        if (executing) {
          setExecuting(false);
          message.warning('Execution timed out');
        }
      }, 300000);

    } catch (error: any) {
      setExecuting(false);
      message.error(`Failed to start execution: ${error.message || 'Unknown error'}`);
    }
  };

  // Update node config
  const handleConfigUpdate = (config: Record<string, any>) => {
    if (!selectedNode) return;
    
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNode.id
          ? { ...n, data: { ...n.data, config, name: config._nodeName || n.data.name } }
          : n
      )
    );
    setDrawerOpen(false);
    message.success('Configuration saved');
  };

  // Update node schema
  const handleSchemaUpdate = (schema: SchemaColumn[]) => {
    if (!selectedNode) return;
    
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNode.id
          ? { ...n, data: { ...n.data, config: { ...(n.data.config as any), output_schema: schema } } }
          : n
      )
    );
    message.success('Schema saved');
  };

  // Get input schema from connected upstream nodes (recursively if needed)
  const getInputSchemaForNode = useCallback((nodeId: string): SchemaColumn[] => {
    // Find edges that connect TO this node
    const incomingEdges = edges.filter((e) => e.target === nodeId);
    if (incomingEdges.length === 0) return [];

    // Get the source node(s)
    const sourceNodeIds = incomingEdges.map((e) => e.source);
    const sourceNodes = nodes.filter((n) => sourceNodeIds.includes(n.id));

    // Collect schemas from all source nodes
    const schemas: SchemaColumn[] = [];
    sourceNodes.forEach((srcNode) => {
      const srcConfig = (srcNode.data as any).config || {};
      const srcType = (srcNode.data as any).type;
      
      // If source is a Map component, get output schema from its mappings
      if (srcType === 'Map' && srcConfig.mappings) {
        const mapOutputSchema = srcConfig.mappings.map((m: any) => ({
          name: m.targetColumn,
          type: m.dataType || 'string',
          length: null,
          precision: null,
          nullable: true,
        }));
        schemas.push(...mapOutputSchema);
      } else if (srcConfig.output_schema) {
        // For input components, use their defined output_schema
        schemas.push(...srcConfig.output_schema);
      } else {
        // For transform components without explicit schema, try to get from their input (recursive)
        const upstreamSchema = getInputSchemaForNode(srcNode.id);
        schemas.push(...upstreamSchema);
      }
    });

    return schemas;
  }, [nodes, edges]);

  // Handle Map editor save - also generate output_schema from mappings
  const handleMapMappingsSave = useCallback((mappings: any[]) => {
    if (!selectedNode) return;

    // Generate output_schema from mappings
    const outputSchema: SchemaColumn[] = mappings.map((m) => ({
      name: m.targetColumn,
      type: m.dataType || 'string',
      length: null,
      precision: null,
      nullable: true,
    }));

    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNode.id
          ? { 
              ...n, 
              data: { 
                ...n.data, 
                config: { 
                  ...(n.data.config as any), 
                  mappings,
                  output_schema: outputSchema 
                } 
              } 
            }
          : n
      )
    );
    setMapEditorOpen(false);
    message.success('Mappings saved');
  }, [selectedNode, setNodes]);

  // Get component metadata for selected node
  const selectedComponent = useMemo(() => {
    if (!selectedNode) return null;
    return components.find((c) => c.type === (selectedNode.data as any).type);
  }, [selectedNode, components]);

  const isInputComponent = selectedNode && INPUT_COMPONENTS.includes((selectedNode.data as any).type);
  const isOutputComponent = selectedNode && ['FileOutputDelimited', 'DatabaseOutput'].includes((selectedNode.data as any).type);
  const isMapComponent = selectedNode && MAP_COMPONENTS.includes((selectedNode.data as any).type);

  // Drawer tabs
  const drawerTabs = useMemo(() => {
    const items = [
      {
        key: 'config',
        label: '⚙️ Settings',
        children: selectedComponent && selectedNode && (
          <ConfigPanel
            node={selectedNode}
            component={selectedComponent}
            onSave={handleConfigUpdate}
            onCancel={() => setDrawerOpen(false)}
          />
        ),
      },
    ];

    if (isInputComponent) {
      items.push({
        key: 'schema',
        label: '📋 Schema',
        children: selectedNode && (
          <SchemaEditor
            schema={(selectedNode.data as any).config?.output_schema || []}
            onSave={handleSchemaUpdate}
          />
        ),
      });
    }

    // Show inherited schema for output components (read-only view)
    if (isOutputComponent && selectedNode) {
      const inheritedSchema = getInputSchemaForNode(selectedNode.id);
      items.push({
        key: 'schema',
        label: `📋 Input Schema (${inheritedSchema.length})`,
        children: (
          <div style={{ padding: '12px' }}>
            <p style={{ color: '#666', marginBottom: '12px' }}>Schema inherited from connected input:</p>
            {inheritedSchema.length === 0 ? (
              <p style={{ color: '#999' }}>No input connected or no schema defined upstream.</p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: '#fafafa' }}>
                    <th style={{ padding: '8px', border: '1px solid #f0f0f0', textAlign: 'left' }}>Column</th>
                    <th style={{ padding: '8px', border: '1px solid #f0f0f0', textAlign: 'left' }}>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {inheritedSchema.map((col, idx) => (
                    <tr key={idx}>
                      <td style={{ padding: '8px', border: '1px solid #f0f0f0' }}>{col.name}</td>
                      <td style={{ padding: '8px', border: '1px solid #f0f0f0' }}>{col.type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ),
      });
    }

    return items;
  }, [selectedComponent, selectedNode, isInputComponent, isOutputComponent, getInputSchemaForNode]);

  return (
    <div className="job-designer">
      {/* Header */}
      <header className="designer-header">
        <div className="header-left">
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')}>
            Back
          </Button>
          <div className="job-info">
            <h2>{currentJob?.name || 'Untitled Job'}</h2>
            <span className="job-id">{jobId}</span>
          </div>
        </div>
        <div className="header-right">
          <Button icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
            Save
          </Button>
          <Button 
            type="primary" 
            icon={<PlayCircleOutlined />}
            onClick={handleExecute}
            loading={executing}
            disabled={nodes.length === 0}
          >
            {executing ? 'Executing...' : 'Execute'}
          </Button>
        </div>
      </header>

      {/* Main Content */}
      <div className="designer-content">
        {/* Component Palette */}
        <aside className="palette-sidebar">
          <ComponentPalette components={components} />
        </aside>

        {/* Canvas */}
        <div className="canvas-area" onDrop={onDrop} onDragOver={onDragOver}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            fitView
            snapToGrid
            snapGrid={[15, 15]}
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
            <Controls />
            <Panel position="top-left" className="canvas-info">
              {nodes.length} components · {edges.length} connections
            </Panel>
          </ReactFlow>
        </div>
      </div>

      {/* Config Drawer */}
      <Drawer
        title={selectedNode ? `${(selectedNode.data as any).label} Configuration` : 'Configuration'}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={450}
        destroyOnClose
      >
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={drawerTabs} />
      </Drawer>

      {/* Map Editor Modal */}
      <Modal
        title={`🔀 Map Editor - ${selectedNode ? (selectedNode.data as any).name || (selectedNode.data as any).label : ''}`}
        open={mapEditorOpen}
        onCancel={() => setMapEditorOpen(false)}
        footer={null}
        width="90%"
        style={{ top: 20 }}
        styles={{ body: { height: 'calc(100vh - 150px)', padding: 0, overflow: 'hidden' } }}
        destroyOnClose
      >
        {selectedNode && (
          <MapEditor
            inputSchema={getInputSchemaForNode(selectedNode.id)}
            outputMappings={(selectedNode.data as any).config?.mappings || []}
            onSave={handleMapMappingsSave}
          />
        )}
      </Modal>
    </div>
  );
}
