import { routeEvent } from './eventRouter';

class RuntimeSocket {
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private backoff = 1000;
  private readonly maxBackoff = 30000;
  private isIntentionalDisconnect = false;

  public connected = false;

  public connect(url: string = 'ws://localhost:8765') {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isIntentionalDisconnect = false;
    console.log(`[runtime] Connecting to ${url}...`);
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log('[runtime] Connected to daemon.');
      this.connected = true;
      this.backoff = 1000;
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
      
      // Request session history to hydrate the UI
      this.sendEvent({ type: 'session.sync_request' });
      this.sendEvent({ type: 'awareness.get_request' });

      // Start ping heartbeat
      this.startPing();
    };

    this.ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'runtime.pong') {
          return; // just a heartbeat response
        }
        routeEvent(payload);
      } catch (err) {
        console.error('[runtime] Failed to parse incoming message:', err);
      }
    };

    this.ws.onclose = () => {
      this.connected = false;
      this.stopPing();
      console.log('[runtime] Disconnected from daemon.');
      
      // Emit a local synthetic event to tell the UI the backend is gone
      routeEvent({
        v: 1,
        type: 'runtime.status',
        status: 'disconnected',
        source: 'local_socket'
      });

      if (!this.isIntentionalDisconnect) {
        this.scheduleReconnect(url);
      }
    };

    this.ws.onerror = (err) => {
      console.error('[runtime] WebSocket error:', err);
      // onclose will be called automatically
    };
  }

  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private startPing() {
    this.stopPing();
    this.pingTimer = setInterval(() => {
      this.sendEvent({ type: 'runtime.ping' });
    }, 15000);
  }
  
  private stopPing() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private scheduleReconnect(url: string) {
    if (this.reconnectTimer) return;
    
    console.log(`[runtime] Reconnecting in ${this.backoff}ms...`);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.backoff = Math.min(this.backoff * 1.5, this.maxBackoff);
      this.connect(url);
    }, this.backoff);
  }

  public disconnect() {
    this.isIntentionalDisconnect = true;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  public sendEvent(payload: Record<string, any>) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log(`[runtime] WebSocket.send() executing for: ${payload.type}`, payload);
      this.ws.send(JSON.stringify(payload));
    } else {
      console.warn(`[runtime] Cannot send event ${payload.type}, socket readyState is ${this.ws?.readyState}`, payload);
    }
  }
}

export const socket = new RuntimeSocket();

if (typeof window !== 'undefined') {
  window.addEventListener('arova-send', ((e: CustomEvent) => {
    socket.sendEvent(e.detail);
  }) as EventListener);
}
