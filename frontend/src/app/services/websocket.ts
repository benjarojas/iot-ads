import { WsMessage } from '../types/domain';

type MessageHandler = (msg: WsMessage) => void;

class DashboardWebSocket {
  private ws: WebSocket | null = null;
  private handlers: Set<MessageHandler> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldConnect = false;
  private backoffMs = 1000;

  connect(): void {
    this.shouldConnect = true;
    this._open();
  }

  disconnect(): void {
    this.shouldConnect = false;
    if (this.reconnectTimer !== null) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }

  /** Subscribe to messages; returns an unsubscribe function. */
  onMessage(handler: MessageHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  private _open(): void {
    if (this.ws && this.ws.readyState < WebSocket.CLOSING) return;
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    this.ws = new WebSocket(`${protocol}://${location.host}/api/ws/dashboard`);

    this.ws.onopen = () => {
      this.backoffMs = 1000;
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const msg: WsMessage = JSON.parse(event.data as string);
        this.handlers.forEach(h => h(msg));
      } catch { /* ignore malformed */ }
    };

    this.ws.onclose = () => {
      this.ws = null;
      if (this.shouldConnect) {
        this.reconnectTimer = setTimeout(() => {
          this.backoffMs = Math.min(this.backoffMs * 2, 30_000);
          this._open();
        }, this.backoffMs);
      }
    };
  }
}

export const dashboardWs = new DashboardWebSocket();
