import type { WSEvent, WSMessageData, WSActivityData, WSToolCallData, WSToolResultData } from '@/types';

type EventCallback = (event: WSEvent) => void;
type ConnectionCallback = (connected: boolean) => void;

// Use WSS for HTTPS, WS for HTTP; connect through nginx proxy
// Using API v4 with single-agent notepad-driven flow
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_URL = `${protocol}//${window.location.host}/api/v4/conversation/ws`;

// Persistence keys for localStorage
const USER_ID_KEY = 'moja-dzialka-user-id';
const SESSION_ID_KEY = 'moja-dzialka-session-id';

// Get or create persistent user ID
function getOrCreateUserId(): string {
  let userId = localStorage.getItem(USER_ID_KEY);
  if (!userId) {
    userId = crypto.randomUUID();
    localStorage.setItem(USER_ID_KEY, userId);
    console.log('[WS] Created new user ID:', userId);
  }
  return userId;
}

// Get stored session ID (may be null)
function getSessionId(): string | null {
  return localStorage.getItem(SESSION_ID_KEY);
}

// Store session ID received from server
function storeSessionId(sessionId: string): void {
  localStorage.setItem(SESSION_ID_KEY, sessionId);
}

class WebSocketService {
  private ws: WebSocket | null = null;
  private eventListeners: Set<EventCallback> = new Set();
  private connectionListeners: Set<ConnectionCallback> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private shouldReconnect = true;

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      this.ws = new WebSocket(WS_URL);

      this.ws.onopen = () => {
        console.log('[WS] Connected');
        this.reconnectAttempts = 0;
        this.notifyConnectionChange(true);

        // Send init message with persistent user_id and session_id
        const userId = getOrCreateUserId();
        const sessionId = getSessionId();
        console.log('[WS] Init with user:', userId, 'session:', sessionId);
        this.send({
          type: 'init',
          user_id: userId,
          session_id: sessionId,
        });
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WSEvent;
          // Validate event structure before notifying
          if (!data || typeof data.type !== 'string') {
            console.warn('[WS] Invalid event structure:', data);
            return;
          }

          // Store session_id when we receive session event (v4: has notepad, v2: had state)
          if (data.type === 'session' && data.data) {
            const sessionData = data.data as { session_id?: string; notepad?: unknown };
            if (sessionData.session_id) {
              storeSessionId(sessionData.session_id);
              console.log('[WS] Stored session ID:', sessionData.session_id);
            }
          }

          this.notifyEvent(data);
        } catch (error) {
          console.error('[WS] Message handling error:', error, 'Raw:', event.data?.substring?.(0, 200));
        }
      };

      this.ws.onclose = (event) => {
        console.log('[WS] Disconnected:', event.code, event.reason);
        this.notifyConnectionChange(false);

        if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = (error) => {
        console.error('[WS] Error:', error);
      };
    } catch (error) {
      console.error('[WS] Connection error:', error);
      this.notifyConnectionChange(false);
    }
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  send(data: object): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn('[WS] Cannot send - not connected');
    }
  }

  sendMessage(content: string): void {
    this.send({
      type: 'message',
      content,
    });
  }

  onEvent(callback: EventCallback): () => void {
    this.eventListeners.add(callback);
    return () => this.eventListeners.delete(callback);
  }

  onConnectionChange(callback: ConnectionCallback): () => void {
    this.connectionListeners.add(callback);
    return () => this.connectionListeners.delete(callback);
  }

  private notifyEvent(event: WSEvent): void {
    this.eventListeners.forEach((cb) => {
      try {
        cb(event);
      } catch (error) {
        console.error('[WS] Event handler error for type:', event.type, error);
      }
    });
  }

  private notifyConnectionChange(connected: boolean): void {
    this.connectionListeners.forEach((cb) => cb(connected));
  }

  private scheduleReconnect(): void {
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    setTimeout(() => this.connect(), delay);
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// Export singleton instance
export const wsService = new WebSocketService();

// Helper function to parse events
export function parseWSEvent(event: WSEvent): {
  type: WSEvent['type'];
  message?: WSMessageData;
  activity?: WSActivityData;
  toolCall?: WSToolCallData;
  toolResult?: WSToolResultData;
} {
  switch (event.type) {
    case 'message':
      return { type: event.type, message: event.data as WSMessageData };
    case 'activity':
      return { type: event.type, activity: event.data as WSActivityData };
    case 'tool_call':
      return { type: event.type, toolCall: event.data as WSToolCallData };
    case 'tool_result':
      return { type: event.type, toolResult: event.data as WSToolResultData };
    default:
      return { type: event.type };
  }
}
