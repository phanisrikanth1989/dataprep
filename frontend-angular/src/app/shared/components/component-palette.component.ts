import { Component, OnInit, Output, EventEmitter } from '@angular/core';
import { ComponentRegistryService } from '../../core/services/component-registry.service';
import { ComponentMetadata } from '../../core/models/types';

/**
 * Component Palette Component
 * Displays draggable components organized by category
 */
@Component({
  selector: 'app-component-palette',
  template: `
    <div class="palette">
      <h3>Components</h3>

      <div *ngIf="loading$ | async" class="loading">
        Loading components...
      </div>

      <div class="categories">
        <div
          *ngFor="let category of categories"
          class="category"
        >
          <h4 class="category-title">{{ category }}</h4>

          <div class="components-list">
            <div
              *ngFor="let component of getComponentsByCategory(category)"
              class="component-item"
              draggable="true"
              (dragstart)="onComponentDragStart($event, component)"
              [title]="component.description"
            >
              <div class="component-icon">📦</div>
              <div class="component-name">{{ component.label }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      .palette {
        padding: 16px;
        height: 100%;
        overflow-y: auto;
        background: #fafafa;
        border-right: 1px solid #f0f0f0;
      }

      .palette h3 {
        margin: 0 0 16px 0;
        font-size: 16px;
        font-weight: 600;
      }

      .loading {
        text-align: center;
        color: #999;
        padding: 20px;
      }

      .categories {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      .category {
        border-radius: 4px;
        background: white;
        border: 1px solid #f0f0f0;
        overflow: hidden;
      }

      .category-title {
        margin: 0;
        padding: 12px 12px;
        background: #fafafa;
        border-bottom: 1px solid #f0f0f0;
        font-size: 13px;
        font-weight: 600;
        color: #666;
      }

      .components-list {
        padding: 8px;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }

      .component-item {
        padding: 12px;
        background: white;
        border: 1px solid #e8e8e8;
        border-radius: 4px;
        cursor: grab;
        transition: all 0.2s;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .component-item:hover {
        background: #f5f5f5;
        border-color: #1890ff;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      }

      .component-item:active {
        cursor: grabbing;
      }

      .component-icon {
        font-size: 18px;
        flex-shrink: 0;
      }

      .component-name {
        flex: 1;
        font-size: 13px;
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
    `,
  ],
})
export class ComponentPaletteComponent implements OnInit {
  @Output() componentSelected = new EventEmitter<ComponentMetadata>();

  components: ComponentMetadata[] = [];
  categories: string[] = [];
  loading$ = this.componentRegistry.loading$;

  constructor(private componentRegistry: ComponentRegistryService) {}

  ngOnInit(): void {
    this.componentRegistry.components$.subscribe((components) => {
      this.components = components;
      this.categories = this.componentRegistry.getCategories();
    });
  }

  getComponentsByCategory(category: string): ComponentMetadata[] {
    return this.components.filter((c) => c.category === category);
  }

  onComponentDragStart(
    event: DragEvent,
    component: ComponentMetadata
  ): void {
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = 'copy';
      event.dataTransfer.setData('component', JSON.stringify(component));
    }
    this.componentSelected.emit(component);
  }
}
