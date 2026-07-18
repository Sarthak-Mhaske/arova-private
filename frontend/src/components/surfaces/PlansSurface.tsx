import React, { useEffect, useState } from 'react';
import { SurfaceHeader, EmptyState, LoadingState } from '../ui/CoherenceComponents';
import { useEnvironmentState } from '../../state';

export const PlansSurface: React.FC = () => {
  const { runtimeState } = useEnvironmentState();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(t);
  }, []);

  const plans = runtimeState?.plans || [];

  return (
    <div className="surface-content" style={{ padding: '42px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <SurfaceHeader title="Implementation Architecture" sub="Plans · Step-by-step execution graphs" />
      
      {isLoading ? (
        <LoadingState message="Connecting to execution runtime..." />
      ) : plans.length === 0 ? (
        <EmptyState 
          title="No Active Plans" 
          description="Plans will appear here when Arova generates step-by-step architectures for complex tasks."
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Future mapping of active plans */}
        </div>
      )}
    </div>
  );
};
