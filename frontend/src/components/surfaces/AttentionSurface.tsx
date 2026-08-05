import React, { useEffect, useState } from 'react';
import { SurfaceHeader, SurfaceSection, MetricCard, InfoRow, LoadingState } from '../ui/CoherenceComponents';
import { useEnvironmentState } from '../../state';

export const AttentionSurface: React.FC = () => {
  const { roomState } = useEnvironmentState();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(t);
  }, []);

  const attentionMode = roomState?.attention || 'Active Focus';
  const focusMins = roomState?.focus_duration_minutes || 15;
  const isDeepWork = attentionMode === 'Deep Work' || attentionMode === 'Active Focus';

  return (
    <div className="surface-content" style={{ padding: '36px 42px', height: '100%', display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
      <SurfaceHeader title="How you are working" sub="Attention · Cognitive heuristics" />
      
      {isLoading ? (
        <LoadingState message="Analyzing heuristic patterns..." />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          <SurfaceSection>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
              <MetricCard 
                label="Current State" 
                value={attentionMode} 
                accent={isDeepWork} 
              />
              <MetricCard 
                label="Focus Duration" 
                value={`${focusMins}m`} 
              />
              <MetricCard 
                label="Cognitive Load" 
                value={roomState?.mode === 'coding' ? 'High' : 'Optimal'} 
              />
            </div>
          </SurfaceSection>

          <SurfaceSection title="Heuristics">
            <InfoRow label="Interruption Rate" value={roomState?.heuristics?.interruption_rate || 'Low'} />
            <InfoRow label="Context Switching" value={roomState?.heuristics?.context_switching || ((roomState?.workspace && roomState.workspace.length > 2) ? 'Moderate' : 'Minimal')} />
            <InfoRow label="Flow Resonance" value={roomState?.heuristics?.flow_resonance ? `${roomState.heuristics.flow_resonance}%` : `${Math.min(96, 75 + Math.floor(focusMins * 0.8))}%`} />
          </SurfaceSection>
        </div>
      )}
    </div>
  );
};
