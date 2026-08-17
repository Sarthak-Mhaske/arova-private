import React from 'react';
import { useSurfaceState } from '../../state';

export const PlansSurface: React.FC = () => {
  const { closeSurface } = useSurfaceState();

  const MILESTONES = [
    {
      id: 'step-1',
      number: '01',
      title: 'Noise Shield & Telemetry Filtering',
      status: 'Completed',
      statusColor: 'var(--accent-sage, #a8c0a8)',
      detail: 'Filter out SSO endpoints, cargo caches, temporary process workers, and noisy browser history.',
      completed: true
    },
    {
      id: 'step-2',
      number: '02',
      title: 'Context Recovery & Deduplication',
      status: 'Completed',
      statusColor: 'var(--accent-sage, #a8c0a8)',
      detail: 'Canonicalize subdomains, group commit hashes, and collapse duplicate research tabs into 3-5 curated items.',
      completed: true
    },
    {
      id: 'step-3',
      number: '03',
      title: 'Autonomous Swarm & Plan Execution',
      status: 'In Development',
      statusColor: 'var(--accent-amber, #e0ba75)',
      detail: 'Dynamic task DAG dispatching across specialized subagents with live verification gates and self-healing rollbacks.',
      completed: false
    },
    {
      id: 'step-4',
      number: '04',
      title: 'Multi-Modal Voice & Tool Synthesis',
      status: 'Queued',
      statusColor: 'var(--ink-3)',
      detail: 'Real-time bidirectional audio stream integration with continuous visual screen grounding.',
      completed: false
    }
  ];

  return (
    <div className="surface-content" style={{ padding: '32px 36px', height: '100%', display: 'flex', flexDirection: 'column', overflowY: 'auto', boxSizing: 'border-box' }}>
      {/* Surface Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
        <div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--ink)', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span>Goal Tree & Execution Plans</span>
            <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 8px', borderRadius: '6px', background: 'rgba(224, 186, 117, 0.15)', color: 'var(--accent-amber, #e0ba75)', border: '1px solid rgba(224, 186, 117, 0.3)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              Planner v1.0
            </span>
          </div>
          <div style={{ fontSize: '13px', color: 'var(--ink-3)', marginTop: '4px', lineHeight: '1.5' }}>
            Hierarchical task decomposition, automated milestone validation, and dynamic execution graphs.
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
            <path d="M4 6h16M4 12h12M4 18h8"/>
          </svg>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--accent-amber, #e0ba75)', letterSpacing: '0.01em' }}>
            Goal Execution Engine · In Active Development
          </div>
          <div style={{ fontSize: '12px', color: 'var(--ink-2)', marginTop: '2px', lineHeight: '1.45' }}>
            The automated goal planner decomposes user objectives into executable DAG dependency graphs with ambient milestone tracking. Full interactive planning will activate in the next release.
          </div>
        </div>
      </div>

      {/* Active Goal Plan Preview */}
      <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--ink)', marginBottom: '12px' }}>
        Active Goal Execution DAG
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '24px' }}>
        {MILESTONES.map((step) => (
          <div
            key={step.id}
            style={{
              padding: '18px 20px',
              background: 'var(--glass-1)',
              border: `1px solid ${step.completed ? 'rgba(168, 192, 168, 0.3)' : 'var(--hairline-2)'}`,
              borderRadius: '12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '16px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: step.completed ? 'rgba(168, 192, 168, 0.15)' : 'var(--glass-2)',
                border: `1px solid ${step.completed ? 'rgba(168, 192, 168, 0.3)' : 'var(--hairline-2)'}`,
                display: 'grid',
                placeItems: 'center',
                fontSize: '12px',
                fontWeight: 700,
                color: step.completed ? 'var(--accent-sage, #a8c0a8)' : 'var(--ink-3)',
                flexShrink: 0
              }}>
                {step.completed ? (
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                ) : step.number}
              </div>

              <div>
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--ink)' }}>{step.title}</div>
                <div style={{ fontSize: '12.5px', color: 'var(--ink-3)', marginTop: '2px', lineHeight: '1.4' }}>{step.detail}</div>
              </div>
            </div>

            <div style={{
              fontSize: '11px',
              fontWeight: 600,
              padding: '4px 10px',
              borderRadius: '6px',
              background: 'var(--glass-2)',
              border: '1px solid var(--hairline-2)',
              color: step.statusColor,
              whiteSpace: 'nowrap',
              flexShrink: 0
            }}>
              {step.status}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
