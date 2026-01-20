import { Component, OnInit, Input, Output, EventEmitter } from '@angular/core';
import { JobNode, JobEdge } from '../../core/models/types';

/**
 * Canvas Component - Visual ETL Designer Canvas
 * Displays draggable components and data flow edges
 * Supports drag-to-connect for creating edges
 */
@Component({
  selector: 'app-canvas',
  template: `
    <div class="canvas-container">
      <svg 
        class="canvas-svg" 
        (mousemove)="onCanvasMouseMove($event)"
        (dragover)="onCanvasDragOver($event)"
        (drop)="onCanvasDrop($event)"
        (mouseup)="onCanvasMouseUp($event)"
      >
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

        <!-- Temporary connection line while dragging -->
        <line
          *ngIf="isConnecting && tempConnectionLine"
          [attr.x1]="tempConnectionLine.x1"
          [attr.y1]="tempConnectionLine.y1"
          [attr.x2]="tempConnectionLine.x2"
          [attr.y2]="tempConnectionLine.y2"
          class="temp-connection-line"
        />

        <!-- Subjob Containers (Talend-style grouping) -->
        <g class="subjobs">
          <g *ngFor="let subjob of subjobs">
            <rect
              [attr.x]="subjob.x"
              [attr.y]="subjob.y"
              [attr.width]="subjob.width"
              [attr.height]="subjob.height"
              class="subjob-container"
              [style.fill]="subjob.color"
            />
            <text
              [attr.x]="subjob.x + 5"
              [attr.y]="subjob.y - 5"
              class="subjob-label"
            >
              {{ subjob.name }}
            </text>
          </g>
        </g>

        <!-- Nodes -->
        <g class="nodes">
          <g
            *ngFor="let node of nodes"
            class="node"
            [class.selected]="node.id === selectedNodeId"
            [class.dragging]="draggingNodeId === node.id"
            (click)="onNodeClick(node)"
            (mousedown)="onNodeMouseDown($event, node)"
            style="cursor: grab;"
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
              font-size="10"
            >
              {{ getNodeDisplayName(node) }}
            </text>

            <!-- Output Port (Right side) -->
            <circle
              class="output-port"
              [attr.cx]="node.x + 120"
              [attr.cy]="node.y + 30"
              r="6"
              (mousedown)="onStartConnection($event, node, 'output')"
              title="Drag to connect"
            />

            <!-- Input Port (Left side) -->
            <circle
              class="input-port"
              [attr.cx]="node.x"
              [attr.cy]="node.y + 30"
              r="6"
              (mousedown)="onStartConnection($event, node, 'input')"
              (mouseenter)="onPortHover($event, node, 'input')"
              (mouseleave)="onPortLeave($event)"
              title="Drop to connect"
            />
          </g>
        </g>
      </svg>

      <div class="canvas-toolbar">
        <button (click)="onUndo()" [disabled]="edgeHistory.length === 0" title="Undo (Ctrl+Z)">↶</button>
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
        font-size: 12px;
        font-weight: 600;
        fill: #000;
      }

      .node-id {
        font-size: 11px;
        fill: #666;
      }

      .output-port {
        fill: #52c41a;
        stroke: #389e0d;
        stroke-width: 2;
        cursor: grab;
        transition: all 0.2s;
      }

      .output-port:hover {
        r: 8;
        filter: drop-shadow(0 0 4px #52c41a);
      }

      .output-port:active {
        cursor: grabbing;
      }

      .input-port {
        fill: #1890ff;
        stroke: #0050b3;
        stroke-width: 2;
        cursor: grab;
        transition: all 0.2s;
      }

      .input-port:hover {
        r: 8;
        filter: drop-shadow(0 0 4px #1890ff);
      }

      .edge-line {
        stroke: #667eea;
        stroke-width: 2;
        fill: none;
        pointer-events: none;
      }

      .edge-line.main {
        stroke: #52c41a;
      }

      .edge-line.reject {
        stroke: #ff4d4f;
        stroke-dasharray: 5,5;
      }

      .temp-connection-line {
        stroke: #1890ff;
        stroke-width: 2;
        stroke-dasharray: 5,5;
        fill: none;
        pointer-events: none;
      }

      .subjob-container {
        stroke: #d9d9d9;
        stroke-width: 2;
        stroke-dasharray: 4, 4;
        opacity: 0.6;
        pointer-events: none;
        rx: 4;
      }

      .subjob-label {
        font-size: 11px;
        font-weight: 600;
        fill: #666;
        pointer-events: none;
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
        font-size: 14px;
      }

      .canvas-toolbar button:hover:not(:disabled) {
        border-color: #1890ff;
        color: #1890ff;
      }

      .canvas-toolbar button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      .node.dragging .node-rect {
        fill: #fff7e6;
        stroke: #ff7a45;
        filter: drop-shadow(0 2px 8px rgba(0, 0, 0, 0.2));
      }

      .node {
        cursor: grab;
      }

      .node.dragging {
        cursor: grabbing;
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
  @Output() edgeCreated = new EventEmitter<JobEdge>();

  // Connection/Linking properties
  isConnecting = false;
  connectingFromNode: JobNode | null = null;
  connectingFromPort: 'input' | 'output' | null = null;
  tempConnectionLine: { x1: number; y1: number; x2: number; y2: number } | null = null;
  hoveredPortNode: JobNode | null = null;

  // Node Dragging properties
  isDragging = false;
  draggingNodeId: string | null = null;
  dragStartX = 0;
  dragStartY = 0;
  dragOffsetX = 0;
  dragOffsetY = 0;

  // Subjob Grouping properties
  subjobs: any[] = [];
  subjobCounter = 0;

  // Undo/History
  edgeHistory: JobEdge[] = [];

  ngOnInit(): void {
    // Listen for Ctrl+Z keyboard shortcut
    document.addEventListener('keydown', (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'z') {
        event.preventDefault();
        this.onUndo();
      }
    });
  }

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

  onNodeMouseDown(event: MouseEvent, node: JobNode): void {
    event.stopPropagation();
    
    const svg = (event.target as SVGElement).closest('svg') as SVGSVGElement;
    if (!svg) return;

    const rect = svg.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;

    // Calculate offset from node's top-left corner (nodes are 120x60)
    this.dragOffsetX = mouseX - node.x;
    this.dragOffsetY = mouseY - node.y;

    this.isDragging = true;
    this.draggingNodeId = node.id;
  }

  onCanvasMouseMove(event: MouseEvent): void {
    const svg = (event.target as SVGElement).closest('svg') as SVGSVGElement;
    if (!svg) return;

    const rect = svg.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // Handle node dragging
    if (this.isDragging && this.draggingNodeId) {
      const node = this.nodes.find((n) => n.id === this.draggingNodeId);
      if (node) {
        // Update node position based on drag offset
        node.x = x - this.dragOffsetX;
        node.y = y - this.dragOffsetY;
        
        // Constrain to reasonable bounds (keep nodes visible in grid)
        node.x = Math.max(-100, Math.min(2000, node.x));
        node.y = Math.max(-100, Math.min(1500, node.y));
        
        // Force change detection
        this.nodes = [...this.nodes];
      }
      return;
    }

    // Handle connection line dragging
    if (!this.isConnecting || !this.tempConnectionLine) return;

    this.tempConnectionLine.x2 = x;
    this.tempConnectionLine.y2 = y;
  }

  onCanvasDragOver(event: DragEvent): void {
    event.preventDefault();
    event.dataTransfer!.dropEffect = 'copy';
  }

  onCanvasDrop(event: DragEvent): void {
    event.preventDefault();
    
    const componentData = event.dataTransfer?.getData('component');
    if (!componentData) return;

    try {
      const component = JSON.parse(componentData);
      
      // Get drop coordinates relative to canvas
      const svg = (event.target as SVGElement);
      const rect = svg.getBoundingClientRect();
      const x = event.clientX - rect.left - 60;
      const y = event.clientY - rect.top - 30;

      // Create new node
      const newNode: JobNode = {
        id: `${component.type}_${Date.now()}`,
        type: component.type,
        label: component.label,
        x: Math.max(0, x),
        y: Math.max(0, y),
        config: {},
      };

      // Add to nodes and emit
      this.nodes = [...this.nodes, newNode];
      this.nodesUpdated.emit(this.nodes);
      
      // Select the new node
      this.nodeSelected.emit(newNode);
    } catch (error) {
      console.error('Error dropping component:', error);
    }
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

  getNodeDisplayName(node: JobNode): string {
    // If node has a custom name, use it
    if (node.name) {
      return node.name;
    }
    
    // Otherwise use counter-based naming
    const nodeIndex = this.nodes
      .filter((n) => n.type === node.type)
      .findIndex((n) => n.id === node.id) + 1;
    return `${node.label || node.type}_${nodeIndex}`;
  }

  /**
   * Start creating a connection from a port
   */
  onStartConnection(
    event: MouseEvent,
    node: JobNode,
    portType: 'input' | 'output'
  ): void {
    event.stopPropagation();
    this.isConnecting = true;
    this.connectingFromNode = node;
    this.connectingFromPort = portType;

    // Get port position
    const circle = event.target as SVGCircleElement;
    const cx = parseFloat(circle.getAttribute('cx') || '0');
    const cy = parseFloat(circle.getAttribute('cy') || '0');

    this.tempConnectionLine = {
      x1: cx,
      y1: cy,
      x2: cx,
      y2: cy,
    };
  }

  /**
   * Complete connection when dropping on another port
   */
  onPortHover(
    event: MouseEvent,
    targetNode: JobNode,
    portType: 'input' | 'output'
  ): void {
    if (!this.isConnecting || !this.connectingFromNode) return;

    // Can't connect to the same node
    if (targetNode.id === this.connectingFromNode.id) return;

    // Can't connect output to output, or input to input
    if (this.connectingFromPort === portType) return;

    this.hoveredPortNode = targetNode;
  }

  onPortLeave(event: MouseEvent): void {
    this.hoveredPortNode = null;
  }

  /**
   * Handle mouse up to complete connection
   */
  onCanvasMouseUp(event: MouseEvent): void {
    // Handle node drag completion
    if (this.isDragging) {
      this.isDragging = false;
      this.draggingNodeId = null;
      // Optionally snap to grid for cleaner layout
      this.nodes.forEach((node) => {
        node.x = Math.round(node.x / 10) * 10; // Snap to 10px grid
        node.y = Math.round(node.y / 10) * 10;
      });
      this.nodes = [...this.nodes]; // Force re-render
      return;
    }

    // Handle connection creation
    if (!this.isConnecting || !this.connectingFromNode || !this.hoveredPortNode) {
      this.completeConnection(false);
      return;
    }

    // Create edge based on connection direction
    let sourceId: string;
    let targetId: string;

    if (this.connectingFromPort === 'output') {
      sourceId = this.connectingFromNode.id;
      targetId = this.hoveredPortNode.id;
    } else {
      sourceId = this.hoveredPortNode.id;
      targetId = this.connectingFromNode.id;
    }

    // Check if edge already exists
    const edgeExists = this.edges.some(
      (e) => e.source === sourceId && e.target === targetId
    );

    if (!edgeExists) {
      const newEdge: JobEdge = {
        id: `edge_${sourceId}_${targetId}_${Date.now()}`,
        source: sourceId,
        target: targetId,
        edge_type: 'main',
      };

      this.edges = [...this.edges, newEdge];
      // Add to history for undo
      this.edgeHistory.push(newEdge);
      
      // Update subjobs when edge is created
      this.updateSubjobs();
      
      this.edgeCreated.emit(newEdge);
    }

    this.completeConnection(true);
  }

  /**
   * Calculate subjobs based on connected components
   */
  private updateSubjobs(): void {
    // Reset subjob assignments
    this.nodes.forEach((node) => {
      node.subjob_id = undefined;
    });

    // Find all connected components using graph traversal
    const visited = new Set<string>();
    let subjobIndex = 0;

    this.nodes.forEach((node) => {
      if (!visited.has(node.id)) {
        // Find all nodes connected to this node
        const connectedNodes = this.getConnectedNodeCluster(node.id, visited);
        
        if (connectedNodes.length > 0) {
          const subjobId = `subjob_${subjobIndex}`;
          connectedNodes.forEach((connectedNode) => {
            connectedNode.subjob_id = subjobId;
            visited.add(connectedNode.id);
          });
          subjobIndex++;
        }
      }
    });

    // Calculate subjob bounding boxes
    this.calculateSubjobBounds();
    this.nodes = [...this.nodes];
  }

  /**
   * Get all nodes connected to a given node (BFS)
   */
  private getConnectedNodeCluster(
    nodeId: string,
    visited: Set<string>
  ): JobNode[] {
    const cluster: JobNode[] = [];
    const queue = [nodeId];
    const localVisited = new Set<string>();

    while (queue.length > 0) {
      const currentId = queue.shift()!;
      if (localVisited.has(currentId)) continue;

      localVisited.add(currentId);
      const node = this.nodes.find((n) => n.id === currentId);
      if (node) {
        cluster.push(node);
      }

      // Find connected nodes
      this.edges.forEach((edge) => {
        if (edge.source === currentId && !localVisited.has(edge.target)) {
          queue.push(edge.target);
        }
        if (edge.target === currentId && !localVisited.has(edge.source)) {
          queue.push(edge.source);
        }
      });
    }

    return cluster;
  }

  /**
   * Calculate bounding box for each subjob
   */
  private calculateSubjobBounds(): void {
    const subjobMap = new Map<string, JobNode[]>();

    // Group nodes by subjob
    this.nodes.forEach((node) => {
      if (node.subjob_id) {
        if (!subjobMap.has(node.subjob_id)) {
          subjobMap.set(node.subjob_id, []);
        }
        subjobMap.get(node.subjob_id)!.push(node);
      }
    });

    // Calculate bounds for each subjob
    this.subjobs = Array.from(subjobMap.entries()).map(([subjobId, subjobNodes]) => {
      const xCoords = subjobNodes.map((n) => n.x);
      const yCoords = subjobNodes.map((n) => n.y);

      const minX = Math.min(...xCoords);
      const minY = Math.min(...yCoords);
      const maxX = Math.max(...xCoords) + 120; // node width
      const maxY = Math.max(...yCoords) + 60; // node height

      return {
        id: subjobId,
        name: `SubJob ${subjobId.split('_')[1]}`,
        node_ids: subjobNodes.map((n) => n.id),
        x: minX - 15,
        y: minY - 35,
        width: maxX - minX + 30,
        height: maxY - minY + 50,
        color: this.getSubjobColor(subjobId),
      };
    });
  }

  /**
   * Get color for subjob (cycle through colors)
   */
  private getSubjobColor(subjobId: string): string {
    const colors = ['#e6f7ff', '#f0f5ff', '#f9f0ff', '#fffbe6', '#f6ffed'];
    const index = parseInt(subjobId.split('_')[1]) % colors.length;
    return colors[index];
  }

  /**
   * Cleanup after connection attempt
   */
  private completeConnection(success: boolean): void {
    this.isConnecting = false;
    this.connectingFromNode = null;
    this.connectingFromPort = null;
    this.tempConnectionLine = null;
    this.hoveredPortNode = null;
  }

  /**
   * Undo the last connection
   */
  onUndo(): void {
    if (this.edgeHistory.length === 0) return;

    // Remove last edge from history
    const edgeToRemove = this.edgeHistory.pop();
    if (!edgeToRemove) return;

    // Remove from edges array
    this.edges = this.edges.filter((e) => e.id !== edgeToRemove.id);
    
    // Recalculate subjobs after edge removal
    this.updateSubjobs();
  }
}
