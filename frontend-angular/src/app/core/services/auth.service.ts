import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

export interface AuthUser {
  username: string;
  isAuthenticated: boolean;
}

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private currentUser$ = new BehaviorSubject<AuthUser | null>(null);
  private isAuthenticated$ = new BehaviorSubject<boolean>(false);

  // Hardcoded credentials for demo
  private readonly VALID_USERNAME = 'admin';
  private readonly VALID_PASSWORD = 'admin123';

  constructor() {
    this.loadAuthState();
  }

  /**
   * Load authentication state from localStorage
   */
  private loadAuthState(): void {
    const savedUser = localStorage.getItem('authUser');
    if (savedUser) {
      try {
        const user = JSON.parse(savedUser);
        this.currentUser$.next(user);
        this.isAuthenticated$.next(true);
      } catch (e) {
        console.error('Failed to load auth state', e);
        localStorage.removeItem('authUser');
      }
    }
  }

  /**
   * Login with username and password
   */
  login(username: string, password: string): Observable<boolean> {
    return new Observable((observer) => {
      // Simulate API delay
      setTimeout(() => {
        if (username === this.VALID_USERNAME && password === this.VALID_PASSWORD) {
          const user: AuthUser = {
            username,
            isAuthenticated: true,
          };
          this.currentUser$.next(user);
          this.isAuthenticated$.next(true);
          localStorage.setItem('authUser', JSON.stringify(user));
          observer.next(true);
          observer.complete();
        } else {
          observer.error(new Error('Invalid username or password'));
        }
      }, 500);
    });
  }

  /**
   * Logout
   */
  logout(): void {
    this.currentUser$.next(null);
    this.isAuthenticated$.next(false);
    localStorage.removeItem('authUser');
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): Observable<boolean> {
    return this.isAuthenticated$.asObservable();
  }

  /**
   * Get current user
   */
  getCurrentUser(): Observable<AuthUser | null> {
    return this.currentUser$.asObservable();
  }

  /**
   * Quick check for authentication (synchronous)
   */
  isAuthenticatedSync(): boolean {
    return this.isAuthenticated$.value;
  }
}
