import { create } from 'zustand';

export type PresenceMode = 'ambient' | 'focus' | 'deep';
export type AtmosphereMode = 'daylight' | 'nocturne';

interface PresenceState {
  mode: PresenceMode;
  atmosphere: AtmosphereMode;
  setMode: (mode: PresenceMode) => void;
  setAtmosphere: (atm: AtmosphereMode) => void;
}

const getInitialAtmosphere = (): AtmosphereMode => {
  try {
    const stored = localStorage.getItem('arova-theme');
    if (stored === 'daylight' || stored === 'nocturne') return stored;
  } catch (e) {
    // silent fail
  }
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'nocturne';
  return 'daylight';
};

const getInitialMode = (): PresenceMode => {
  try {
    const stored = localStorage.getItem('arova-mode') as PresenceMode;
    if (stored && ['ambient', 'focus', 'deep'].includes(stored)) return stored;
  } catch (e) {
    // silent fail
  }
  return 'ambient';
};

export const usePresenceState = create<PresenceState>((set) => ({
  mode: getInitialMode(),
  atmosphere: getInitialAtmosphere(),
  setMode: (mode) => {
    try {
      localStorage.setItem('arova-mode', mode);
    } catch (e) {
      // silent fail
    }
    set({ mode });
  },
  setAtmosphere: (atm) => {
    try {
      localStorage.setItem('arova-theme', atm);
    } catch (e) {
      // silent fail
    }
    set({ atmosphere: atm });
  },
}));
