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

export interface AmbientSnapshot {
  active_app?: string | null;
  window_title?: string | null;
  workspace?: string | null;
  is_idle?: boolean;
  time_of_day?: string;
  open_windows?: string[];
  playing_media?: string[];
  attention_narrative?: string | null;
}

interface AwarenessState {
  policy: AwarenessPolicy | null;
  hidden: string[];
  visible: Array<{ provider: string, activity: string, source: string, confidence: number }>;
  activeWorkspace: any | null;
  continueCardDismissed: boolean;
  ambientSnapshot: AmbientSnapshot | null;
  setPolicy: (policy: AwarenessPolicy) => void;
  setHidden: (hidden: string[]) => void;
  setVisible: (visible: any[]) => void;
  setActiveWorkspace: (ws: any | null) => void;
  setAmbientSnapshot: (snapshot: AmbientSnapshot) => void;
  dismissContinueCard: () => void;
  resetContinueCard: () => void;
}

export const useAwarenessState = create<AwarenessState>((set) => ({
  policy: null,
  hidden: [],
  visible: [],
  activeWorkspace: null,
  continueCardDismissed: false,
  ambientSnapshot: null,
  setPolicy: (policy) => set({ policy }),
  setHidden: (hidden) => set({ hidden }),
  setVisible: (visible) => set({ visible }),
  setActiveWorkspace: (activeWorkspace) => set({ activeWorkspace }),
  setAmbientSnapshot: (ambientSnapshot) => set({ ambientSnapshot }),
  dismissContinueCard: () => set({ continueCardDismissed: true }),
  resetContinueCard: () => set({ continueCardDismissed: false }),
}));
