import { useCallback, useEffect, useState, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
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
import { Button, message, Modal, Tooltip, Dropdown, Menu, Badge, Tabs, Upload, Empty, Tree } from 'antd';
import type { UploadProps, TreeProps } from 'antd';
import type { DataNode } from 'antd/es/tree';
import {
  ArrowLeftOutlined,
  SaveOutlined,
  PlayCircleOutlined,
  UndoOutlined,
  RedoOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  FullscreenOutlined,
  SettingOutlined,
  BugOutlined,
  AppstoreOutlined,
  FolderOutlined,
  FolderOpenOutlined,
  DatabaseOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UploadOutlined,
  DownloadOutlined,
  ImportOutlined,
  ExportOutlined,
  FileTextOutlined,
  FileExcelOutlined,
  CodeOutlined,
  ApiOutlined,
  CloudServerOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  TableOutlined,
} from '@ant-design/icons';
import { useStore } from '../store';
import { v4 as uuidv4 } from 'uuid';
import type { JobNode, JobEdge, SchemaColumn } from '../types';
import type { 
  DBConnection, 
  ContextGroup, 
  ContextVariable, 
  ExecutionLog, 
  ValidationProblem,
  RepositoryNode 
} from '../types/repository';

// Components
import RepositoryTree from '../components/RepositoryTree';
import DBConnectionWizard from '../components/DBConnectionWizard';
import EnhancedComponentPalette from '../components/EnhancedComponentPalette';
import PropertiesPanel from '../components/PropertiesPanel';
import ContextVariablesManager from '../components/ContextVariablesManager';
import ExecutionPanel from '../components/ExecutionPanel';
import ETLNode from '../components/ETLNode';
import MapEditor from '../components/MapEditor';
import FileMetadataWizard from '../components/FileMetadataWizard';

import './JobDesignerEnhanced.css';

// Custom node types
const nodeTypes = { etlNode: ETLNode };

// Input components that support schema definition
const INPUT_COMPONENTS = ['FileInputDelimited', 'DatabaseInput', 'FileInputExcel', 'FileInputJSON'];
const MAP_COMPONENTS = ['Map'];

export default function JobDesignerEnhanced() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const { currentJob, loadJob, updateJob, components, loadComponents, darkMode, toggleDarkMode } = useStore();

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  
  // Panel visibility
  const [leftPanelCollapsed, setLeftPanelCollapsed] = useState(false);
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false);
  const [bottomPanelCollapsed, setBottomPanelCollapsed] = useState(false);
  const [bottomPanelExpanded, setBottomPanelExpanded] = useState(false);
  const [bottomPanelTab, setBottomPanelTab] = useState<'component' | 'run' | 'problems' | 'context'>('component');
  
  // File metadata state
  const [fileMetadata, setFileMetadata] = useState<any[]>([]);
  const [fileMetadataWizardOpen, setFileMetadataWizardOpen] = useState(false);
  const [fileMetadataType, setFileMetadataType] = useState<'delimited' | 'excel' | 'json' | 'xml'>('delimited');
  
  // Selected node
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  
  // Modals
  const [dbWizardOpen, setDbWizardOpen] = useState(false);
  const [editingConnection, setEditingConnection] = useState<DBConnection | undefined>();
  const [contextManagerOpen, setContextManagerOpen] = useState(false);
  const [mapEditorOpen, setMapEditorOpen] = useState(false);
  
  // State
  const [saving, setSaving] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [executionProgress, setExecutionProgress] = useState(0);
  const [selectedContext, setSelectedContext] = useState('DEV');
  
  // Data state (would be from store in production)
  const [dbConnections, setDbConnections] = useState<DBConnection[]>([]);
  const [contextGroups, setContextGroups] = useState<ContextGroup[]>([
    { id: 'ctx-dev', name: 'DEV', variables: [], isDefault: true },
    { id: 'ctx-qa', name: 'QA', variables: [], isDefault: false },
    { id: 'ctx-prod', name: 'PROD', variables: [], isDefault: false },
  ]);
  const [executionLogs, setExecutionLogs] = useState<ExecutionLog[]>([]);
  const [validationProblems, setValidationProblems] = useState<ValidationProblem[]>([]);
  const [savedJobs, setSavedJobs] = useState<{ id: string; name: string }[]>([]);
  
  // Undo/Redo history
  const [history, setHistory] = useState<{ nodes: Node[]; edges: Edge[] }[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  
  // Refs
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  // Keyboard shortcuts (Ctrl+S to save)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [nodes, edges, currentJob, jobId]);

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
        style: {
          stroke: e.edge_type === 'reject' ? '#ff4d4f' : e.edge_type === 'trigger' ? '#faad14' : '#1890ff',
          strokeWidth: 2,
        },
      }));
      setNodes(flowNodes);
      setEdges(flowEdges);
      
      // Initialize history
      setHistory([{ nodes: flowNodes, edges: flowEdges }]);
      setHistoryIndex(0);
    }
  }, [currentJob, setNodes, setEdges]);

  // Validate job and update problems
  useEffect(() => {
    const problems: ValidationProblem[] = [];
    
    // Check for unconnected components
    nodes.forEach((node) => {
      const hasIncoming = edges.some((e) => e.target === node.id);
      const hasOutgoing = edges.some((e) => e.source === node.id);
      const nodeType = (node.data as any).type;
      
      if (!hasIncoming && !INPUT_COMPONENTS.includes(nodeType)) {
        problems.push({
          id: `prob-${node.id}-noinput`,
          severity: 'warning',
          message: `${(node.data as any).label} has no input connection`,
          component: (node.data as any).name || (node.data as any).label,
          nodeId: node.id,
        });
      }
      
      if (!hasOutgoing && !['FileOutputDelimited', 'DatabaseOutput'].includes(nodeType)) {
        problems.push({
          id: `prob-${node.id}-nooutput`,
          severity: 'warning',
          message: `${(node.data as any).label} has no output connection`,
          component: (node.data as any).name || (node.data as any).label,
          nodeId: node.id,
        });
      }
      
      // Check for missing required config
      const config = (node.data as any).config || {};
      if (INPUT_COMPONENTS.includes(nodeType) && !config.filePath && !config.connection_id) {
        problems.push({
          id: `prob-${node.id}-noconfig`,
          severity: 'error',
          message: `${(node.data as any).label} has no data source configured`,
          component: (node.data as any).name || (node.data as any).label,
          nodeId: node.id,
        });
      }
    });
    
    setValidationProblems(problems);
  }, [nodes, edges]);

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
      saveToHistory();
    },
    [setEdges]
  );

  // Save to undo history
  const saveToHistory = useCallback(() => {
    setHistory((prev) => {
      const newHistory = prev.slice(0, historyIndex + 1);
      newHistory.push({ nodes: [...nodes], edges: [...edges] });
      return newHistory.slice(-50); // Keep last 50 states
    });
    setHistoryIndex((prev) => Math.min(prev + 1, 49));
  }, [nodes, edges, historyIndex]);

  // Undo
  const handleUndo = useCallback(() => {
    if (historyIndex > 0) {
      const newIndex = historyIndex - 1;
      const state = history[newIndex];
      setNodes(state.nodes);
      setEdges(state.edges);
      setHistoryIndex(newIndex);
    }
  }, [history, historyIndex, setNodes, setEdges]);

  // Redo
  const handleRedo = useCallback(() => {
    if (historyIndex < history.length - 1) {
      const newIndex = historyIndex + 1;
      const state = history[newIndex];
      setNodes(state.nodes);
      setEdges(state.edges);
      setHistoryIndex(newIndex);
    }
  }, [history, historyIndex, setNodes, setEdges]);

  // Handle node click
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
    const nodeType = (node.data as any).type;
    
    if (MAP_COMPONENTS.includes(nodeType)) {
      setMapEditorOpen(true);
    } else {
      // Show component properties in bottom panel
      setBottomPanelTab('component');
      setBottomPanelCollapsed(false);
    }
  }, []);

  // Handle canvas click (deselect)
  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // Handle drop from palette
  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const componentType = event.dataTransfer.getData('application/reactflow');
      const dbConnectionData = event.dataTransfer.getData('application/db-connection');
      const repositoryItem = event.dataTransfer.getData('repository-item');
      
      if (!componentType && !dbConnectionData && !repositoryItem) return;

      const bounds = reactFlowWrapper.current?.getBoundingClientRect();
      if (!bounds) return;

      const position = {
        x: event.clientX - bounds.left - 75,
        y: event.clientY - bounds.top - 30,
      };

      // Handle repository item drop (tables, connections)
      if (repositoryItem) {
        const { type, data } = JSON.parse(repositoryItem);
        
        if (type === 'db-table') {
          // Create DatabaseInput with table info
          const newNode: Node = {
            id: `node-${uuidv4()}`,
            type: 'etlNode',
            position,
            data: {
              label: 'DatabaseInput',
              type: 'DatabaseInput',
              name: `${data.name}_input`,
              config: {
                connection_id: data.connectionId,
                table_name: data.name,
                schema_name: data.schema,
              },
            },
          };
          setNodes((nds) => [...nds, newNode]);
          message.success(`Created input for table: ${data.name}`);
        } else if (type === 'db-connection') {
          // Create DatabaseInput with connection
          const newNode: Node = {
            id: `node-${uuidv4()}`,
            type: 'etlNode',
            position,
            data: {
              label: 'DatabaseInput',
              type: 'DatabaseInput',
              name: `${data.name}_input`,
              config: {
                connection_id: data.id,
                connection_name: data.name,
              },
            },
          };
          setNodes((nds) => [...nds, newNode]);
          message.success(`Created input from ${data.name}`);
        } else if (type === 'file-item') {
          // Create FileInput
          const newNode: Node = {
            id: `node-${uuidv4()}`,
            type: 'etlNode',
            position,
            data: {
              label: 'FileInputDelimited',
              type: 'FileInputDelimited',
              name: `${data.name}_input`,
              config: {
                filePath: data.path,
              },
            },
          };
          setNodes((nds) => [...nds, newNode]);
          message.success(`Created input for file: ${data.name}`);
        }
        saveToHistory();
        return;
      }

      if (dbConnectionData) {
        // Dropped a DB connection - create DatabaseInput node
        const connection: DBConnection = JSON.parse(dbConnectionData);
        const newNode: Node = {
          id: `node-${uuidv4()}`,
          type: 'etlNode',
          position,
          data: {
            label: 'DatabaseInput',
            type: 'DatabaseInput',
            name: `${connection.name}_input`,
            config: {
              connection_id: connection.id,
              connection_name: connection.name,
            },
          },
        };
        setNodes((nds) => [...nds, newNode]);
        message.success(`Created input from ${connection.name}`);
      } else if (componentType) {
        const component = components.find((c) => c.type === componentType);
        if (!component) return;

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
      }
      
      saveToHistory();
    },
    [components, setNodes, saveToHistory]
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
      // Add to saved jobs list if not already present
      setSavedJobs((prev) => {
        if (prev.some((j) => j.id === jobId)) return prev;
        return [...prev, { id: jobId, name: currentJob.name }];
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
  const handleExecute = async (mode: 'run' | 'debug') => {
    if (!jobId) return;

    // Check for errors
    const errors = validationProblems.filter((p) => p.severity === 'error');
    if (errors.length > 0) {
      message.error(`Cannot execute: ${errors.length} error(s) found. Fix them first.`);
      setBottomPanelCollapsed(false);
      return;
    }

    const saved = await handleSave();
    if (!saved) return;

    setExecuting(true);
    setBottomPanelCollapsed(false);
    setExecutionProgress(0);
    
    // Add execution start log
    const startLog: ExecutionLog = {
      id: `log-${Date.now()}`,
      timestamp: new Date().toISOString(),
      level: 'info',
      message: `Starting ${mode === 'debug' ? 'debug' : 'execution'} with context: ${selectedContext}`,
      component: 'System',
    };
    setExecutionLogs((prev) => [...prev, startLog]);

    try {
      const { startExecution, pollExecution } = useStore.getState();
      const taskId = await startExecution(jobId);

      // Simulate progress
      const progressInterval = setInterval(() => {
        setExecutionProgress((prev) => Math.min(prev + 10, 90));
      }, 500);

      const pollInterval = setInterval(async () => {
        try {
          const status = await pollExecution(taskId);
          
          // Add log for each component processed
          const componentLog: ExecutionLog = {
            id: `log-${Date.now()}`,
            timestamp: new Date().toISOString(),
            level: 'info',
            message: `Processing: ${status.status}`,
            component: 'Engine',
          };
          setExecutionLogs((prev) => [...prev, componentLog]);

          if (status.status === 'success') {
            clearInterval(pollInterval);
            clearInterval(progressInterval);
            setExecutionProgress(100);
            setExecuting(false);
            
            const successLog: ExecutionLog = {
              id: `log-${Date.now()}`,
              timestamp: new Date().toISOString(),
              level: 'info',
              message: 'Execution completed successfully!',
              component: 'System',
            };
            setExecutionLogs((prev) => [...prev, successLog]);
            message.success('Job executed successfully!');
          } else if (status.status === 'error') {
            clearInterval(pollInterval);
            clearInterval(progressInterval);
            setExecuting(false);
            
            const errorLog: ExecutionLog = {
              id: `log-${Date.now()}`,
              timestamp: new Date().toISOString(),
              level: 'error',
              message: status.error_message || 'Unknown error',
              component: 'System',
            };
            setExecutionLogs((prev) => [...prev, errorLog]);
            message.error(`Execution failed: ${status.error_message || 'Unknown error'}`);
          }
        } catch (err) {
          clearInterval(pollInterval);
          clearInterval(progressInterval);
          setExecuting(false);
        }
      }, 1000);

      setTimeout(() => {
        clearInterval(pollInterval);
        clearInterval(progressInterval);
        if (executing) {
          setExecuting(false);
          message.warning('Execution timed out');
        }
      }, 300000);
    } catch (error: any) {
      setExecuting(false);
      const errorLog: ExecutionLog = {
        id: `log-${Date.now()}`,
        timestamp: new Date().toISOString(),
        level: 'error',
        message: error.message || 'Failed to start execution',
        component: 'System',
      };
      setExecutionLogs((prev) => [...prev, errorLog]);
      message.error(`Failed to start execution: ${error.message || 'Unknown error'}`);
    }
  };

  // Stop execution
  const handleStopExecution = () => {
    setExecuting(false);
    setExecutionProgress(0);
    const stopLog: ExecutionLog = {
      id: `log-${Date.now()}`,
      timestamp: new Date().toISOString(),
      level: 'warn',
      message: 'Execution stopped by user',
      component: 'System',
    };
    setExecutionLogs((prev) => [...prev, stopLog]);
    message.info('Execution stopped');
  };

  // Update node properties
  const handleNodeUpdate = (updatedNode: Node) => {
    setNodes((nds) =>
      nds.map((n) => (n.id === updatedNode.id ? updatedNode : n))
    );
    setSelectedNode(updatedNode);
    saveToHistory();
    message.success('Configuration saved');
  };

  // Import job from JSON file
  const handleImportJob = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string;
        const jobData = JSON.parse(content);
        
        // Validate job structure
        if (!jobData.nodes || !Array.isArray(jobData.nodes)) {
          message.error('Invalid job file: missing nodes array');
          return;
        }
        if (!jobData.edges || !Array.isArray(jobData.edges)) {
          message.error('Invalid job file: missing edges array');
          return;
        }

        // Convert backend node format to React Flow nodes
        const importedNodes: Node[] = jobData.nodes.map((node: any) => ({
          id: node.id,
          type: 'etlNode',
          position: { x: node.x || 0, y: node.y || 0 },
          data: {
            type: node.type,
            label: node.label || node.type,
            name: node.label || node.type,
            config: node.config || {},
            schema: node.config?.output_schema || [],
          },
        }));

        // Convert backend edge format to React Flow edges
        const importedEdges: Edge[] = jobData.edges.map((edge: any) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          type: 'smoothstep',
          style: { stroke: '#1890ff', strokeWidth: 2 },
        }));

        // Update state
        setNodes(importedNodes);
        setEdges(importedEdges);
        saveToHistory();

        // Log success
        const importLog: ExecutionLog = {
          id: `log-${Date.now()}`,
          timestamp: new Date().toISOString(),
          level: 'info',
          message: `Imported job "${jobData.name || 'Untitled'}" with ${importedNodes.length} nodes and ${importedEdges.length} edges`,
          component: 'Import',
        };
        setExecutionLogs((prev) => [...prev, importLog]);
        
        message.success(`Job imported successfully: ${importedNodes.length} nodes, ${importedEdges.length} edges`);
      } catch (error: any) {
        console.error('Import error:', error);
        message.error(`Failed to import job: ${error.message || 'Invalid JSON'}`);
      }
    };
    reader.onerror = () => {
      message.error('Failed to read file');
    };
    reader.readAsText(file);
    
    // Prevent upload to server
    return false;
  };

  // Export job as JSON file
  const handleExportJob = () => {
    if (nodes.length === 0) {
      message.warning('No nodes to export');
      return;
    }

    // Convert React Flow format to backend format
    const exportData = {
      id: jobId || uuidv4(),
      name: currentJob?.name || 'Exported Job',
      description: currentJob?.description || '',
      nodes: nodes.map((node) => ({
        id: node.id,
        type: (node.data as any).type,
        label: (node.data as any).label || (node.data as any).name,
        x: node.position.x,
        y: node.position.y,
        config: (node.data as any).config || {},
        subjob_id: null,
        is_subjob_start: false,
      })),
      edges: edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        edge_type: 'flow',
        name: null,
        trigger_type: null,
        condition: null,
      })),
      context: {},
      java_config: { enabled: false },
      python_config: { enabled: false },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    // Create and download file
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${exportData.name.replace(/[^a-z0-9]/gi, '_')}_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    message.success('Job exported successfully');
  };

  // DB Connection handlers
  const handleCreateConnection = () => {
    setEditingConnection(undefined);
    setDbWizardOpen(true);
  };

  const handleEditConnection = (conn: any) => {
    setEditingConnection(conn as DBConnection);
    setDbWizardOpen(true);
  };

  const handleSaveConnection = (conn: DBConnection) => {
    if (editingConnection) {
      setDbConnections((prev) =>
        prev.map((c) => (c.id === conn.id ? conn : c))
      );
    } else {
      setDbConnections((prev) => [...prev, { ...conn, id: `conn-${uuidv4()}` }]);
    }
    setDbWizardOpen(false);
    message.success(`Connection ${editingConnection ? 'updated' : 'created'}`);
  };

  const handleDeleteConnection = (connId: string) => {
    setDbConnections((prev) => prev.filter((c) => c.id !== connId));
    message.success('Connection deleted');
  };

  // Context handlers
  const handleSaveContextGroups = (groups: ContextGroup[]) => {
    setContextGroups(groups);
    setContextManagerOpen(false);
    message.success('Context variables saved');
  };

  // Get input schema for node (for map editor)
  const getInputSchemaForNode = useCallback((nodeId: string): SchemaColumn[] => {
    const incomingEdges = edges.filter((e) => e.target === nodeId);
    if (incomingEdges.length === 0) return [];

    const sourceNodeIds = incomingEdges.map((e) => e.source);
    const sourceNodes = nodes.filter((n) => sourceNodeIds.includes(n.id));

    const schemas: SchemaColumn[] = [];
    sourceNodes.forEach((srcNode) => {
      const srcConfig = (srcNode.data as any).config || {};
      const srcType = (srcNode.data as any).type;

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
        schemas.push(...srcConfig.output_schema);
      } else {
        const upstreamSchema = getInputSchemaForNode(srcNode.id);
        schemas.push(...upstreamSchema);
      }
    });

    return schemas;
  }, [nodes, edges]);

  // Handle Map editor save
  const handleMapMappingsSave = useCallback((mappings: any[]) => {
    if (!selectedNode) return;

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
                  output_schema: outputSchema,
                },
              },
            }
          : n
      )
    );
    setMapEditorOpen(false);
    saveToHistory();
    message.success('Mappings saved');
  }, [selectedNode, setNodes, saveToHistory]);

  // Get selected component metadata
  const selectedComponent = useMemo(() => {
    if (!selectedNode) return null;
    return components.find((c) => c.type === (selectedNode.data as any).type);
  }, [selectedNode, components]);

  // Build repository tree data
  const repositoryData: RepositoryNode[] = useMemo(() => [
    {
      key: 'metadata',
      title: 'Metadata',
      type: 'folder',
      children: [
        {
          key: 'db-connections',
          title: 'DB Connections',
          type: 'db-folder',
          children: dbConnections.map((conn) => ({
            key: conn.id,
            title: conn.name,
            type: 'db-connection' as const,
            data: conn,
          })),
        },
        {
          key: 'file-connections',
          title: 'File Connections',
          type: 'file-folder',
          children: [],
        },
      ],
    },
    {
      key: 'job-designs',
      title: 'Job Designs',
      type: 'folder',
      children: [],
    },
    {
      key: 'contexts',
      title: 'Context Variables',
      type: 'context-folder',
      children: contextGroups.map((group) => ({
        key: group.id,
        title: group.name,
        type: 'context-group' as const,
        data: group,
      })),
    },
  ], [dbConnections, contextGroups]);

  // Error/Warning counts
  const errorCount = validationProblems.filter((p) => p.severity === 'error').length;
  const warningCount = validationProblems.filter((p) => p.severity === 'warning').length;

  return (
    <div className="job-designer-enhanced">
      {/* Header */}
      <header className="designer-header-enhanced">
        <div className="header-left">
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')} />
          <div className="job-info">
            <h2>{currentJob?.name || 'Untitled Job'}</h2>
            <span className="job-id">{jobId}</span>
          </div>
        </div>

        <div className="header-toolbar">
          <Tooltip title="Undo (Ctrl+Z)">
            <Button
              icon={<UndoOutlined />}
              onClick={handleUndo}
              disabled={historyIndex <= 0}
            />
          </Tooltip>
          <Tooltip title="Redo (Ctrl+Y)">
            <Button
              icon={<RedoOutlined />}
              onClick={handleRedo}
              disabled={historyIndex >= history.length - 1}
            />
          </Tooltip>
        </div>

        <div className="header-right">
          <Button
            className="dark-mode-toggle"
            icon={darkMode ? <span>☀️</span> : <span>🌙</span>}
            onClick={toggleDarkMode}
            size="small"
          />
          <Button
            icon={<BugOutlined />}
            onClick={() => setBottomPanelCollapsed(!bottomPanelCollapsed)}
            size="small"
            className="header-btn"
          >
            problems
          </Button>
          <Button 
            icon={<SaveOutlined />} 
            onClick={handleSave} 
            loading={saving} 
            size="small"
            className="header-btn"
          >
            save
          </Button>
          <Button
            icon={<PlayCircleOutlined />}
            onClick={() => handleExecute('run')}
            loading={executing}
            disabled={nodes.length === 0}
            className="run-btn"
            size="small"
          >
            {executing ? 'running...' : 'run'}
          </Button>
        </div>
      </header>

      {/* Main Content */}
      <div className="designer-main">
        {/* Left Panel - Talend-like Repository with Metadata */}
        <aside className={`left-panel ${leftPanelCollapsed ? 'collapsed' : ''}`}>
          <div className="panel-header">
            <span className="panel-title">
              <FolderOutlined /> Repository
            </span>
            <Button
              type="text"
              size="small"
              icon={leftPanelCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setLeftPanelCollapsed(!leftPanelCollapsed)}
            />
          </div>
          {!leftPanelCollapsed && (
            <div className="panel-content repository-panel">
              <div className="left-panel-actions">
                <Upload
                  accept=".json"
                  showUploadList={false}
                  beforeUpload={handleImportJob}
                >
                  <Button icon={<ImportOutlined />} size="small" block>
                    Import JSON
                  </Button>
                </Upload>
              </div>
              <Tree
                showIcon={false}
                className="metadata-tree-compact"
                defaultExpandedKeys={['metadata', 'job-designs']}
                onSelect={(keys, info) => {
                  const node = info.node as any;
                  if (node.action) {
                    node.action();
                  }
                }}
                onRightClick={({ event, node }: any) => {
                  event.preventDefault();
                  // Could show context menu here
                }}
                treeData={[
                  {
                    title: 'Job Designs',
                    key: 'job-designs',
                    children: savedJobs.map((job) => ({
                      title: (
                        <span
                          className="tree-node-draggable"
                          onClick={() => navigate(`/jobs/${job.id}`)}
                        >
                          {job.name}
                        </span>
                      ),
                      key: job.id,
                      isLeaf: true,
                    })),
                  },
                  {
                    title: 'Metadata',
                    key: 'metadata',
                    children: [
                      {
                        title: (
                          <span className="tree-node-with-action">
                            DB Connections
                            <Tooltip title="Create New Connection">
                              <PlusOutlined 
                                className="tree-action-icon"
                                onClick={(e) => { e.stopPropagation(); handleCreateConnection(); }}
                              />
                            </Tooltip>
                          </span>
                        ),
                        key: 'db-connections',
                        children: dbConnections.map((conn) => ({
                          title: (
                            <span 
                              className="tree-node-draggable"
                              draggable
                              onDragStart={(e) => {
                                e.dataTransfer.setData('application/db-connection', JSON.stringify(conn));
                                e.dataTransfer.effectAllowed = 'copy';
                              }}
                            >
                              {conn.name}
                              <span className="tree-node-meta">({conn.dbType || conn.type})</span>
                            </span>
                          ),
                          key: conn.id,
                          isLeaf: true,
                          action: () => handleEditConnection(conn),
                        })),
                      },
                      {
                        title: (
                          <span className="tree-node-with-action">
                            File Delimited
                            <Tooltip title="Create New Delimited Schema">
                              <PlusOutlined 
                                className="tree-action-icon"
                                onClick={(e) => { 
                                  e.stopPropagation(); 
                                  setFileMetadataType('delimited');
                                  setFileMetadataWizardOpen(true);
                                }}
                              />
                            </Tooltip>
                          </span>
                        ),
                        key: 'file-delimited',
                        children: fileMetadata
                          .filter((f) => f.type === 'delimited')
                          .map((f) => ({
                            title: (
                              <span 
                                className="tree-node-draggable"
                                draggable
                                onDragStart={(e) => {
                                  e.dataTransfer.setData('application/file-metadata', JSON.stringify(f));
                                  e.dataTransfer.effectAllowed = 'copy';
                                }}
                              >
                                {f.name}
                              </span>
                            ),
                            key: f.id,
                            isLeaf: true,
                          })),
                      },
                      {
                        title: (
                          <span className="tree-node-with-action">
                            File Excel
                            <Tooltip title="Create New Excel Schema">
                              <PlusOutlined 
                                className="tree-action-icon"
                                onClick={(e) => { 
                                  e.stopPropagation(); 
                                  setFileMetadataType('excel');
                                  setFileMetadataWizardOpen(true);
                                }}
                              />
                            </Tooltip>
                          </span>
                        ),
                        key: 'file-excel',
                        children: fileMetadata
                          .filter((f) => f.type === 'excel')
                          .map((f) => ({
                            title: f.name,
                            key: f.id,
                            isLeaf: true,
                          })),
                      },
                      {
                        title: (
                          <span className="tree-node-with-action">
                            File JSON
                            <Tooltip title="Create New JSON Schema">
                              <PlusOutlined 
                                className="tree-action-icon"
                                onClick={(e) => { 
                                  e.stopPropagation(); 
                                  setFileMetadataType('json');
                                  setFileMetadataWizardOpen(true);
                                }}
                              />
                            </Tooltip>
                          </span>
                        ),
                        key: 'file-json',
                        children: fileMetadata
                          .filter((f) => f.type === 'json')
                          .map((f) => ({
                            title: f.name,
                            key: f.id,
                            isLeaf: true,
                          })),
                      },
                      {
                        title: (
                          <span className="tree-node-with-action">
                            File XML
                            <Tooltip title="Create New XML Schema">
                              <PlusOutlined 
                                className="tree-action-icon"
                                onClick={(e) => { 
                                  e.stopPropagation(); 
                                  setFileMetadataType('xml');
                                  setFileMetadataWizardOpen(true);
                                }}
                              />
                            </Tooltip>
                          </span>
                        ),
                        key: 'file-xml',
                        children: fileMetadata
                          .filter((f) => f.type === 'xml')
                          .map((f) => ({
                            title: f.name,
                            key: f.id,
                            isLeaf: true,
                          })),
                      },
                    ],
                  },
                ]}
              />
            </div>
          )}
        </aside>

        {/* Center - Canvas Area */}
        <div className="center-area">
          <div
            className="canvas-wrapper"
            ref={reactFlowWrapper}
            onDrop={onDrop}
            onDragOver={onDragOver}
          >
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={onNodeClick}
              onPaneClick={onPaneClick}
              nodeTypes={nodeTypes}
              fitView
              snapToGrid
              snapGrid={[15, 15]}
            >
              <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
              <Controls />
              <MiniMap
                nodeStrokeWidth={3}
                zoomable
                pannable
                style={{ background: '#f0f0f0' }}
              />
              <Panel position="top-left" className="canvas-stats">
                {nodes.length} components · {edges.length} connections
                {warningCount > 0 && (
                  <span className="warning-badge"> · ⚠️ {warningCount}</span>
                )}
                {errorCount > 0 && (
                  <span className="error-badge"> · ❌ {errorCount}</span>
                )}
              </Panel>
            </ReactFlow>
          </div>

          {/* Bottom Panel - Talend-style with Component/Run/Problems tabs */}
          <div className={`bottom-panel ${bottomPanelCollapsed ? 'collapsed' : ''} ${bottomPanelExpanded ? 'expanded' : ''}`}>
            <div 
              className="panel-header" 
              onDoubleClick={() => {
                if (!bottomPanelCollapsed) {
                  setBottomPanelExpanded(!bottomPanelExpanded);
                }
              }}
            >
              <Tabs
                activeKey={bottomPanelTab}
                onChange={(key) => setBottomPanelTab(key as 'component' | 'run' | 'problems' | 'context')}
                size="small"
                items={[
                  {
                    key: 'component',
                    label: (
                      <span className="bottom-tab-label">
                        component
                        {selectedNode && <span className="tab-dot active" />}
                      </span>
                    ),
                  },
                  {
                    key: 'run',
                    label: (
                      <span className="bottom-tab-label">
                        run
                        {executing && <span className="tab-dot running" />}
                      </span>
                    ),
                  },
                  {
                    key: 'problems',
                    label: (
                      <span className="bottom-tab-label">
                        problems
                        {(errorCount + warningCount) > 0 && (
                          <span className="tab-count">{errorCount + warningCount}</span>
                        )}
                      </span>
                    ),
                  },
                  {
                    key: 'context',
                    label: (
                      <span className="bottom-tab-label">
                        context
                        <span className="tab-count green">{contextGroups.length}</span>
                      </span>
                    ),
                  },
                ]}
              />
              <Button
                type="text"
                size="small"
                onClick={() => setBottomPanelCollapsed(!bottomPanelCollapsed)}
              >
                {bottomPanelCollapsed ? '▲' : '▼'}
              </Button>
            </div>
            {!bottomPanelCollapsed && (
              <div className="panel-content bottom-panel-content">
                {bottomPanelTab === 'component' && (
                  <div className="component-properties-panel">
                    {selectedNode ? (
                      <PropertiesPanel
                        selectedNode={selectedNode}
                        component={selectedComponent || undefined}
                        dbConnections={dbConnections}
                        onNodeUpdate={handleNodeUpdate}
                        onBrowseFile={() => {}}
                      />
                    ) : (
                      <div className="no-selection">
                        <Empty 
                          image={Empty.PRESENTED_IMAGE_SIMPLE}
                          description="Select a component to view its properties"
                        />
                      </div>
                    )}
                  </div>
                )}
                {bottomPanelTab === 'run' && (
                  <ExecutionPanel
                    isRunning={executing}
                    progress={executionProgress}
                    logs={executionLogs}
                    problems={validationProblems}
                    contextGroups={contextGroups}
                    selectedContext={selectedContext}
                    onContextChange={setSelectedContext}
                    onRun={() => handleExecute('run')}
                    onDebug={() => handleExecute('debug')}
                    onStop={handleStopExecution}
                    onClearLogs={() => setExecutionLogs([])}
                    onProblemClick={(problem) => {
                      const node = nodes.find((n) => n.id === problem.nodeId);
                      if (node) {
                        setSelectedNode(node);
                        setBottomPanelTab('component');
                      }
                    }}
                  />
                )}
                {bottomPanelTab === 'problems' && (
                  <div className="problems-panel">
                    {validationProblems.length === 0 ? (
                      <div className="no-problems">
                        <Empty 
                          image={Empty.PRESENTED_IMAGE_SIMPLE}
                          description="No problems detected"
                        />
                      </div>
                    ) : (
                      <div className="problems-list">
                        {validationProblems.map((problem) => (
                          <div 
                            key={problem.id} 
                            className={`problem-item ${problem.severity}`}
                            onClick={() => {
                              const node = nodes.find((n) => n.id === problem.nodeId);
                              if (node) {
                                setSelectedNode(node);
                                setBottomPanelTab('component');
                              }
                            }}
                          >
                            <span className="problem-icon">
                              {problem.severity === 'error' ? '❌' : '⚠️'}
                            </span>
                            <span className="problem-component">[{problem.component}]</span>
                            <span className="problem-message">{problem.message}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                {bottomPanelTab === 'context' && (
                  <div className="context-panel-talend">
                    <div className="context-tabs">
                      {contextGroups.map((ctx) => (
                        <div 
                          key={ctx.id} 
                          className={`context-tab ${selectedContext === ctx.name ? 'active' : ''}`}
                          onClick={() => setSelectedContext(ctx.name)}
                        >
                          {ctx.name}
                          {ctx.isDefault && <span className="default-badge">*</span>}
                        </div>
                      ))}
                      <Button 
                        type="text" 
                        size="small" 
                        icon={<PlusOutlined />}
                        onClick={() => setContextManagerOpen(true)}
                        className="add-context-btn"
                      />
                    </div>
                    <div className="context-table-container">
                      <table className="context-variables-table">
                        <thead>
                          <tr>
                            <th style={{ width: '30%' }}>Name</th>
                            <th style={{ width: '15%' }}>Type</th>
                            <th style={{ width: '45%' }}>Value</th>
                            <th style={{ width: '10%' }}>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {contextGroups.find(c => c.name === selectedContext)?.variables.map((v) => (
                            <tr key={v.id}>
                              <td className="var-name-cell">{v.name}</td>
                              <td className="var-type-cell">{v.type}</td>
                              <td className="var-value-cell">
                                {v.type === 'password' ? '••••••' : (v.value || '')}
                              </td>
                              <td className="var-actions-cell">
                                <Button type="text" size="small" icon={<EditOutlined />} onClick={() => setContextManagerOpen(true)} />
                                <Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => {
                                  const updatedGroups = contextGroups.map(g => 
                                    g.name === selectedContext 
                                      ? { ...g, variables: g.variables.filter(vr => vr.id !== v.id) }
                                      : g
                                  );
                                  setContextGroups(updatedGroups);
                                }} />
                              </td>
                            </tr>
                          ))}
                          <tr className="add-variable-row">
                            <td colSpan={4}>
                              <Button 
                                type="dashed" 
                                size="small" 
                                icon={<PlusOutlined />}
                                onClick={() => setContextManagerOpen(true)}
                                style={{ width: '100%' }}
                              >
                                Add Variable
                              </Button>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Panel - Component Palette Only */}
        <aside className={`right-panel ${rightPanelCollapsed ? 'collapsed' : ''}`}>
          <div className="panel-header">
            <span className="panel-title">
              <AppstoreOutlined /> Palette
            </span>
            <Button
              type="text"
              size="small"
              icon={rightPanelCollapsed ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
              onClick={() => setRightPanelCollapsed(!rightPanelCollapsed)}
            />
          </div>
          {!rightPanelCollapsed && (
            <div className="panel-content">
              <EnhancedComponentPalette components={components} />
            </div>
          )}
        </aside>
      </div>

      {/* DB Connection Wizard */}
      <DBConnectionWizard
        visible={dbWizardOpen}
        connection={editingConnection}
        onSave={handleSaveConnection}
        onCancel={() => setDbWizardOpen(false)}
      />

      {/* Context Variables Manager */}
      <ContextVariablesManager
        visible={contextManagerOpen}
        contextGroups={contextGroups}
        onSave={handleSaveContextGroups}
        onCancel={() => setContextManagerOpen(false)}
      />

      {/* Map Editor Modal */}
      <Modal
        title={`🔀 Map Editor - ${selectedNode ? (selectedNode.data as any).name || (selectedNode.data as any).label : ''}`}
        open={mapEditorOpen}
        onCancel={() => setMapEditorOpen(false)}
        footer={null}
        width="70%"
        style={{ top: 40 }}
        styles={{ body: { height: 'calc(100vh - 200px)', padding: 0, overflow: 'hidden' } }}
        destroyOnClose
        className="map-editor-modal"
      >
        {selectedNode && (
          <MapEditor
            inputSchema={getInputSchemaForNode(selectedNode.id)}
            outputMappings={(selectedNode.data as any).config?.mappings || []}
            onSave={handleMapMappingsSave}
          />
        )}
      </Modal>

      {/* File Metadata Wizard */}
      <FileMetadataWizard
        visible={fileMetadataWizardOpen}
        fileType={fileMetadataType}
        onSave={(metadata) => {
          setFileMetadata((prev) => [...prev, metadata]);
        }}
        onCancel={() => setFileMetadataWizardOpen(false)}
      />
    </div>
  );
}
