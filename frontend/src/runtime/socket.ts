import { routeEvent } from './eventRouter';
import { invoke } from '@tauri-apps/api/core';
import { useStartupState } from '../state/startupState';

function feLog(msg: string) {
  console.log(msg);
  try {
    invoke('log_from_frontend', { msg }).catch(() => {});
  } catch (e) {}
}

class RuntimeSocket {
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private backoff = 400;
  private readonly maxBackoff = 2500;
  private isIntentionalDisconnect = false;
  private hasEverConnected = false;

  public connected = false;

  public connect(url: string = 'ws://127.0.0.1:8765') {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isIntentionalDisconnect = false;
    feLog(`[runtime] Initializing connection logic for ${url}...`);

    if (!this.hasEverConnected && useStartupState.getState().reconnectAttempts === 0 && useStartupState.getState().phase === 'starting') {
      setTimeout(() => {
        if (!this.hasEverConnected && useStartupState.getState().phase === 'starting') {
          useStartupState.getState().setPhase('launching_daemon');
        }
      }, 450);
      setTimeout(() => {
        if (!this.hasEverConnected && useStartupState.getState().phase === 'launching_daemon') {
          useStartupState.getState().setPhase('initializing_workspace');
        }
      }, 1200);
      setTimeout(() => {
        if (!this.hasEverConnected && useStartupState.getState().phase === 'initializing_workspace') {
          useStartupState.getState().setPhase('connecting');
        }
      }, 2200);

      // On cold boot, wait 350ms before creating WebSocket to allow daemon process initialization
      setTimeout(() => {
        this._rawConnect(url);
      }, 350);
    } else {
      this._rawConnect(url);
    }
  }

  private _rawConnect(url: string) {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    feLog(`[runtime] Opening WebSocket to ${url}...`);
    this.ws = new WebSocket(url);


    this.ws.onopen = () => {
      feLog('[runtime] Connected to daemon on ' + url);
      this.connected = true;
      this.hasEverConnected = true;
      this.backoff = 400;
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
      
      useStartupState.getState().setPhase('ready');

      routeEvent({
        v: 1,
        type: 'runtime.status',
        status: 'connected',
        source: 'local_socket'
      });

      // Request session history to hydrate the UI
      this.sendEvent({ type: 'session.sync_request' });
      this.sendEvent({ type: 'awareness.get_request' });
      this.sendEvent({ type: 'workspace.sync_request' });

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
        feLog('[runtime] Failed to parse incoming message: ' + String(err));
      }
    };

    this.ws.onclose = (event) => {
      this.connected = false;
      this.stopPing();
      feLog(`[runtime] Disconnected from daemon (code: ${event.code}, reason: ${event.reason}). Reconnecting...`);
      
      // Emit seamless reconnecting state so the UI never shows a crash
      routeEvent({
        v: 1,
        type: 'runtime.status',
        status: 'reconnecting',
        source: 'local_socket'
      });

      if (!this.isIntentionalDisconnect) {
        if (!this.hasEverConnected) {
          useStartupState.getState().incrementAttempts();
          const attempts = useStartupState.getState().reconnectAttempts;
          if (attempts >= 8) {
            useStartupState.getState().setPhase('failed', "Couldn't start local engine.");
            return;
          }
        }
        this.scheduleReconnect(url);
      }
    };

    this.ws.onerror = (err) => {
      feLog('[runtime] WebSocket onerror fired: ' + String(err));
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
    
    const delay = this.hasEverConnected ? this.backoff : 400;
    feLog(`[runtime] Reconnecting in ${delay}ms...`);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.backoff = Math.min(this.backoff * 1.5, this.maxBackoff);
      this.connect(url);
    }, delay);
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
      feLog(`[runtime] WebSocket.send() executing for: ${payload.type}`);
      this.ws.send(JSON.stringify(payload));
    } else {
      feLog(`[runtime] Cannot send event ${payload.type}, socket readyState is ${this.ws?.readyState}`);
    }
  }
}

export const socket = new RuntimeSocket();

if (typeof window !== 'undefined') {
  window.addEventListener('arova-send', ((e: CustomEvent) => {
    socket.sendEvent(e.detail);
  }) as EventListener);

  let syncTimer: any = null;
  const reSyncOnWake = () => {
    if (document.visibilityState === 'visible') {
      if (!socket.connected) {
        socket.connect();
      } else {
        if (syncTimer) clearTimeout(syncTimer);
        syncTimer = setTimeout(() => {
          socket.sendEvent({ type: 'session.sync_request' });
          socket.sendEvent({ type: 'awareness.get_request' });
        }, 100);
      }
    }
  };

  window.addEventListener('focus', reSyncOnWake);
  window.addEventListener('online', reSyncOnWake);
  document.addEventListener('visibilitychange', reSyncOnWake);
}
