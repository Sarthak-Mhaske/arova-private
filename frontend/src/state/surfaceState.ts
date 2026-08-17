import { create } from 'zustand';

export type SurfaceType = 
  | 'presence' | 'work'
  | 'cognition' | 'threads' | 'memory' | 'timeline'
  | 'environment' | 'workspace' | 'awareness'
  | 'system' | 'settings' 
  | 'command_palette'
  | 'session_timeline'
  | 'developer_mode'
  | 'journal'
  | null;

interface SurfaceState {
  activeSurface: SurfaceType;
  activeTab: string | null;
  openSurface: (surface: SurfaceType, tab?: string | null) => void;
  closeSurface: () => void;
  setActiveTab: (tab: string | null) => void;
}

export const useSurfaceState = create<SurfaceState>((set) => ({
  activeSurface: null,
  activeTab: null,
  openSurface: (activeSurface, activeTab = null) => set({ activeSurface, activeTab: activeTab ?? null }),
  closeSurface: () => set({ activeSurface: null, activeTab: null }),
  setActiveTab: (activeTab) => set({ activeTab }),
}));
