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
          <button
            class="category-title"
            (click)="toggleCategory(category)"
            type="button"
          >
            <span class="expand-icon" [class.expanded]="expandedCategories.has(category)">
              ▶
            </span>
            <span class="category-name">{{ category }}</span>
            <span class="component-count">
              ({{ getFilteredComponentsByCategory(category).length }})
            </span>
          </button>

          <div 
            class="components-list"
            *ngIf="expandedCategories.has(category)"
            [@slideDown]
          >
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
        padding: 12px;
        height: 100%;
        overflow-y: auto;
        background: #fafafa;
        border-right: 1px solid #f0f0f0;
      }

      .palette h3 {
        margin: 0 0 12px 0;
        font-size: 14px;
        font-weight: 600;
        color: #222;
      }

      .search-input {
        width: 100%;
        margin-bottom: 12px;
        font-size: 12px;
      }

      .loading {
        text-align: center;
        color: #999;
        padding: 20px;
        font-size: 12px;
      }

      .no-results {
        text-align: center;
        color: #999;
        padding: 20px;
        font-size: 12px;
      }

      .categories {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }

      .category {
        border-radius: 2px;
        background: white;
        border: 1px solid #e8e8e8;
        overflow: hidden;
      }

      .category-title {
        width: 100%;
        margin: 0;
        padding: 8px 10px;
        background: #f5f5f5;
        border: none;
        border-bottom: 1px solid #e8e8e8;
        font-size: 12px;
        font-weight: 600;
        color: #333;
        cursor: pointer;
        transition: all 0.2s;
        display: flex;
        align-items: center;
        gap: 6px;
        text-align: left;
      }

      .category-title:hover {
        background: #efefef;
      }

      .category-title:active {
        background: #e8e8e8;
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

      .category-name {
        flex: 1;
        font-weight: 600;
      }

      .component-count {
        font-size: 11px;
        color: #999;
        font-weight: normal;
      }

      .components-list {
        padding: 6px;
        display: flex;
        flex-direction: column;
        gap: 6px;
        border-bottom: 1px solid #e8e8e8;
      }

      .component-item {
        padding: 8px 10px;
        background: #fafafa;
        border: 1px solid #e8e8e8;
        border-radius: 2px;
        cursor: grab;
        transition: all 0.2s;
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
      }

      .component-item:hover {
        background: #f0f7ff;
        border-color: #1890ff;
        box-shadow: 0 1px 4px rgba(24, 144, 255, 0.2);
      }

      .component-item:active {
        cursor: grabbing;
        background: #e6f7ff;
      }

      .component-icon {
        font-size: 14px;
        flex-shrink: 0;
      }

      .component-name {
        flex: 1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        color: #333;
        font-weight: 500;
      }
    `,
  ],
  animations: [
    // Using CSS transitions instead of animations for simplicity
  ],
})
export class ComponentPaletteComponent implements OnInit {
  @Output() componentSelected = new EventEmitter<ComponentMetadata>();

  components: ComponentMetadata[] = [];
  filteredComponents: ComponentMetadata[] = [];
  categories: string[] = [];
  filteredCategories: string[] = [];
  searchTerm: string = '';
  expandedCategories: Set<string> = new Set();
  loading$ = this.componentRegistry.loading$;

  constructor(private componentRegistry: ComponentRegistryService) {}

  ngOnInit(): void {
    this.componentRegistry.components$.subscribe((components) => {
      this.components = components;
      this.filteredComponents = components;
      this.categories = this.componentRegistry.getCategories();
      this.filteredCategories = this.categories;
      
      // Expand all categories by default
      this.categories.forEach(cat => this.expandedCategories.add(cat));
    });
  }

  onSearchChange(): void {
    if (!this.searchTerm.trim()) {
      this.filteredComponents = this.components;
      this.filteredCategories = this.categories;
    } else {
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
  }

  toggleCategory(category: string): void {
    if (this.expandedCategories.has(category)) {
      this.expandedCategories.delete(category);
    } else {
      this.expandedCategories.add(category);
    }
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
