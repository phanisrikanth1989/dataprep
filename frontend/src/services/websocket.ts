import { useEffect, useRef, useCallback } from 'react';
import { ExecutionUpdate } from '../types';

type UpdateCallback = (update: ExecutionUpdate) => void;

export const useWebSocket = () => {
  const connectionsRef = useRef<Record<string, WebSocket>>({});

  const connect = useCallback(
    (taskId: string, onUpdate: UpdateCallback) => {
      if (connectionsRef.current[taskId]) {
        return () => {};
      }

      const wsUrl = `${import.meta.env.VITE_WS_URL || 'ws://localhost:8000'}/api/execution/ws/${taskId}`;

      try {
        const ws = new WebSocket(wsUrl);

        ws.onmessage = (event) => {
          try {
            const update = JSON.parse(event.data);
            onUpdate(update);
          } catch (e) {
            console.error('Error parsing WebSocket message:', e);
          }
        };

        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          onUpdate({
            type: 'error',
            task_id: taskId,
            data: { error: 'WebSocket connection error' },
            timestamp: new Date().toISOString(),
          });
        };

        ws.onclose = () => {
          delete connectionsRef.current[taskId];
        };

        connectionsRef.current[taskId] = ws;

        // Return cleanup function
        return () => {
          if (connectionsRef.current[taskId]) {
            connectionsRef.current[taskId].close();
            delete connectionsRef.current[taskId];
          }
        };
      } catch (error) {
        console.error('Error connecting WebSocket:', error);
        return () => {};
      }
    },
    []
  );

  const disconnect = useCallback((taskId: string) => {
    if (connectionsRef.current[taskId]) {
      connectionsRef.current[taskId].close();
      delete connectionsRef.current[taskId];
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      Object.values(connectionsRef.current).forEach((ws) => ws.close());
      connectionsRef.current = {};
    };
  }, []);

  return { connect, disconnect };
};
