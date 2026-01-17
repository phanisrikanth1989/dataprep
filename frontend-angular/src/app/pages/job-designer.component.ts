import { Component, OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { JobService } from '@services/job.service';
import { ExecutionService } from '@services/execution.service';
import { JobSchema, JobNode, JobEdge, ComponentField } from '@models/types';
import { NzMessageService } from 'ng-zorro-antd/message';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { v4 as uuidv4 } from 'uuid';

/**
 * Job Designer Component - Main ETL visual job designer
 */
@Component({
  selector: 'app-job-designer',
  template: `
    <div class="job-designer">
      <!-- Header Toolbar -->
      <div class="designer-header">
        <div class="header-left">
          <button nz-button nzType="text" class="btn-back" (click)="onBack()">
            <span class="icon">←</span> Back to Jobs
          </button>
          <div class="job-info">
            <h2 class="job-title">{{ job?.name || 'Untitled Job' }}</h2>
            <span class="job-status" [class.modified]="!isSaving">{{ job?.id }}</span>
          </div>
        </div>
        <div class="header-right">
          <button nz-button class="btn-save" (click)="onSave()" [nzLoading]="isSaving">
            <span class="icon">💾</span> Save Job
          </button>
          <button nz-button nzType="primary" class="btn-execute" (click)="onExecute()">
            <span class="icon">▶</span> Execute
          </button>
        </div>
      </div>

      <!-- Main Designer Area -->
      <div class="designer-content">
        <!-- Left Sidebar - Job Designer Controls & Config Panel -->
        <div class="sidebar sidebar-left">
          <div class="sidebar-header">
            <h3>Configuration</h3>
            <button nz-button nzType="text" nzSize="small" *ngIf="selectedNode" (click)="onConfigCancelled()" class="btn-close">✕</button>
          </div>
          <app-config-panel
            *ngIf="selectedNode"
            [selectedNode]="selectedNode"
            [fields]="selectedFields"
            (configUpdated)="onConfigUpdated($event)"
            (cancelled)="onConfigCancelled()"
          ></app-config-panel>
          <div *ngIf="!selectedNode" class="no-selection">
            <p>Select a component on the canvas to configure</p>
          </div>
        </div>

        <!-- Center - Canvas (Main Building Area) -->
        <div class="canvas-wrapper">
          <div class="canvas-header">
            <span class="canvas-info">{{ nodes.length }} components | {{ edges.length }} connections</span>
          </div>
          <app-canvas
            [nodes]="nodes"
            [edges]="edges"
            [selectedNodeId]="selectedNodeId"
            (nodeSelected)="onNodeSelect($event)"
            (nodesUpdated)="onNodesUpdated($event)"
            class="canvas-area"
          ></app-canvas>
        </div>

        <!-- Right Sidebar - Component Palette -->
        <div class="sidebar sidebar-right">
          <div class="sidebar-header">
            <h3>Components</h3>
          </div>
          <app-component-palette></app-component-palette>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      .job-designer {
        display: flex;
        flex-direction: column;
        height: 100vh;
        background: #f5f7fa;
      }

      .designer-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 24px;
        background: white;
        border-bottom: 1px solid #e2e8f0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
      }

      .header-left {
        display: flex;
        align-items: center;
        gap: 20px;
      }

      .btn-back {
        color: #667eea;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 6px;
        transition: all 0.2s ease;
      }

      .btn-back:hover {
        color: #764ba2;
      }

      .job-info {
        border-left: 1px solid #e2e8f0;
        padding-left: 20px;
      }

      .job-title {
        margin: 0;
        font-size: 20px;
        font-weight: 600;
        color: #2d3748;
      }

      .job-status {
        font-size: 12px;
        color: #a0aec0;
        font-family: 'Monaco', 'Courier', monospace;
      }

      .job-status.modified {
        color: #f6ad55;
      }

      .header-right {
        display: flex;
        gap: 12px;
      }

      .btn-save, .btn-execute {
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 500;
        border-radius: 6px;
        padding: 8px 16px;
      }

      .btn-save {
        background: #f7fafc !important;
        border: 1px solid #cbd5e0 !important;
        color: #2d3748 !important;
      }

      .btn-save:hover {
        background: #edf2f7 !important;
      }

      .btn-execute {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border: none !important;
      }

      .icon {
        font-size: 16px;
      }

      .designer-content {
        display: flex;
        flex: 1;
        overflow: hidden;
        gap: 1px;
        background: #e2e8f0;
      }

      .sidebar {
        background: white;
        display: flex;
        flex-direction: column;
        border-right: 1px solid #e2e8f0;
        overflow: hidden;
      }

      .sidebar-left {
        width: 340px;
        border-right: 2px solid #e2e8f0;
      }

      .sidebar-right {
        width: 300px;
        border-left: 2px solid #e2e8f0;
        border-right: none;
      }

      .sidebar-header {
        padding: 16px 20px;
        border-bottom: 1px solid #e2e8f0;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .sidebar-header h3 {
        margin: 0;
        font-size: 14px;
        font-weight: 600;
        color: #2d3748;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }

      .btn-close {
        color: #a0aec0 !important;
        padding: 0 !important;
      }

      .btn-close:hover {
        color: #4a5568 !important;
      }

      .canvas-wrapper {
        flex: 1;
        display: flex;
        flex-direction: column;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        position: relative;
      }

      .canvas-header {
        padding: 12px 20px;
        background: rgba(255, 255, 255, 0.7);
        border-bottom: 1px solid rgba(0, 0, 0, 0.05);
        font-size: 12px;
        color: #718096;
        font-weight: 500;
      }

      .canvas-area {
        flex: 1;
        overflow: hidden;
      }

      .no-selection {
        padding: 40px 20px;
        text-align: center;
        color: #cbd5e0;
        display: flex;
        align-items: center;
        justify-content: center;
        flex: 1;
      }

      .no-selection p {
        margin: 0;
        font-size: 14px;
        color: #a0aec0;
      }

      app-component-palette {
        flex: 1;
        overflow-y: auto;
      }

      app-config-panel {
        flex: 1;
        overflow-y: auto;
      }
    `,
  ],
})
export class JobDesignerComponent implements OnInit, OnDestroy {
  job: JobSchema | null = null;
  nodes: JobNode[] = [];
  edges: JobEdge[] = [];
  selectedNodeId: string | null = null;
  selectedNode: JobNode | null = null;
  selectedFields: ComponentField[] = [];
  isSaving = false;

