import React, { useState, useEffect } from 'react';
import { usePresenceState, useCognitionState, useSurfaceState } from '../../state';

export const TopAnchors: React.FC = () => {
  const { mode, setMode, atmosphere, setAtmosphere } = usePresenceState();
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
    <>
      {/* Centered Brand Title */}
      <div 
        style={{
          position: 'fixed',
          top: '28px',
          left: '50%',
          transform: 'translateX(-50%)',
          fontSize: '11px',
          fontWeight: 700,
          letterSpacing: '0.45em',
          textTransform: 'uppercase',
          color: 'var(--ink-mute)',
          zIndex: 'var(--z-anchors, 6)',
          pointerEvents: 'none',
          userSelect: 'none',
          opacity: 0.85
        }}
      >
        A R O V A
      </div>

      <div className="anchors-top">
      {/* Mode Selector */}
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

      {/* Theme Selector */}
      <div className="modes">
        <button
          className={atmosphere === 'daylight' ? 'active' : ''}
          onClick={() => setAtmosphere('daylight')}
        >
          Daylight
        </button>
        <button
          className={atmosphere === 'nocturne' ? 'active' : ''}
          onClick={() => setAtmosphere('nocturne')}
        >
          Nocturne
        </button>
      </div>

      {/* Time Anchor */}
      <div className="anchor">
        <span className="dot"></span> {dayName} · {timeStr}
      </div>

      {/* Global Shortcut Summon Trigger Badge */}
      <button 
        className="anchor"
        onClick={() => openSurface('command_palette')}
        style={{ 
          background: 'var(--glass-1)', 
          border: '1px solid var(--hairline-2)', 
          cursor: 'pointer', 
          fontFamily: 'inherit', 
          fontSize: '12px', 
          color: 'var(--ink-2)',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '5px 10px',
          borderRadius: '999px',
          transition: 'all 0.2s ease'
        }}
        title="Press Ctrl+Space (or ⌘+Space) to summon Command Palette"
      >
        <span style={{ fontSize: '11px', color: 'var(--accent-amber)', fontWeight: 700, padding: '1px 5px', borderRadius: '4px', background: 'rgba(217, 119, 6, 0.15)', border: '1px solid rgba(217, 119, 6, 0.25)' }}>
          {typeof navigator !== 'undefined' && (navigator.platform?.toUpperCase().includes('MAC') || navigator.userAgent?.includes('Mac')) ? '⌘ Space' : 'Ctrl Space'}
        </span>
        <span style={{ fontWeight: 500 }}>Command</span>
      </button>

      {/* Status Anchor */}
      <button 
        className={`anchor ${atmosphere === 'daylight' ? 'cyan' : 'sage'}`} 
        onClick={() => openSurface('threads')}
        style={{ background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit', fontSize: 'inherit', color: 'inherit' }}
      >
        <span className="dot" style={{ background: atmosphere === 'daylight' ? '#0284c7' : '#22c55e', boxShadow: atmosphere === 'daylight' ? '0 0 8px rgba(2,132,199,0.6)' : '0 0 8px rgba(34,197,94,0.6)' }}></span> {threadLabel}
      </button>
    </div>
  </>
);
};

