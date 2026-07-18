import { mockStreamItems, mockAwarenessFragments, mockSensings } from './mock';
import type { StreamItem, AwarenessFragment } from '../state';

// In a real Tauri app, these would use `@tauri-apps/api/core/invoke`
export const fetchStreamItems = async (): Promise<StreamItem[]> => {
  return new Promise(resolve => setTimeout(() => resolve(mockStreamItems), 300));
};

export const fetchAwareness = async (): Promise<AwarenessFragment[]> => {
  return new Promise(resolve => setTimeout(() => resolve(mockAwarenessFragments), 200));
};

export const sendUserInput = async (text: string): Promise<void> => {
  console.log('Sending user input to backend:', text);
  return new Promise(resolve => setTimeout(resolve, 500));
};

// Cyclic ambient awareness updates
let sensingIdx = 0;
export const getNextSensing = (): { key: string; value: string } => {
  const [key, value] = mockSensings[sensingIdx % mockSensings.length];
  sensingIdx++;
  return { key, value };
};

export const executeThreadAction = async (action: string, thread_id: string, payload: any = {}): Promise<void> => {
  console.log(`Executing thread action ${action} for ${thread_id}`);
  window.dispatchEvent(new CustomEvent('arova-send', {
    detail: {
      type: 'intention.thread_action',
      action,
      thread_id,
      payload
    }
  }));
};
