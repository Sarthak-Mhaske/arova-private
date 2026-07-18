import React, { useEffect, useState } from 'react';
import { SurfaceHeader, SurfaceSection, MetricCard, InfoRow, EmptyState, LoadingState } from '../ui/CoherenceComponents';
import { useEnvironmentState } from '../../state';

export const AttentionSurface: React.FC = () => {
  const { roomState } = useEnvironmentState();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(t);
  }, []);

  const hasAttention = roomState && roomState.attention;

  return (
    <div className="surface-content" style={{ padding: '42px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <SurfaceHeader title="How you are working" sub="Attention · Cognitive heuristics" />
      
      {isLoading ? (
        <LoadingState message="Analyzing heuristic patterns..." />
      ) : !hasAttention ? (
        <EmptyState 
          title="Attention Idle" 
          description="Arova requires more interaction data to determine your current cognitive state."
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          <SurfaceSection>
            <div style={{ display: 'flex', gap: '16px' }}>
              <MetricCard 
                label="Current State" 
                value={roomState.attention} 
                accent={roomState.attention === 'Deep Work'} 
              />
              <MetricCard 
                label="Focus Duration" 
                value={`${roomState.focus_duration_minutes || 0}m`} 
              />
            </div>
          </SurfaceSection>

          <SurfaceSection title="Heuristics">
            <InfoRow label="Interruption Rate" value="Low" />
            <InfoRow label="Context Switching" value="Minimal" />
            <InfoRow label="Flow Resonance" value="87%" />
          </SurfaceSection>
        </div>
      )}
    </div>
  );
};
