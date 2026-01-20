import { Component, OnInit, Output, EventEmitter } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { NzMessageService } from 'ng-zorro-antd/message';

interface Connection {
  id: string;
  name: string;
  type: string;
  host: string;
  database: string;
  table_count: number;
}

interface Table {
  name: string;
  rows: number;
  column_count: number;
  columns: any[];
}

interface Column {
  name: string;
  type: string;
  nullable: boolean;
}

/**
 * Metadata Browser Component
 * Browse database connections, tables, and schemas
 */
@Component({
  selector: 'app-metadata-browser',
  template: `
    <div class="metadata-browser">
      <div class="browser-header">
        <h3>Metadata Browser</h3>
      </div>

      <!-- Connections List -->
      <div class="connections-section">
        <div class="section-header">
          <span>Connections</span>
          <button 
            nz-button 
            nzType="text" 
            nzSize="small"
            (click)="refreshConnections()"
            [nzLoading]="loading"
          >
            🔄
          </button>
        </div>

        <div class="loading" *ngIf="loading">
          Loading connections...
        </div>

        <div class="connections-list" *ngIf="!loading">
          <div
            *ngFor="let conn of connections"
            class="connection-item"
            [class.active]="selectedConnection?.id === conn.id"
            (click)="selectConnection(conn)"
          >
            <div class="connection-name">📦 {{ conn.name }}</div>
            <div class="connection-meta">
              {{ conn.table_count }} tables
            </div>
          </div>

          <div *ngIf="connections.length === 0" class="empty-state">
            No connections available
          </div>
        </div>
      </div>

      <!-- Tables for Selected Connection -->
      <div class="tables-section" *ngIf="selectedConnection">
        <div class="section-header">
          <span>Tables</span>
        </div>

        <div class="loading" *ngIf="loadingTables">
          Loading tables...
        </div>

        <div class="tables-list" *ngIf="!loadingTables">
          <div
            *ngFor="let table of selectedTables"
            class="table-item"
            [class.expanded]="expandedTables.has(table.name)"
          >
            <!-- Table Header -->
            <button
              class="table-header-btn"
              (click)="toggleTable(table.name)"
              type="button"
            >
              <span class="expand-icon" [class.expanded]="expandedTables.has(table.name)">
                ▶
              </span>
              <span class="table-name">📋 {{ table.name }}</span>
              <span class="table-meta">({{ table.rows }} rows)</span>
            </button>

            <!-- Columns -->
            <div class="columns-list" *ngIf="expandedTables.has(table.name)">
              <div
                *ngFor="let col of table.columns"
                class="column-item"
                draggable="true"
                (dragstart)="onColumnDragStart($event, col, table.name)"
                [title]="col.type"
              >
                <span class="column-icon">📊</span>
                <span class="column-name">{{ col.name }}</span>
                <span class="column-type">{{ col.type }}</span>
                <span 
                  class="nullable-badge"
                  *ngIf="col.nullable"
                >
                  NULL
                </span>
              </div>

              <button
                class="preview-btn"
                nz-button
                nzType="text"
                nzSize="small"
                (click)="previewTable(table.name)"
              >
                👁️ Preview Data
              </button>
            </div>
          </div>

          <div *ngIf="selectedTables.length === 0" class="empty-state">
            No tables found
          </div>
        </div>
      </div>

      <!-- Data Preview Modal -->
      <div class="preview-modal" *ngIf="previewData">
        <div class="modal-backdrop" (click)="closePreview()"></div>
        <div class="modal-content">
          <div class="modal-header">
            <h4>{{ previewData.connection }}.{{ previewData.table }}</h4>
            <button 
              nz-button 
              nzType="text"
              (click)="closePreview()"
            >
              ✕
            </button>
          </div>
          <div class="modal-body">
            <div class="preview-stats">
              Total rows: {{ previewData.total_rows }} | Showing: {{ previewData.rows.length }}
            </div>
            <table class="preview-table">
              <thead>
                <tr>
                  <th *ngFor="let col of previewData.columns">{{ col }}</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let row of previewData.rows">
                  <td *ngFor="let col of previewData.columns">{{ row[col] }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      .metadata-browser {
        padding: 12px;
        height: 100%;
        display: flex;
        flex-direction: column;
        background: #fafafa;
        border-left: 1px solid #f0f0f0;
        overflow-y: auto;
      }

      .browser-header {
        padding-bottom: 12px;
        border-bottom: 1px solid #e8e8e8;
        margin-bottom: 12px;
      }

      .browser-header h3 {
        margin: 0;
        font-size: 14px;
        font-weight: 600;
        color: #222;
      }

      .connections-section,
      .tables-section {
        margin-bottom: 16px;
        flex-shrink: 0;
      }

      .tables-section {
        flex: 1;
        overflow-y: auto;
      }

      .section-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        font-size: 12px;
        font-weight: 600;
        color: #666;
        margin-bottom: 8px;
      }

      .loading {
        text-align: center;
        color: #999;
        font-size: 12px;
        padding: 12px;
      }

      .connections-list {
        display: flex;
        flex-direction: column;
        gap: 4px;
        max-height: 200px;
        overflow-y: auto;
      }

      .connection-item {
        padding: 8px;
        background: white;
        border: 1px solid #e8e8e8;
        border-radius: 2px;
        cursor: pointer;
        transition: all 0.2s;
      }

      .connection-item:hover {
        background: #f5f5f5;
        border-color: #1890ff;
      }

      .connection-item.active {
        background: #e6f7ff;
        border-color: #1890ff;
      }

      .connection-name {
        font-size: 12px;
        font-weight: 500;
        margin-bottom: 2px;
      }

      .connection-meta {
        font-size: 11px;
        color: #999;
      }

      .tables-list {
        display: flex;
        flex-direction: column;
        gap: 4px;
        max-height: 600px;
        overflow-y: auto;
      }

      .table-item {
        border: 1px solid #e8e8e8;
        border-radius: 2px;
        background: white;
        overflow: hidden;
      }

      .table-header-btn {
        width: 100%;
        padding: 8px;
        border: none;
        background: #fafafa;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        transition: background 0.2s;
        text-align: left;
      }

      .table-header-btn:hover {
        background: #f0f0f0;
      }

      .expand-icon {
        display: inline-block;
        font-size: 10px;
        transition: transform 0.2s;
        transform: rotate(0deg);
        width: 14px;
        text-align: center;
      }

      .expand-icon.expanded {
        transform: rotate(90deg);
      }

      .table-name {
        flex: 1;
        font-weight: 500;
      }

      .table-meta {
        font-size: 11px;
        color: #999;
      }

      .columns-list {
        padding: 4px;
        border-top: 1px solid #f0f0f0;
        background: #fafafa;
        display: flex;
        flex-direction: column;
        gap: 2px;
      }

      .column-item {
        padding: 6px 8px;
        background: white;
        border: 1px solid #e8e8e8;
        border-radius: 2px;
        cursor: grab;
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 11px;
        transition: all 0.2s;
      }

      .column-item:hover {
        background: #f5f5f5;
        border-color: #1890ff;
        box-shadow: 0 1px 4px rgba(24, 144, 255, 0.2);
      }

      .column-item:active {
        cursor: grabbing;
      }

      .column-icon {
        font-size: 12px;
        flex-shrink: 0;
      }

      .column-name {
        flex: 1;
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .column-type {
        font-size: 10px;
        color: #999;
        background: #f0f0f0;
        padding: 2px 4px;
        border-radius: 2px;
        white-space: nowrap;
      }

      .nullable-badge {
        font-size: 9px;
        background: #fff7e6;
        color: #d4a574;
        padding: 2px 4px;
        border-radius: 2px;
        white-space: nowrap;
      }

      .preview-btn {
        width: 100%;
        margin-top: 4px;
        font-size: 11px;
        text-align: center;
      }

      .empty-state {
        text-align: center;
        color: #999;
        font-size: 11px;
        padding: 16px;
      }

      /* Preview Modal Styles */
      .preview-modal {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 1000;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .modal-backdrop {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.45);
        cursor: pointer;
      }

      .modal-content {
        position: relative;
        background: white;
        border-radius: 4px;
        max-width: 800px;
        max-height: 600px;
        width: 90%;
        display: flex;
        flex-direction: column;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
      }

      .modal-header {
        padding: 12px 16px;
        border-bottom: 1px solid #e8e8e8;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .modal-header h4 {
        margin: 0;
        font-size: 13px;
        font-weight: 600;
      }

      .modal-body {
        flex: 1;
        padding: 12px 16px;
        overflow-y: auto;
      }

      .preview-stats {
        font-size: 11px;
        color: #999;
        margin-bottom: 12px;
      }

      .preview-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 11px;
      }

      .preview-table th {
        background: #fafafa;
        padding: 6px;
        text-align: left;
        border-bottom: 2px solid #e8e8e8;
        font-weight: 600;
        color: #666;
      }

      .preview-table td {
        padding: 6px;
        border-bottom: 1px solid #f0f0f0;
      }

      .preview-table tr:hover {
        background: #f9f9f9;
      }
    `,
  ],
})
export class MetadataBrowserComponent implements OnInit {
  @Output() columnSelected = new EventEmitter<any>();

