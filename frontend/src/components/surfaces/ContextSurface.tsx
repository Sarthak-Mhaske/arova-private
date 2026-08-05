import React, { useEffect } from 'react';
import { SurfaceHeader, SurfaceSection, InfoRow } from '../ui/CoherenceComponents';
import { useEnvironmentState, useAwarenessState, useCognitionState, useOrbState } from '../../state';
import { socket } from '../../runtime/socket';

export const ContextSurface: React.FC = () => {
  const { roomState, contextState } = useEnvironmentState();
  const { activeWorkspace, visible } = useAwarenessState();
  const { threads, items } = useCognitionState();
  const { mode: orbMode } = useOrbState();

  useEffect(() => {
    socket.sendEvent({ type: 'awareness.get_request' });
    socket.sendEvent({ type: 'workspace.get_request' });
  }, []);

  // Compute dynamic live values
  const currentRoom = activeWorkspace?.title || contextState?.room || (roomState?.mode ? `Room: ${roomState.mode}` : 'Conversational Workspace');
  const activeThread = threads?.[0]?.topic || threads?.[0]?.summary || contextState?.active_thread || 'Main Cognitive Stream';

  // Last user query for intent inference
  const lastUserSaid = items?.filter(i => i.type === 'userSaid').slice(-1)[0]?.text;
  const currentIntent = contextState?.current_intent || activeWorkspace?.context?.current_intent || (lastUserSaid ? `Responding to: "${lastUserSaid.slice(0, 50)}${lastUserSaid.length > 50 ? '...' : ''}"` : 'Deep System Audit & Refinement');

  const cognitiveState = orbMode ? `${orbMode.toUpperCase()} (Live)` : 'Coherent';
  const observedApp = visible?.[0]?.activity || (roomState?.workspace?.length ? roomState.workspace.join(' + ') : 'Active Application Window');

  return (
    <div className="surface-content" style={{ padding: '36px 42px', height: '100%', display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
      <SurfaceHeader title="What I understand" sub="Context · Current semantic projection" />
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <SurfaceSection title="Semantic Projection">
          <InfoRow label="Current Room / Workspace" value={currentRoom} />
          <InfoRow label="Active Thread" value={activeThread} />
          <InfoRow label="Current Intent" value={currentIntent} />
          <InfoRow label="Cognitive State" value={cognitiveState} />
          <InfoRow label="Observed Activity" value={observedApp} />
        </SurfaceSection>
      </div>
    </div>
  );
};
