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
  
  lastExecutionMetadata: any | null;
  setLastExecutionMetadata: (meta: any | null) => void;
  
  activeAction: string | null;
  setActiveAction: (action: string | null) => void;
}

export const useCognitionState = create<CognitionState>((set) => ({
  items: [],
  threads: [],
  memories: [],
  activeStreamId: null,
  pendingMemories: [],
  sensitiveCandidate: null,
  contextualCandidate: null,
  lastExecutionMetadata: null,
  activeAction: null,
  setThreads: (threads) => set({ threads }),
  setMemories: (memories) => set({ memories }),
  setPendingMemories: (memories) => set({ pendingMemories: memories }),
  setSensitiveCandidate: (candidate) => set({ sensitiveCandidate: candidate }),
  setContextualCandidate: (candidate) => set({ contextualCandidate: candidate }),
  setLastExecutionMetadata: (meta) => set({ lastExecutionMetadata: meta }),
  setActiveAction: (action) => set({ activeAction: action }),
  setItems: (newItems) => set((state) => {
    if (newItems.length === 0) {
      return { items: [] };
    }
    
    // 1. Strictly deduplicate newItems by ID, keeping the latest occurrence
    const uniqueNewItems: StreamItem[] = [];
    const seenIds = new Set<string>();
    for (let i = newItems.length - 1; i >= 0; i--) {
      if (!seenIds.has(newItems[i].id)) {
        seenIds.add(newItems[i].id);
        uniqueNewItems.unshift(newItems[i]);
      }
    }
    
    // 2. Deduplicate user messages that are identical to the last seen user message
    const finalNewItems: StreamItem[] = [];
    let lastUserText = '';
    for (const item of uniqueNewItems) {
      if (item.type === 'userSaid') {
        if (item.text === lastUserText) {
          continue; // Skip if it's identical to the previous user message
        }
        lastUserText = item.text;
      }
      // Note: We deliberately do NOT reset lastUserText on non-user messages.
      // This prevents duplicates when the backend sends User -> Assistant -> User(Duplicate)
      finalNewItems.push(item);
    }
    
    // 3. Keep any in-flight active streams that weren't in the new list
    const finalNewIds = new Set(finalNewItems.map(i => i.id));
    const activeUnsaved = state.items.filter(i => 
      !finalNewIds.has(i.id) && 
      i.type !== 'userSaid' && 
      (i.type !== 'surfacing' || i.id === state.activeStreamId)
    );
    
    return { items: [...finalNewItems, ...activeUnsaved] };
  }),
  addItems: (newItems) => set((state) => ({ items: [...state.items, ...newItems] })),
  removeItems: (ids) => set((state) => {
    const idSet = new Set(ids);
    return { items: state.items.filter(i => !idSet.has(i.id)) };
  }),
  addUserInput: (text) => set((state) => {
    // Deduplicate rapid consecutive identical messages (fixes websocket echo bugs)
    const now = Date.now();
    const isDuplicate = state.items.some(item => 
      item.type === 'userSaid' && 
      item.text === text && 
      (now - item.timestamp) < 2000
    );
    
    if (isDuplicate) return state;

    return {
      items: [...state.items, {
        id: Math.random().toString(36).substring(7),
        type: 'userSaid',
        timestamp: now,
        text
      }]
    };
  }),
  
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
