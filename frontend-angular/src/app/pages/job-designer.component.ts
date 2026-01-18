import { Component, OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { JobService } from '@services/job.service';
import { ExecutionService } from '@services/execution.service';
import { ComponentRegistryService } from '@services/component-registry.service';
import { JobSchema, JobNode, JobEdge, ComponentField, ComponentMetadata } from '@models/types';
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
    <div class="job-designer" (keydown)="onKeyDown($event)" tabindex="0">
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

      <!-- Component Search Palette (Talend-like) -->
      <div *ngIf="showComponentSearch" class="component-search-overlay" (click)="closeComponentSearch()">
        <div class="component-search-modal" (click)="$event.stopPropagation()">
          <div class="search-header">
            <input
              #searchInput
              type="text"
              placeholder="Search components... (Press ESC to cancel)"
              [(ngModel)]="componentSearchTerm"
              (input)="onComponentSearchInput()"
              (keydown)="onSearchKeyDown($event)"
              class="search-input-modal"
              autofocus
            />
          </div>
          
          <div class="search-results">
            <div *ngIf="filteredSearchComponents.length === 0" class="no-results">
              No components found
            </div>
            
            <div class="results-list">
              <div
                *ngFor="let comp of filteredSearchComponents; let i = index"
                class="result-item"
                [class.selected]="i === selectedSearchIndex"
                (click)="selectComponentFromSearch(comp)"
              >
                <div class="result-icon">📦</div>
                <div class="result-info">
                  <div class="result-name">{{ comp.label }}</div>
                  <div class="result-type">{{ comp.type }}</div>
                </div>
              </div>
            </div>
          </div>

          <div class="search-footer">
            <small>↑↓ to navigate • Enter to select • ESC to close</small>
          </div>
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
        font-size: 16px;
        font-weight: 600;
        color: #2d3748;
      }

      .job-status {
        font-size: 11px;
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
        font-size: 11px;
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

      /* Component Search Palette Styles */
      .component-search-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: flex-start;
        justify-content: center;
        padding-top: 80px;
        z-index: 1000;
      }

      .component-search-modal {
        background: white;
        border-radius: 8px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
        width: 90%;
        max-width: 600px;
        max-height: 70vh;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        animation: slideDown 0.2s ease-out;
      }

      @keyframes slideDown {
        from {
          opacity: 0;
          transform: translateY(-20px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }

      .search-header {
        padding: 16px;
        border-bottom: 1px solid #e8e8e8;
      }

      .search-input-modal {
        width: 100%;
        padding: 10px 12px;
        font-size: 13px;
        border: 2px solid #1890ff;
        border-radius: 4px;
        outline: none;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto;
      }

      .search-input-modal:focus {
        border-color: #40a9ff;
      }

      .search-results {
        flex: 1;
        overflow-y: auto;
        background: #fafafa;
      }

      .results-list {
        display: flex;
        flex-direction: column;
      }

      .result-item {
        padding: 12px 16px;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 12px;
        transition: all 0.15s;
        border-left: 3px solid transparent;
      }

      .result-item:hover {
        background: #f0f0f0;
        border-left-color: #1890ff;
      }

      .result-item.selected {
        background: #e6f7ff;
        border-left-color: #1890ff;
      }

      .result-icon {
        font-size: 20px;
        flex-shrink: 0;
      }

      .result-info {
        flex: 1;
        min-width: 0;
      }

      .result-name {
        font-weight: 500;
        color: #2d3748;
        font-size: 12px;
      }

      .result-type {
        font-size: 11px;
        color: #999;
        margin-top: 2px;
      }

      .no-results {
        padding: 40px 20px;
        text-align: center;
        color: #999;
        font-size: 14px;
      }

      .search-footer {
        padding: 12px 16px;
        background: #f5f5f5;
        border-top: 1px solid #e8e8e8;
        text-align: center;
        color: #999;
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

  // Component Search Properties
  showComponentSearch = false;
  componentSearchTerm = '';
  filteredSearchComponents: ComponentMetadata[] = [];
  selectedSearchIndex = 0;
  allComponents: ComponentMetadata[] = [];
  private lastDropPosition = { x: 300, y: 150 };

  private destroy$ = new Subject<void>();

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private jobService: JobService,
    private executionService: ExecutionService,
    private componentRegistry: ComponentRegistryService,
    private message: NzMessageService
  ) {}

  ngOnInit(): void {
    const jobId = this.route.snapshot.paramMap.get('jobId');
    if (jobId) {
      this.loadJob(jobId);
    }
    // Load all components for search
    this.componentRegistry.components$
      .pipe(takeUntil(this.destroy$))
      .subscribe((components) => {
        this.allComponents = components;
      });  }

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
    // Get component metadata from registry
    this.componentRegistry.components$.pipe(takeUntil(this.destroy$)).subscribe((components) => {
      const component = components.find((c) => c.type === componentType);
      if (component && component.fields) {
        this.selectedFields = component.fields;
      } else {
        this.selectedFields = [];
      }
    });
  }

  onConfigUpdated(config: Record<string, any>): void {
    if (this.selectedNode) {
      // Extract and save the nodeName if provided
      if (config['_nodeName']) {
        this.selectedNode.name = config['_nodeName'];
        delete config['_nodeName'];
      }
      
      this.selectedNode.config = config;
      this.selectedNodeId = null;
      this.selectedNode = null;
      
      // Trigger canvas refresh to update display name
      this.nodes = [...this.nodes];
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

  /**
   * Handle keyboard shortcuts
   * Delete key: Delete selected node and connected edges
   * Any alphanumeric: Open component search
   */
  onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Delete' && this.selectedNode) {
      event.preventDefault();
      this.deleteSelectedNode();
    }
    // Open component search on alphanumeric key (but not if typing in input)
    else if (
      !this.showComponentSearch &&
      /^[a-zA-Z0-9]$/.test(event.key) &&
      !(event.target as HTMLElement).tagName.match(/INPUT|TEXTAREA/)
    ) {
      event.preventDefault();
      this.openComponentSearch(event.key);
    }
  }

  /**
   * Open component search palette (Talend-like)
   */
  openComponentSearch(initialChar: string = ''): void {
    this.showComponentSearch = true;
    this.componentSearchTerm = initialChar;
    this.selectedSearchIndex = 0;
    this.onComponentSearchInput();

    // Focus search input after modal renders
    setTimeout(() => {
      const input = document.querySelector('.search-input-modal') as HTMLInputElement;
      if (input) {
        input.focus();
        input.setSelectionRange(initialChar.length, initialChar.length);
      }
    }, 0);
  }

  closeComponentSearch(): void {
    this.showComponentSearch = false;
    this.componentSearchTerm = '';
    this.filteredSearchComponents = [];
    this.selectedSearchIndex = 0;
  }

  onComponentSearchInput(): void {
    const term = this.componentSearchTerm.toLowerCase().trim();

    if (!term) {
      this.filteredSearchComponents = this.allComponents;
    } else {
      this.filteredSearchComponents = this.allComponents.filter(
        (c) =>
          c.label.toLowerCase().includes(term) ||
          c.type.toLowerCase().includes(term) ||
          c.description?.toLowerCase().includes(term)
      );
    }

    this.selectedSearchIndex = 0;
  }

  onSearchKeyDown(event: KeyboardEvent): void {
    switch (event.key) {
      case 'Escape':
        event.preventDefault();
        this.closeComponentSearch();
        break;

      case 'ArrowUp':
        event.preventDefault();
        this.selectedSearchIndex = Math.max(0, this.selectedSearchIndex - 1);
        this.scrollSearchResultIntoView();
        break;

      case 'ArrowDown':
        event.preventDefault();
        this.selectedSearchIndex = Math.min(
          this.filteredSearchComponents.length - 1,
          this.selectedSearchIndex + 1
        );
        this.scrollSearchResultIntoView();
        break;

      case 'Enter':
        event.preventDefault();
        if (
          this.filteredSearchComponents.length > 0 &&
          this.selectedSearchIndex >= 0
        ) {
          this.selectComponentFromSearch(
            this.filteredSearchComponents[this.selectedSearchIndex]
          );
        }
        break;
    }
  }

  selectComponentFromSearch(component: ComponentMetadata): void {
    // Create a new node for the component
    const newNode: JobNode = {
      id: `${component.type}_${Date.now()}`,
      type: component.type,
      label: component.label,
      x: this.lastDropPosition.x + 50,
      y: this.lastDropPosition.y + 50,
      config: {},
    };

    this.nodes = [...this.nodes, newNode];
    this.lastDropPosition = { x: newNode.x, y: newNode.y };

    this.message.success(`Component "${component.label}" added`);
    this.closeComponentSearch();
  }

  private scrollSearchResultIntoView(): void {
    setTimeout(() => {
      const selectedItem = document.querySelector(
        '.result-item.selected'
      ) as HTMLElement;
      if (selectedItem) {
        selectedItem.scrollIntoView({ block: 'nearest' });
      }
    }, 0);
  }

  /**
   * Delete the selected node and all connected edges
   */
  private deleteSelectedNode(): void {
    if (!this.selectedNode) return;

    const nodeId = this.selectedNode.id;

    // Remove the node
    this.nodes = this.nodes.filter((n) => n.id !== nodeId);

    // Remove all edges connected to this node
    this.edges = this.edges.filter(
      (e) => e.source !== nodeId && e.target !== nodeId
    );

    // Clear selection
    this.selectedNodeId = null;
    this.selectedNode = null;

    this.message.success(`Component deleted`);
  }
}
