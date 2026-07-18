import React, { useState } from 'react';
import { executeThreadAction } from '../../ipc';

interface ThreadCardProps {
  thread: {
    thread_id: string;
    title: string;
    state: string;
    resonance?: number; // legacy
    continuity_resonance?: number;
    active_pressures?: number;
    pinned?: boolean;
    last_active?: number;
    last_updated?: number;
    workspace_match?: string;
    summary?: string;
    unresolved_questions?: string[];
    why_it_matters?: string;
    continuity_snapshot?: {
      provenance?: Array<{
        source_type: string;
        source_id: string;
        confidence: number;
        explanation: string;
      }>;
    };
  };
}

const formatRelativeTime = (timestamp?: number) => {
  if (!timestamp) return 'Just now';
  const diffMs = Date.now() - timestamp * 1000;
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
};

export const ThreadCard: React.FC<ThreadCardProps> = ({ thread }) => {
  const [showMenu, setShowMenu] = useState(false);
  const [showProvenance, setShowProvenance] = useState(false);

  const handleAction = (action: string, payload: any = {}) => {
    executeThreadAction(action, thread.thread_id, payload);
    setShowMenu(false);
  };

  const resonanceValue = thread.continuity_resonance || thread.resonance || 0;
  const pressureValue = thread.active_pressures || 0;
  
  const summary = thread.summary || thread.title;
  const nextAction = thread.unresolved_questions && thread.unresolved_questions.length > 0 
    ? thread.unresolved_questions[0] 
    : null;
  const whyItMatters = thread.why_it_matters;
  const provenance = thread.continuity_snapshot?.provenance || [];

  return (
    <div 
      className={`thread-card ${thread.state}`}
      style={{
        background: 'var(--glass-1)',
        padding: '24px',
        borderRadius: '16px',
        border: `1px solid var(--glass-edge)`,
        boxShadow: resonanceValue > 50 ? `0 0 20px rgba(180, 150, 255, 0.1)` : 'none',
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        gap: '24px'
      }}
    >
      <div style={{ position: 'absolute', top: '16px', right: '16px' }}>
        <button 
          onClick={() => setShowMenu(!showMenu)}
          style={{ background: 'none', border: 'none', color: 'var(--ink-3)', cursor: 'pointer', padding: '0 4px', fontSize: '18px' }}
        >⋮</button>
        {showMenu && (
          <div style={{
            position: 'absolute', top: '24px', right: '0', background: 'var(--glass-2)',
            backdropFilter: 'blur(16px)', border: '1px solid var(--hairline-2)', borderRadius: '8px',
            padding: '4px', zIndex: 100, display: 'flex', flexDirection: 'column',
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)', minWidth: '120px'
          }}>
            <button onClick={() => handleAction('pin')} style={menuButtonStyle}>{thread.pinned ? 'Unpin' : 'Pin'}</button>
            <button onClick={() => handleAction('archive')} style={{...menuButtonStyle, color: '#e55'}}>Archive</button>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
          {thread.pinned && (
            <span style={{ display: 'flex', alignItems: 'center', paddingTop: '2px' }}>
              <svg 
                width="16" height="16" viewBox="0 0 24 24" 
                fill="rgba(180, 150, 255, 0.15)" 
                stroke="rgba(180, 150, 255, 0.8)" 
                strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" 
                style={{ transform: 'rotate(45deg)', filter: 'drop-shadow(0 0 4px rgba(180, 150, 255, 0.4))' }}
              >
                <path d="M12 17v5M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"></path>
              </svg>
            </span>
          )}
          <div style={{ fontSize: '18px', fontWeight: 500, color: 'var(--ink)', lineHeight: '1.4' }}>
            {summary}
          </div>
        </div>

        {nextAction && (
          <div>
            <div style={{ fontSize: '12px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>Next Action</div>
            <div style={{ fontSize: '15px', color: 'var(--ink-2)' }}>{nextAction}</div>
          </div>
        )}

        {whyItMatters && (
          <div>
            <div style={{ fontSize: '12px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>Why It Matters</div>
            <div style={{ fontSize: '15px', color: 'var(--ink-2)' }}>{whyItMatters}</div>
          </div>
        )}

        {provenance.length > 0 && (
          <div style={{ marginTop: '8px' }}>
            <button 
              onClick={() => setShowProvenance(!showProvenance)}
              style={{ background: 'none', border: 'none', color: 'var(--accent-gold)', fontSize: '13px', cursor: 'pointer', padding: 0, textDecoration: 'underline', opacity: 0.8 }}
            >
              Why did you know this?
            </button>
            {showProvenance && (
              <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px', padding: '12px', background: 'rgba(0,0,0,0.15)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                {provenance.map((prov, i) => (
                  <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--ink)' }}>{prov.source_id}</span>
                      <span style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase' }}>{prov.source_type}</span>
                    </div>
                    <div style={{ fontSize: '13px', color: 'var(--ink-2)' }}>{prov.explanation}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div style={{ height: '1px', background: 'var(--hairline-2)', width: '100%' }}></div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '16px' }}>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Pressure</div>
            <div style={{ fontSize: '13px', color: 'var(--ink)' }}>{pressureValue > 0.7 ? 'High' : pressureValue > 0.3 ? 'Medium' : 'Low'}</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Workspace</div>
            <div style={{ fontSize: '13px', color: 'var(--ink)' }}>{thread.workspace_match || 'None'}</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Last Active</div>
            <div style={{ fontSize: '13px', color: 'var(--ink)' }}>{formatRelativeTime(thread.last_updated || thread.last_active)}</div>
          </div>
        </div>

        <button 
          onClick={() => handleAction('resume')}
          style={{ 
            padding: '8px 16px', 
            borderRadius: '8px', 
            border: '1px solid var(--accent-amber)', 
            background: 'rgba(255, 170, 0, 0.1)', 
            color: 'var(--accent-amber)', 
            fontSize: '14px', 
            cursor: 'pointer',
            fontWeight: 500,
            transition: 'all 0.2s ease'
          }}
        >
          Continue →
        </button>
      </div>
    </div>
  );
};

const menuButtonStyle: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: 'var(--ink)',
  padding: '8px 12px',
  textAlign: 'left',
  cursor: 'pointer',
  borderRadius: '4px',
  width: '100%',
  fontSize: '14px'
};
