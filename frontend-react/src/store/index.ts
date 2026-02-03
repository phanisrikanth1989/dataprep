import { create } from 'zustand';
import type { JobSchema, JobListItem, ComponentMetadata, ExecutionStatus } from '../types';
import type { DBConnection, ContextGroup, ExecutionLog, ValidationProblem } from '../types/repository';
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
  
  // NEW: DB Connections
  dbConnections: DBConnection[];
  dbConnectionsLoading: boolean;
  
  // NEW: Context Groups
  contextGroups: ContextGroup[];
  selectedContext: string;
  
  // NEW: Execution Logs & Problems
  executionLogs: ExecutionLog[];
  validationProblems: ValidationProblem[];
  
  // NEW: UI State
  selectedNodeId: string | null;
  darkMode: boolean;
  
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
  
  // NEW: DB Connection Actions
  addDbConnection: (connection: DBConnection) => void;
  updateDbConnection: (id: string, connection: DBConnection) => void;
  deleteDbConnection: (id: string) => void;
  
  // NEW: Context Actions
  setContextGroups: (groups: ContextGroup[]) => void;
  setSelectedContext: (contextName: string) => void;
  
  // NEW: Logging Actions
  addExecutionLog: (log: ExecutionLog) => void;
  clearExecutionLogs: () => void;
  setValidationProblems: (problems: ValidationProblem[]) => void;
  
  // NEW: UI Actions
  setSelectedNodeId: (nodeId: string | null) => void;
  toggleDarkMode: () => void;
}

export const useStore = create<AppState>((set, get) => ({
  // Initial state
  jobs: [],
  currentJob: null,
  jobsLoading: false,
  components: [],
  componentsLoading: false,
  darkMode: localStorage.getItem('darkMode') === 'true',
  executionStatus: null,
  isExecuting: false,
  isAuthenticated: localStorage.getItem('auth') === 'true',
  username: localStorage.getItem('username'),
  
  // NEW: Initial state for DB Connections
  dbConnections: [],
  dbConnectionsLoading: false,
  
  // NEW: Initial state for Context Groups
  contextGroups: [
    { id: 'ctx-dev', name: 'DEV', variables: [], isDefault: true },
    { id: 'ctx-qa', name: 'QA', variables: [], isDefault: false },
    { id: 'ctx-prod', name: 'PROD', variables: [], isDefault: false },
  ],
  selectedContext: 'DEV',
  
  // NEW: Initial state for logs/problems
  executionLogs: [],
  validationProblems: [],
  
  // NEW: UI State
  selectedNodeId: null,

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
  
  // NEW: DB Connection Actions
  addDbConnection: (connection: DBConnection) => {
    set((state) => ({
      dbConnections: [...state.dbConnections, connection],
    }));
  },

  updateDbConnection: (id: string, connection: DBConnection) => {
    set((state) => ({
      dbConnections: state.dbConnections.map((c) =>
        c.id === id ? connection : c
      ),
    }));
  },

  deleteDbConnection: (id: string) => {
    set((state) => ({
      dbConnections: state.dbConnections.filter((c) => c.id !== id),
    }));
  },

  // NEW: Context Actions
  setContextGroups: (groups: ContextGroup[]) => {
    set({ contextGroups: groups });
  },

  setSelectedContext: (contextName: string) => {
    set({ selectedContext: contextName });
  },

  // NEW: Logging Actions
  addExecutionLog: (log: ExecutionLog) => {
    set((state) => ({
      executionLogs: [...state.executionLogs, log],
    }));
  },

  clearExecutionLogs: () => {
    set({ executionLogs: [] });
  },

  setValidationProblems: (problems: ValidationProblem[]) => {
    set({ validationProblems: problems });
  },

  // NEW: UI Actions
  setSelectedNodeId: (nodeId: string | null) => {
    set({ selectedNodeId: nodeId });
  },

  toggleDarkMode: () => {
    const newValue = !get().darkMode;
    localStorage.setItem('darkMode', String(newValue));
    set({ darkMode: newValue });
  },
}));
