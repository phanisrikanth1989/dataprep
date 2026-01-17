import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, Subject } from 'rxjs';
import { io, Socket } from 'socket.io-client';
import { environment } from '../../../environments/environment';
import { ExecutionStatus } from '../models/types';

/**
 * WebSocket Service - Real-time execution updates
 * Connects to: ws://localhost:8000/ws/execution/{task_id}
 */
@Injectable({
  providedIn: 'root',
})
export class WebSocketService {
  private socket: Socket | null = null;
  private currentTaskId: string = '';

  // Subjects for emitting updates
  private executionUpdateSubject = new Subject<ExecutionStatus>();
  private connectionStatusSubject = new BehaviorSubject<boolean>(false);
  private errorSubject = new Subject<string>();

  // Public observables
  public executionUpdate$ = this.executionUpdateSubject.asObservable();
  public connectionStatus$ = this.connectionStatusSubject.asObservable();
  public error$ = this.errorSubject.asObservable();

  constructor() {}

  /**
   * Connect to WebSocket for execution updates
   * @param taskId Task ID to monitor
   * @returns Promise that resolves when connected
   */
  connect(taskId: string): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.currentTaskId = taskId;
        const wsUrl = `${environment.wsUrl}/ws/execution/${taskId}`;

        this.socket = io(environment.wsUrl, {
          path: `/ws/execution/${taskId}`,
          transports: ['websocket', 'polling'],
          reconnection: true,
          reconnectionDelay: 1000,
          reconnectionDelayMax: 5000,
          reconnectionAttempts: 5,
        });

        // Connection established
        this.socket.on('connect', () => {
          console.log(`WebSocket connected: ${taskId}`);
          this.connectionStatusSubject.next(true);
          resolve();
        });

        // Receive execution updates
        this.socket.on('update', (data: ExecutionStatus) => {
          console.log('Execution update received:', data);
          this.executionUpdateSubject.next(data);
        });

        // Handle messages (for compatibility)
        this.socket.on('message', (data: ExecutionStatus) => {
          console.log('Execution message received:', data);
          this.executionUpdateSubject.next(data);
        });

        // Connection error
        this.socket.on('error', (error: any) => {
          console.error('WebSocket error:', error);
          this.errorSubject.next(error);
          reject(error);
        });

        // Disconnection
        this.socket.on('disconnect', (reason: string) => {
          console.log('WebSocket disconnected:', reason);
          this.connectionStatusSubject.next(false);
        });

        // Reconnection attempt
        this.socket.on('reconnect_attempt', () => {
          console.log('WebSocket reconnection attempt...');
        });
      } catch (error) {
        console.error('WebSocket connection error:', error);
        this.errorSubject.next(String(error));
        reject(error);
      }
    });
  }

  /**
   * Disconnect WebSocket
   */
  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
      this.connectionStatusSubject.next(false);
      console.log('WebSocket disconnected');
    }
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.connectionStatusSubject.value;
  }

  /**
   * Get current task ID
   */
  getCurrentTaskId(): string {
    return this.currentTaskId;
  }

  /**
   * Emit custom message (if needed)
   */
  emit(event: string, data: any): void {
    if (this.socket) {
      this.socket.emit(event, data);
    }
  }

  /**
   * Listen for custom event
   */
  on(event: string): Observable<any> {
    return new Observable((observer) => {
      if (this.socket) {
        this.socket.on(event, (data) => {
          observer.next(data);
        });
      }
    });
  }
}
