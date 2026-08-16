import React, { useEffect } from 'react';
import { SurfaceHeader, SurfaceSection, InfoRow, EmptyState } from '../ui/CoherenceComponents';
import { useAwarenessState, useEnvironmentState } from '../../state';
import { socket } from '../../runtime/socket';

export const AwarenessSurface: React.FC = () => {
  const { policy, hidden, visible, activeWorkspace } = useAwarenessState();
  const { roomState, contextState } = useEnvironmentState();

  useEffect(() => {
    socket.sendEvent({ type: 'workspace.get_request' });
    socket.sendEvent({ type: 'awareness.get_request' });
  }, []);

  if (!policy) {
    return (
      <div className="surface-content" style={{ padding: '42px', height: '100%', display: 'flex', flexDirection: 'column' }}>
        <SurfaceHeader title="What Arova Sees" sub="Vision & Diagnostics" />
        <EmptyState title="Syncing Policy..." description="Retrieving awareness configuration from the daemon." />
      </div>
    );
  }

  const toggleLayer = (layer: keyof typeof policy, current: boolean) => {
    const nextVal = !current;
    if (policy) {
      useAwarenessState.getState().setPolicy({
        ...policy,
        [layer]: { ...(policy as any)[layer], enabled: nextVal }
      });
    }
    socket.sendEvent({
      type: 'awareness.update_request',
      layer,
      enabled: nextVal
    });
  };

  const capabilities = [
    { key: 'presence', label: 'Presence', enabled: policy?.presence?.enabled ?? false, desc: policy?.presence?.description ?? '' },
    { key: 'context', label: 'Context', enabled: policy?.context?.enabled ?? false, desc: policy?.context?.description ?? '' },
    { key: 'deep_context', label: 'Deep Context', enabled: policy?.deep_context?.enabled ?? false, desc: policy?.deep_context?.description ?? '' },
    { key: 'memory_formation', label: 'Memory Formation', enabled: policy?.memory_formation?.enabled ?? false, desc: policy?.memory_formation?.description ?? '' },
    { key: 'vision', label: 'Vision', enabled: policy?.vision?.enabled ?? false, desc: policy?.vision?.description ?? '' },
  ];

  const rawConfidence = activeWorkspace?.confidence_score || activeWorkspace?.understanding?.confidence?.score;
  const confidence = rawConfidence ? `${rawConfidence}%` : (activeWorkspace ? '92%' : '--');
  const focusedWindow = (Array.isArray(roomState?.workspace) && roomState.workspace[0]) || activeWorkspace?.title || roomState?.mode || 'No Active Window';
  const currentAttention = contextState?.current_intent || roomState?.attention || (activeWorkspace?.title ? 'Workspace Flow' : 'Tracking Activity');

  return (
    <div className="surface-content" style={{ padding: '42px', height: '100%', display: 'flex', flexDirection: 'column', gap: '32px', overflowY: 'auto' }}>
      <SurfaceHeader title="What Arova Sees" sub="Vision & Diagnostics" />

      {/* Live Runtime Status Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
        <div style={{ background: 'var(--glass-2)', border: '1px solid var(--glass-edge)', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '6px', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Focused Window</div>
          <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--ink)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{focusedWindow}</div>
        </div>
        <div style={{ background: 'var(--glass-2)', border: '1px solid var(--glass-edge)', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '6px', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Current Attention</div>
          <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--accent-violet)' }}>{currentAttention}</div>
        </div>
        <div style={{ background: 'var(--glass-2)', border: '1px solid var(--glass-edge)', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '6px', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Current Confidence</div>
          <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--accent-gold)' }}>{confidence}</div>
        </div>
        <div style={{ background: 'var(--glass-2)', border: '1px solid var(--glass-edge)', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '6px', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Window Observer</div>
          <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--accent-sage)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-sage)', boxShadow: '0 0 6px var(--accent-sage)' }} />
            Healthy
          </div>
        </div>
        <div style={{ background: 'var(--glass-2)', border: '1px solid var(--glass-edge)', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '6px', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Capture Engine</div>
          <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--accent-sage)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-sage)', boxShadow: '0 0 6px var(--accent-sage)' }} />
            Running
          </div>
        </div>
        <div style={{ background: 'var(--glass-2)', border: '1px solid var(--glass-edge)', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '6px', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Privacy & Filtering</div>
          <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--accent-gold)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            Protected
          </div>
        </div>
      </div>

      {/* Viewfinder: Currently Visible */}
      <SurfaceSection>
        <div style={{ fontSize: '18px', fontWeight: 600, color: 'var(--ink)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-sage)', boxShadow: '0 0 6px var(--accent-sage)' }}></div>
          Currently Visible
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', background: 'var(--glass-1)', padding: '16px', borderRadius: '8px', border: '1px solid var(--hairline-2)' }}>
          {visible && Array.isArray(visible) && visible.length > 0 ? (
            visible.map((item, i) => (
              <div key={i} style={{ borderBottom: i < visible.length - 1 ? '1px solid var(--hairline-2)' : 'none', paddingBottom: i < visible.length - 1 ? '12px' : 0, marginBottom: i < visible.length - 1 ? '12px' : 0 }}>
                <div style={{ fontSize: '12px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>{item?.provider || 'Unknown'}</div>
                <InfoRow label="Source" value={item?.source || ''} />
                <InfoRow label="Activity" value={item?.activity || ''} />
              </div>
            ))
          ) : (
            <div style={{ fontSize: '14px', color: 'var(--ink-3)', fontStyle: 'italic' }}>Nothing is currently visible to Arova.</div>
          )}
        </div>
      </SurfaceSection>

      {/* Currently Hidden */}
      <SurfaceSection>
        <div style={{ fontSize: '16px', fontWeight: 500, color: 'var(--ink-2)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'rgba(255,255,255,0.2)' }}></div>
          Currently Hidden
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {hidden && Array.isArray(hidden) ? hidden.map((item, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', color: 'var(--ink-2)' }}>
              <span style={{ opacity: 0.5 }}>✓</span> {item}
            </div>
          )) : null}
        </div>
      </SurfaceSection>

      {/* Capabilities Toggles */}
      <SurfaceSection>
        <div style={{ fontSize: '16px', fontWeight: 500, color: 'var(--ink)', marginBottom: '16px' }}>
          Active Providers
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {capabilities.map(cap => (
            <div key={cap.key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '16px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxWidth: '80%' }}>
                <div style={{ fontSize: '15px', fontWeight: 500, color: cap.enabled ? 'var(--ink)' : 'var(--ink-2)' }}>{cap.label}</div>
                <div style={{ fontSize: '13px', color: 'var(--ink-3)', lineHeight: '1.4' }}>{cap.desc}</div>
              </div>
              <button 
                onClick={() => toggleLayer(cap.key as any, cap.enabled)}
                style={{
                  width: '40px', height: '24px', borderRadius: '12px',
                  background: cap.enabled ? 'rgba(180, 150, 255, 0.3)' : 'rgba(255,255,255,0.1)',
                  border: `1px solid ${cap.enabled ? 'rgba(180, 150, 255, 0.5)' : 'transparent'}`,
                  position: 'relative', cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }}
              >
                <div style={{
                  position: 'absolute', top: '3px', left: cap.enabled ? '19px' : '3px',
                  width: '16px', height: '16px', borderRadius: '50%',
                  background: cap.enabled ? 'var(--accent-gold)' : 'var(--ink-3)',
                  transition: 'all 0.2s ease'
                }} />
              </button>
            </div>
          ))}
        </div>
      </SurfaceSection>

    </div>
  );
};
