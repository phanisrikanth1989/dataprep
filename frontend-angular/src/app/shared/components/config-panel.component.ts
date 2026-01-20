import { Component, OnInit, Input, Output, EventEmitter } from '@angular/core';
import { FormBuilder, FormGroup, FormControl, Validators } from '@angular/forms';
import { JobNode } from '../../core/models/types';
import { NzMessageService } from 'ng-zorro-antd/message';

/**
 * Configuration Panel Component
 * Dynamic form generator for component configuration with optional schema editor
 */
@Component({
  selector: 'app-config-panel',
  template: `
    <div class="config-panel">
      <div *ngIf="!selectedNode" class="empty-state">
        <p>Select a component to configure</p>
      </div>

      <div *ngIf="selectedNode" class="config-content">
        <div class="tab-header">
          <h3 class="component-title">{{ selectedNode.label }} Configuration</h3>
          <div class="tabs">
            <button 
              class="tab-button"
              [class.active]="activeTab === 'config'"
              (click)="activeTab = 'config'"
              type="button"
            >
              Configuration
            </button>
            <button 
              *ngIf="isInputComponent()"
              class="tab-button"
              [class.active]="activeTab === 'schema'"
              (click)="activeTab = 'schema'"
              type="button"
            >
              Output Schema
            </button>
          </div>
        </div>

        <!-- Configuration Tab -->
        <form 
          [formGroup]="configForm" 
          (ngSubmit)="onSave()"
          *ngIf="activeTab === 'config'"
        >
          <!-- Rename field -->
          <div class="form-field rename-field">
            <label for="nodeName">
              Component Name (for development)
            </label>
            <input
              nz-input
              id="nodeName"
              placeholder="e.g., Read Customer Data"
              [formControl]="getFormControl('nodeName')"
            />
            <small class="description">
              Custom name to identify this component during development
            </small>
          </div>

          <div class="divider"></div>

          <div *ngFor="let field of fields" class="form-field">
            <label [for]="field.name">
              {{ field.label }}
              <span *ngIf="field.required" class="required">*</span>
            </label>

            <!-- Text input -->
            <input
              *ngIf="field.type === 'text'"
              nz-input
              [id]="field.name"

              [placeholder]="field.placeholder"
              [formControl]="getFormControl(field.name)"
            />

            <!-- Number input -->
            <input
              *ngIf="field.type === 'number'"
              nz-input
              type="number"
              [id]="field.name"
              [placeholder]="field.placeholder"
              [formControl]="getFormControl(field.name)"
            />

            <!-- Boolean toggle -->
            <label
              *ngIf="field.type === 'boolean'"
              nz-checkbox
              [formControl]="getFormControl(field.name)"
            >
              {{ field.label }}
            </label>

            <!-- Select dropdown -->
            <select
              *ngIf="field.type === 'select'"
              nz-select
              [id]="field.name"
              [formControl]="getFormControl(field.name)"
            >
              <option
                *ngFor="let option of field.options"
                [value]="option"
              >
                {{ option }}
              </option>
            </select>

            <!-- Expression/Text Area -->
            <textarea
              *ngIf="field.type === 'expression'"
              nz-input
              [id]="field.name"
              [placeholder]="field.placeholder"
              [formControl]="getFormControl(field.name)"
              rows="4"
            ></textarea>

            <small *ngIf="field.description" class="description">
              {{ field.description }}
            </small>
          </div>

          <div class="button-group">
            <button
              nz-button
              nzType="primary"
              [disabled]="configForm.invalid"
            >
              Save Configuration
            </button>
            <button nz-button (click)="onCancel()">Cancel</button>
          </div>
        </form>

        <!-- Schema Tab -->
        <div *ngIf="activeTab === 'schema' && isInputComponent()" class="schema-tab">
          <app-schema-editor
            [existingSchema]="selectedNode.config['output_schema'] || []"
            (schemaSaved)="onSchemaSaved($event)"
            (cancelled)="activeTab = 'config'"
          ></app-schema-editor>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      .config-panel {
        padding: 0;
        height: 100%;
        border-left: 1px solid #f0f0f0;
        background: #fafafa;
        overflow-y: auto;
        overflow-x: hidden;
        display: flex;
        flex-direction: column;
      }

      .empty-state {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: #999;
      }

      .config-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }

      .tab-header {
        padding: 12px 16px;
        background: white;
        border-bottom: 1px solid #e8e8e8;
        flex-shrink: 0;
      }

      .component-title {
        margin: 0 0 8px 0;
        font-size: 13px;
        font-weight: 600;
        color: #222;
      }

      .tabs {
        display: flex;
        gap: 4px;
      }

      .tab-button {
        padding: 6px 12px;
        font-size: 12px;
        border: 1px solid #e8e8e8;
        background: #f5f5f5;
        cursor: pointer;
        border-radius: 2px;
        transition: all 0.2s;
      }

      .tab-button:hover {
        background: #f0f0f0;
      }

      .tab-button.active {
        background: white;
        border-color: #1890ff;
        color: #1890ff;
        font-weight: 600;
      }

      .schema-tab {
        padding: 12px 16px;
        flex: 1;
        overflow-y: auto;
      }

      .config-content form {
        padding: 12px 16px;
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        grid-auto-flow: dense;
        flex: 1;
        overflow-y: auto;
      }

      .rename-field {
        grid-column: 1 / -1;
        margin-bottom: 8px;
        padding-bottom: 8px;
        border-bottom: 1px solid #e8e8e8;
      }

      .divider {
        grid-column: 1 / -1;
        height: 1px;
        background: #e8e8e8;
        margin: 0;
      }

      .form-field {
        margin-bottom: 0;
        padding: 0;
      }

      .form-field textarea {
        grid-column: 1 / -1;
      }

      label {
        display: block;
        margin-bottom: 4px;
        font-weight: 500;
        font-size: 12px;
      }

      .required {
        color: #ff4d4f;
      }

      input,
      select,
      textarea {
        width: 100%;
        font-size: 12px;
      }

      input[type="checkbox"] {
        width: auto;
        margin-right: 6px;
      }

      .description {
        display: block;
        margin-top: 2px;
        color: #999;
        font-size: 11px;
      }

      .button-group {
        grid-column: 1 / -1;
        margin-top: 12px;
        display: flex;
        gap: 8px;
      }

      .button-group button {
        flex: 1;
      }

      /* Make text areas shorter by default */
      textarea {
        min-height: 60px !important;
      }
    `,
  ],
})
export class ConfigPanelComponent implements OnInit {
  @Input() selectedNode: JobNode | null = null;
  @Input() fields: any[] = [];
  @Output() configUpdated = new EventEmitter<Record<string, any>>();
  @Output() cancelled = new EventEmitter<void>();

