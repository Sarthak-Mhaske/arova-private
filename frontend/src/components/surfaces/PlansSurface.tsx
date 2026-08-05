import React, { useEffect, useState } from 'react';
import { SurfaceHeader, EmptyState, LoadingState } from '../ui/CoherenceComponents';
import { useEnvironmentState } from '../../state';

interface NodeItem {
  id: string;
  capability?: string;
  action?: string;
  payload?: any;
  state: string;
  output?: string | null;
  error?: string | null;
}

interface PlanItem {
  plan_id?: string;
  id?: string;
  title: string;
  when?: string;
  timestamp?: number;
  status: 'Running' | 'Completed' | 'Failed' | string;
  progress: number;
  nodes?: NodeItem[];
}

export const PlansSurface: React.FC = () => {
  const { runtimeState } = useEnvironmentState();
  const [isLoading, setIsLoading] = useState(true);
  const [expandedPlans, setExpandedPlans] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const t = setTimeout(() => setIsLoading(false), 600);
    return () => clearTimeout(t);
  }, []);

  const plans: PlanItem[] = runtimeState?.plans || [];

  const toggleExpand = (id: string) => {
    setExpandedPlans(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const getStatusBadge = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'running' || s === 'active') {
      return (
        <span style={{
          padding: '4px 10px',
          borderRadius: '20px',
          fontSize: '11px',
          fontWeight: 600,
          background: 'rgba(59, 130, 246, 0.15)',
          color: '#60a5fa',
          border: '1px solid rgba(59, 130, 246, 0.3)',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          letterSpacing: '0.03em',
          textTransform: 'uppercase'
        }}>
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#60a5fa', boxShadow: '0 0 8px #60a5fa' }} />
          Running
        </span>
      );
    }
    if (s === 'completed' || s === 'success') {
      return (
        <span style={{
          padding: '4px 10px',
          borderRadius: '20px',
          fontSize: '11px',
          fontWeight: 600,
          background: 'rgba(16, 185, 129, 0.15)',
          color: '#34d399',
          border: '1px solid rgba(16, 185, 129, 0.3)',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          letterSpacing: '0.03em',
          textTransform: 'uppercase'
        }}>
          ✓ Completed
        </span>
      );
    }
    if (s === 'failed' || s === 'error') {
      return (
        <span style={{
          padding: '4px 10px',
          borderRadius: '20px',
          fontSize: '11px',
          fontWeight: 600,
          background: 'rgba(239, 68, 68, 0.15)',
          color: '#f87171',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          letterSpacing: '0.03em',
          textTransform: 'uppercase'
        }}>
          ✕ Failed
        </span>
      );
    }
    return (
      <span style={{
        padding: '4px 10px',
        borderRadius: '20px',
        fontSize: '11px',
        fontWeight: 600,
        background: 'var(--glass-1)',
        color: 'var(--ink-2)',
        border: '1px solid var(--hairline-2)',
        textTransform: 'uppercase'
      }}>
        {status}
      </span>
    );
  };

  const getNodeStateIcon = (state: string) => {
    const s = state.toLowerCase();
    if (s === 'completed' || s === 'success') {
      return (
        <div style={{ width: '26px', height: '26px', borderRadius: '50%', background: 'rgba(16, 185, 129, 0.2)', border: '1px solid #34d399', color: '#34d399', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '13px', zIndex: 2 }}>
          ✓
        </div>
      );
    }
    if (s === 'running') {
      return (
        <div style={{ width: '26px', height: '26px', borderRadius: '50%', background: 'rgba(59, 130, 246, 0.2)', border: '1px solid #60a5fa', color: '#60a5fa', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '13px', zIndex: 2 }}>
          ●
        </div>
      );
    }
    if (s === 'failed' || s === 'error') {
      return (
        <div style={{ width: '26px', height: '26px', borderRadius: '50%', background: 'rgba(239, 68, 68, 0.2)', border: '1px solid #f87171', color: '#f87171', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '13px', zIndex: 2 }}>
          ✕
        </div>
      );
    }
    return (
      <div style={{ width: '26px', height: '26px', borderRadius: '50%', background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', color: 'var(--ink-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', zIndex: 2 }}>
        ○
      </div>
    );
  };

  return (
    <div className="surface-content" style={{ padding: '42px', height: '100%', display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
      <SurfaceHeader title="Implementation Architecture" sub="Plans · Step-by-step execution graphs" />
      
      {isLoading ? (
        <LoadingState message="Connecting to execution runtime..." />
      ) : plans.length === 0 ? (
        <EmptyState 
          title="No Active Plans" 
          description="Plans will appear here when Arova generates step-by-step architectures for complex tasks."
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', paddingBottom: '32px' }}>
          {plans.map((plan, idx) => {
            const planId = plan.plan_id || plan.id || `plan-${idx}`;
            const isExpanded = expandedPlans[planId] !== undefined ? expandedPlans[planId] : idx === 0;
            const nodes = plan.nodes || [];
            const completedNodes = nodes.filter(n => ['completed', 'success', 'COMPLETED'].includes(String(n.state).toLowerCase())).length;

            return (
              <div 
                key={planId} 
                style={{ 
                  background: 'var(--glass-2)', 
                  borderRadius: '16px', 
                  border: '1px solid var(--glass-edge)', 
                  boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
                  overflow: 'hidden',
                  transition: 'border-color 0.2s ease, transform 0.2s ease',
                }}
              >
                {/* Card Header Bar */}
                <div 
                  onClick={() => toggleExpand(planId)}
                  style={{ 
                    padding: '20px 24px', 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center', 
                    cursor: 'pointer',
                    borderBottom: isExpanded && nodes.length > 0 ? '1px solid var(--hairline-1)' : 'none',
                    background: 'rgba(255, 255, 255, 0.02)'
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      {getStatusBadge(plan.status || 'Running')}
                      <span style={{ fontSize: '13px', color: 'var(--ink-2)' }}>{plan.when || 'Recently'}</span>
                    </div>
                    <div style={{ fontWeight: 600, fontSize: '18px', color: 'var(--ink)', letterSpacing: '-0.01em' }}>
                      {plan.title}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                    {nodes.length > 0 && (
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--ink)' }}>
                          {plan.progress}%
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--ink-2)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          {completedNodes} of {nodes.length} steps
                        </div>
                      </div>
                    )}
                    <button 
                      style={{ 
                        background: 'var(--glass-1)', 
                        border: '1px solid var(--hairline-2)', 
                        borderRadius: '8px', 
                        width: '32px', 
                        height: '32px', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center', 
                        color: 'var(--ink)', 
                        cursor: 'pointer',
                        transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                        transition: 'transform 0.2s ease'
                      }}
                      aria-label="Toggle details"
                    >
                      ▼
                    </button>
                  </div>
                </div>

                {/* Progress Bar */}
                <div style={{ background: 'var(--glass-1)', height: '3px', width: '100%', overflow: 'hidden' }}>
                  <div style={{ 
                    width: `${plan.progress || 0}%`, 
                    background: plan.status === 'Completed' ? '#34d399' : plan.status === 'Failed' ? '#f87171' : 'var(--accent-gold, #f59e0b)', 
                    height: '100%',
                    transition: 'width 0.4s ease, background-color 0.3s ease'
                  }} />
                </div>

                {/* Step-by-step Node Tree */}
                {isExpanded && nodes.length > 0 && (
                  <div style={{ padding: '24px', background: 'rgba(0, 0, 0, 0.1)' }}>
                    <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--ink-2)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '16px' }}>
                      Execution Nodes ({nodes.length})
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', position: 'relative', paddingLeft: '4px' }}>
                      {/* Vertical connector pipeline */}
                      {nodes.length > 1 && (
                        <div style={{
                          position: 'absolute',
                          top: '24px',
                          bottom: '24px',
                          left: '16px',
                          width: '2px',
                          background: 'var(--hairline-2)',
                          zIndex: 1
                        }} />
                      )}

                      {nodes.map((node, nIdx) => {
                        const capName = node.capability || node.action || 'capability';
                        const stateStr = strToCapital(String(node.state));

                        return (
                          <div key={node.id || nIdx} style={{ display: 'flex', gap: '16px', position: 'relative', zIndex: 2 }}>
                            {getNodeStateIcon(String(node.state))}

                            <div style={{ 
                              flex: 1, 
                              background: 'var(--glass-1)', 
                              border: '1px solid var(--hairline-1)', 
                              borderRadius: '12px', 
                              padding: '14px 18px',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '10px',
                              boxShadow: '0 2px 8px rgba(0,0,0,0.06)'
                            }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                  <span style={{ 
                                    fontFamily: 'monospace', 
                                    background: 'rgba(255, 255, 255, 0.08)', 
                                    padding: '4px 8px', 
                                    borderRadius: '6px', 
                                    fontSize: '12px', 
                                    fontWeight: 600, 
                                    color: 'var(--ink)' 
                                  }}>
                                    {capName}
                                  </span>
                                  <span style={{ fontSize: '12px', color: 'var(--ink-2)' }}>Step #{nIdx + 1}</span>
                                </div>
                                <span style={{ fontSize: '11px', fontWeight: 600, color: getStateColor(String(node.state)), textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                  {stateStr}
                                </span>
                              </div>

                              {/* Payload arguments */}
                              {node.payload && Object.keys(node.payload).length > 0 && (
                                <div style={{ background: 'rgba(0, 0, 0, 0.2)', padding: '8px 12px', borderRadius: '8px', fontSize: '12px', fontFamily: 'monospace', color: 'var(--ink-2)', overflowX: 'auto' }}>
                                  <span style={{ color: 'var(--ink-3)', userSelect: 'none' }}>args: </span>
                                  {JSON.stringify(node.payload)}
                                </div>
                              )}

                              {/* Output message */}
                              {node.output && (
                                <div style={{ background: 'rgba(16, 185, 129, 0.1)', borderLeft: '3px solid #34d399', padding: '8px 12px', borderRadius: '4px', fontSize: '13px', color: '#a7f3d0' }}>
                                  <span style={{ fontWeight: 600, marginRight: '6px' }}>→ Output:</span> 
                                  {node.output}
                                </div>
                              )}

                              {/* Error message */}
                              {node.error && (
                                <div style={{ background: 'rgba(239, 68, 68, 0.1)', borderLeft: '3px solid #f87171', padding: '8px 12px', borderRadius: '4px', fontSize: '13px', color: '#fca5a5' }}>
                                  <span style={{ fontWeight: 600, marginRight: '6px' }}>▲ Error:</span> 
                                  {node.error}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

function strToCapital(s: string): string {
  if (!s) return 'Unknown';
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

function getStateColor(state: string): string {
  const s = state.toLowerCase();
  if (s === 'completed' || s === 'success') return '#34d399';
  if (s === 'failed' || s === 'error') return '#f87171';
  if (s === 'running') return '#60a5fa';
  return 'var(--ink-2)';
}
