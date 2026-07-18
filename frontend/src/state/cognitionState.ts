import { create } from 'zustand';

export type StreamItemType = 'surfacing' | 'userSaid' | 'cognitionEvent' | 'memoryGhost';

export interface BaseStreamItem {
  id: string;
  type: StreamItemType;
  timestamp: number;
}

export type SurfacingKind = "memory" | "context" | "timeline" | "momentum";

export interface SurfacingItem extends BaseStreamItem {
  type: 'surfacing';
  kind?: SurfacingKind;
  from: string;
  lede?: string;
  paragraphs: string[];
  actions?: { 
    label: string; 
    primary?: boolean;
    eventType?: string;
    eventPayload?: any;
    clientAction?: 'open_timeline' | 'dismiss';
  }[];
}

export interface UserSaidItem extends BaseStreamItem {
  type: 'userSaid';
  text: string;
}

export interface CognitionEventItem extends BaseStreamItem {
  type: 'cognitionEvent';
  events: { text: string; state: 'active' | 'memory' | 'done' }[];
}

export interface MemoryGhostItem extends BaseStreamItem {
  type: 'memoryGhost';
  from: string;
  text: string;
}

export type StreamItem = SurfacingItem | UserSaidItem | CognitionEventItem | MemoryGhostItem;

interface CognitionState {
  items: StreamItem[];
  setItems: (items: StreamItem[]) => void;
  addItems: (items: StreamItem[]) => void;
  removeItems: (ids: string[]) => void;
  addUserInput: (text: string) => void;
  
  activeStreamId: string | null;
  
  // Append-only streaming support
  streamStart: (streamId: string) => void;
  streamDelta: (streamId: string, delta: string) => void;
  streamEnd: (streamId: string) => void;
  
  // Phase 3: Cognitive Threads
  threads: any[];
  setThreads: (threads: any[]) => void;
  
  // Phase 7: Semantic Memories
  memories: any[];
  setMemories: (memories: any[]) => void;
  
  // Phase 7.5: Intelligent Memory Consent System
  pendingMemories: any[];
  setPendingMemories: (memories: any[]) => void;
  sensitiveCandidate: any | null;
  setSensitiveCandidate: (candidate: any | null) => void;
  contextualCandidate: any | null;
  setContextualCandidate: (candidate: any | null) => void;
}

export const useCognitionState = create<CognitionState>((set) => ({
  items: [],
  threads: [],
  memories: [],
  activeStreamId: null,
  pendingMemories: [],
  sensitiveCandidate: null,
  contextualCandidate: null,
  setThreads: (threads) => set({ threads }),
  setMemories: (memories) => set({ memories }),
  setPendingMemories: (memories) => set({ pendingMemories: memories }),
  setSensitiveCandidate: (candidate) => set({ sensitiveCandidate: candidate }),
  setContextualCandidate: (candidate) => set({ contextualCandidate: candidate }),
  setItems: (newItems) => set((state) => {
    // If explicitly setting to empty, clear everything
    if (newItems.length === 0) {
      return { items: [] };
    }
    const newIds = new Set(newItems.map(i => i.id));
    const activeUnsaved = state.items.filter(i => !newIds.has(i.id));
    return { items: [...newItems, ...activeUnsaved] };
  }),
  addItems: (newItems) => set((state) => ({ items: [...state.items, ...newItems] })),
  removeItems: (ids) => set((state) => {
    const idSet = new Set(ids);
    return { items: state.items.filter(i => !idSet.has(i.id)) };
  }),
  addUserInput: (text) => set((state) => ({
    items: [...state.items, {
      id: Math.random().toString(36).substring(7),
      type: 'userSaid',
      timestamp: Date.now(),
      text
    }]
  })),
  
  streamStart: (streamId) => set((state) => {
    // Prevent duplicate stream start, but take ownership
    const existing = state.items.find(i => i.id === streamId);
    if (existing) {
      return { activeStreamId: streamId };
    }
    
    const newItem: SurfacingItem = {
      id: streamId,
      type: 'surfacing',
      timestamp: Date.now(),
      from: 'Arova',
      paragraphs: [''] // Start with one empty paragraph
    };
    return { items: [...state.items, newItem], activeStreamId: streamId };
  }),
  
  streamDelta: (streamId, delta) => set((state) => {
    console.log(`[cognitionState] streamDelta received for: ${streamId}. activeStreamId=${state.activeStreamId}`);
    if (state.activeStreamId !== streamId) {
      console.warn(`[runtime] Discarded stale delta for stream ${streamId}`);
      return state;
    }

    return {
      items: state.items.map(item => {
        if (item.id === streamId && item.type === 'surfacing') {
          // Append to the last paragraph
          const paragraphs = [...item.paragraphs];
          if (paragraphs.length > 0) {
            paragraphs[paragraphs.length - 1] += delta;
          } else {
            paragraphs.push(delta);
          }
          return { ...item, paragraphs };
        }
        return item;
      })
    };
  }),
  
  streamEnd: (streamId) => set((state) => {
    // Clear active ownership if this was the active stream
    if (state.activeStreamId === streamId) {
      return { activeStreamId: null };
    }
    return state;
  })
}));
