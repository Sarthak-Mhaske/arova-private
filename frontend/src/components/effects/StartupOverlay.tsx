import React, { useEffect, useState } from 'react';
import { useStartupState, StartupPhase } from '../../state/startupState';
import { invoke } from '@tauri-apps/api/core';
import { socket } from '../../runtime/socket';

const PHASE_LABELS: Record<StartupPhase, string> = {
  starting: 'Starting Arova...',
  launching_daemon: 'Launching local cognition daemon...',
  initializing_workspace: 'Initializing workspace state...',
  connecting: 'Connecting to engine...',
  ready: '✓ Ready',
  failed: "Couldn't start local engine"
};

const PHASE_STEPS: StartupPhase[] = ['starting', 'launching_daemon', 'initializing_workspace', 'connecting'];

export const StartupOverlay: React.FC = () => {
  const { phase, error, reset } = useStartupState();
  const [visible, setVisible] = useState(true);
  const [fade, setFade] = useState(false);

  useEffect(() => {
    if (phase === 'ready') {
      const t1 = setTimeout(() => setFade(true), 500);
      const t2 = setTimeout(() => setVisible(false), 1100);
      return () => {
        clearTimeout(t1);
        clearTimeout(t2);
      };
    } else {
      setVisible(true);
      setFade(false);
    }
  }, [phase]);

  if (!visible && phase === 'ready') return null;

  const handleRetry = () => {
    reset();
    socket.connect();
  };

  const handleViewLogs = async () => {
    try {
      await invoke('export_debug_report');
      alert('Debug report generated (daemon.log in application root).');
    } catch (err) {
      console.error('Failed to export debug report:', err);
      alert('Check daemon.log in your installation directory.');
    }
  };

  const currentStepIdx = PHASE_STEPS.indexOf(phase as StartupPhase);

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 99999,
        background: 'radial-gradient(1000px 900px at 50% 42%, rgba(26, 22, 32, 0.94) 0%, rgba(10, 9, 14, 0.97) 100%)',
        backdropFilter: 'blur(36px) saturate(150%)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        opacity: fade ? 0 : 1,
        transition: 'opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
        color: '#f4ece1',
        fontFamily: "'Inter', 'SF Pro Display', system-ui, sans-serif",
        userSelect: 'none'
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '28px',
          width: '420px',
          maxWidth: '90vw',
          textAlign: 'center',
          padding: '44px 36px',
          borderRadius: '24px',
          background: 'rgba(22, 19, 28, 0.7)',
          border: '1px solid rgba(232, 208, 164, 0.12)',
          boxShadow: '0 30px 80px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
          position: 'relative',
          overflow: 'hidden'
        }}
      >
        {/* Subtle glass shimmer background line */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '1px',
            background: 'linear-gradient(90deg, transparent, rgba(232, 208, 164, 0.3), transparent)'
          }}
        />

        {/* Glowing Arova Ethereal Indicator */}
        <div style={{ position: 'relative', width: '64px', height: '64px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {phase === 'ready' ? (
            <div
              style={{
                width: '56px',
                height: '56px',
                borderRadius: '50%',
                background: 'radial-gradient(circle, rgba(74, 222, 128, 0.25) 0%, rgba(74, 222, 128, 0.05) 70%)',
                border: '1px solid rgba(74, 222, 128, 0.5)',
                color: '#4ade80',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '24px',
                fontWeight: 600,
                boxShadow: '0 0 30px rgba(74, 222, 128, 0.3)'
              }}
            >
              ✓
            </div>
          ) : phase === 'failed' ? (
            <div
              style={{
                width: '56px',
                height: '56px',
                borderRadius: '50%',
                background: 'radial-gradient(circle, rgba(248, 113, 113, 0.25) 0%, rgba(248, 113, 113, 0.05) 70%)',
                border: '1px solid rgba(248, 113, 113, 0.5)',
                color: '#f87171',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '24px',
                fontWeight: 600,
                boxShadow: '0 0 30px rgba(248, 113, 113, 0.3)'
              }}
            >
              !
            </div>
          ) : (
            <>
              {/* Pulsing Ethereal Halo Rings */}
              <div
                style={{
                  position: 'absolute',
                  inset: '-6px',
                  borderRadius: '50%',
                  border: '1px solid rgba(232, 208, 164, 0.25)',
                  animation: 'arova-pulse-ring 2.4s ease-in-out infinite'
                }}
              />
              <div
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '50%',
                  border: '2px solid rgba(255, 255, 255, 0.08)',
                  borderTopColor: '#e8d0a4',
                  borderRightColor: 'rgba(232, 208, 164, 0.4)',
                  animation: 'arova-spin 1.2s cubic-bezier(0.5, 0, 0.5, 1) infinite',
                  boxShadow: '0 0 20px rgba(232, 208, 164, 0.15)'
                }}
              />
            </>
          )}
        </div>

        {/* Phase Header & Descriptions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
          <h2
            style={{
              fontSize: '17px',
              fontWeight: 500,
              letterSpacing: '-0.015em',
              margin: 0,
              color: phase === 'failed' ? '#f87171' : phase === 'ready' ? '#4ade80' : '#f4ece1'
            }}
          >
            {PHASE_LABELS[phase]}
          </h2>

          {phase !== 'failed' && phase !== 'ready' && (
            <p style={{ fontSize: '13px', color: 'rgba(244, 236, 225, 0.55)', margin: 0, fontWeight: 400 }}>
              Preparing your context-aware environment
            </p>
          )}

          {phase === 'failed' && (
            <p style={{ fontSize: '13px', color: 'rgba(248, 113, 113, 0.8)', margin: 0, lineHeight: 1.4 }}>
              {error || 'Unable to establish local daemon socket bridge.'}
            </p>
          )}
        </div>

        {/* Step Progress Ladder Dots */}
        {phase !== 'failed' && phase !== 'ready' && (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', justifyContent: 'center' }}>
            {PHASE_STEPS.map((step, idx) => (
              <div
                key={step}
                style={{
                  height: '4px',
                  width: idx === currentStepIdx ? '24px' : '8px',
                  borderRadius: '2px',
                  background: idx <= currentStepIdx ? '#e8d0a4' : 'rgba(255, 255, 255, 0.12)',
                  transition: 'all 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
                  boxShadow: idx === currentStepIdx ? '0 0 10px rgba(232, 208, 164, 0.4)' : 'none'
                }}
              />
            ))}
          </div>
        )}

        {/* Action Buttons on Failure */}
        {phase === 'failed' && (
          <div style={{ display: 'flex', gap: '12px', marginTop: '6px', width: '100%' }}>
            <button
              onClick={handleRetry}
              style={{
                flex: 1,
                padding: '11px 20px',
                borderRadius: '12px',
                background: 'linear-gradient(135deg, #e8d0a4 0%, #d4a878 100%)',
                color: '#14110d',
                border: 'none',
                fontSize: '13.5px',
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: '0 4px 16px rgba(232, 208, 164, 0.25)',
                transition: 'all 0.2s ease'
              }}
            >
              Retry
            </button>
            <button
              onClick={handleViewLogs}
              style={{
                flex: 1,
                padding: '11px 20px',
                borderRadius: '12px',
                background: 'rgba(255, 255, 255, 0.06)',
                color: '#f4ece1',
                border: '1px solid rgba(255, 255, 255, 0.14)',
                fontSize: '13.5px',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              View Logs
            </button>
          </div>
        )}
      </div>

      <style>{`
        @keyframes arova-spin {
          to { transform: rotate(360deg); }
        }
        @keyframes arova-pulse-ring {
          0%, 100% { transform: scale(0.95); opacity: 0.3; }
          50% { transform: scale(1.1); opacity: 0.75; }
        }
      `}</style>
    </div>
  );
};
