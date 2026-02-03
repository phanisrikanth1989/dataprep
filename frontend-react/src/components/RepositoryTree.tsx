import { useState, useMemo, useCallback } from 'react';
import { Tree, Input, Dropdown, Modal, message, Tooltip, Empty } from 'antd';
import type { MenuProps } from 'antd';
import {
  DatabaseOutlined,
  FileTextOutlined,
  FolderOutlined,
  FolderOpenOutlined,
  TableOutlined,
  SettingOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
  SearchOutlined,
  BranchesOutlined,
} from '@ant-design/icons';
import type { DataNode, EventDataNode } from 'antd/es/tree';
import './RepositoryTree.css';

// Types
interface DBConnection {
  id: string;
  name: string;
  dbType?: string;
  type?: string;
  host: string;
  port: number;
  database: string;
  username: string;
  status?: string;
  schemas?: Array<{
    name: string;
    tables: Array<{ name: string }>;
  }>;
}

interface ContextGroup {
  id: string;
  name: string;
  isDefault?: boolean;
  variables: Array<{
    id: string;
    name: string;
    value: string;
    type: string;
  }>;
}

interface JobListItem {
  id: string;
  name: string;
  description?: string;
}

interface Props {
  dbConnections: DBConnection[];
  contextGroups: ContextGroup[];
  jobs: JobListItem[];
  onCreateConnection: () => void;
  onEditConnection: (connection: DBConnection) => void;
  onTestConnection?: (connection: DBConnection) => void;
  onDeleteConnection: (connectionId: string) => void;
  onRetrieveSchema?: (connection: DBConnection) => void;
  onCreateJob: () => void;
  onOpenJob: (jobId: string) => void;
  onDeleteJob?: (jobId: string) => void;
  onDuplicateJob?: (jobId: string) => void;
  onExportJob?: (jobId: string) => void;
  onCreateContext?: () => void;
  onEditContext?: (context: ContextGroup) => void;
  onDeleteContext?: (contextId: string) => void;
  onDragStart?: (nodeType: string, data: any) => void;
}

// Extended DataNode type
interface TreeDataNode extends DataNode {
  nodeType?: string;
  data?: any;
  children?: TreeDataNode[];
}

// Icons for different node types
const getIcon = (type: string, expanded?: boolean) => {
  switch (type) {
    case 'db-connections':
      return expanded ? <FolderOpenOutlined style={{ color: '#faad14' }} /> : <FolderOutlined style={{ color: '#faad14' }} />;
    case 'db-connection':
      return <DatabaseOutlined style={{ color: '#52c41a' }} />;
    case 'db-table':
      return <TableOutlined style={{ color: '#1890ff' }} />;
    case 'context-variables':
      return <SettingOutlined style={{ color: '#fa541c' }} />;
    case 'context-group':
      return <BranchesOutlined style={{ color: '#52c41a' }} />;
    case 'job-designs':
      return expanded ? <FolderOpenOutlined style={{ color: '#1890ff' }} /> : <FolderOutlined style={{ color: '#1890ff' }} />;
    case 'job-item':
      return <FileTextOutlined style={{ color: '#1890ff' }} />;
    default:
      return <FolderOutlined />;
  }
};