  private destroy$ = new Subject<void>();

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private jobService: JobService,
    private executionService: ExecutionService,
    private message: NzMessageService
  ) {}

  ngOnInit(): void {
    const jobId = this.route.snapshot.paramMap.get('jobId');
    if (jobId) {
      this.loadJob(jobId);
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  loadJob(jobId: string): void {
    this.jobService
      .loadJob(jobId)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (job: JobSchema) => {
          this.job = job;
          this.nodes = job.nodes || [];
          this.edges = job.edges || [];
        },
        error: (error: any) => {
          this.message.error('Error loading job');
          console.error(error);
          this.router.navigate(['/']);
        },
      });
  }

  onNodeSelect(node: JobNode): void {
    this.selectedNodeId = node.id;
    this.selectedNode = node;
    // Load component fields based on component type
    this.loadComponentFields(node.type);
  }

  loadComponentFields(componentType: string): void {
    // Placeholder - would load from component registry
    this.selectedFields = [];
  }

  onConfigUpdated(config: Record<string, any>): void {
    if (this.selectedNode) {
      this.selectedNode.config = config;
      this.selectedNodeId = null;
      this.selectedNode = null;
    }
  }

  onConfigCancelled(): void {
    this.selectedNodeId = null;
    this.selectedNode = null;
  }

  onNodesUpdated(updatedNodes: JobNode[]): void {
    this.nodes = updatedNodes;
  }

  onSave(): void {
    if (!this.job) return;

    this.isSaving = true;

    const updatedJob: JobSchema = {
      ...this.job,
      nodes: this.nodes,
      edges: this.edges,
      updated_at: new Date().toISOString(),
    };

    this.jobService.updateJob(this.job.id, updatedJob).subscribe({
      next: (saved: JobSchema) => {
        this.message.success('Job saved successfully');
        this.job = saved;
        this.isSaving = false;
      },
      error: (error: any) => {
        this.message.error('Error saving job');
        console.error(error);
        this.isSaving = false;
      },
    });
  }

  onExecute(): void {
    if (!this.job) return;

    this.message.loading('Starting job execution...');

    this.executionService.startExecution(this.job.id).subscribe({
      next: (response: any) => {
        this.message.success('Job execution started');
        this.router.navigate(['/execution', response.task_id]);
      },
      error: (error: any) => {
        this.message.error('Error starting execution');
        console.error(error);
      },
    });
  }

  onBack(): void {
    this.router.navigate(['/']);
  }
}
