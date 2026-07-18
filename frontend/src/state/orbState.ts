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
  isPulsing: boolean;
  modulation: CognitiveModulation;
  setMode: (mode: OrbMode) => void;
  setModulation: (mod: Partial<CognitiveModulation>) => void;
  triggerPulse: () => void;
}

export const useOrbState = create<OrbState>((set) => ({
  mode: 'present',
  isPulsing: false,
  modulation: {
    breathing_rhythm: 0.5,
    turbulence: 0.2,
    warmth: 0.5,
    saturation: 0.5
  },
  setMode: (mode) => set({ mode }),
  setModulation: (mod) => set((state) => ({ modulation: { ...state.modulation, ...mod } })),
  triggerPulse: () => {
    set({ isPulsing: true });
    setTimeout(() => {
      set({ isPulsing: false });
    }, 1000);
  }
}));