export default function RepositoryTree({
  dbConnections,
  contextGroups,
  jobs,
  onCreateConnection,
  onEditConnection,
  onTestConnection,
  onDeleteConnection,
  onRetrieveSchema,
  onCreateJob,
  onOpenJob,
  onDeleteJob,
  onDuplicateJob,
  onExportJob,
  onCreateContext,
  onEditContext,
  onDeleteContext,
  onDragStart,
}: Props) {
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>(['metadata', 'db-connections', 'contexts', 'jobs']);
  const [searchValue, setSearchValue] = useState('');
  const [contextMenuNode, setContextMenuNode] = useState<TreeDataNode | null>(null);
  const [contextMenuPosition, setContextMenuPosition] = useState({ x: 0, y: 0 });
  const [contextMenuOpen, setContextMenuOpen] = useState(false);

  // Build tree data
  const treeData: TreeDataNode[] = useMemo(() => [
    {
      key: 'metadata',
      title: 'Metadata',
      icon: <DatabaseOutlined style={{ color: '#722ed1' }} />,
      nodeType: 'metadata',
      selectable: false,
      children: [
        {
          key: 'db-connections',
          title: `DB Connections (${dbConnections.length})`,
          icon: getIcon('db-connections', expandedKeys.includes('db-connections')),
          nodeType: 'db-connections',
          selectable: false,
          children: dbConnections.map((conn) => ({
            key: conn.id,
            title: conn.name,
            icon: getIcon('db-connection'),
            nodeType: 'db-connection',
            data: conn,
            isLeaf: !(conn.schemas && conn.schemas.length > 0),
            children: conn.schemas?.map((schema) => ({
              key: `${conn.id}-${schema.name}`,
              title: schema.name,
              nodeType: 'db-schema',
              children: schema.tables.map((table) => ({
                key: `${conn.id}-${schema.name}-${table.name}`,
                title: table.name,
                icon: getIcon('db-table'),
                nodeType: 'db-table',
                data: { ...table, connectionId: conn.id, schema: schema.name },
                isLeaf: true,
              })),
            })),
          })),
        },
      ],
    },
    {
      key: 'contexts',
      title: 'Context Variables',
      icon: getIcon('context-variables', expandedKeys.includes('contexts')),
      nodeType: 'context-variables',
      selectable: false,
      children: contextGroups.map((group) => ({
        key: group.id,
        title: `${group.name}${group.isDefault ? ' (Default)' : ''}`,
        icon: getIcon('context-group'),
        nodeType: 'context-group',
        data: group,
        isLeaf: true,
      })),
    },
    {
      key: 'jobs',
      title: `Job Designs (${jobs.length})`,
      icon: getIcon('job-designs', expandedKeys.includes('jobs')),
      nodeType: 'job-designs',
      selectable: false,
      children: jobs.map((job) => ({
        key: job.id,
        title: job.name,
        icon: getIcon('job-item'),
        nodeType: 'job-item',
        data: job,
        isLeaf: true,
      })),
    },
  ], [dbConnections, contextGroups, jobs, expandedKeys]);

  // Handle right-click
  const handleRightClick = useCallback(
    ({ event, node }: { event: React.MouseEvent; node: EventDataNode<TreeDataNode> }) => {
      event.preventDefault();
      event.stopPropagation();
      setContextMenuNode(node as TreeDataNode);
      setContextMenuPosition({ x: event.clientX, y: event.clientY });
      setContextMenuOpen(true);
    },
    []
  );

  // Build context menu
  const contextMenuItems = useMemo((): MenuProps['items'] => {
    if (!contextMenuNode) return [];
    const nodeType = contextMenuNode.nodeType;
    const nodeData = contextMenuNode.data;

    switch (nodeType) {
      case 'db-connections':
        return [
          { key: 'create', label: 'Create Connection', icon: <PlusOutlined />, onClick: () => onCreateConnection() },
        ];
      case 'db-connection':
        return [
          { key: 'edit', label: 'Edit Connection', icon: <EditOutlined />, onClick: () => onEditConnection(nodeData) },
          { key: 'test', label: 'Test Connection', icon: <ReloadOutlined />, onClick: () => onTestConnection?.(nodeData) },
          { key: 'schema', label: 'Retrieve Schema', icon: <TableOutlined />, onClick: () => onRetrieveSchema?.(nodeData) },
          { type: 'divider' },
          { key: 'delete', label: 'Delete', icon: <DeleteOutlined />, danger: true, onClick: () => onDeleteConnection(nodeData.id) },
        ];
      case 'context-variables':
        return [
          { key: 'create', label: 'Create Context Group', icon: <PlusOutlined />, onClick: () => onCreateContext?.() },
        ];
      case 'context-group':
        return [
          { key: 'edit', label: 'Edit Context', icon: <EditOutlined />, onClick: () => onEditContext?.(nodeData) },
          { type: 'divider' },
          { key: 'delete', label: 'Delete', icon: <DeleteOutlined />, danger: true, onClick: () => onDeleteContext?.(nodeData.id) },
        ];
      case 'job-designs':
        return [
          { key: 'create', label: 'Create Job', icon: <PlusOutlined />, onClick: () => onCreateJob() },
        ];
      case 'job-item':
        return [
          { key: 'open', label: 'Open Job', icon: <EditOutlined />, onClick: () => onOpenJob(nodeData.id) },
          { key: 'duplicate', label: 'Duplicate', icon: <PlusOutlined />, onClick: () => onDuplicateJob?.(nodeData.id) },
          { key: 'export', label: 'Export', onClick: () => onExportJob?.(nodeData.id) },
          { type: 'divider' },
          { key: 'delete', label: 'Delete', icon: <DeleteOutlined />, danger: true, onClick: () => onDeleteJob?.(nodeData.id) },
        ];
      default:
        return [];
    }
  }, [contextMenuNode, onCreateConnection, onEditConnection, onTestConnection, onDeleteConnection, 
      onRetrieveSchema, onCreateContext, onEditContext, onDeleteContext, onCreateJob, onOpenJob,
      onDeleteJob, onDuplicateJob, onExportJob]);

  // Handle drag start
  const handleDragStart = useCallback(
    (info: { event: React.DragEvent; node: EventDataNode<DataNode> }) => {
      const node = info.node as TreeDataNode;
      const nodeType = node.nodeType;
      const nodeData = node.data;

      if (nodeType && ['db-table', 'db-connection', 'file-item'].includes(nodeType)) {
        info.event.dataTransfer.setData('repository-item', JSON.stringify({ type: nodeType, data: nodeData }));
        onDragStart?.(nodeType, nodeData);
      }
    },
    [onDragStart]
  );

  // Handle double-click
  const handleDoubleClick = useCallback(
    (e: React.MouseEvent, node: TreeDataNode) => {
      if (node.nodeType === 'job-item' && node.data) {
        onOpenJob(node.data.id);
      } else if (node.nodeType === 'db-connection' && node.data) {
        onEditConnection(node.data);
      }
    },
    [onOpenJob, onEditConnection]
  );

  return (
    <div className="repository-tree">
      <div className="repository-header">
        <span className="header-title">Repository</span>
      </div>

      <div className="repository-search">
        <Input
          placeholder="Search..."
          prefix={<SearchOutlined />}
          value={searchValue}
          onChange={(e) => setSearchValue(e.target.value)}
          allowClear
          size="small"
        />
      </div>

      <div className="repository-content">
        {treeData.length === 0 ? (
          <Empty description="No items" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <Dropdown
            menu={{ items: contextMenuItems }}
            trigger={['contextMenu']}
            open={contextMenuOpen}
            onOpenChange={(open) => setContextMenuOpen(open)}
          >
            <div>
              <Tree
                showIcon
                draggable
                blockNode
                treeData={treeData}
                expandedKeys={expandedKeys}
                onExpand={(keys) => setExpandedKeys(keys)}
                onRightClick={handleRightClick}
                onDragStart={handleDragStart}
                onDoubleClick={(e, node) => handleDoubleClick(e, node as TreeDataNode)}
                titleRender={(nodeData) => {
                  const node = nodeData as TreeDataNode;
                  return (
                    <Tooltip title={node.nodeType === 'db-connection' ? `${node.data?.host}:${node.data?.port}` : undefined}>
                      <span className="tree-node-title">{String(node.title)}</span>
                    </Tooltip>
                  );
                }}
              />
            </div>
          </Dropdown>
        )}
      </div>
    </div>
  );
}
