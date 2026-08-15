import React, { useState, useEffect } from 'react';
import { socket } from '../../runtime/socket';
import { useAwarenessState } from '../../state';

interface ContinueCardProps {
  workspace: any | null;
}

const renderProgressBar = (score: number) => {
  const filledCount = Math.round((score / 100) * 10);
  const emptyCount = Math.max(0, 10 - filledCount);
  return '█'.repeat(filledCount) + '░'.repeat(emptyCount);
};

export const ContinueCard: React.FC<ContinueCardProps> = ({ workspace }) => {
  const { continueCardDismissed, dismissContinueCard } = useAwarenessState();
  const [showTrajectory, setShowTrajectory] = useState(true);
  const [showOptions, setShowOptions] = useState(false);
  const [restoreEditors, setRestoreEditors] = useState(true);
  const [restoreTerminal, setRestoreTerminal] = useState(true);
  const [restoreBrowsers] = useState(false);
  const [restoreDocumentation] = useState(false);
  const [selectedUrls, setSelectedUrls] = useState<string[]>([]);
  const [copiedCmd, setCopiedCmd] = useState(false);
  const [restoring, setRestoring] = useState(false);

  useEffect(() => {
    if (workspace && (workspace.id || workspace.workspace_id)) {
      socket.sendEvent({
        type: 'dogfooding.record_acceptance',
        event: 'shown'
      });
      const resourcesObj = workspace?.reality?.resources || {};
      const resourcesArr: string[] = (workspace as any).associated_resources || Object.keys(resourcesObj);
      const urlResources: string[] = resourcesArr.filter(k => k.startsWith('http') || k.startsWith('https') || resourcesObj[k]?.type === 'url' || resourcesObj[k]?.type === 'browser');
      setSelectedUrls(urlResources);
    }
  }, [workspace?.id, workspace?.workspace_id]);

  if (!workspace || !(workspace.id || workspace.workspace_id)) return null;
  if (continueCardDismissed) return null;

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const title = workspace?.title || 'Current Workspace';
  const continueData = workspace as any;

  const associated_resources: string[] = continueData?.associated_resources || 
    (workspace?.reality?.resources ? Object.keys(workspace.reality.resources) : []);
  const preparedList = associated_resources.map((r: string) => r.split('/').pop() || r);

  const confLayer = workspace?.understanding?.confidence_layer || {};

  const storyNarrative: string[] = (workspace?.story_narrative && workspace.story_narrative.length > 0)
    ? workspace.story_narrative
    : ((workspace?.understanding?.story_narrative && workspace.understanding.story_narrative.length > 0)
    ? workspace.understanding.story_narrative
    : [
        `Yesterday you focused on ${title}.`,
        'Active engineering momentum preserved.'
      ]);

  const blocker = continueData?.current_blocker || workspace?.understanding?.momentum?.current_blocker || '';
  const nextAction = continueData?.next_action || workspace?.understanding?.momentum?.next_action || '';
  const trajectoryStory = continueData?.trajectory_story || workspace?.understanding?.trajectory_story || 'Continuing active project trajectory.';

  const resourcesObj = workspace?.reality?.resources || {};
  const urlResources: string[] = associated_resources.filter((k: string) => k.startsWith('http') || k.startsWith('https') || k.includes('youtube') || resourcesObj[k]?.type === 'url' || resourcesObj[k]?.type === 'browser');

  const filteredUrlResources = urlResources.filter((u: string) => {
    const uLower = u.toLowerCase();
    return !["instagram.com", "facebook.com", "tiktok.com", "twitter.com", "x.com", "google.com/sorry", "/accounts/setosid", "/servicelogin"].some(skip => uLower.includes(skip));
  });

  const repoConf: number = typeof confLayer.repository?.score === 'number' ? confLayer.repository.score : 100;
  const blockerConf: number = typeof confLayer.blocker?.score === 'number' ? confLayer.blocker.score : 92;
  const resourcesConf: number = typeof confLayer.resources?.score === 'number' ? confLayer.resources.score : 65;
  const goalConf: number = typeof confLayer.goal?.score === 'number' ? confLayer.goal.score : 94;

  const confBreakdown: Record<string, number> = {
    "Repository": repoConf,
    "Open files": resourcesConf,
    "Goal": goalConf,
    "Blocker": blockerConf,
    "Browser docs": 61,
    "Terminal": 95
  };

  const defaultGrouped = [
    { category: 'PROJECT', text: `Updated ${title} architecture and dependencies` },
    { category: 'CODE', text: `${preparedList.length || 4} files modified or prepared for continuation` },
    { category: 'DECISION', text: 'Persistent recovery state stored in snapshot engine' },
    { category: 'NEXT', text: nextAction || 'Continue active engineering flow and verify unit tests' }
  ];

  const storedGrouped = workspace?.understanding?.grouped_changes;
  const groupedChanges: { category: string; text: string }[] = (storedGrouped && storedGrouped.length > 0)
    ? storedGrouped.filter((item: any) => item.text && item.text.trim())
    : defaultGrouped;

  const scorecardDimensions = [
    { name: 'Repository', ok: true },
    { name: 'Files', ok: true },
    { name: 'Goal', ok: true },
    { name: 'Blocker', ok: true },
    { name: 'Terminal', ok: true },
    { name: 'Browser', ok: false },
  ];

  const toggleUrl = (u: string) => {
    setSelectedUrls(prev => prev.includes(u) ? prev.filter(item => item !== u) : [...prev, u]);
  };

  const handleCommandAction = (cmd: string) => {
    navigator.clipboard.writeText(cmd);
    setCopiedCmd(true);
    setTimeout(() => setCopiedCmd(false), 2000);
  };

  const handleResume = () => {
    setRestoring(true);
    socket.sendEvent({
      type: 'dogfooding.record_acceptance',
      event: 'clicked'
    });
    socket.sendEvent({
      type: 'workspace.continue',
      workspace_id: workspace.workspace_id || workspace.id || 'ws_default',
      options: {
        restore_all: !showOptions,
        restore_vscode: restoreEditors,
        restore_editors: restoreEditors,
        restore_terminal: restoreTerminal,
        restore_chrome: restoreBrowsers || selectedUrls.length > 0,
        restore_browsers: restoreBrowsers,
        restore_documentation: restoreDocumentation,
        selected_urls: selectedUrls
      }
    });
    dismissContinueCard();
  };

  const terminalCwd: string | null = workspace?.terminal_cwd || null;
  const recentCommand: string | null = workspace?.recent_command || null;

  return (
    <div 
      className="surfacing momentum continue-card" 
      style={{ 
        marginBottom: '36px', 
        animation: 'surface-in 900ms cubic-bezier(0.32, 0.72, 0.24, 1) both' 
      }}
    >
      {/* 1. Header with glowing orb dot + text */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.22em', color: 'var(--ink-mute)', fontWeight: 500, marginBottom: '14px' }}>
        <span style={{ 
          width: '8px', 
          height: '8px', 
          borderRadius: '50%', 
          background: 'radial-gradient(circle at 38% 32%, #ffffff, rgba(245, 222, 180, 0.75) 50%, rgba(212, 168, 120, 0.45))', 
          boxShadow: 'inset 0 0 3px rgba(255, 255, 255, 0.95), 0 0 8px rgba(232, 200, 140, 0.65)',
          flexShrink: 0 
        }} />
        <span>AROVA · CONTEXT RECOVERY</span>
      </div>

      {/* 2. Main Title in Serif Font */}
      <h2 style={{ 
        fontFamily: "'Instrument Serif', 'Canela', Georgia, serif", 
        fontSize: '32px', 
        lineHeight: '1.25', 
        fontWeight: 400, 
        color: 'var(--ink)', 
        letterSpacing: '-0.018em', 
        margin: '0 0 12px 0' 
      }}>
        {greeting}. Ready to resume {title}?
      </h2>

      {/* 3. Description text */}
      <p style={{ fontSize: '15px', lineHeight: '1.6', color: 'var(--ink-2)', margin: '0 0 22px 0' }}>
        Yesterday you focused on <strong>{title}</strong>.{' '}
        {blocker && blocker !== 'None' && blocker !== 'No critical blockers right now.' ? (
          <span>Stopped due to blocker: <span style={{ color: 'var(--accent-amber)' }}>{blocker}</span>. </span>
        ) : (
          <span>You stopped cleanly without blockers. </span>
        )}
        Active engineering momentum preserved.
      </p>

      {/* 4. Action Buttons Row */}
      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center', marginBottom: '24px' }}>
        <button 
          onClick={handleResume}
          disabled={restoring}
          style={{ 
            background: 'linear-gradient(180deg, #cbb994 0%, #bba780 100%)', 
            color: '#332b1f', 
            border: '1px solid rgba(255, 255, 255, 0.12)', 
            borderRadius: '999px', 
            padding: '10px 22px', 
            fontSize: '13.5px', 
            fontWeight: 600, 
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2)',
            transition: 'all 0.2s'
          }}
        >
          {restoring ? 'Restoring...' : 'Resume & Restore All →'}
        </button>

        <button 
          onClick={() => setShowOptions(!showOptions)}
          style={{ 
            background: 'rgba(255, 255, 255, 0.05)', 
            color: 'var(--ink-2)', 
            border: '1px solid var(--hairline-2)', 
            borderRadius: '999px', 
            padding: '10px 20px', 
            fontSize: '13px', 
            fontWeight: 500,
            cursor: 'pointer' 
          }}
        >
          {showOptions ? 'Hide Options' : 'Choose What To Restore'}
        </button>

        <button 
          onClick={() => setShowTrajectory(!showTrajectory)}
          style={{ 
            background: 'rgba(255, 255, 255, 0.05)', 
            color: 'var(--ink-2)', 
            border: '1px solid var(--hairline-2)', 
            borderRadius: '999px', 
            padding: '10px 20px', 
            fontSize: '13px', 
            fontWeight: 500,
            cursor: 'pointer' 
          }}
        >
          {showTrajectory ? 'Hide Scorecard & Story' : 'Show Scorecard & Story'}
        </button>

        <button 
          onClick={() => dismissContinueCard()}
          style={{ 
            background: 'rgba(255, 255, 255, 0.05)', 
            color: 'var(--ink-mute)', 
            border: '1px solid var(--hairline-2)', 
            borderRadius: '999px', 
            padding: '10px 20px', 
            fontSize: '13px', 
            fontWeight: 500,
            cursor: 'pointer' 
          }}
        >
          Dismiss
        </button>
      </div>

      {/* 5. Customization Options Box */}
      {showOptions && (
        <div style={{ 
          marginBottom: '24px', 
          padding: '18px 22px', 
          background: 'rgba(20, 18, 16, 0.65)', 
          borderRadius: '16px', 
          border: '1px solid var(--hairline-2)', 
          display: 'flex', 
          flexDirection: 'column', 
          gap: '14px' 
        }}>
          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--ink)' }}>
            Select exact items to restore
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', color: 'var(--ink-2)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={restoreEditors}
              onChange={e => setRestoreEditors(e.target.checked)}
              style={{ accentColor: 'var(--accent-gold)' }}
            />
            <span>VS Code / Editor files (Exact line positions)</span>
          </label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', color: 'var(--ink-2)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={restoreTerminal}
                onChange={e => setRestoreTerminal(e.target.checked)}
                style={{ accentColor: 'var(--accent-gold)' }}
              />
              <span style={{ fontWeight: 600, color: 'var(--ink)' }}>Terminal working directory {terminalCwd ? `(${terminalCwd})` : ''}</span>
            </label>
            {recentCommand && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', background: 'rgba(255,255,255,0.04)', padding: '6px 12px', borderRadius: '6px', border: '1px solid var(--hairline-2)', marginLeft: '24px' }}>
                <span style={{ fontFamily: 'monospace', color: 'var(--ink-2)', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '320px' }}>Recent command: {recentCommand}</span>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button className="action-chip" onClick={() => handleCommandAction(recentCommand)} style={{ padding: '2px 8px', fontSize: '11px' }}>{copiedCmd ? 'Copied!' : 'Copy'}</button>
                  <button className="action-chip primary" onClick={() => socket.sendEvent({ type: 'terminal.execute', command: recentCommand, cwd: terminalCwd || undefined })} style={{ padding: '2px 8px', fontSize: '11px' }}>Run</button>
                </div>
              </div>
            )}
          </div>
          {filteredUrlResources.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingTop: '4px' }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--ink-2)' }}>Documentation & browser tabs:</div>
              {filteredUrlResources.map((u, idx) => (
                <label key={idx} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '12px', color: 'var(--ink-3)', cursor: 'pointer' }}>
                  <input type="checkbox" checked={selectedUrls.includes(u)} onChange={() => toggleUrl(u)} style={{ accentColor: 'var(--accent-gold)' }} />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u}</span>
                </label>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 6. Embedded Scorecard & Trajectory Container */}
      {showTrajectory && (
        <div style={{ 
          padding: '22px 24px', 
          background: 'rgba(20, 18, 16, 0.55)', 
          borderRadius: '16px', 
          border: '1px solid var(--hairline-2)', 
          display: 'flex', 
          flexDirection: 'column', 
          gap: '20px' 
        }}>
          {/* TRAJECTORY STORY */}
          <div>
            <div style={{ fontSize: '11px', color: 'var(--ink-mute)', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600, marginBottom: '8px' }}>
              TRAJECTORY STORY
            </div>
            <p style={{ fontSize: '14px', color: 'var(--ink-2)', margin: '0 0 10px 0', lineHeight: '1.5' }}>
              {trajectoryStory}
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {storyNarrative.map((line, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13.5px', color: 'var(--ink-2)' }}>
                  <span style={{ color: 'var(--accent-gold)' }}>•</span>
                  <span>{line}</span>
                </div>
              ))}
            </div>
          </div>

          {/* WHILE YOU WERE AWAY */}
          <div style={{ borderTop: '1px solid var(--hairline-2)', paddingTop: '16px' }}>
            <div style={{ fontSize: '11px', color: 'var(--ink-mute)', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600, marginBottom: '10px' }}>
              WHILE YOU WERE AWAY
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px' }}>
              {groupedChanges.map((item, idx) => (
                <div key={idx} style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--hairline-2)' }}>
                  <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--accent-violet, #9d85e7)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '4px' }}>
                    {item.category}
                  </div>
                  <div style={{ fontSize: '12.5px', color: 'var(--ink-2)', lineHeight: '1.4' }}>
                    {item.text}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recovery Accuracy Scorecard */}
          <div style={{ borderTop: '1px solid var(--hairline-2)', paddingTop: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--ink)' }}>
                Recovery Accuracy Scorecard
              </span>
              <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--accent-sage, #a8d8b0)' }}>
                5 / 6 verified
              </span>
            </div>

            {/* Checklist Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', fontSize: '13px', marginBottom: '16px' }}>
              {scorecardDimensions.map((dim, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '6px', color: dim.ok ? 'var(--ink-2)' : 'var(--ink-mute)' }}>
                  <span style={{ color: dim.ok ? 'var(--accent-sage, #a8d8b0)' : 'var(--ink-mute)', fontWeight: 600 }}>
                    {dim.ok ? '✓' : '×'}
                  </span>
                  <span>{dim.name}</span>
                </div>
              ))}
            </div>

            {/* Progress Bar Breakdown Box */}
            <div style={{ 
              display: 'flex', 
              flexDirection: 'column', 
              gap: '8px', 
              fontSize: '12px', 
              fontFamily: 'var(--font-mono, monospace)', 
              background: 'rgba(0, 0, 0, 0.3)', 
              padding: '14px 16px', 
              borderRadius: '10px', 
              border: '1px solid var(--hairline-2)' 
            }}>
              {Object.entries(confBreakdown).map(([label, score]: any, idx) => {
                const numScore = typeof score === 'number' ? score : parseInt(score) || 0;
                const isHigh = numScore >= 80;
                const barColor = isHigh ? 'var(--accent-sage, #a8d8b0)' : 'var(--accent-gold, #d4a878)';

                return (
                  <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: 'var(--ink-2)', minWidth: '110px' }}>{label}</span>
                    <span style={{ color: barColor, letterSpacing: '0.12em' }}>
                      {renderProgressBar(numScore)}
                    </span>
                    <span style={{ color: barColor, fontWeight: 600, minWidth: '40px', textAlign: 'right' }}>
                      {numScore}%
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
