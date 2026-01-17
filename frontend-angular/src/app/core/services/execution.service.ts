import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { ApiService } from './api.service';
import { WebSocketService } from './websocket.service';
import { ExecutionStatus, ExecutionResponse } from '../models/types';

/**
 * Execution Management Service - Handles job execution and monitoring
 */
@Injectable({
  providedIn: 'root',
})
export class ExecutionService {
  private executionStatusSubject = new BehaviorSubject<ExecutionStatus | null>(
    null
  );
  private executionHistorySubject = new BehaviorSubject<ExecutionStatus[]>([]);
  private isExecutingSubject = new BehaviorSubject<boolean>(false);

  public executionStatus$ = this.executionStatusSubject.asObservable();
  public executionHistory$ = this.executionHistorySubject.asObservable();
  public isExecuting$ = this.isExecutingSubject.asObservable();

  private currentTaskId: string = '';
  private executionHistory: ExecutionStatus[] = [];

  constructor(
    private apiService: ApiService,
    private websocketService: WebSocketService
  ) {}

  /**
   * Start job execution
   * @param jobId Job ID to execute
   * @param contextOverrides Optional context variable overrides
   */
  startExecution(
    jobId: string,
    contextOverrides?: Record<string, any>
  ): Observable<ExecutionResponse> {
    this.isExecutingSubject.next(true);

    return new Observable((observer) => {
      this.apiService.startExecution(jobId, contextOverrides).subscribe({
        next: (response: ExecutionResponse) => {
          console.log('Execution started:', response);
          this.currentTaskId = response.task_id;

          // Connect WebSocket for real-time updates
          this.websocketService.connect(response.task_id).then(() => {
            // Subscribe to execution updates
            this.websocketService.executionUpdate$.subscribe((update) => {
              this.executionStatusSubject.next(update);
              this.addToHistory(update);

              // Stop executing if job completed or failed
              if (update.status === 'success' || update.status === 'error') {
                this.isExecutingSubject.next(false);
              }
            });

            observer.next(response);
            observer.complete();
          });
        },
        error: (error) => {
          console.error('Error starting execution:', error);
          this.isExecutingSubject.next(false);
          observer.error(error);
        },
      });
    });
  }

  /**
   * Get current execution status
   */
  getExecutionStatus(): Observable<ExecutionStatus | null> {
    return this.executionStatus$;
  }

  /**
   * Get execution status from server (polling)
   */
  pollExecutionStatus(taskId: string): Observable<ExecutionStatus> {
    return this.apiService.getExecutionStatus(taskId);
  }

  /**
   * Stop execution
   */
  stopExecution(taskId: string): Observable<any> {
    return new Observable((observer) => {
      this.apiService.stopExecution(taskId).subscribe({
        next: (result) => {
          this.isExecutingSubject.next(false);
          this.websocketService.disconnect();
          observer.next(result);
          observer.complete();
        },
        error: (error) => {
          console.error('Error stopping execution:', error);
          observer.error(error);
        },
      });
    });
  }

  /**
   * Get execution history
   */
  getExecutionHistory(): Observable<ExecutionStatus[]> {
    return this.executionHistory$;
  }

  /**
   * Add execution to history
   */
  private addToHistory(execution: ExecutionStatus): void {
    const history = this.executionHistorySubject.value;
    // Check if already exists (update instead of add)
    const existingIndex = history.findIndex(
      (e) => e.task_id === execution.task_id
    );

    if (existingIndex >= 0) {
      history[existingIndex] = execution;
    } else {
      history.unshift(execution);
    }

    this.executionHistorySubject.next([...history]);
  }

  /**
   * Clear execution history
   */
  clearHistory(): void {
    this.executionHistorySubject.next([]);
  }

  /**
   * Get current task ID
   */
  getCurrentTaskId(): string {
    return this.currentTaskId;
  }

  /**
   * Check if executing
   */
  isExecuting(): Observable<boolean> {
    return this.isExecuting$;
  }

  /**
   * Disconnect WebSocket
   */
  disconnect(): void {
    this.websocketService.disconnect();
    this.isExecutingSubject.next(false);
  }
}
