import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useCognitionState } from '../../state';
import { socket } from '../../runtime/socket';

const MDiv: any = motion.div;

export const PersonalMemoryPolicyDialog: React.FC = () => {
  const { contextualCandidate, setContextualCandidate } = useCognitionState();
  const [selectedPolicy, setSelectedPolicy] = useState<string>('review_queue');

  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setContextualCandidate(null);
      }
    };
    if (contextualCandidate) {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [contextualCandidate, setContextualCandidate]);

  if (!contextualCandidate) return null;

  const handleConfirm = (rememberThis: boolean) => {
    socket.sendEvent({ type: 'memory.set_tier2_policy', mode: selectedPolicy });

    if (rememberThis) {
      socket.sendEvent({ type: 'memory.approve', memory_id: contextualCandidate.id, duration: 'permanent', memory: contextualCandidate });
    } else {
      socket.sendEvent({ type: 'memory.reject', memory_id: contextualCandidate.id });
    }

    setContextualCandidate(null);
  };

  const policies = [
    { id: 'review_queue', label: 'Review later', desc: 'Inbox' },
    { id: 'auto_save', label: 'Save automatically', desc: '' },
    { id: 'ask', label: 'Ask every time', desc: '' },
  ];

  return (
    <AnimatePresence>
      <MDiv
        drag
        dragMomentum={false}
        initial={{ opacity: 0, scale: 0.9, filter: 'blur(6px)' }}
        animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
        exit={{ opacity: 0, scale: 0.9, filter: 'blur(6px)' }}
        transition={{ duration: 0.5, ease: [0.32, 0.72, 0.24, 1] }}
        style={{
          position: 'fixed',
          top: 'calc(50vh - 150px)',
          left: 'calc(50vw - 180px)',
          width: '360px',
          background: 'var(--glass-2)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid var(--hairline-2)',
          borderRadius: '14px',
          padding: '18px 22px',
          zIndex: 'var(--z-tooltip)',
          cursor: 'grab'
        }}
      >
        {/* Label */}
        <div style={{
          fontSize: '10px',
          fontWeight: 600,
          letterSpacing: '0.22em',
          textTransform: 'uppercase' as const,
          color: 'var(--accent-gold)',
          marginBottom: '10px'
        }}>
          REMEMBERING
        </div>

        {/* Memory content */}
        <div style={{
          fontSize: '14.5px',
          lineHeight: 1.55,
          color: 'var(--ink)',
          marginBottom: '6px'
        }}>
          {contextualCandidate.content}
        </div>

        <div style={{
          fontSize: '12.5px',
          color: 'var(--ink-3)',
          lineHeight: 1.5,
          marginBottom: '16px'
        }}>
          Personal memories help maintain continuity.
          How should Arova handle memories like this?
        </div>

        {/* Policy selection */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '16px' }}>
          {policies.map(p => (
            <label
              key={p.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '8px 12px',
                borderRadius: '8px',
                background: selectedPolicy === p.id ? 'var(--glass-3)' : 'transparent',
                border: selectedPolicy === p.id ? '1px solid var(--hairline-2)' : '1px solid transparent',
                cursor: 'pointer',
                transition: 'all 180ms ease',
                fontSize: '13px',
                color: 'var(--ink-2)',
              }}
              onClick={() => setSelectedPolicy(p.id)}
            >
              <div style={{
                width: '14px',
                height: '14px',
                borderRadius: '50%',
                border: `2px solid ${selectedPolicy === p.id ? 'var(--accent-gold)' : 'var(--ink-mute)'}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                transition: 'border-color 180ms ease'
              }}>
                {selectedPolicy === p.id && (
                  <div style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    background: 'var(--accent-gold)'
                  }} />
                )}
              </div>
              <span>{p.label}</span>
              {p.desc && <span style={{ fontSize: '11px', color: 'var(--ink-mute)', marginLeft: 'auto' }}>{p.desc}</span>}
            </label>
          ))}
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={() => handleConfirm(true)} style={{
            background: 'var(--glass-3)',
            border: '1px solid var(--hairline-2)',
            borderRadius: '8px',
            padding: '7px 16px',
            fontSize: '12.5px',
            color: 'var(--ink)',
            cursor: 'pointer',
            fontFamily: 'var(--font)',
            fontWeight: 500,
            transition: 'background 180ms ease'
          }}>
            Remember This
          </button>
          <button onClick={() => handleConfirm(false)} style={{
            background: 'transparent',
            border: 'none',
            padding: '7px 14px',
            fontSize: '12.5px',
            color: 'var(--ink-mute)',
            cursor: 'pointer',
            fontFamily: 'var(--font)',
            fontWeight: 500
          }}>
            Don't Remember
          </button>
        </div>
      </MDiv>
    </AnimatePresence>
  );
};