  connections: Connection[] = [];
  selectedConnection: Connection | null = null;
  selectedTables: Table[] = [];
  expandedTables: Set<string> = new Set();
  previewData: any = null;

  loading = false;
  loadingTables = false;

  constructor(
    private http: HttpClient,
    private message: NzMessageService
  ) {}

  ngOnInit(): void {
    this.refreshConnections();
  }

  refreshConnections(): void {
    this.loading = true;
    this.http.get<Connection[]>('/api/metadata/connections').subscribe(
      (data) => {
        this.connections = data;
        this.loading = false;
      },
      (error) => {
        this.message.error('Failed to load connections');
        this.loading = false;
      }
    );
  }

  selectConnection(conn: Connection): void {
    this.selectedConnection = conn;
    this.expandedTables.clear();
    this.loadTables();
  }

  loadTables(): void {
    if (!this.selectedConnection) return;

    this.loadingTables = true;
    this.http
      .get<Table[]>(
        `/api/metadata/connections/${this.selectedConnection.id}/tables`
      )
      .subscribe(
        (data) => {
          this.selectedTables = data;
          this.loadingTables = false;
        },
        (error) => {
          this.message.error('Failed to load tables');
          this.loadingTables = false;
        }
      );
  }

  toggleTable(tableName: string): void {
    if (this.expandedTables.has(tableName)) {
      this.expandedTables.delete(tableName);
    } else {
      this.expandedTables.add(tableName);
    }
  }

  onColumnDragStart(event: DragEvent, column: Column, tableName: string): void {
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = 'copy';
      event.dataTransfer.setData(
        'metadata-column',
        JSON.stringify({
          connection: this.selectedConnection?.id,
          table: tableName,
          column: column.name,
          type: column.type,
          nullable: column.nullable,
        })
      );
    }
    this.columnSelected.emit({ column, tableName });
  }

  previewTable(tableName: string): void {
    if (!this.selectedConnection) return;

    this.http
      .get(
        `/api/metadata/connections/${this.selectedConnection.id}/tables/${tableName}/preview`
      )
      .subscribe(
        (data: any) => {
          this.previewData = data;
        },
        (error) => {
          this.message.error('Failed to load preview data');
        }
      );
  }

  closePreview(): void {
    this.previewData = null;
  }
}
