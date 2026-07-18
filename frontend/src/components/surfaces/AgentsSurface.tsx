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
          {/* Future mapping of active agents */}
        </div>
      )}
    </div>
  );
};
