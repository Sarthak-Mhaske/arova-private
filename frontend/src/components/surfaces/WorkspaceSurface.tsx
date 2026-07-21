import React, { useEffect, useState } from 'react';
import { SurfaceHeader, SurfaceSection, InfoRow, EmptyState, LoadingState } from '../ui/CoherenceComponents';
import { useEnvironmentState, useAwarenessState } from '../../state';

export const WorkspaceSurface: React.FC = () => {
  const { roomState } = useEnvironmentState();
  const { activeWorkspace } = useAwarenessState();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(t);
  }, []);

  const hasWorkspace = roomState && roomState.workspace && roomState.workspace.length > 0;

  return (
    <div className="surface-content" style={{ padding: '42px', height: '100%', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <SurfaceHeader title="What you are doing" sub="Workspace · Application context" />
      
      {!activeWorkspace && (
        <div
          style={{
            background: 'linear-gradient(135deg, rgba(180, 150, 255, 0.08) 0%, rgba(20, 20, 30, 0.7) 100%)',
            border: '1px solid rgba(180, 150, 255, 0.25)',
            borderRadius: '16px',
            padding: '32px',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px'
          }}
        >
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--ink, #fff)', letterSpacing: '-0.01em' }}>
            Welcome to Arova
          </div>
          <div style={{ fontSize: '14px', color: 'rgba(255, 255, 255, 0.8)', lineHeight: '1.6' }}>
            Arova builds a working memory automatically while you work.
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingLeft: '8px', color: 'rgba(255, 255, 255, 0.7)', fontSize: '13px' }}>
            <div>• Continue coding</div>
            <div>• Browse the web</div>
            <div>• Read documents</div>
          </div>
          <div style={{ fontSize: '13px', color: '#a881ff', fontStyle: 'italic', marginTop: '4px' }}>
            I'll quietly build your first workspace.
          </div>
        </div>
      )}
      
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
