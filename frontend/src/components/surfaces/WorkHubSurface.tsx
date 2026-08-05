import React, { useEffect, useState } from 'react';
import { socket } from '../../runtime/socket';

interface WorkHubSurfaceProps {
  onContinue?: () => void;
}

export const WorkHubSurface: React.FC<WorkHubSurfaceProps> = ({ onContinue }) => {
  const [activeWorkspace, setActiveWorkspace] = useState<any>(null);
  const [completedWork, setCompletedWork] = useState<any[]>([]);
  const [_isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const handleEvent = (e: any) => {
      const ev = e.detail;
      if (ev && ev.type === 'workspace.sync') {
        if (ev.active_workspace) {
          setActiveWorkspace(ev.active_workspace);
        }
        if (Array.isArray(ev.completed_work)) {
          setCompletedWork(ev.completed_work);
        }
        setIsLoading(false);
      } else if (ev && (ev.type === 'work.COMPLETED_WORK_CREATED' || ev.type === 'work.WORK_UPDATED')) {
        socket.sendEvent({ type: 'workspace.get_request' });
      }
    };

    window.addEventListener('arova-event', handleEvent);
    socket.sendEvent({ type: 'workspace.get_request' });

    const timeout = setTimeout(() => {
      setIsLoading(false);
    }, 1000);

    return () => {
      window.removeEventListener('arova-event', handleEvent);
      clearTimeout(timeout);
    };
  }, []);

  const handleAccept = (workId: string) => {
    socket.sendEvent({ type: 'work.accept', work_id: workId });
    setCompletedWork(prev => prev.map(w => w.work_id === workId ? { ...w, status: 'Accepted' } : w));
  };

  const handleReject = (workId: string) => {
    socket.sendEvent({ type: 'work.reject', work_id: workId });
    setCompletedWork(prev => prev.map(w => w.work_id === workId ? { ...w, status: 'Rejected' } : w));
  };

  const displayWork = completedWork;

  const activeTitle = activeWorkspace?.title || 'Current Workspace';
  const activeGoal = activeWorkspace?.understanding?.momentum?.goal || '';

  return (
    <div className="surface-content" style={{ padding: '36px 42px', height: '100%', display: 'flex', flexDirection: 'column', overflowY: 'auto', boxSizing: 'border-box' }}>
      
      {/* Header Banner */}
      <div style={{ marginBottom: '28px' }}>
        <div style={{ fontSize: '13px', color: 'var(--accent-gold)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '4px' }}>
          Active Objective
        </div>
        <div style={{ fontSize: '26px', fontWeight: 700, color: 'var(--ink)', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
          {activeTitle}
        </div>
        <div style={{ fontSize: '14px', color: 'var(--ink-2)', marginTop: '6px', lineHeight: 1.5 }}>
          {activeGoal}
        </div>
      </div>

      {/* Main Completed Work List */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: '12px', color: 'var(--ink-3)', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            Project Journal · Finished Work
          </div>
          <div style={{ fontSize: '12px', color: 'var(--accent-gold)', fontWeight: 500 }}>
            Inferred NWR: ~{displayWork.reduce((acc, w) => acc + (w.status === 'Accepted' ? w.net_work_removed_minutes : (w.verified ? w.net_work_removed_minutes : 0)), 0)} mins saved
          </div>
        </div>

        {displayWork.map((work) => {
          const isFailed = work.status === 'Failed Verification';
          const isAccepted = work.status === 'Accepted';
          const isRejected = work.status === 'Rejected';
          const version = work.version || 1;

          return (
            <div 
              key={work.work_id} 
              style={{
                padding: '20px 24px',
                background: isFailed ? 'rgba(239, 83, 80, 0.06)' : isAccepted ? 'rgba(76, 175, 80, 0.06)' : 'var(--glass-1)',
                border: `1px solid ${isFailed ? 'rgba(239, 83, 80, 0.25)' : isAccepted ? 'rgba(76, 175, 80, 0.25)' : 'var(--hairline-2)'}`,
                borderRadius: '14px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                transition: 'all 0.2s ease'
              }}
            >
              {/* Badge, Version & Headline */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    background: isFailed ? 'rgba(239, 83, 80, 0.2)' : isAccepted ? 'rgba(76, 175, 80, 0.2)' : 'rgba(212, 168, 120, 0.2)',
                    color: isFailed ? '#ef5350' : isAccepted ? '#4caf50' : 'var(--accent-gold)'
                  }}>
                    {isFailed ? 'Failed Verification' : isAccepted ? 'Applied' : work.workflow}
                  </span>

                  <span style={{
                    padding: '2px 6px',
                    borderRadius: '4px',
                    fontSize: '10px',
                    fontWeight: 600,
                    background: 'var(--glass-2)',
                    color: 'var(--ink-2)'
                  }}>
                    v{version}
                  </span>

                  <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--ink)' }}>
                    {work.headline}
                  </div>
                </div>

                {work.net_work_removed_minutes > 0 && !isRejected && (
                  <div style={{ fontSize: '12px', color: 'var(--ink-3)', whiteSpace: 'nowrap' }}>
                    ~{work.net_work_removed_minutes} mins removed
                  </div>
                )}
              </div>

              {/* Proof / Reason */}
              <div style={{ fontSize: '13px', color: isFailed ? '#ef5350' : 'var(--ink-2)', lineHeight: 1.5, background: 'rgba(0,0,0,0.15)', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--hairline-2)' }}>
                {isFailed ? (
                  <div>
                    <strong>I tried to complete this. Here's why it failed verification:</strong> {work.failure_reason || work.verification_proof}
                  </div>
                ) : (
                  <div>
                    <strong>Verification Proof:</strong> {work.verification_proof}
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              {!isAccepted && !isRejected && (
                <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
                  {!isFailed && (
                    <button
                      onClick={() => handleAccept(work.work_id)}
                      style={{
                        padding: '6px 16px',
                        borderRadius: '6px',
                        border: 'none',
                        background: 'var(--ink)',
                        color: 'var(--surface)',
                        fontWeight: 600,
                        fontSize: '13px',
                        cursor: 'pointer',
                        transition: 'opacity 0.2s'
                      }}
                    >
                      {work.action_type === 'apply_patch' ? 'Apply Patch →' : work.action_type === 'open_docs' ? 'Open Docs →' : 'Review & Apply →'}
                    </button>
                  )}
                  <button
                    onClick={() => handleReject(work.work_id)}
                    style={{
                      padding: '6px 14px',
                      borderRadius: '6px',
                      border: '1px solid var(--hairline-2)',
                      background: 'transparent',
                      color: 'var(--ink-3)',
                      fontWeight: 500,
                      fontSize: '13px',
                      cursor: 'pointer'
                    }}
                  >
                    Dismiss
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Primary Action Button */}
      <div style={{ marginTop: 'auto', paddingTop: '12px', borderTop: '1px solid var(--hairline-2)', display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={() => {
            if (onContinue) onContinue();
            else socket.sendEvent({ type: 'workspace.continue', workspace_id: activeWorkspace?.workspace_id });
          }}
          style={{
            padding: '12px 28px',
            borderRadius: '10px',
            border: 'none',
            background: 'var(--accent-gold)',
            color: '#000',
            fontWeight: 700,
            fontSize: '14px',
            cursor: 'pointer',
            boxShadow: '0 4px 20px rgba(212, 168, 120, 0.3)',
            transition: 'transform 0.1s ease'
          }}
        >
          Continue Working →
        </button>
      </div>

    </div>
  );
};
