import React, { useEffect } from 'react';
import { SurfaceHeader, SurfaceSection, EmptyState } from '../ui/CoherenceComponents';
import { useAwarenessState } from '../../state';
import { socket } from '../../runtime/socket';

export const AwarenessSurface: React.FC = () => {
  const { policy, hidden } = useAwarenessState();

  useEffect(() => {
    socket.sendEvent({ type: 'awareness.get_request' });
  }, []);

  if (!policy) {
    return (
      <div className="surface-content" style={{ padding: '42px', height: '100%', display: 'flex', flexDirection: 'column' }}>
        <SurfaceHeader title="Ambient Awareness &amp; Privacy" sub="Telemetry Channels &amp; Security Boundaries" />
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
    {
      key: 'presence',
      label: 'Presence Tracking',
      enabled: policy?.presence?.enabled ?? false,
      desc: 'Observes active window titles, focus transitions, and duration per application.',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <polyline points="12 6 12 12 16 14"></polyline>
        </svg>
      )
    },
    {
      key: 'context',
      label: 'Workspace & IDE Tracking',
      enabled: policy?.context?.enabled ?? false,
      desc: 'Discovers active repositories, git branches, and project directory roots in VS Code, Cursor, and Terminal.',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
        </svg>
      )
    },
    {
      key: 'deep_context',
      label: 'Deep Context & Terminal Inspection',
      enabled: policy?.deep_context?.enabled ?? false,
      desc: 'Reads visible code buffers, file diffs, and terminal execution output when deep reasoning is needed.',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="4 17 10 11 4 5"></polyline>
          <line x1="12" y1="19" x2="20" y2="19"></line>
        </svg>
      )
    },
    {
      key: 'memory_formation',
      label: 'Continuous Memory Formation',
      enabled: policy?.memory_formation?.enabled ?? false,
      desc: 'Synthesizes and persists architectural decisions, user preferences, and project facts across sessions.',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
          <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
          <line x1="12" y1="22.08" x2="12" y2="12"></line>
        </svg>
      )
    },
    {
      key: 'vision',
      label: 'Vision & Screen Analysis',
      enabled: policy?.vision?.enabled ?? false,
      desc: 'Captures and analyzes display screenshots on explicit user summon or when spatial ambiguity occurs.',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
          <circle cx="12" cy="12" r="3"></circle>
        </svg>
      )
    },
  ];

  const defaultHiddenItems = [
    'Password Managers (1Password, Bitwarden, KeePass, LastPass)',
    'Banking, Financial & Crypto Portals',
    'Private & Incognito Browser Sessions',
    'Authentication Headers, Tokens & API Keys',
    'System Keychain & Secure Enclave Data'
  ];

  const displayHidden = hidden && Array.isArray(hidden) && hidden.length > 0 ? hidden : defaultHiddenItems;

  return (
    <div className="surface-content" style={{ padding: '42px', height: '100%', display: 'flex', flexDirection: 'column', gap: '28px', overflowY: 'auto' }}>
      <SurfaceHeader title="Ambient Awareness &amp; Privacy" sub="Telemetry Channels &amp; Strict Security Boundaries" />

      {/* Telemetry & Awareness Capabilities */}
      <SurfaceSection>
        <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--ink)', marginBottom: '6px' }}>
          Active Awareness Providers
        </div>
        <div style={{ fontSize: '13px', color: 'var(--ink-3)', marginBottom: '16px' }}>
          Configure which ambient telemetry channels Arova is permitted to monitor on your system.
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {capabilities.map(cap => (
            <div 
              key={cap.key} 
              style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center', 
                padding: '16px 20px',
                background: 'var(--glass-1)',
                border: '1px solid var(--hairline-2)',
                borderRadius: '12px',
                transition: 'border-color 0.2s ease'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px', maxWidth: '80%' }}>
                <div style={{ color: cap.enabled ? 'var(--accent-gold)' : 'var(--ink-3)', flexShrink: 0 }}>
                  {cap.icon}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: cap.enabled ? 'var(--ink)' : 'var(--ink-2)' }}>{cap.label}</div>
                  <div style={{ fontSize: '12px', color: 'var(--ink-3)', lineHeight: '1.4' }}>{cap.desc}</div>
                </div>
              </div>
              <button 
                onClick={() => toggleLayer(cap.key as any, cap.enabled)}
                style={{
                  width: '44px', height: '24px', borderRadius: '12px',
                  background: cap.enabled ? 'rgba(235, 175, 75, 0.25)' : 'rgba(255,255,255,0.08)',
                  border: `1px solid ${cap.enabled ? 'rgba(235, 175, 75, 0.6)' : 'var(--hairline-2)'}`,
                  position: 'relative', cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  flexShrink: 0
                }}
              >
                <div style={{
                  position: 'absolute', top: '2px', left: cap.enabled ? '22px' : '2px',
                  width: '18px', height: '18px', borderRadius: '50%',
                  background: cap.enabled ? 'var(--accent-gold)' : 'var(--ink-3)',
                  transition: 'all 0.2s ease',
                  boxShadow: cap.enabled ? '0 0 6px rgba(235, 175, 75, 0.4)' : 'none'
                }} />
              </button>
            </div>
          ))}
        </div>
      </SurfaceSection>

      {/* Strictly Protected & Filtered Boundaries */}
      <SurfaceSection>
        <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--ink)', marginBottom: '6px' }}>
          Strictly Protected &amp; Filtered Boundaries
        </div>
        <div style={{ fontSize: '13px', color: 'var(--ink-3)', marginBottom: '14px' }}>
          These applications and patterns are strictly blocked by Arova's deterministic kernel policy at all times.
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '10px' }}>
          {displayHidden.map((item, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', color: 'var(--ink-2)', padding: '12px 14px', background: 'rgba(0,0,0,0.15)', border: '1px solid var(--hairline-2)', borderRadius: '10px' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--accent-sage)', flexShrink: 0 }}>
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                <polyline points="9 12 11 14 15 10"/>
              </svg>
              <span>{item}</span>
            </div>
          ))}
        </div>
      </SurfaceSection>

    </div>
  );
};
