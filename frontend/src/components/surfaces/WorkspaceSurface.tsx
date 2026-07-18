import React, { useEffect, useState } from 'react';
import { SurfaceHeader, SurfaceSection, InfoRow, EmptyState, LoadingState } from '../ui/CoherenceComponents';
import { useEnvironmentState, useAwarenessState } from '../../state';
import { ContinueCard } from './ContinueCard';

export const WorkspaceSurface: React.FC = () => {
  const { roomState } = useEnvironmentState();
  const { activeWorkspace } = useAwarenessState();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(t);
  }, []);

  const hasWorkspace = roomState && roomState.workspace && roomState.workspace.length > 0;

  const displayWorkspace = activeWorkspace || {
    title: 'Arova Development',
    understanding: {
      momentum: {
        progress_percentage: 82,
        current_blocker: 'Pending queue persistence',
        next_action: 'Implement SQLite persistence'
      },
      health: { status: 'Focused' },
      confidence: { score: 97 }
    }
  };

  return (
    <div className="surface-content" style={{ padding: '42px', height: '100%', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <SurfaceHeader title="What you are doing" sub="Workspace · Application context" />
      <ContinueCard workspace={displayWorkspace} />
      
      {isLoading ? (
        <LoadingState message="Connecting to local window manager..." />
      ) : !hasWorkspace ? (
        <EmptyState 
          title="No Active Workspace" 
          description="Arova is not currently tracking any active applications. Ensure the Privacy toggle is enabled in Settings."
        />
      ) : (
        <SurfaceSection>
          <div style={{ fontSize: '13px', color: 'var(--ink-2)', marginBottom: '8px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Active Applications
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '24px' }}>
            {roomState.workspace.map((app: string, idx: number) => (
              <div key={idx} style={{ background: 'var(--glass-2)', padding: '8px 16px', borderRadius: '8px', border: '1px solid var(--hairline-2)', fontSize: '14px', color: 'var(--ink)' }}>
                {app}
              </div>
            ))}
          </div>

          <div style={{ fontSize: '13px', color: 'var(--ink-2)', marginBottom: '8px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Focus History
          </div>
          <InfoRow label="Primary Context" value={roomState.workspace[0]} />
          <InfoRow label="Secondary Context" value={roomState.workspace[1] || 'None'} />
        </SurfaceSection>
      )}
    </div>
  );
};
