import { create } from 'zustand';

export type StartupPhase = 'starting' | 'launching_daemon' | 'initializing_workspace' | 'connecting' | 'ready' | 'failed';

interface StartupState {
  phase: StartupPhase;
  error: string | null;
  reconnectAttempts: number;
  setPhase: (phase: StartupPhase, error?: string | null) => void;
  incrementAttempts: () => void;
  reset: () => void;
}

export const useStartupState = create<StartupState>((set) => ({
  phase: 'starting',
  error: null,
  reconnectAttempts: 0,
  setPhase: (phase, error = null) => set({ phase, error }),
  incrementAttempts: () => set((s) => ({ reconnectAttempts: s.reconnectAttempts + 1 })),
  reset: () => set({ phase: 'starting', error: null, reconnectAttempts: 0 }),
}));
