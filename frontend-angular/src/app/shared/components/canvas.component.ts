import { Component, OnInit, Input, Output, EventEmitter } from '@angular/core';
import { JobNode, JobEdge } from '../../core/models/types';

/**
 * Canvas Component - Visual ETL Designer Canvas
 * Displays draggable components and data flow edges
 * Uses SVG for rendering
 */
@Component({
  selector: 'app-canvas',
  template: `
    <div class="canvas-container">
      <svg class="canvas-svg" (mousemove)="onCanvasMouseMove($event)">
        <!-- Grid background -->
        <defs>
          <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path
              d="M 20 0 L 0 0 0 20"
              fill="none"
              stroke="#e8e8e8"
              stroke-width="0.5"
            />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />

        <!-- Edges -->
        <g class="edges">
          <line
            *ngFor="let edge of edges"
            [attr.x1]="getNodeCenter(edge.source)?.x"
            [attr.y1]="getNodeCenter(edge.source)?.y"
            [attr.x2]="getNodeCenter(edge.target)?.x"
            [attr.y2]="getNodeCenter(edge.target)?.y"
            class="edge-line"
            [class.main]="edge.edge_type === 'main'"
            [class.reject]="edge.edge_type === 'reject'"
          />
        </g>

        <!-- Nodes -->
        <g class="nodes">
          <g
            *ngFor="let node of nodes"
            class="node"
            [class.selected]="node.id === selectedNodeId"
            (click)="onNodeClick(node)"
          >
            <rect
              class="node-rect"
              [attr.x]="node.x"
              [attr.y]="node.y"
              width="120"
              height="60"
            />
            <text
              class="node-label"
              [attr.x]="node.x + 60"
              [attr.y]="node.y + 20"
              text-anchor="middle"
            >
              {{ node.type }}
            </text>
            <text
              class="node-id"
              [attr.x]="node.x + 60"
              [attr.y]="node.y + 40"
              text-anchor="middle"
              font-size="12"
            >
              {{ node.id }}
            </text>
          </g>
        </g>
      </svg>

      <div class="canvas-toolbar">
        <button (click)="onZoomIn()" title="Zoom In">+</button>
        <button (click)="onZoomOut()" title="Zoom Out">−</button>
        <button (click)="onFitToView()" title="Fit to View">Fit</button>
        <button (click)="onClear()" title="Clear Canvas">Clear</button>
      </div>
    </div>
  `,
  styles: [
    `
      .canvas-container {
        position: relative;
        width: 100%;
        height: 100%;
        background: white;
        border: 1px solid #ddd;
      }

      .canvas-svg {
        width: 100%;
        height: 100%;
        background: white;
      }

      .edge-line {
        stroke: #999;
        stroke-width: 2;
        fill: none;
      }

      .edge-line.main {
        stroke: #1890ff;
      }

      .edge-line.reject {
        stroke: #ff4d4f;
        stroke-dasharray: 5, 5;
      }

      .node-rect {
        fill: #fafafa;
        stroke: #999;
        stroke-width: 2;
        rx: 4;
      }

      .node.selected .node-rect {
        fill: #e6f7ff;
        stroke: #1890ff;
        stroke-width: 3;
      }

      .node-label {
        font-size: 14px;
        font-weight: 600;
        fill: #000;
      }

      .node-id {
        font-size: 11px;
        fill: #666;
      }

      .canvas-toolbar {
        position: absolute;
        bottom: 20px;
        right: 20px;
        display: flex;
        gap: 8px;
      }

      .canvas-toolbar button {
        width: 36px;
        height: 36px;
        border: 1px solid #ddd;
        background: white;
        cursor: pointer;
        border-radius: 4px;
        font-size: 16px;
      }

      .canvas-toolbar button:hover {
        border-color: #1890ff;
        color: #1890ff;
      }
    `,
  ],
})
export class CanvasComponent implements OnInit {
  @Input() nodes: JobNode[] = [];
  @Input() edges: JobEdge[] = [];
  @Input() selectedNodeId: string | null = null;
  @Output() nodeSelected = new EventEmitter<JobNode>();
  @Output() nodesUpdated = new EventEmitter<JobNode[]>();

  ngOnInit(): void {}

  getNodeCenter(
    nodeId: string
  ): { x: number; y: number } | undefined {
    const node = this.nodes.find((n) => n.id === nodeId);
    if (node) {
      return { x: node.x + 60, y: node.y + 30 };
    }
    return undefined;
  }

  onNodeClick(node: JobNode): void {
    this.nodeSelected.emit(node);
  }

  onCanvasMouseMove(event: MouseEvent): void {
    // Can be used for drag operations
  }

  onZoomIn(): void {
    // Implementation for zoom in
  }

  onZoomOut(): void {
    // Implementation for zoom out
  }

  onFitToView(): void {
    // Implementation for fit to view
  }

  onClear(): void {
    if (confirm('Are you sure you want to clear the canvas?')) {
      this.nodes = [];
      this.edges = [];
      this.nodesUpdated.emit([]);
    }
  }
}
