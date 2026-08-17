import React, { useEffect } from 'react';
import { SurfaceHeader, SurfaceSection, InfoRow } from '../ui/CoherenceComponents';
import { useEnvironmentState, useAwarenessState } from '../../state';
import { socket } from '../../runtime/socket';

export const WorkspaceSurface: React.FC = () => {
  const { roomState } = useEnvironmentState();
  const { activeWorkspace, visible } = useAwarenessState();

  useEffect(() => {
    socket.sendEvent({ type: 'workspace.get_request' });
    socket.sendEvent({ type: 'awareness.get_request' });
  }, []);

  const openApps = Array.isArray(roomState?.workspace) && roomState.workspace.length > 0 
    ? roomState.workspace 
    : [];

  const primaryApp = openApps[0] || activeWorkspace?.title || 'Terminal / System';
  const gitBranch = activeWorkspace?.git_branch || activeWorkspace?.branch || null;
  const projectRoot = activeWorkspace?.project_root || activeWorkspace?.repo || activeWorkspace?.title || null;
  const activeFile = activeWorkspace?.active_file || visible?.[0]?.source || null;

  return (
    <div className="surface-content" style={{ padding: '42px', height: '100%', display: 'flex', flexDirection: 'column', gap: '24px', overflowY: 'auto' }}>
      <SurfaceHeader title="Workspace Context" sub="Live Project Telemetry · Active IDE &amp; Repositories" />

      {/* Primary Focus Card */}
      <div style={{ background: 'var(--glass-2)', border: '1px solid var(--glass-edge)', borderRadius: '14px', padding: '24px', display: 'flex', flexDirection: 'column', gap: '14px', boxShadow: 'var(--shadow-sm)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>Active Foreground Context</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--accent-sage)', fontWeight: 500 }}>
            <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--accent-sage)', boxShadow: '0 0 6px var(--accent-sage)' }} />
            Live Tracking
          </div>
        </div>
        <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--ink)', letterSpacing: '-0.01em' }}>
          {primaryApp}
        </div>
      </div>

      {/* Workspace Details */}
      <SurfaceSection title="Project &amp; Environment">
        <InfoRow label="Active Application" value={primaryApp} />
        {projectRoot && <InfoRow label="Project Root" value={projectRoot} />}
        {gitBranch && <InfoRow label="Git Branch" value={gitBranch} />}
        {activeFile && <InfoRow label="Active Buffer / File" value={activeFile} />}
        <InfoRow label="Context Engine" value="Local OS Process Observer" />
      </SurfaceSection>

      {/* Open Applications Stack */}
      {openApps.length > 0 && (
        <SurfaceSection title="Discovered Application Stack">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '4px' }}>
            {openApps.map((app: string, idx: number) => (
              <div 
                key={idx} 
                style={{ 
                  background: idx === 0 ? 'rgba(255, 255, 255, 0.08)' : 'var(--glass-1)', 
                  padding: '8px 16px', 
                  borderRadius: '10px', 
                  border: `1px solid ${idx === 0 ? 'var(--hairline-1)' : 'var(--hairline-2)'}`, 
                  fontSize: '13px', 
                  color: idx === 0 ? 'var(--ink)' : 'var(--ink-2)',
                  fontWeight: idx === 0 ? 600 : 400,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                {idx === 0 && <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-gold)' }} />}
                {app}
              </div>
            ))}
          </div>
        </SurfaceSection>
      )}
    </div>
  );
};
