import { create } from 'zustand';

export type SurfaceType = 
  | 'presence'
  | 'cognition' | 'threads' | 'memory' | 'plans' | 'timeline'
  | 'environment' | 'context' | 'workspace' | 'attention' | 'awareness'
  | 'runtime' | 'agents' | 'calibration' | 'diagnostics'
  | 'settings' 
  | null;

interface SurfaceState {
  activeSurface: SurfaceType;
  openSurface: (surface: SurfaceType) => void;
  closeSurface: () => void;
}

export const useSurfaceState = create<SurfaceState>((set) => ({
  activeSurface: null,
  openSurface: (activeSurface) => set({ activeSurface }),
  closeSurface: () => set({ activeSurface: null }),
}));
