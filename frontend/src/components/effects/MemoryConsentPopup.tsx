import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useCognitionState } from '../../state';
import { socket } from '../../runtime/socket';

const MDiv: any = motion.div;

export const MemoryConsentPopup: React.FC = () => {
  const { sensitiveCandidate, setSensitiveCandidate } = useCognitionState();
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    if (!sensitiveCandidate) { setProgress(100); return; }

    const duration = 30000;
    const interval = 100;
    const step = (interval / duration) * 100;
    const timer = setInterval(() => {
      setProgress(p => {
        if (p <= 0) {
          socket.sendEvent({ type: 'memory.reject', memory_id: sensitiveCandidate.id });
          setSensitiveCandidate(null);
          return 100;
        }
        return p - step;
      });
    }, interval);

    return () => clearInterval(timer);
  }, [sensitiveCandidate, setSensitiveCandidate]);

  const handleAction = (duration: 'permanent' | '30_days' | 'session_only' | 'reject') => {
    if (duration === 'reject') {
      socket.sendEvent({ type: 'memory.reject', memory_id: sensitiveCandidate.id });
    } else {
      socket.sendEvent({ type: 'memory.approve', memory_id: sensitiveCandidate.id, duration, memory: sensitiveCandidate });
    }
    setSensitiveCandidate(null);
  };

  return (
    <AnimatePresence>
      {sensitiveCandidate && (
        <MDiv
          drag
          dragMomentum={false}
          initial={{ opacity: 0, scale: 0.9, filter: 'blur(4px)' }}
          animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
          exit={{ opacity: 0, scale: 0.9, filter: 'blur(4px)' }}
          transition={{ duration: 0.4, ease: [0.32, 0.72, 0.24, 1] }}
          style={{
            position: 'fixed',
            top: 'calc(50vh - 120px)',
            left: 'calc(50vw - 170px)',
            width: '340px',
            background: 'var(--glass-2)',
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
            border: '1px solid var(--hairline-2)',
            borderRadius: '14px',
            padding: '16px 20px',
            zIndex: 'var(--z-tooltip)',
            overflow: 'hidden',
            cursor: 'grab'
          }}
        >
          {/* Label */}
          <div style={{
            fontSize: '10px',
            fontWeight: 600,
            letterSpacing: '0.22em',
            textTransform: 'uppercase' as const,
            color: 'var(--accent-amber)',
            marginBottom: '8px'
          }}>
            SENSITIVE
          </div>

          {/* Content */}
          <div style={{
            fontSize: '14.5px',
            lineHeight: 1.55,
            color: 'var(--ink)',
            marginBottom: '14px'
          }}>
            {sensitiveCandidate.content}
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button onClick={() => handleAction('permanent')} style={{
              background: 'var(--glass-3)',
              border: '1px solid var(--hairline-2)',
              borderRadius: '8px',
              padding: '6px 12px',
              fontSize: '12px',
              color: 'var(--ink-2)',
              cursor: 'pointer',
              fontFamily: 'var(--font)',
              fontWeight: 500,
              transition: 'background 180ms ease'
            }}>
              Remember
            </button>
            <button onClick={() => handleAction('session_only')} style={{
              background: 'transparent',
              border: '1px solid var(--hairline)',
              borderRadius: '8px',
              padding: '6px 12px',
              fontSize: '12px',
              color: 'var(--ink-3)',
              cursor: 'pointer',
              fontFamily: 'var(--font)',
              fontWeight: 500
            }}>
              Session Only
            </button>
            <button onClick={() => handleAction('reject')} style={{
              background: 'transparent',
              border: 'none',
              padding: '6px 12px',
              fontSize: '12px',
              color: 'var(--ink-mute)',
              cursor: 'pointer',
              fontFamily: 'var(--font)',
              fontWeight: 500
            }}>
              Dismiss
            </button>
          </div>

          {/* Timeout bar */}
          <div style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            width: `${progress}%`,
            height: '2px',
            background: 'var(--accent-amber)',
            opacity: 0.5,
            transition: 'width 100ms linear',
            borderRadius: '0 1px 0 0'
          }} />
        </MDiv>
      )}
    </AnimatePresence>
  );
};
