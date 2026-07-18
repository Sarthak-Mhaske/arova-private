import { create } from 'zustand';

export interface AwarenessFragment {
  key: string;
  value: string;
  accent?: 'accent' | 'thinking' | 'warm';
}

interface EnvironmentState {
  fragments: AwarenessFragment[];
  roomState: any;
  contextState: any;
  runtimeState: any;
  setFragments: (fragments: AwarenessFragment[]) => void;
  setRoomState: (state: any) => void;
  setContextState: (state: any) => void;
  setRuntimeState: (state: any) => void;
}

export const useEnvironmentState = create<EnvironmentState>((set) => ({
  fragments: [],
  roomState: null,
  contextState: null,
  runtimeState: null,
  setFragments: (fragments) => set({ fragments }),
  setRoomState: (roomState) => set({ roomState }),
  setContextState: (contextState) => set({ contextState }),
  setRuntimeState: (runtimeState) => set({ runtimeState }),
}));
