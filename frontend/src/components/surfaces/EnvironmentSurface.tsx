import React from 'react';
import { SurfaceHead } from './SurfaceHead';
import { useEnvironmentState } from '../../state';

export const EnvironmentSurface: React.FC = () => {
  const { roomState } = useEnvironmentState();

  if (!roomState) {
    return (
      <>
        <SurfaceHead title="What I perceive" sub="Environment · Awaiting signals..." />
        <div className="surface-content" style={{ padding: '0 42px 42px' }}>
          <div style={{ color: 'var(--ink-3)', fontSize: '15px' }}>Waiting for environment sync...</div>
        </div>
      </>
    );
  }

  return (
    <>
      <SurfaceHead title="What I perceive" sub="Environment · Ambient Intelligence" />
      <div className="surface-content" style={{ padding: '0 42px 42px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        
        <div className="tune" style={{ background: 'var(--glass-1)', padding: '24px', borderRadius: '16px', border: '1px solid var(--glass-edge)' }}>
          <div style={{ fontSize: '18px', fontWeight: 500, color: 'var(--ink)', marginBottom: '24px' }}>
            Current Room: <span style={{ color: 'var(--accent-amber)' }}>{roomState.mode || 'Idle'}</span>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '16px' }}>
            
            <div style={{ background: 'var(--glass-2)', padding: '16px', borderRadius: '12px', border: '1px solid var(--hairline-2)' }}>
              <div style={{ fontSize: '13px', color: 'var(--ink-2)', marginBottom: '8px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Workspace Activity
              </div>
              <div style={{ fontSize: '15px', color: 'var(--ink)' }}>
                {roomState.workspace && roomState.workspace.length > 0 ? roomState.workspace.join(' + ') : 'No active applications'}
              </div>
            </div>

            <div style={{ display: 'flex', gap: '16px' }}>
              <div style={{ flex: 1, background: 'var(--glass-2)', padding: '16px', borderRadius: '12px', border: '1px solid var(--hairline-2)' }}>
                <div style={{ fontSize: '13px', color: 'var(--ink-2)', marginBottom: '8px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Focus Duration
                </div>
                <div style={{ fontSize: '24px', color: 'var(--ink)' }}>
                  {roomState.focus_duration_minutes || 0} <span style={{ fontSize: '14px', color: 'var(--ink-3)' }}>min</span>
                </div>
              </div>
              
              <div style={{ flex: 1, background: 'var(--glass-2)', padding: '16px', borderRadius: '12px', border: '1px solid var(--hairline-2)' }}>
                <div style={{ fontSize: '13px', color: 'var(--ink-2)', marginBottom: '8px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Attention
                </div>
                <div style={{ fontSize: '18px', color: 'var(--ink)', marginTop: '6px' }}>
                  {roomState.attention || 'Scattered'}
                </div>
              </div>
            </div>

          </div>
        </div>

      </div>
    </>
  );
};
