import { useOrbState } from '../state/orbState';
import { useCognitionState } from '../state/cognitionState';
import { useEnvironmentState } from '../state/environmentState';
import { useAwarenessState } from '../state/awarenessState';

export function routeEvent(event: any) {
  if (!event || typeof event !== 'object' || !event.type) {
    console.warn('[runtime] Invalid event received:', event);
    return;
  }

  // Global broadcast for any component listening directly
  window.dispatchEvent(new CustomEvent('arova-event', { detail: event }));

  console.log(`[runtime] Handling event: ${event.type}`, event);

  switch (event.type) {
    case 'orb.state':
      useOrbState.getState().setMode(event.state);
      break;

    case 'stream.start':
      console.log("[stream.start]", event.stream_id);
      useCognitionState.getState().streamStart(event.stream_id);
      break;

    case 'stream.delta':
      useCognitionState.getState().streamDelta(event.stream_id, event.delta);
      break;

    case 'stream.end':
      useCognitionState.getState().streamEnd(event.stream_id);
      break;

    case 'stream.interrupted':
      useCognitionState.getState().streamEnd(event.stream_id);
      useOrbState.getState().setMode('interrupted');
      setTimeout(() => {
        const currentMode = useOrbState.getState().mode;
        if (currentMode === 'interrupted') {
          useOrbState.getState().setMode('idle');
        }
      }, 600);
      break;

    case 'user.message':
      // The backend echo of the user's message
      useCognitionState.getState().addUserInput(event.text);
      break;

    case 'awareness.update':
      // The backend detected an attention state change.
      // Ask the daemon for an immediate sync of the visible context payload
      // so the Awareness UI updates instantly when changing windows.
      import('./socket').then(({ socket }) => {
        socket.sendEvent({ type: 'awareness.get_request' });
      });
      break;

    case 'runtime.status':
      if (event.status === 'connected') {
        // Wake the UI up
        useOrbState.getState().setMode('idle');
        console.log('[runtime] Backend is connected and active.');
      } else if (event.status === 'disconnected') {
        // Fallback UI indication
        useOrbState.getState().setMode('disconnected');
        console.log('[runtime] Backend disconnected. UI is dormant.');
      }
      break;

    case 'voice.transcript':
      useCognitionState.getState().addUserInput(event.text);
      break;
    case 'memory.ghost':
      useCognitionState.getState().addItems([{
        id: Math.random().toString(36).substring(7),
        type: 'memoryGhost',
        timestamp: Date.now(),
        from: 'Arova Memory',
        text: event.text
      }]);
      break;

    case 'session.sync':
      if (Array.isArray(event.messages)) {
        const parsedItems = event.messages.map((m: any) => {
          if (m.role === 'user') {
            return { id: m.id, type: 'userSaid', timestamp: m.timestamp, text: m.content };
          } else if (m.role === 'assistant') {
            return { id: m.id, type: 'surfacing', timestamp: m.timestamp, from: 'Arova', paragraphs: [m.content] };
          }
          return null;
        }).filter(Boolean);
        useCognitionState.getState().setItems(parsedItems);
      }
      break;

    case 'cognition.modulation':
      if (event.profile) {
        // Map presence profile properties to orb visual modulation parameters
        let turbulence = 0.2;
        let warmth = 0.5;
        let rhythm = 0.5;
        
        if (event.profile.emotional_temperature === 'warm') warmth = 0.8;
        if (event.profile.emotional_temperature === 'clinical') warmth = 0.2;
        
        if (event.profile.cadence === 'calming') rhythm = 0.2;
        if (event.profile.cadence === 'brisk') rhythm = 0.8;
        
        if (event.profile.verbosity === 'concise') turbulence = 0.1; // steady
        
        useOrbState.getState().setModulation({
          turbulence,
          warmth,
          breathing_rhythm: rhythm,
          saturation: event.profile.ambient_density // link density to color intensity roughly
        });
      }
      break;

    case 'thread.sync':
      if (Array.isArray(event.threads)) {
        useCognitionState.getState().setThreads(event.threads);
      }
      break;

    case 'projection.updated':
      if (event.projection) {
        if (event.projection.orb_state) {
          useOrbState.getState().setMode(event.projection.orb_state.state);
        }
        if (Array.isArray(event.projection.stream_items)) {
          useCognitionState.getState().setItems(event.projection.stream_items);
        }
        if (event.projection.room_state) {
          useEnvironmentState.getState().setRoomState(event.projection.room_state);
        }
        if (event.projection.context_state) {
          useEnvironmentState.getState().setContextState(event.projection.context_state);
        }
        if (event.projection.runtime_state) {
          useEnvironmentState.getState().setRuntimeState(event.projection.runtime_state);
        }
      }
      break;

    case 'cognition.surfacing_push':
      if (event.item) {
        useCognitionState.getState().addItems([{
          id: Math.random().toString(36).substring(7),
          timestamp: Date.now(),
          ...event.item
        }]);
      }
      break;

    case 'memory.query_response':
      if (Array.isArray(event.memories)) {
        useCognitionState.getState().setMemories(event.memories);
      }
      break;

    case 'memory.mutation_success':
    case 'memory.saved':
      // The UI will likely re-fetch, but we could also broadcast a refresh event
      // Instead of coupling it here, the UI component will just call sendEvent({type: 'memory.query_request'})
      break;

    case 'memory.pending_review':
      useCognitionState.getState().setPendingMemories([
        ...useCognitionState.getState().pendingMemories,
        event.memory
      ]);
      break;

    case 'memory.sensitive_candidate':
      useCognitionState.getState().setSensitiveCandidate(event.memory);
      break;

    case 'memory.contextual_dialog':
      useCognitionState.getState().setContextualCandidate(event.memory);
      break;

    case 'awareness.sync':
      if (event.policy) useAwarenessState.getState().setPolicy(event.policy);
      if (event.hidden) useAwarenessState.getState().setHidden(event.hidden);
      if (event.visible) useAwarenessState.getState().setVisible(event.visible);
      if (event.active_workspace !== undefined) {
        useAwarenessState.getState().setActiveWorkspace(event.active_workspace);
      }
      break;

    case 'workspace.sync':
      if (event.active_workspace !== undefined) {
        useAwarenessState.getState().setActiveWorkspace(event.active_workspace);
      }
      break;

    default:
      console.warn(`[runtime] Unknown event: ${event.type}`, event);
      break;
  }
}
