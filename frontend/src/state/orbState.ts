import { create } from 'zustand';

export type OrbMode = 'present' | 'idle' | 'listening' | 'thinking' | 'streaming' | 'executing' | 'reflecting' | 'interrupted' | 'error' | 'disconnected' | 'reconnecting';

interface CognitiveModulation {
  breathing_rhythm: number; // 0.0 to 1.0
  turbulence: number;       // 0.0 to 1.0
  warmth: number;           // 0.0 to 1.0
  saturation: number;       // 0.0 to 1.0
}

interface OrbState {
  mode: OrbMode;
  details: string;
  rawState: string;
  isPulsing: boolean;
  modulation: CognitiveModulation;
  setMode: (mode: OrbMode, details?: string, rawState?: string) => void;
  setModulation: (mod: Partial<CognitiveModulation>) => void;
  triggerPulse: () => void;
}

let autoSettleTimer: ReturnType<typeof setTimeout> | null = null;

export const useOrbState = create<OrbState>((set, get) => ({
  mode: 'present',
  details: '',
  rawState: '',
  isPulsing: false,
  modulation: {
    breathing_rhythm: 0.5,
    turbulence: 0.2,
    warmth: 0.5,
    saturation: 0.5
  },
  setMode: (mode, details = '', rawState = '') => {
    if (autoSettleTimer) {
      clearTimeout(autoSettleTimer);
      autoSettleTimer = null;
    }
    set({ mode, details, rawState });

    // Dynamic auto-settle safety watchdog: if orb enters thinking/executing/reflecting, auto-settle after 7s
    if (['thinking', 'executing', 'reflecting'].includes(mode)) {
      autoSettleTimer = setTimeout(() => {
        if (['thinking', 'executing', 'reflecting'].includes(get().mode)) {
          set({ mode: 'present', details: '', rawState: 'idle' });
        }
      }, 7000);
    }
  },
  setModulation: (mod) => set((state) => ({ modulation: { ...state.modulation, ...mod } })),
  triggerPulse: () => {
    set({ isPulsing: true });
    setTimeout(() => {
      set({ isPulsing: false });
    }, 1000);
  }
}));
