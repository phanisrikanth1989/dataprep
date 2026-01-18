import { Component, OnInit, Output, EventEmitter } from '@angular/core';
import { ComponentRegistryService } from '../../core/services/component-registry.service';
import { ComponentMetadata } from '../../core/models/types';

/**
 * Component Palette Component
 * Displays draggable components organized by category with search functionality
 */
@Component({
  selector: 'app-component-palette',
  template: `
    <div class="palette">
      <h3>Components</h3>

      <!-- Search Input -->
      <input
        type="text"
        nz-input
        placeholder="Type to search components..."
        [(ngModel)]="searchTerm"
        (input)="onSearchChange()"
        class="search-input"
      />

      <div *ngIf="loading$ | async" class="loading">
        Loading components...
      </div>

      <div *ngIf="filteredComponents.length === 0 && !(loading$ | async)" class="no-results">
        No components found
      </div>

      <div class="categories">
        <div
          *ngFor="let category of filteredCategories"
          class="category"
        >
          <h4 class="category-title">{{ category }}</h4>

          <div class="components-list">
            <div
              *ngFor="let component of getFilteredComponentsByCategory(category)"
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
        margin: 0 0 10px 0;
        font-size: 13px;
        font-weight: 600;
      }

      .search-input {
        width: 100%;
        margin-bottom: 12px;
      }

      .loading {
        text-align: center;
        color: #999;
        padding: 20px;
      }

      .no-results {
        text-align: center;
        color: #999;
        padding: 20px;
        font-size: 13px;
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
        font-size: 16px;
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
  filteredComponents: ComponentMetadata[] = [];
  categories: string[] = [];
  filteredCategories: string[] = [];
  searchTerm: string = '';
  loading$ = this.componentRegistry.loading$;

  constructor(private componentRegistry: ComponentRegistryService) {}

  ngOnInit(): void {
    this.componentRegistry.components$.subscribe((components) => {
      this.components = components;
      this.filteredComponents = components;
      this.categories = this.componentRegistry.getCategories();
      this.filteredCategories = this.categories;
    });
  }

  onSearchChange(): void {
    if (!this.searchTerm.trim()) {
      this.filteredComponents = this.components;
      this.filteredCategories = this.categories;
      return;
    }

    const term = this.searchTerm.toLowerCase();
    this.filteredComponents = this.components.filter(
      (c) =>
        c.label.toLowerCase().includes(term) ||
        c.description?.toLowerCase().includes(term) ||
        c.type.toLowerCase().includes(term)
    );

    // Only show categories that have filtered components
    this.filteredCategories = this.categories.filter(
      (cat) =>
        this.filteredComponents.filter((c) => c.category === cat).length > 0
    );
  }

  getFilteredComponentsByCategory(category: string): ComponentMetadata[] {
    return this.filteredComponents.filter((c) => c.category === category);
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
