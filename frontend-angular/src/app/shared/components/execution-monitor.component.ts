import { Component, OnInit, Input, OnDestroy } from '@angular/core';
import { ExecutionService } from '../../core/services/execution.service';
import { ExecutionStatus } from '../../core/models/types';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';

/**
 * Execution Monitor Component
 * Real-time job execution monitoring with progress and logs
 */
@Component({
  selector: 'app-execution-monitor',
  template: `
    <div class="execution-monitor">
      <div *ngIf="!currentExecution" class="no-execution">
        <p>No execution running</p>
      </div>

      <div *ngIf="currentExecution" class="execution-content">
        <!-- Header -->
        <div class="execution-header">
          <h3>Execution: {{ currentExecution.task_id }}</h3>
          <span
            class="status-badge"
            [class.pending]="currentExecution.status === 'pending'"
            [class.running]="currentExecution.status === 'running'"
            [class.success]="currentExecution.status === 'success'"
            [class.error]="currentExecution.status === 'error'"
          >
            {{ currentExecution.status | uppercase }}
          </span>
        </div>

        <!-- Progress Bar -->
        <div class="progress-section">
          <div class="progress-label">
            Progress: {{ currentExecution.progress }}%
          </div>
          <div class="progress-bar">
            <div
              class="progress-fill"
              [style.width.%]="currentExecution.progress"
            ></div>
          </div>
        </div>

        <!-- Statistics -->
        <div *ngIf="currentExecution.stats" class="stats-section">
          <h4>Statistics</h4>
          <div class="stats-grid">
            <div *ngFor="let stat of getStatsArray()" class="stat-item">
              <span class="stat-label">{{ stat.key }}</span>
              <span class="stat-value">{{ stat.value }}</span>
            </div>
          </div>
        </div>

        <!-- Logs -->
        <div class="logs-section">
          <h4>Execution Logs</h4>
          <div class="logs-container">
            <div *ngFor="let log of currentExecution.logs" class="log-entry">
              {{ log }}
            </div>
          </div>
        </div>

        <!-- Error Message -->
        <div
          *ngIf="currentExecution.error_message"
          class="error-section"
        >
          <h4>Error</h4>
          <div class="error-message">
            {{ currentExecution.error_message }}
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="action-buttons">
          <button
            nz-button
            nzType="primary"
            *ngIf="currentExecution.status === 'running'"
            (click)="onStop()"
          >
            Stop Execution
          </button>
          <button
            nz-button
            *ngIf="
              currentExecution.status === 'success' ||
              currentExecution.status === 'error'
            "
            (click)="onClose()"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      .execution-monitor {
        padding: 20px;
        height: 100%;
        overflow-y: auto;
        background: white;
      }

      .no-execution {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: #999;
      }

      .execution-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
        border-bottom: 1px solid #f0f0f0;
        padding-bottom: 12px;
      }

      .execution-header h3 {
        margin: 0;
        font-size: 16px;
      }

      .status-badge {
        padding: 4px 12px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 600;
      }

      .status-badge.pending {
        background: #f5f5f5;
        color: #666;
      }

      .status-badge.running {
        background: #e6f7ff;
        color: #1890ff;
      }

      .status-badge.success {
        background: #f6ffed;
        color: #52c41a;
      }

      .status-badge.error {
        background: #fff2f0;
        color: #ff4d4f;
      }

      .progress-section {
        margin-bottom: 20px;
      }

      .progress-label {
        font-size: 13px;
        margin-bottom: 8px;
        color: #666;
      }

      .progress-bar {
        width: 100%;
        height: 24px;
        background: #f0f0f0;
        border-radius: 4px;
        overflow: hidden;
      }

      .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #1890ff, #52c41a);
        transition: width 0.3s ease;
      }

      .stats-section {
        margin-bottom: 20px;
        padding: 12px;
        background: #fafafa;
        border-radius: 4px;
      }

      .stats-section h4 {
        margin: 0 0 12px 0;
        font-size: 13px;
      }

      .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 12px;
      }

      .stat-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .stat-label {
        font-size: 12px;
        color: #666;
      }

      .stat-value {
        font-size: 14px;
        font-weight: 600;
        color: #1890ff;
      }

      .logs-section {
        margin-bottom: 20px;
      }

      .logs-section h4 {
        margin: 0 0 12px 0;
        font-size: 13px;
      }

      .logs-container {
        max-height: 250px;
        overflow-y: auto;
        background: #f5f5f5;
        border: 1px solid #f0f0f0;
        border-radius: 4px;
        padding: 8px;
        font-family: 'Courier New', monospace;
        font-size: 12px;
      }

      .log-entry {
        padding: 4px 0;
        color: #666;
        word-break: break-all;
      }

      .error-section {
        margin-bottom: 20px;
        padding: 12px;
        background: #fff2f0;
        border: 1px solid #ffccc7;
        border-radius: 4px;
      }

      .error-section h4 {
        margin: 0 0 8px 0;
        font-size: 13px;
        color: #ff4d4f;
      }

      .error-message {
        font-size: 12px;
        color: #ff4d4f;
        word-break: break-all;
      }

      .action-buttons {
        display: flex;
        gap: 10px;
        margin-top: 20px;
      }

      .action-buttons button {
        flex: 1;
      }
    `,
  ],
})
export class ExecutionMonitorComponent implements OnInit, OnDestroy {
  @Input() taskId: string = '';

  currentExecution: ExecutionStatus | null = null;
  private destroy$ = new Subject<void>();

  constructor(private executionService: ExecutionService) {}

  ngOnInit(): void {
    this.executionService.executionStatus$
      .pipe(takeUntil(this.destroy$))
      .subscribe((status) => {
        this.currentExecution = status;
      });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  getStatsArray(): { key: string; value: any }[] {
    if (!this.currentExecution?.stats) {
      return [];
    }

    return Object.entries(this.currentExecution.stats).map(([key, value]) => ({
      key,
      value,
    }));
  }

  onStop(): void {
    if (this.taskId && confirm('Are you sure you want to stop this execution?')) {
      this.executionService.stopExecution(this.taskId).subscribe({
        next: () => {
          console.log('Execution stopped');
        },
        error: (error) => {
          console.error('Error stopping execution:', error);
        },
      });
    }
  }

  onClose(): void {
    this.executionService.disconnect();
  }
}
