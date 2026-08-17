import React from 'react';
import { useSurfaceState } from '../../state';

export const AgentsSurface: React.FC = () => {
  const { closeSurface } = useSurfaceState();

  const AGENT_ROLES = [
    {
      id: 'code-architect',
      title: 'Code Architect & AST Specialist',
      status: 'Standby / Initializing',
      statusColor: 'var(--accent-ice, #8eb0d0)',
      description: 'Performs multi-file code generation, semantic AST inspection, refactoring passes, and git branch isolation.',
      tags: ['AST Inspection', 'Diff Generation', 'Linter Guard', 'Multi-File Edit'],
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
          <polyline points="16 18 22 12 16 6"/>
          <polyline points="8 6 2 12 8 18"/>
        </svg>
      )
    },
    {
      id: 'research-specialist',
      title: 'Research & Knowledge Specialist',
      status: 'Standby / Initializing',
      statusColor: 'var(--accent-gold, #e0ba75)',
      description: 'Scours technical documentation, extracts API signatures, and synthesizes permanent structured entities into the Memory Vault.',
      tags: ['Web Ingestion', 'API Schema Mapping', 'Memory Vault Integration', 'Summarization'],
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
          <circle cx="11" cy="11" r="8"/>
          <line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
      )
    },
    {
      id: 'verification-sentinel',
      title: 'Verification & Test Sentinel',
      status: 'Standby / Initializing',
      statusColor: 'var(--accent-violet, #a89dc8)',
      description: 'Executes headless test suites in background sandboxes, analyzes compiler diagnostics, and catches regressions before committing.',
      tags: ['Test Runner', 'Log Trace Analysis', 'Self-Correction', 'CI/CD Emulation'],
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
          <polyline points="22 4 12 14.01 9 11.01"/>
        </svg>
      )
    },
    {
      id: 'ambience-guardian',
      title: 'Ambience & Context Guardian',
      status: 'Live (Ambient Tracking)',
      statusColor: 'var(--accent-sage, #a8c0a8)',
      description: 'Passively observes active IDE files, terminal CWDs, and research tabs to curate clean 4-layer reality snapshots.',
      tags: ['Working Set Recovery', 'Noise Shielding', 'Snapshot Engine', 'Process Context'],
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
          <circle cx="12" cy="12" r="9"/>
          <path d="M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>
        </svg>
      )
    }
  ];

  return (
    <div className="surface-content" style={{ padding: '32px 36px', height: '100%', display: 'flex', flexDirection: 'column', overflowY: 'auto', boxSizing: 'border-box' }}>
      {/* Surface Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
        <div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--ink)', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span>Autonomous Agent Swarm</span>
            <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 8px', borderRadius: '6px', background: 'rgba(168, 192, 168, 0.15)', color: 'var(--accent-sage, #a8c0a8)', border: '1px solid rgba(168, 192, 168, 0.3)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              Swarm v1.0
            </span>
          </div>
          <div style={{ fontSize: '13px', color: 'var(--ink-3)', marginTop: '4px', lineHeight: '1.5' }}>
            Multi-agent coordination runtime for concurrent development, deep research, and background verification.
          </div>
        </div>

        <button 
          data-close
          onClick={() => closeSurface()}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--ink-3)',
            cursor: 'pointer',
            padding: '8px',
            borderRadius: '8px',
            display: 'grid',
            placeItems: 'center'
          }}
        >
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      {/* Under Development Banner */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(224, 186, 117, 0.1) 0%, rgba(26, 23, 20, 0.6) 100%)',
        border: '1px solid rgba(224, 186, 117, 0.28)',
        borderRadius: '14px',
        padding: '16px 20px',
        marginBottom: '24px',
        display: 'flex',
        alignItems: 'center',
        gap: '16px'
      }}>
        <div style={{
          width: '38px',
          height: '38px',
          borderRadius: '10px',
          background: 'rgba(224, 186, 117, 0.18)',
          border: '1px solid rgba(224, 186, 117, 0.35)',
          display: 'grid',
          placeItems: 'center',
          color: 'var(--accent-amber, #e0ba75)',
          flexShrink: 0
        }}>
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--accent-amber, #e0ba75)', letterSpacing: '0.01em' }}>
            Autonomous Substrate · In Active Development
          </div>
          <div style={{ fontSize: '12px', color: 'var(--ink-2)', marginTop: '2px', lineHeight: '1.45' }}>
            The multi-agent execution runtime is currently being wired to the unified Memory Vault graph and background dispatchers. Full autonomous swarm execution will activate in an upcoming release.
          </div>
        </div>
      </div>

      {/* Overview Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '14px', marginBottom: '24px' }}>
        <div style={{ padding: '16px 18px', background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '12px' }}>
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', letterSpacing: '0.08em', fontWeight: 600, textTransform: 'uppercase' }}>Configured Roles</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--ink)', marginTop: '4px' }}>4 Agents</div>
        </div>

        <div style={{ padding: '16px 18px', background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '12px' }}>
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', letterSpacing: '0.08em', fontWeight: 600, textTransform: 'uppercase' }}>Coordination Model</div>
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--ink)', marginTop: '6px' }}>Human-in-the-Loop</div>
        </div>

        <div style={{ padding: '16px 18px', background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '12px' }}>
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', letterSpacing: '0.08em', fontWeight: 600, textTransform: 'uppercase' }}>Execution Sandbox</div>
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--ink)', marginTop: '6px' }}>Native Dispatcher</div>
        </div>

        <div style={{ padding: '16px 18px', background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '12px' }}>
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', letterSpacing: '0.08em', fontWeight: 600, textTransform: 'uppercase' }}>Active Telemetry</div>
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--accent-sage, #a8c0a8)', marginTop: '6px' }}>Cognitive Stream</div>
        </div>
      </div>

      {/* Agent Role Cards Grid */}
      <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--ink)', marginBottom: '12px' }}>
        Swarm Roster & Capabilities
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '14px', marginBottom: '24px' }}>
        {AGENT_ROLES.map(agent => (
          <div 
            key={agent.id} 
            style={{ 
              padding: '20px', 
              background: 'var(--glass-1)', 
              border: '1px solid var(--hairline-2)', 
              borderRadius: '14px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              gap: '14px'
            }}
          >
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'var(--glass-2)', border: '1px solid var(--hairline-2)', display: 'grid', placeItems: 'center', color: 'var(--ink)' }}>
                    {agent.icon}
                  </div>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--ink)' }}>{agent.title}</div>
                </div>
              </div>
              <div style={{ fontSize: '12.5px', color: 'var(--ink-2)', lineHeight: '1.5', marginBottom: '12px' }}>
                {agent.description}
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '12px' }}>
                {agent.tags.map(tag => (
                  <span 
                    key={tag}
                    style={{
                      fontSize: '10.5px',
                      padding: '2px 8px',
                      borderRadius: '6px',
                      background: 'var(--glass-2)',
                      border: '1px solid var(--hairline-2)',
                      color: 'var(--ink-3)'
                    }}
                  >
                    {tag}
                  </span>
                ))}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '10px', borderTop: '1px solid var(--hairline-2)' }}>
                <span style={{ fontSize: '11px', color: 'var(--ink-3)' }}>Status</span>
                <span style={{ fontSize: '11px', fontWeight: 600, color: agent.statusColor }}>{agent.status}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
