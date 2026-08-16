import React, { useState, useEffect } from 'react';
import { usePresenceState } from '../../state';
import { socket } from '../../runtime/socket';

export const SyncStatusPill: React.FC = () => {
  const { atmosphere } = usePresenceState();
  const [connected, setConnected] = useState(socket.connected);
  const [lastSyncTime, setLastSyncTime] = useState<Date>(new Date());
  const [timeAgoStr, setTimeAgoStr] = useState('Just now');

  useEffect(() => {
    const handleEvent = () => {
      setConnected(true);
      setLastSyncTime(new Date());
    };

    window.addEventListener('arova-event', handleEvent);
    const interval = setInterval(() => {
      setConnected(socket.connected);
      const diffSecs = Math.floor((Date.now() - lastSyncTime.getTime()) / 1000);
      if (diffSecs < 10) setTimeAgoStr('Just now');
      else if (diffSecs < 60) setTimeAgoStr(`${diffSecs}s ago`);
      else {
        const mins = Math.floor(diffSecs / 60);
        setTimeAgoStr(`${mins}m ago`);
      }
    }, 5000);

    return () => {
      window.removeEventListener('arova-event', handleEvent);
      clearInterval(interval);
    };
  }, [lastSyncTime]);

  return (
    <div className="sync-status-pill">
      {/* 8-point compass star / diamond SVG icon badge */}
      <div 
        style={{
          width: '32px',
          height: '32px',
          borderRadius: '50%',
          background: 'var(--glass-2)',
          border: '1px solid var(--hairline-2)',
          display: 'grid',
          placeItems: 'center',
          color: 'var(--accent-gold, #e0a352)',
          flexShrink: 0
        }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
        </svg>
      </div>

      {/* Status text */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
        <div style={{ fontSize: '13px', fontWeight: 650, color: 'var(--ink)', letterSpacing: '0.01em', lineHeight: 1.2 }}>
          {connected ? 'Arova is up to date' : 'Connecting to daemon...'}
        </div>
        <div style={{ fontSize: '11.5px', fontWeight: 500, color: 'var(--ink-2)', display: 'flex', alignItems: 'center', gap: '6px', lineHeight: 1.2 }}>
          <span 
            style={{ 
              width: '6px', 
              height: '6px', 
              borderRadius: '50%', 
              background: connected 
                ? (atmosphere === 'daylight' ? '#16a34a' : '#22c55e') 
                : '#ef4444',
              boxShadow: connected 
                ? (atmosphere === 'daylight' ? '0 0 6px rgba(22,163,74,0.8)' : '0 0 6px rgba(34,197,94,0.8)') 
                : '0 0 6px rgba(239,68,68,0.8)'
            }} 
          />
          <span>{connected ? `Last sync: ${timeAgoStr}` : 'Offline'}</span>
        </div>
      </div>
    </div>
  );
};

