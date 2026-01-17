import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { ApiService } from './api.service';
import { ComponentMetadata } from '../models/types';

/**
 * Component Registry Service - Manages available components
 */
@Injectable({
  providedIn: 'root',
})
export class ComponentRegistryService {
  private componentsSubject = new BehaviorSubject<ComponentMetadata[]>([]);
  private loadingSubject = new BehaviorSubject<boolean>(false);

  public components$ = this.componentsSubject.asObservable();
  public loading$ = this.loadingSubject.asObservable();

  constructor(private apiService: ApiService) {
    this.loadComponents();
  }

  /**
   * Load all available components from backend
   */
  private loadComponents(): void {
    this.loadingSubject.next(true);
    this.apiService.listComponents().subscribe({
      next: (components) => {
        this.componentsSubject.next(components);
        this.loadingSubject.next(false);
      },
      error: (error) => {
        console.error('Error loading components:', error);
        this.loadingSubject.next(false);
      },
    });
  }

  /**
   * Get all components
   */
  getComponents(): Observable<ComponentMetadata[]> {
    return this.components$;
  }

  /**
   * Get components by category
   */
  getComponentsByCategory(category: string): Observable<ComponentMetadata[]> {
    return new Observable((observer) => {
      this.components$.subscribe((components) => {
        observer.next(components.filter((c) => c.category === category));
        observer.complete();
      });
    });
  }

  /**
   * Get specific component metadata
   */
  getComponent(type: string): Observable<ComponentMetadata> {
    return this.apiService.getComponent(type);
  }

  /**
   * Get component by type
   */
  getComponentByType(type: string): ComponentMetadata | undefined {
    return this.componentsSubject.value.find((c) => c.type === type);
  }

  /**
   * Get all categories
   */
  getCategories(): string[] {
    const components = this.componentsSubject.value;
    const categories = new Set(components.map((c) => c.category));
    return Array.from(categories).sort();
  }

  /**
   * Refresh components list
   */
  refreshComponents(): void {
    this.loadComponents();
  }
}
