import axios, { AxiosInstance } from 'axios';
import { JobSchema, ExecutionStatus, ComponentMetadata } from '../types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Job API
export const jobsAPI = {
  list: () => api.get('/jobs'),
  get: (id: string) => api.get(`/jobs/${id}`),
  create: (data: JobSchema) => api.post('/jobs', data),
  update: (id: string, data: JobSchema) => api.put(`/jobs/${id}`, data),
  delete: (id: string) => api.delete(`/jobs/${id}`),
  export: (id: string) => api.get(`/jobs/${id}/export`),
};

// Component API
export const componentsAPI = {
  list: () => api.get('/components'),
  get: (type: string): Promise<{ data: ComponentMetadata }> => api.get(`/components/${type}`),
};

// Execution API
export const executionAPI = {
  start: (jobId: string, contextOverrides?: Record<string, any>) =>
    api.post('/execution/start', {
      job_id: jobId,
      context_overrides: contextOverrides,
    }),
  getStatus: (taskId: string): Promise<{ data: ExecutionStatus }> =>
    api.get(`/execution/${taskId}`),
  stop: (taskId: string) => api.post(`/execution/${taskId}/stop`),
};

export default api;
