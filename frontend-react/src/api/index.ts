import axios from 'axios';
import type { JobSchema, JobListItem, ComponentMetadata, ExecutionStatus } from '../types';
import type { DBConnection, ContextGroup } from '../types/repository';

const API_BASE = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Job APIs
export const jobApi = {
  list: () => api.get<JobListItem[]>('/jobs').then(r => r.data),
  get: (id: string) => api.get<JobSchema>(`/jobs/${id}`).then(r => r.data),
  create: (job: JobSchema) => api.post<JobSchema>('/jobs', job).then(r => r.data),
  update: (id: string, job: JobSchema) => api.put<JobSchema>(`/jobs/${id}`, job).then(r => r.data),
  delete: (id: string) => api.delete(`/jobs/${id}`).then(r => r.data),
  export: (id: string) => api.get(`/jobs/${id}/export`).then(r => r.data),
};

// Component APIs
export const componentApi = {
  list: () => api.get<ComponentMetadata[]>('/components').then(r => r.data),
  get: (type: string) => api.get<ComponentMetadata>(`/components/${type}`).then(r => r.data),
};

// Execution APIs
export const executionApi = {
  start: (jobId: string, contextOverrides?: Record<string, any>) =>
    api.post<{ task_id: string; job_id: string; status: string }>('/execution/start', {
      job_id: jobId,
      context_overrides: contextOverrides,
    }).then(r => r.data),
  getStatus: (taskId: string) => api.get<ExecutionStatus>(`/execution/${taskId}`).then(r => r.data),
  stop: (taskId: string) => api.post(`/execution/${taskId}/stop`).then(r => r.data),
};

// DB Connection APIs
export const connectionApi = {
  list: () => api.get<DBConnection[]>('/connections').then(r => r.data),
  get: (id: string) => api.get<DBConnection>(`/connections/${id}`).then(r => r.data),
  create: (connection: DBConnection) => api.post<DBConnection>('/connections', connection).then(r => r.data),
  update: (id: string, connection: DBConnection) => api.put<DBConnection>(`/connections/${id}`, connection).then(r => r.data),
  delete: (id: string) => api.delete(`/connections/${id}`).then(r => r.data),
  test: (params: {
    type: string;
    host: string;
    port: number;
    database: string;
    username: string;
    password: string;
    ssl?: boolean;
  }) => api.post<{ success: boolean; message: string; version?: string }>('/connections/test', params).then(r => r.data),
  retrieveSchema: (params: {
    type: string;
    host: string;
    port: number;
    database: string;
    username: string;
    password: string;
    ssl?: boolean;
  }) => api.post<{ success: boolean; schemas: any[]; message?: string }>('/connections/schema', params).then(r => r.data),
};

// Context APIs
export const contextApi = {
  list: () => api.get<ContextGroup[]>('/contexts').then(r => r.data),
  get: (id: string) => api.get<ContextGroup>(`/contexts/${id}`).then(r => r.data),
  create: (context: ContextGroup) => api.post<ContextGroup>('/contexts', context).then(r => r.data),
  update: (id: string, context: ContextGroup) => api.put<ContextGroup>(`/contexts/${id}`, context).then(r => r.data),
  delete: (id: string) => api.delete(`/contexts/${id}`).then(r => r.data),
  updateAll: (contexts: ContextGroup[]) => api.put<ContextGroup[]>('/contexts', contexts).then(r => r.data),
};

// Health check
export const healthCheck = () => api.get('/health').then(r => r.data);

export default api;
