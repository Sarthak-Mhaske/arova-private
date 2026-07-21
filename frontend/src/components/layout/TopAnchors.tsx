import React, { useState, useEffect } from 'react';
import { usePresenceState, useCognitionState, useSurfaceState } from '../../state';

export const TopAnchors: React.FC = () => {
  const { mode, setMode } = usePresenceState();
  const { threads } = useCognitionState();
  const { openSurface } = useSurfaceState();
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 10000);
    return () => clearInterval(timer);
  }, []);

  const dayName = now.toLocaleDateString('en-US', { weekday: 'long' });
  const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });

  const activeThreads = threads.filter(t => t.state !== 'archived' && t.state !== 'resolved' && t.state !== 'done');
  const threadCount = activeThreads.length;
  const threadLabel = threadCount === 0 ? 'Workspace clear' : threadCount === 1 ? '1 active thread' : `${threadCount} active threads`;

  return (
    <div className="anchors-top">
      <div className="modes">
        <button
          className={mode === 'ambient' ? 'active' : ''}
          onClick={() => setMode('ambient')}
        >
          Ambient
        </button>
        <button
          className={mode === 'focus' ? 'active' : ''}
          onClick={() => setMode('focus')}
        >
          Focus
        </button>
        <button
          className={mode === 'deep' ? 'active' : ''}
          onClick={() => setMode('deep')}
        >
          Deep
        </button>
      </div>

      <div className="modes">
        <button
          className={usePresenceState().atmosphere === 'daylight' ? 'active' : ''}
          onClick={() => usePresenceState.getState().setAtmosphere('daylight')}
        >
          Daylight
        </button>
        <button
          className={usePresenceState().atmosphere === 'nocturne' ? 'active' : ''}
          onClick={() => usePresenceState.getState().setAtmosphere('nocturne')}
        >
          Nocturne
        </button>
      </div>

      <div className="anchor"><span className="dot"></span> {dayName} · {timeStr}</div>
      <button 
        className="anchor violet" 
        onClick={() => openSurface('threads')}
        style={{ background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit', fontSize: 'inherit', color: 'inherit' }}
      >
        <span className="dot"></span> {threadLabel}
      </button>
    </div>
  );
};
