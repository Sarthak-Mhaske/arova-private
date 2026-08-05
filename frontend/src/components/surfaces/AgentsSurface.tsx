import React, { useEffect, useState } from 'react';
import { SurfaceHeader, EmptyState, LoadingState } from '../ui/CoherenceComponents';
import { useEnvironmentState } from '../../state';

export const AgentsSurface: React.FC = () => {
  const { runtimeState } = useEnvironmentState();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(t);
  }, []);

  const agents = runtimeState?.agents || [];

  return (
    <div className="surface-content" style={{ padding: '42px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <SurfaceHeader title="Autonomous Execution" sub="Agents · Background tasks and delegation" />
      
      {isLoading ? (
        <LoadingState message="Connecting to execution runtime..." />
      ) : agents.length === 0 ? (
        <EmptyState 
          title="No Active Autonomous Agents" 
          description="Agents will appear here when Arova is given long-running execution tasks."
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {agents.map((agent: any, idx: number) => (
            <div key={idx} style={{ padding: '16px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                 <div style={{ fontWeight: 600, fontSize: '15px', color: `var(--accent-${agent.color || 'default'})` }}>{agent.name}</div>
                 <div style={{ fontSize: '12px', color: 'var(--ink-3)' }}>{agent.statusText}</div>
              </div>
              <div style={{ fontSize: '14px', color: 'var(--ink-2)' }}>{agent.role}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