  configForm!: FormGroup;
  activeTab: 'config' | 'schema' = 'config';

  // Input component types that support schema definition
  INPUT_COMPONENT_TYPES = ['FileInputDelimited', 'FileTouch'];

  constructor(
    private fb: FormBuilder,
    private message: NzMessageService
  ) {}

  ngOnInit(): void {
    this.buildForm();
  }

  ngOnChanges(): void {
    this.buildForm();
    this.activeTab = 'config'; // Reset to config tab when component changes
  }

  /**
   * Check if the selected component is an input component that supports schema definition
   */
  isInputComponent(): boolean {
    if (!this.selectedNode) return false;
    return this.INPUT_COMPONENT_TYPES.includes(this.selectedNode.type);
  }

  private buildForm(): void {
    if (!this.selectedNode || !this.fields) {
      return;
    }

    const group: Record<string, any> = {};

    // Add nodeName field for custom naming during development
    group['nodeName'] = [this.selectedNode?.name || '', []];

    this.fields.forEach((field) => {
      const validators = [];
      if (field.required) {
        validators.push(Validators.required);
      }

      const value = this.selectedNode?.config[field.name] || field.default || '';
      group[field.name] = [value, validators];
    });

    this.configForm = this.fb.group(group);
  }

  onSave(): void {
    if (this.configForm.valid && this.selectedNode) {
      const updatedConfig = this.configForm.value;
      // Extract nodeName and separate it from component config
      const nodeName = updatedConfig.nodeName;
      delete updatedConfig.nodeName;
      
      // Emit with both config and nodeName
      this.configUpdated.emit({
        ...updatedConfig,
        _nodeName: nodeName,
      });
      this.message.success('Configuration saved');
    }
  }

  /**
   * Handle schema save from schema editor
   */
  onSchemaSaved(schema: any[]): void {
    if (this.selectedNode) {
      this.configUpdated.emit({
        output_schema: schema,
        _nodeName: this.selectedNode.name,
      });
      this.activeTab = 'config';
      this.message.success('Schema saved');
    }
  }

  onCancel(): void {
    this.cancelled.emit();
  }

  /**
   * Get form control with proper typing
   * Casts AbstractControl to FormControl to avoid type errors
   */
  getFormControl(fieldName: string): FormControl {
    return this.configForm.get(fieldName) as FormControl;
  }
}
