import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  JobSchema,
  JobListResponse,
  ComponentMetadata,
  ExecutionRequest,
  ExecutionResponse,
  ExecutionStatus,
} from '../models/types';

/**
 * API Service - Handles all REST API communication with backend
 * Integrates with: backend/app/routes/jobs.py, components.py, execution.py
 */
@Injectable({
  providedIn: 'root',
})
export class ApiService {
  private apiUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  // ============================================================
  // JOB MANAGEMENT APIs
  // ============================================================

  /**
   * GET /api/jobs - List all jobs
   */
  listJobs(): Observable<JobListResponse[]> {
    return this.http.get<JobListResponse[]>(`${this.apiUrl}/jobs`);
  }

  /**
   * GET /api/jobs/{id} - Get job details
   */
  getJob(jobId: string): Observable<JobSchema> {
    return this.http.get<JobSchema>(`${this.apiUrl}/jobs/${jobId}`);
  }

  /**
   * POST /api/jobs - Create new job
   */
  createJob(job: JobSchema): Observable<JobSchema> {
    return this.http.post<JobSchema>(`${this.apiUrl}/jobs`, job);
  }

  /**
   * PUT /api/jobs/{id} - Update job
   */
  updateJob(jobId: string, job: JobSchema): Observable<JobSchema> {
    return this.http.put<JobSchema>(`${this.apiUrl}/jobs/${jobId}`, job);
  }

  /**
   * DELETE /api/jobs/{id} - Delete job
   */
  deleteJob(jobId: string): Observable<any> {
    return this.http.delete(`${this.apiUrl}/jobs/${jobId}`);
  }

  /**
   * GET /api/jobs/{id}/export - Export job config for engine
   */
  exportJob(jobId: string): Observable<any> {
    return this.http.get(`${this.apiUrl}/jobs/${jobId}/export`);
  }

  // ============================================================
  // COMPONENT APIs
  // ============================================================

  /**
   * GET /api/components - List all available components
   */
  listComponents(): Observable<ComponentMetadata[]> {
    return this.http.get<ComponentMetadata[]>(`${this.apiUrl}/components`);
  }

  /**
   * GET /api/components/{type} - Get component metadata
   */
  getComponent(type: string): Observable<ComponentMetadata> {
    return this.http.get<ComponentMetadata>(`${this.apiUrl}/components/${type}`);
  }

  // ============================================================
  // EXECUTION APIs
  // ============================================================

  /**
   * POST /api/execution/start - Start job execution
   */
  startExecution(
    jobId: string,
    contextOverrides?: Record<string, any>
  ): Observable<ExecutionResponse> {
    const request: ExecutionRequest = {
      job_id: jobId,
      context_overrides: contextOverrides,
    };
    return this.http.post<ExecutionResponse>(
      `${this.apiUrl}/execution/start`,
      request
    );
  }

  /**
   * GET /api/execution/{taskId} - Get execution status
   */
  getExecutionStatus(taskId: string): Observable<ExecutionStatus> {
    return this.http.get<ExecutionStatus>(`${this.apiUrl}/execution/${taskId}`);
  }

  /**
   * POST /api/execution/{taskId}/stop - Stop execution
   */
  stopExecution(taskId: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/execution/${taskId}/stop`, {});
  }

  /**
   * Health check endpoint
   */
  healthCheck(): Observable<any> {
    return this.http.get(`${environment.apiUrl.replace('/api', '')}/health`);
  }
}
