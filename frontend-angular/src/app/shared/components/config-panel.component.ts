import { Component, OnInit, Input, Output, EventEmitter } from '@angular/core';
import { FormBuilder, FormGroup, FormControl, Validators } from '@angular/forms';
import { JobNode } from '../../core/models/types';
import { NzMessageService } from 'ng-zorro-antd/message';

/**
 * Configuration Panel Component
 * Dynamic form generator for component configuration
 */
@Component({
  selector: 'app-config-panel',
  template: `
    <div class="config-panel">
      <div *ngIf="!selectedNode" class="empty-state">
        <p>Select a component to configure</p>
      </div>

      <div *ngIf="selectedNode" class="config-content">
        <h3>{{ selectedNode.label }} Configuration</h3>

        <form [formGroup]="configForm" (ngSubmit)="onSave()">
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
      </div>
    </div>
  `,
  styles: [
    `
      .config-panel {
        padding: 20px;
        height: 100%;
        overflow-y: auto;
        border-left: 1px solid #f0f0f0;
        background: #fafafa;
      }

      .empty-state {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: #999;
      }

      .config-content h3 {
        margin-bottom: 16px;
        font-size: 13px;
        font-weight: 600;
      }

      .form-field {
        margin-bottom: 16px;
      }

      label {
        display: block;
        margin-bottom: 6px;
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
      }

      .description {
        display: block;
        margin-top: 4px;
        color: #999;
        font-size: 11px;
      }

      .divider {
        height: 1px;
        background: #e8e8e8;
        margin: 16px 0;
      }

      .rename-field {
        margin-bottom: 16px;
        padding-bottom: 16px;
      }

      .button-group {
        margin-top: 20px;
        display: flex;
        gap: 10px;
      }

      .button-group button {
        flex: 1;
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

  constructor(
    private fb: FormBuilder,
    private message: NzMessageService
  ) {}

  ngOnInit(): void {
    this.buildForm();
  }

  ngOnChanges(): void {
    this.buildForm();
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
