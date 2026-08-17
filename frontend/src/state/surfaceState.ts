import { create } from 'zustand';

export type SurfaceType = 
  | 'presence' | 'work'
  | 'cognition' | 'threads' | 'memory' | 'timeline'
  | 'environment' | 'workspace' | 'awareness'
  | 'settings' 
  | 'command_palette'
  | 'session_timeline'
  | 'developer_mode'
  | 'journal'
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
