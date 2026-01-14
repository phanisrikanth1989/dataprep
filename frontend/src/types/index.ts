export interface JobNode {
  id: string;
  type: string;
  label: string;
  x: number;
  y: number;
  config: Record<string, any>;
  subjob_id?: string;
  is_subjob_start?: boolean;
}

export interface JobEdge {
  id: string;
  source: string;
  target: string;
  edge_type: string;
  name?: string;
  trigger_type?: string;
  condition?: string;
}

export interface JobSchema {
  id: string;
  name: string;
  description?: string;
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
  allow_multiple_inputs: boolean;
}

export interface ExecutionStatus {
  task_id: string;
  job_id: string;
  status: 'pending' | 'running' | 'success' | 'error';
  progress: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  stats: Record<string, any>;
}

export interface ExecutionUpdate {
  type: 'progress' | 'stats' | 'log' | 'complete' | 'error';
  task_id: string;
  data: Record<string, any>;
  message?: string;
  timestamp: string;
}
