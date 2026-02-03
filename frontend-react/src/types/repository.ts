/**
 * Repository and Metadata Type Definitions
 * Talend-like repository structure
 */

// Database Connection Types
export interface DBConnection {
  id: string;
  name: string;
  dbType: 'oracle' | 'postgres' | 'mysql' | 'sqlserver' | 'db2' | 'sqlite' | string;
  type?: string; // Alias for dbType for compatibility
  host: string;
  port: number;
  database: string;
  serviceName?: string; // For Oracle
  username: string;
  password?: string;
  ssl?: boolean;
  sslMode?: string;
  connectionTimeout?: number;
  fetchSize?: number;
  autoCommit?: boolean;
  readOnly?: boolean;
  driverClass?: string;
  jdbcUrl?: string;
  status?: 'connected' | 'disconnected' | 'error';
  lastTested?: string;
  createdAt?: string;
  updatedAt?: string;
  schemas?: DBSchema[];
}

export interface DBSchema {
  name: string;
  tables: DBTable[];
}

export interface DBTable {
  name: string;
  schema: string;
  type: 'TABLE' | 'VIEW';
  rowCount?: number;
  columns: DBColumn[];
}

export interface DBColumn {
  name: string;
  type: string;
  nullable: boolean;
  primaryKey: boolean;
  length?: number;
  precision?: number;
  scale?: number;
  defaultValue?: string;
  comment?: string;
}

// File Metadata Types
export interface FileMetadata {
  id: string;
  name: string;
  type: 'delimited' | 'excel' | 'json' | 'xml';
  path: string;
  schema: FileSchemaColumn[];
  settings: Record<string, any>;
  createdAt: string;
  updatedAt: string;
}

export interface FileSchemaColumn {
  name: string;
  type: string;
  length?: number;
  pattern?: string;
  nullable: boolean;
  defaultValue?: string;
}

// Context Variables
export interface ContextGroup {
  id: string;
  name: string;
  description?: string;
  isDefault: boolean;
  variables: ContextVariable[];
  createdAt?: string;
  updatedAt?: string;
}

export interface ContextVariable {
  id: string;
  name: string;
  type: 'string' | 'integer' | 'boolean' | 'password' | 'date' | 'file';
  value: string;
  description?: string;
  promptAtRun?: boolean;
}

// Repository Tree Types
export interface RepositoryNode {
  key: string;
  title: string;
  icon?: React.ReactNode;
  type: RepositoryNodeType;
  children?: RepositoryNode[];
  data?: any;
  isLeaf?: boolean;
  selectable?: boolean;
}

export type RepositoryNodeType =
  | 'root'
  | 'folder'
  | 'metadata'
  | 'db-connections'
  | 'db-connection'
  | 'db-folder'
  | 'db-schema'
  | 'db-table'
  | 'file-folder'
  | 'file-delimited'
  | 'file-excel'
  | 'file-json'
  | 'file-xml'
  | 'file-item'
  | 'rest-soap'
  | 'ftp-sftp'
  | 'context-folder'
  | 'context-variables'
  | 'context-group'
  | 'job-designs'
  | 'standard-jobs'
  | 'joblets'
  | 'job-item'
  | 'documentation'
  | 'routines';

// Context Menu Actions
export interface ContextMenuAction {
  key: string;
  label: string;
  icon?: React.ReactNode;
  danger?: boolean;
  disabled?: boolean;
  children?: ContextMenuAction[];
  onClick?: () => void;
}

// Job Designs
export interface JobFolder {
  id: string;
  name: string;
  parentId?: string;
  jobs: string[];
  subfolders: JobFolder[];
}

// Execution Types
export interface ExecutionLog {
  id: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'debug' | 'INFO' | 'WARN' | 'ERROR' | 'DEBUG';
  component?: string;
  message: string;
  details?: string;
}

export interface ValidationProblem {
  id: string;
  severity: 'error' | 'warning' | 'info';
  component?: string;
  field?: string;
  message: string;
  suggestion?: string;
  nodeId?: string;
}

// Subjob Types
export interface Subjob {
  id: string;
  name: string;
  nodeIds: string[];
  color?: string;
  collapsed?: boolean;
}

// Connection Types (for edges)
export type ConnectionType = 'row' | 'main' | 'lookup' | 'reject' | 'trigger' | 'onSubjobOk' | 'onComponentOk' | 'onComponentError' | 'iterate';

export interface ConnectionTypeOption {
  type: ConnectionType;
  label: string;
  color: string;
  animated: boolean;
  description: string;
}

export const CONNECTION_TYPES: ConnectionTypeOption[] = [
  { type: 'main', label: 'Main (Row)', color: '#1890ff', animated: false, description: 'Main data flow' },
  { type: 'lookup', label: 'Lookup', color: '#52c41a', animated: false, description: 'Lookup data flow' },
  { type: 'reject', label: 'Reject', color: '#ff4d4f', animated: false, description: 'Rejected rows' },
  { type: 'onSubjobOk', label: 'On Subjob Ok', color: '#722ed1', animated: true, description: 'Trigger when subjob completes successfully' },
  { type: 'onComponentOk', label: 'On Component Ok', color: '#13c2c2', animated: true, description: 'Trigger when component completes successfully' },
  { type: 'onComponentError', label: 'On Component Error', color: '#fa541c', animated: true, description: 'Trigger when component fails' },
  { type: 'iterate', label: 'Iterate', color: '#eb2f96', animated: true, description: 'Loop iteration' },
];

// Default DB ports
export const DEFAULT_DB_PORTS: Record<string, number> = {
  oracle: 1521,
  postgres: 5432,
  mysql: 3306,
  sqlserver: 1433,
  db2: 50000,
  sqlite: 0,
};
