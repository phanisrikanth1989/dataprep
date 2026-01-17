/**
 * Type definitions for RecDataPrep
 * Migrated from React frontend
 */

// Component and Job related types
export interface JobNode {
  id: string;
  type: string;              // Component type
  label: string;
  x: number;                 // Canvas position
  y: number;
  config: Record<string, any>;
  subjob_id?: string;
  is_subjob_start?: boolean;
}

export interface JobEdge {
  id: string;
  source: string;            // Source node ID
  target: string;            // Target node ID
  edge_type: string;         // "main", "reject", "trigger"
  name?: string;
  trigger_type?: string;
  condition?: string;
}

export interface JobSchema {
  id: string;
  name: string;
  description?: string;
  version?: string;
  nodes: JobNode[];
  edges: JobEdge[];
  context: Record<string, any>;
  java_config: Record<string, any>;
  python_config: Record<string, any>;
  created_at?: string;
  updated_at?: string;
}

export interface ComponentField {
  name: string;
  type: 'text' | 'number' | 'boolean' | 'select' | 'expression' | 'array';
  label: string;
  description?: string;
  default?: any;
  required?: boolean;
  options?: string[];
  placeholder?: string;
}

export interface ComponentMetadata {
  type: string;
  label: string;
  category: string;
  icon: string;
  description: string;
  fields: ComponentField[];
  input_count: number;
  output_count: number;
  allow_multiple_inputs?: boolean;
}

// Execution related types
export interface ExecutionStatus {
  task_id: string;
  job_id: string;
  status: 'pending' | 'running' | 'success' | 'error';
  progress: number;          // 0-100
  started_at: string;
  completed_at?: string;
  error_message?: string;
  logs: string[];
  stats?: Record<string, any>;
}

export interface ExecutionUpdate {
  task_id: string;
  job_id: string;
  status: string;
  progress: number;
  logs: string[];
  stats?: Record<string, any>;
  error_message?: string;
}

export interface ExecutionRequest {
  job_id: string;
  context_overrides?: Record<string, any>;
}

export interface ExecutionResponse {
  task_id: string;
  job_id: string;
  status: string;
}

// API Response types
export interface JobListResponse {
  id: string;
  name: string;
  description?: string;
  node_count: number;
  edge_count: number;
  created_at: string;
  updated_at: string;
}

export interface ComponentsResponse extends ComponentMetadata {}

export interface ApiErrorResponse {
  detail: string;
}
