import { create } from 'zustand';
import type { JobSchema, JobListItem, ComponentMetadata, ExecutionStatus } from '../types';
import { jobApi, componentApi, executionApi } from '../api';

interface AppState {
  // Jobs
  jobs: JobListItem[];
  currentJob: JobSchema | null;
  jobsLoading: boolean;
  
  // Components
  components: ComponentMetadata[];
  componentsLoading: boolean;
  
  // Execution
  executionStatus: ExecutionStatus | null;
  isExecuting: boolean;
  
  // Auth (simple)
  isAuthenticated: boolean;
  username: string | null;
  
  // Actions
  loadJobs: () => Promise<void>;
  loadJob: (id: string) => Promise<JobSchema>;
  createJob: (job: JobSchema) => Promise<JobSchema>;
  updateJob: (id: string, job: JobSchema) => Promise<JobSchema>;
  deleteJob: (id: string) => Promise<void>;
  setCurrentJob: (job: JobSchema | null) => void;
  
  loadComponents: () => Promise<void>;
  
  startExecution: (jobId: string) => Promise<string>;
  pollExecution: (taskId: string) => Promise<ExecutionStatus>;
  stopExecution: (taskId: string) => Promise<void>;
  
  login: (username: string, password: string) => boolean;
  logout: () => void;
}

export const useStore = create<AppState>((set, get) => ({
  // Initial state
  jobs: [],
  currentJob: null,
  jobsLoading: false,
  components: [],
  componentsLoading: false,
  executionStatus: null,
  isExecuting: false,
  isAuthenticated: localStorage.getItem('auth') === 'true',
  username: localStorage.getItem('username'),

  // Job actions
  loadJobs: async () => {
    set({ jobsLoading: true });
    try {
      const jobs = await jobApi.list();
      set({ jobs, jobsLoading: false });
    } catch (error) {
      console.error('Failed to load jobs:', error);
      set({ jobsLoading: false });
    }
  },

  loadJob: async (id: string) => {
    const job = await jobApi.get(id);
    set({ currentJob: job });
    return job;
  },

  createJob: async (job: JobSchema) => {
    const created = await jobApi.create(job);
    get().loadJobs();
    return created;
  },

  updateJob: async (id: string, job: JobSchema) => {
    const updated = await jobApi.update(id, job);
    set({ currentJob: updated });
    get().loadJobs();
    return updated;
  },

  deleteJob: async (id: string) => {
    await jobApi.delete(id);
    get().loadJobs();
  },

  setCurrentJob: (job) => set({ currentJob: job }),

  // Component actions
  loadComponents: async () => {
    set({ componentsLoading: true });
    try {
      const components = await componentApi.list();
      set({ components, componentsLoading: false });
    } catch (error) {
      console.error('Failed to load components:', error);
      set({ componentsLoading: false });
    }
  },

  // Execution actions
  startExecution: async (jobId: string) => {
    set({ isExecuting: true });
    const result = await executionApi.start(jobId);
    return result.task_id;
  },

  pollExecution: async (taskId: string) => {
    const status = await executionApi.getStatus(taskId);
    set({ executionStatus: status });
    if (status.status === 'success' || status.status === 'error') {
      set({ isExecuting: false });
    }
    return status;
  },

  stopExecution: async (taskId: string) => {
    await executionApi.stop(taskId);
    set({ isExecuting: false });
  },

  // Auth actions
  login: (username: string, password: string) => {
    if (username === 'admin' && password === 'admin123') {
      localStorage.setItem('auth', 'true');
      localStorage.setItem('username', username);
      set({ isAuthenticated: true, username });
      return true;
    }
    return false;
  },

  logout: () => {
    localStorage.removeItem('auth');
    localStorage.removeItem('username');
    set({ isAuthenticated: false, username: null });
  },
}));
