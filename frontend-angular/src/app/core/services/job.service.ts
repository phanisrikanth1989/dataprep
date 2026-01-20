import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { ApiService } from './api.service';
import { JobSchema, JobListResponse } from '../models/types';

/**
 * Job Management Service - Business logic for job operations
 */
@Injectable({
  providedIn: 'root',
})
export class JobService {
  private jobsSubject = new BehaviorSubject<JobListResponse[]>([]);
  private currentJobSubject = new BehaviorSubject<JobSchema | null>(null);
  private loadingSubject = new BehaviorSubject<boolean>(false);

  public jobs$ = this.jobsSubject.asObservable();
  public currentJob$ = this.currentJobSubject.asObservable();
  public loading$ = this.loadingSubject.asObservable();

  constructor(private apiService: ApiService) {}

  /**
   * Load all jobs
   */
  loadJobs(): void {
    this.loadingSubject.next(true);
    this.apiService.listJobs().subscribe({
      next: (jobs) => {
        this.jobsSubject.next(jobs);
        this.loadingSubject.next(false);
      },
      error: (error) => {
        console.error('Error loading jobs:', error);
        this.loadingSubject.next(false);
      },
    });
  }

  /**
   * Get all jobs
   */
  getJobs(): Observable<JobListResponse[]> {
    return this.jobs$;
  }

  /**
   * Load specific job
   */
  loadJob(jobId: string): Observable<JobSchema> {
    this.loadingSubject.next(true);
    return new Observable((observer) => {
      this.apiService.getJob(jobId).subscribe({
        next: (job) => {
          this.currentJobSubject.next(job);
          this.loadingSubject.next(false);
          observer.next(job);
          observer.complete();
        },
        error: (error) => {
          console.error('Error loading job:', error);
          this.loadingSubject.next(false);
          observer.error(error);
        },
      });
    });
  }

  /**
   * Get current job
   */
  getCurrentJob(): Observable<JobSchema | null> {
    return this.currentJob$;
  }

  /**
   * Create new job
   */
  createJob(job: JobSchema): Observable<JobSchema> {
    this.loadingSubject.next(true);
    return new Observable((observer) => {
      this.apiService.createJob(job).subscribe({
        next: (createdJob) => {
          this.loadingSubject.next(false);
          this.loadJobs(); // Refresh list
          observer.next(createdJob);
          observer.complete();
        },
        error: (error) => {
          console.error('Error creating job:', error);
          this.loadingSubject.next(false);
          observer.error(error);
        },
      });
    });
  }

  /**
   * Update job
   */
  updateJob(jobId: string, job: JobSchema): Observable<JobSchema> {
    this.loadingSubject.next(true);
    return new Observable((observer) => {
      this.apiService.updateJob(jobId, job).subscribe({
        next: (updatedJob) => {
          this.currentJobSubject.next(updatedJob);
          this.loadingSubject.next(false);
          this.loadJobs(); // Refresh list
          observer.next(updatedJob);
          observer.complete();
        },
        error: (error) => {
          console.error('Error updating job:', error);
          this.loadingSubject.next(false);
          observer.error(error);
        },
      });
    });
  }

  /**
   * Delete job
   */
  deleteJob(jobId: string): Observable<any> {
    this.loadingSubject.next(true);
    return new Observable((observer) => {
      this.apiService.deleteJob(jobId).subscribe({
        next: (result) => {
          this.loadingSubject.next(false);
          this.loadJobs(); // Refresh list
          observer.next(result);
          observer.complete();
        },
        error: (error) => {
          console.error('Error deleting job:', error);
          this.loadingSubject.next(false);
          observer.error(error);
        },
      });
    });
  }

  /**
   * Export job config
   */
  exportJob(jobId: string): Observable<any> {
    return this.apiService.exportJob(jobId);
  }

  /**
   * Create new blank job
   */
  createBlankJob(jobName: string): JobSchema {
    const jobId = `job_${Date.now()}`;
    return {
      id: jobId,
      name: jobName,
      description: '',
      nodes: [],
      edges: [],
      context: {},
      java_config: { enabled: false },
      python_config: { enabled: false },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
  }
}
