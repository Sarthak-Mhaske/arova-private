import React, { useEffect, useState } from 'react';
import { useSurfaceState, useCognitionState } from '../../state';
import { SurfaceHeader, EmptyState, LoadingState } from '../ui/CoherenceComponents';
import { ThreadCard } from './ThreadCard';
import { socket } from '../../runtime/socket';

export const ThreadsSurface: React.FC = () => {
  const { activeSurface } = useSurfaceState();
  const { threads } = useCognitionState();
  const [isLoading, setIsLoading] = useState(true);
  const [showBackground, setShowBackground] = useState(false);

  useEffect(() => {
    // Simulated loading delay to enforce Completion Rule
    const t = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(t);
  }, []);

  if (activeSurface !== 'threads' as any) return null;

  const activeThreads = threads.filter(t => t.state !== 'archived');
  
  const momentumThreads = activeThreads.filter(t => 
    t.pinned || (t.resonance && t.resonance > 0) || (t.active_pressures && t.active_pressures > 0)
  );
  
  const backgroundThreads = activeThreads.filter(t => !momentumThreads.includes(t));

  return (
    <div className="surface-content" id="surface-threads" style={{ padding: '42px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <SurfaceHeader title="Cognitive Threads" sub="Contextual sessions and organized chats" />
        <button
          onClick={() => {
            socket.sendEvent({ type: 'client.new_thread' });
            useCognitionState.getState().setItems([]);
            useSurfaceState.getState().closeSurface();
          }}
          style={{
            padding: '8px 16px',
            borderRadius: '8px',
            border: '1px solid var(--hairline-2)',
            background: 'var(--glass-2)',
            color: 'var(--ink)',
            fontSize: '13px',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
        >
          <span>+</span> New Chat
        </button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {isLoading ? (
          <LoadingState message="Synchronizing cognitive threads..." />
        ) : activeThreads.length === 0 ? (
          <EmptyState 
            title="No Active Momentum" 
            description="Your cognitive workspace is clear. No threads currently require your attention."
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
            {momentumThreads.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h3 style={{ fontSize: '14px', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--ink-3)', margin: 0 }}>Momentum</h3>
                {momentumThreads.map(t => (
                  <ThreadCard key={t.thread_id} thread={t} />
                ))}
              </div>
            )}
            
            {backgroundThreads.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <button 
                  onClick={() => setShowBackground(!showBackground)}
                  style={{
                    background: 'none', border: 'none', padding: 0, margin: 0,
                    display: 'flex', alignItems: 'center', gap: '8px',
                    fontSize: '14px', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--ink-3)', cursor: 'pointer'
                  }}
                >
                  <span style={{ transform: showBackground ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }}>▸</span>
                  Background Threads ({backgroundThreads.length})
                </button>
                
                {showBackground && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', paddingLeft: '16px', marginTop: '8px' }}>
                    {backgroundThreads.map(t => (
                      <div key={t.thread_id} style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--ink-2)', fontSize: '15px' }}>
                        <span style={{ color: 'var(--ink-4)' }}>▸</span>
                        {t.title}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
