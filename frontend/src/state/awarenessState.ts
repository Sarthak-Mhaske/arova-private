import { create } from 'zustand';

export interface AwarenessLayer {
  enabled: boolean;
  allowed_apps: string[];
  description?: string;
}

export interface AwarenessPolicy {
  presence: AwarenessLayer;
  context: AwarenessLayer;
  deep_context: AwarenessLayer;
  memory_formation: AwarenessLayer;
  vision: AwarenessLayer;
}

interface AwarenessState {
  policy: AwarenessPolicy | null;
  hidden: string[];
  visible: Array<{ provider: string, activity: string, source: string, confidence: number }>;
  activeWorkspace: any | null;
  setPolicy: (policy: AwarenessPolicy) => void;
  setHidden: (hidden: string[]) => void;
  setVisible: (visible: any[]) => void;
  setActiveWorkspace: (ws: any | null) => void;
}

export const useAwarenessState = create<AwarenessState>((set) => ({
  policy: null,
  hidden: [],
  visible: [],
  activeWorkspace: null,
  setPolicy: (policy) => set({ policy }),
  setHidden: (hidden) => set({ hidden }),
  setVisible: (visible) => set({ visible }),
  setActiveWorkspace: (activeWorkspace) => set({ activeWorkspace }),
}));
