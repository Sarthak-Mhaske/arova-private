import React from 'react';
import { SurfaceHead } from './SurfaceHead';
import { useCognitionState, useOrbState, useEnvironmentState } from '../../state';

export const ProjectionInspector: React.FC = () => {
  const { threads, items, memories } = useCognitionState();
  const { mode } = useOrbState();
  const { roomState, fragments } = useEnvironmentState();

  return (
    <>
      <SurfaceHead title="Projection Inspector" sub="Phase 7.25 · Raw Runtime Dump" />
      <div className="surface-content" style={{ padding: '0 42px 42px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        
        <div style={{ background: 'var(--glass-1)', padding: '24px', borderRadius: '16px', border: '1px solid var(--glass-edge)', fontFamily: 'monospace', fontSize: '13px' }}>
          <div style={{ color: 'var(--ink)', marginBottom: '8px' }}>// Raw RuntimeProjection received by frontend</div>
          <div style={{ color: 'var(--ink-2)' }}>
            <pre style={{ whiteSpace: 'pre-wrap', margin: 0, padding: '16px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px' }}>
{JSON.stringify({
  orb_state: { state: mode },
  visible_threads: threads.length,
  ambient_signals: fragments.length,
  surfaced_memories: memories.length,
  stream_items_count: items.length,
  room_state: roomState || {}
}, null, 2)}
            </pre>
          </div>
        </div>

      </div>
    </>
  );
};
