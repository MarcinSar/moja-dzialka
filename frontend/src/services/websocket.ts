import type { WSEvent, WSMessageData, WSActivityData, WSToolCallData, WSToolResultData } from '@/types';

type EventCallback = (event: WSEvent) => void;
type ConnectionCallback = (connected: boolean) => void;

// Use WSS for HTTPS, WS for HTTP; connect through nginx proxy
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_URL = `${protocol}//${window.location.host}/api/v1/conversation/ws`;

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

        // Send init message
        this.send({ type: 'init' });
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WSEvent;
          this.notifyEvent(data);
        } catch (error) {
          console.error('[WS] Failed to parse message:', error);
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
    this.eventListeners.forEach((cb) => cb(event));
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
