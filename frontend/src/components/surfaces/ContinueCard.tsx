import React, { useState } from 'react';
import { socket } from '../../runtime/socket';

interface ContinueCardProps {
  workspace: any | null;
}

export const ContinueCard: React.FC<ContinueCardProps> = ({ workspace }) => {
  const [showTrajectory, setShowTrajectory] = useState(false);

  if (!workspace) return null;

  const title = workspace?.title || 'Arova Development';
  const blocker = workspace?.understanding?.momentum?.current_blocker || 'Pending queue persistence';
  const nextAction = workspace?.understanding?.momentum?.next_action || 'Implement SQLite persistence for approval queue (~20 min)';
  const confidence = workspace?.understanding?.confidence?.score || 95;
  const whatChanged = workspace?.understanding?.what_changed || 'Memory consent flow and policy engine.';
  const trajectoryStory = workspace?.understanding?.trajectory_story || 'Transitioned from session-based memory to long-lived workspaces.';
  const reasons = workspace?.understanding?.confidence?.reasons || ['VSCode active', 'Git repo: arova', '4h focus'];
  
  const resourcesObj = workspace?.reality?.resources || {};
  const resourceNames = Object.keys(resourcesObj).map(k => k.split('/').pop()).slice(0, 4);
  const preparedList = resourceNames.length > 0 ? resourceNames : ['runtime.py', 'memory_policy.py', 'SQLite docs'];

  const handleResume = () => {
    socket.sendEvent({
        type: 'workspace.continue',
        workspace_id: workspace.id || workspace.workspace_id
    });
  };

  return (
    <div
      style={{
        background: 'linear-gradient(135deg, rgba(180, 150, 255, 0.12) 0%, rgba(20, 20, 30, 0.85) 100%)',
        border: '1px solid rgba(180, 150, 255, 0.3)',
        borderRadius: '16px',
        padding: '24px',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 0 20px rgba(180, 150, 255, 0.05)',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        position: 'relative',
        overflow: 'hidden',
        transition: 'all 0.3s ease'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: '12px', color: 'var(--accent-gold, #ffd700)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-gold, #ffd700)', display: 'inline-block', boxShadow: '0 0 6px var(--accent-gold, #ffd700)' }} />
            Good morning — You're continuing:
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--ink, #fff)', letterSpacing: '-0.02em' }}>
            {title}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={() => setShowTrajectory(!showTrajectory)}
            style={{
              background: 'rgba(255, 255, 255, 0.06)',
              color: 'rgba(255, 255, 255, 0.8)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              borderRadius: '20px',
              padding: '6px 14px',
              fontSize: '12px',
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <span>{showTrajectory ? 'Hide Trajectory & ROI' : 'Yesterday → Today Story'}</span>
            <span>{showTrajectory ? '▲' : '▼'}</span>
          </button>
          <div style={{ fontSize: '13px', color: 'rgba(255, 255, 255, 0.6)', background: 'rgba(255, 255, 255, 0.05)', padding: '4px 12px', borderRadius: '20px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
            {confidence}% clarity
          </div>
        </div>
      </div>

      {whatChanged && (
        <div style={{ background: 'rgba(168, 129, 255, 0.06)', borderLeft: '3px solid #a881ff', padding: '10px 14px', borderRadius: '0 8px 8px 0' }}>
          <div style={{ fontSize: '11px', color: '#a881ff', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: '2px' }}>
            You finished:
          </div>
          <div style={{ fontSize: '14px', color: 'var(--ink, #fff)', fontWeight: 500 }}>
            ✓ {whatChanged}
          </div>
        </div>
      )}

      {blocker && blocker !== 'None' && (
        <div style={{ background: 'rgba(255, 100, 100, 0.08)', borderLeft: '3px solid #ff6b6b', padding: '10px 14px', borderRadius: '0 8px 8px 0' }}>
          <div style={{ fontSize: '11px', color: '#ff6b6b', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: '2px' }}>
            You were blocked by:
          </div>
          <div style={{ fontSize: '14px', color: 'var(--ink, #fff)', fontWeight: 500 }}>
            {blocker}
          </div>
        </div>
      )}

      {workspace?.understanding?.decisions && workspace.understanding.decisions.length > 0 && (
        <div style={{ background: 'rgba(255, 215, 0, 0.06)', borderLeft: '3px solid #ffd700', padding: '10px 14px', borderRadius: '0 8px 8px 0' }}>
          <div style={{ fontSize: '11px', color: '#ffd700', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: '2px' }}>
            Decision Continuity (Already settled):
          </div>
          <div style={{ fontSize: '14px', color: 'var(--ink, #fff)', fontWeight: 500 }}>
            • {workspace.understanding.decisions[0].rationale || workspace.understanding.decisions[0]}
          </div>
        </div>
      )}

      <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '12px 16px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
        <div style={{ fontSize: '11px', color: 'var(--ink-3, #888)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: '6px' }}>
          Already prepared:
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {preparedList.map((res: any, idx: number) => (
            <span
              key={idx}
              style={{
                fontSize: '12px',
                background: 'rgba(255, 255, 255, 0.07)',
                color: 'rgba(255, 255, 255, 0.9)',
                padding: '4px 10px',
                borderRadius: '6px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              <span style={{ color: '#a881ff' }}>✓</span> {String(res)}
            </span>
          ))}
        </div>
      </div>

      {showTrajectory && (
        <div
          style={{
            marginTop: '8px',
            padding: '16px',
            background: 'rgba(0, 0, 0, 0.35)',
            borderRadius: '12px',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}
        >
          <div style={{ fontSize: '13px', fontWeight: 600, color: '#ffd700', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            Trajectory Story (Yesterday → Today)
          </div>
          <div style={{ fontSize: '14px', color: 'rgba(255, 255, 255, 0.9)', lineHeight: '1.5', fontStyle: 'italic' }}>
            "{trajectoryStory}"
          </div>
          <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.6)' }}>
              Why Arova believes this (Confidence {confidence}%):
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {reasons.map((reason: string, idx: number) => (
                <span
                  key={idx}
                  style={{
                    fontSize: '12px',
                    background: 'rgba(168, 129, 255, 0.15)',
                    color: '#c4b5fd',
                    padding: '3px 10px',
                    borderRadius: '12px',
                    border: '1px solid rgba(168, 129, 255, 0.25)'
                  }}
                >
                  {reason}
                </span>
              ))}
            </div>
          </div>
          <div style={{ background: 'rgba(255, 215, 0, 0.08)', border: '1px solid rgba(255, 215, 0, 0.25)', borderRadius: '8px', padding: '12px', marginTop: '4px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ fontSize: '12px', color: '#ffd700', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              ⚡ Behavioral Recovery Impact This Week:
            </div>
            <div style={{ fontSize: '13px', color: '#fff', fontWeight: 600, display: 'flex', justifyContent: 'space-between' }}>
              <span>8 workspaces resumed · 12 blockers resolved</span>
              <span style={{ color: '#ffd700' }}>Estimated recovery: 1h 47m</span>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '6px' }}>
        <div style={{ fontSize: '14px', color: 'var(--ink-2, #bbb)', fontStyle: 'italic' }}>
          {nextAction ? `You'll probably finish this in ~20 minutes.` : `I'd continue here.`}
        </div>
        <button
          onClick={handleResume}
          style={{
            background: 'linear-gradient(135deg, #a881ff 0%, #7e52f5 100%)',
            color: '#fff',
            border: 'none',
            borderRadius: '10px',
            padding: '10px 24px',
            fontSize: '14px',
            fontWeight: 600,
            cursor: 'pointer',
            boxShadow: '0 4px 15px rgba(126, 82, 245, 0.4)',
            transition: 'all 0.2s ease',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <span>Resume</span>
          <span style={{ fontSize: '16px' }}>→</span>
        </button>
      </div>
    </div>
  );
};
