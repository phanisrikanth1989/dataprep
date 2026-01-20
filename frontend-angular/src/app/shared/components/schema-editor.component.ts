import { Component, OnInit, Input, Output, EventEmitter } from '@angular/core';
import { FormBuilder, FormGroup, FormArray, FormControl, Validators } from '@angular/forms';
import { NzMessageService } from 'ng-zorro-antd/message';

/**
 * Schema Editor Component
 * Allows defining output schema columns for input components (like FileInputDelimited)
 * Similar to Talend's schema tab
 */
@Component({
  selector: 'app-schema-editor',
  template: `
    <div class="schema-editor">
      <div class="schema-header">
        <h4>Output Schema</h4>
        <button 
          nz-button 
          nzType="primary" 
          nzSize="small"
          (click)="addColumn()"
        >
          + Add Column
        </button>
      </div>

      <div class="schema-actions">
        <button 
          nz-button 
          nzSize="small"
          nzDanger
          (click)="clearSchema()"
          [disabled]="columns.length === 0"
        >
          Clear All
        </button>
      </div>

      <div *ngIf="columns.length === 0" class="empty-state">
        <p>No columns defined. Click "Add Column" to start defining schema.</p>
      </div>

      <form [formGroup]="schemaForm" *ngIf="columns.length > 0">
        <div class="schema-table">
          <!-- Header -->
          <div class="schema-row header">
            <div class="col col-position">#</div>
            <div class="col col-name">Column Name</div>
            <div class="col col-type">Data Type</div>
            <div class="col col-nullable">Nullable</div>
            <div class="col col-actions">Actions</div>
          </div>

          <!-- Rows -->
          <div 
            *ngFor="let column of columns; let i = index"
            class="schema-row"
            formArrayName="columns"
          >
            <div class="col col-position">{{ i + 1 }}</div>

            <div class="col col-name" [formGroupName]="i">
              <input
                nz-input
                type="text"
                formControlName="name"
                placeholder="e.g., customer_id"
                class="small-input"
              />
            </div>

            <div class="col col-type" [formGroupName]="i">
              <select nz-select formControlName="type" class="small-select">
                <option value="id_String">String</option>
                <option value="id_Integer">Integer</option>
                <option value="id_Long">Long</option>
                <option value="id_Float">Float</option>
                <option value="id_Double">Double</option>
                <option value="id_Boolean">Boolean</option>
                <option value="id_Date">Date</option>
                <option value="id_BigDecimal">Decimal</option>
              </select>
            </div>

            <div class="col col-nullable" [formGroupName]="i">
              <label nz-checkbox formControlName="nullable"></label>
            </div>

            <div class="col col-actions">
              <button
                nz-button
                nzType="text"
                nzDanger
                nzSize="small"
                (click)="removeColumn(i)"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      </form>

      <div class="schema-footer">
        <button 
          nz-button 
          nzType="primary"
          (click)="saveSchema()"
          [disabled]="!schemaForm.valid || columns.length === 0"
        >
          Save Schema
        </button>
        <button 
          nz-button 
          (click)="cancel()"
        >
          Cancel
        </button>
      </div>
    </div>
  `,
  styles: [
    `
      .schema-editor {
        padding: 12px;
        background: white;
        border-radius: 4px;
      }

      .schema-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
        border-bottom: 1px solid #e8e8e8;
        padding-bottom: 8px;
      }

      .schema-header h4 {
        margin: 0;
        font-size: 13px;
        font-weight: 600;
      }

      .schema-actions {
        margin-bottom: 12px;
        display: flex;
        gap: 8px;
      }

      .empty-state {
        text-align: center;
        color: #999;
        padding: 20px;
        font-size: 12px;
      }

      .schema-table {
        border: 1px solid #e8e8e8;
        border-radius: 2px;
        overflow: hidden;
        margin-bottom: 12px;
        max-height: 400px;
        overflow-y: auto;
      }

      .schema-row {
        display: grid;
        grid-template-columns: 40px 1fr 120px 80px 80px;
        gap: 8px;
        padding: 8px;
        border-bottom: 1px solid #f0f0f0;
        align-items: center;
      }

      .schema-row.header {
        background: #fafafa;
        font-weight: 600;
        font-size: 12px;
        color: #666;
        border-bottom: 2px solid #e8e8e8;
        padding: 10px 8px;
      }

      .schema-row:hover {
        background: #f9f9f9;
      }

      .col {
        font-size: 12px;
      }

      .col-position {
        text-align: center;
        color: #999;
      }

      .col-name {
        min-width: 0;
      }

      .col-type {
        min-width: 0;
      }

      .col-nullable {
        display: flex;
        justify-content: center;
      }

      .col-actions {
        display: flex;
        justify-content: center;
        gap: 4px;
      }

      .small-input,
      .small-select {
        font-size: 12px;
        height: 28px !important;
        padding: 4px 8px !important;
      }

      .schema-footer {
        display: flex;
        gap: 8px;
        justify-content: flex-end;
        padding-top: 8px;
        border-top: 1px solid #e8e8e8;
      }

      .schema-footer button {
        min-width: 80px;
      }
    `,
  ],
})
export class SchemaEditorComponent implements OnInit {
  @Input() existingSchema: any[] = [];
  @Output() schemaSaved = new EventEmitter<any[]>();
  @Output() cancelled = new EventEmitter<void>();

  schemaForm!: FormGroup;

  get columns(): any[] {
    return this.schemaForm.get('columns')?.value || [];
  }

  constructor(
    private fb: FormBuilder,
    private message: NzMessageService
  ) {}

  ngOnInit(): void {
    this.initializeForm();
  }

  private initializeForm(): void {
    const columns = this.fb.array(
      (this.existingSchema && this.existingSchema.length > 0)
        ? this.existingSchema.map((col) =>
            this.fb.group({
              name: [col.name || '', [Validators.required]],
              type: [col.type || 'id_String', [Validators.required]],
              nullable: [col.nullable !== false],
            })
          )
        : [this.createColumnGroup()]
    );

    this.schemaForm = this.fb.group({
      columns: columns,
    });
  }

  private createColumnGroup(): FormGroup {
    return this.fb.group({
      name: ['', [Validators.required]],
      type: ['id_String', [Validators.required]],
      nullable: [true],
    });
  }

  addColumn(): void {
    const columns = this.schemaForm.get('columns') as FormArray;
    columns.push(this.createColumnGroup());
  }

  removeColumn(index: number): void {
    const columns = this.schemaForm.get('columns') as FormArray;
    columns.removeAt(index);
  }

  clearSchema(): void {
    const columns = this.schemaForm.get('columns') as FormArray;
    while (columns.length > 0) {
      columns.removeAt(0);
    }
    this.message.warning('Schema cleared');
  }

  saveSchema(): void {
    if (this.schemaForm.valid) {
      const schema = this.columns.map((col) => ({
        name: col.name,
        type: col.type,
        nullable: col.nullable !== false,
      }));
      this.schemaSaved.emit(schema);
      this.message.success('Schema saved successfully');
    }
  }

  cancel(): void {
    this.cancelled.emit();
  }
}
