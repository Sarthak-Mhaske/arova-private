import React, { useEffect, useState } from 'react';
import { SurfaceHeader, SurfaceSection, InfoRow, EmptyState, LoadingState } from '../ui/CoherenceComponents';
import { useEnvironmentState } from '../../state';

export const ContextSurface: React.FC = () => {
  const { contextState } = useEnvironmentState();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="surface-content" style={{ padding: '42px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <SurfaceHeader title="What I understand" sub="Context · Current semantic projection" />
      
      {isLoading ? (
        <LoadingState message="Synchronizing semantic context..." />
      ) : !contextState ? (
        <EmptyState 
          title="Context Idle" 
          description="Arova is waiting for significant activity to form a coherent context."
        />
      ) : (
        <SurfaceSection>
          <InfoRow label="Current Room" value={contextState.room || 'Idle'} />
          <InfoRow label="Active Thread" value={contextState.active_thread || 'None'} />
          <InfoRow label="Current Intent" value={contextState.current_intent || 'None'} />
        </SurfaceSection>
      )}
    </div>
  );
};
