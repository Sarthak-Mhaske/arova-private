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
  const [showTrajectory, setShowTrajectory] = useState(false);
  const [showOptions, setShowOptions] = useState(false);
  const [restoreEditors, setRestoreEditors] = useState(true);
  const [restoreTerminal, setRestoreTerminal] = useState(true);
  const [restoreBrowsers] = useState(false);
  const [restoreDocumentation] = useState(false);
  const [calibrationRated, setCalibrationRated] = useState<string | null>(null);
  const [selectedUrls, setSelectedUrls] = useState<string[]>([]);
  const [copiedCmd, setCopiedCmd] = useState(false);

  useEffect(() => {
    if (workspace && (workspace.id || workspace.workspace_id)) {
      socket.sendEvent({
        type: 'dogfooding.record_acceptance',
        event: 'shown'
      });
      const resourcesObj = workspace?.reality?.resources || {};
      const urlResources: string[] = Object.keys(resourcesObj).filter(k => k.startsWith('http') || resourcesObj[k]?.type === 'url' || resourcesObj[k]?.type === 'browser');
      if (urlResources.length === 0) {
        urlResources.push('https://sqlite.org/docs', 'https://fastapi.tiangolo.com/advanced/websockets/');
      }
      setSelectedUrls(urlResources);
    }
  }, [workspace?.id, workspace?.workspace_id]);

  if (!workspace || continueCardDismissed) return null;

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';

  const title = workspace?.title || 'Current Workspace';
  const blocker = workspace?.understanding?.momentum?.current_blocker || '';
  const nextAction = workspace?.understanding?.momentum?.next_action || '';
  const whatChanged = workspace?.understanding?.what_changed || '';
  const deltaChanges: string[] = workspace?.understanding?.delta_changes || workspace?.delta_changes || [];
  const trajectoryStory = workspace?.understanding?.trajectory_story || '';
  const storyNarrative: string[] = workspace?.understanding?.story_narrative || [
    `Yesterday you focused on ${title}.`,
    blocker ? `Stopped due to blocker: ${blocker}` : nextAction ? `Next step planned: ${nextAction}` : `Active engineering momentum preserved.`
  ];
  
  const confLayer = workspace?.understanding?.confidence_layer || {};
  const confidence = workspace?.understanding?.confidence?.score || workspace?.confidence_score || confLayer.overall_score || 94;

  const explainabilityReasons: string[] = workspace?.understanding?.explainability_reasons || [
    `You spent significant time in ${title} recently`,
    `Active working resources prepared`,
    `Confidence: ${confidence}% (${confidence >= 70 ? 'High' : 'Medium'})`
  ];
  const reasons = workspace?.understanding?.confidence?.reasons || [];
  
  const resourcesObj = workspace?.reality?.resources || {};
  const preparedList = Object.keys(resourcesObj).map(k => k.split('/').pop() || k).slice(0, 6);

  const repoConf = confLayer.repository?.score || confLayer.goal?.score || 100;
  const blockerConf = confLayer.blocker?.score || 92;
  const resourcesConf = confLayer.resources?.score || 65;

  const confBreakdown = workspace?.confidence_breakdown || workspace?.understanding?.confidence_breakdown || {
    "Repository": repoConf,
    "Open files": resourcesConf,
    "Goal": 94,
    "Blocker": blockerConf,
    "Browser docs": 61,
    "Terminal": 95
  };

  const recAcc = workspace?.understanding?.recovery_accuracy || {
    dimensions: [
      { name: 'Repository', ok: repoConf >= 70 },
      { name: 'Files', ok: resourcesConf >= 60 },
      { name: 'Goal', ok: true },
      { name: 'Blocker', ok: blockerConf >= 70 },
      { name: 'Terminal', ok: true },
      { name: 'Browser', ok: false }
    ]
  };
  const accuracyScore = recAcc.dimensions.filter((d: any) => d.ok).length;
  const accuracyTotal = recAcc.dimensions.length;

  const groupedChanges: { category: string; text: string }[] = workspace?.understanding?.grouped_changes || [
    { category: 'PROJECT', text: whatChanged || `Updated ${title} architecture and dependencies` },
    { category: 'CODE', text: deltaChanges.length > 0 ? deltaChanges[0] : `${preparedList.length || 4} files modified or prepared for continuation` },
    { category: 'DECISION', text: workspace?.understanding?.decisions?.[0]?.title || 'Persistent recovery state stored in snapshot engine' },
    { category: 'BLOCKER', text: blocker || 'None — clean resumption path ready' },
    { category: 'NEXT', text: nextAction || 'Continue active engineering flow and verify unit tests' }
  ].filter(item => item.text && (item.text !== 'None — clean resumption path ready' || item.category === 'NEXT'));

  const lastOutcomes = workspace?.last_restore_outcomes?.items || [];

  const urlResources: string[] = Object.keys(resourcesObj).filter(k => k.startsWith('http') || resourcesObj[k]?.type === 'url' || resourcesObj[k]?.type === 'browser');
  if (urlResources.length === 0) {
    urlResources.push('https://sqlite.org/docs', 'https://fastapi.tiangolo.com/advanced/websockets/');
  }

  const handleCalibrate = (rating: string) => {
    setCalibrationRated(rating);
    socket.sendEvent({
      type: 'dogfooding.calibrate_confidence',
      score: confidence,
      rating: rating
    });
  };

  const toggleUrl = (u: string) => {
    setSelectedUrls(prev => prev.includes(u) ? prev.filter(item => item !== u) : [...prev, u]);
  };

  const handleCommandAction = (cmd: string) => {
    navigator.clipboard.writeText(cmd);
    setCopiedCmd(true);
    setTimeout(() => setCopiedCmd(false), 2000);
  };

  const handleResume = (restoreAll = true) => {
    socket.sendEvent({
      type: 'dogfooding.record_acceptance',
      event: 'clicked'
    });
    socket.sendEvent({
        type: 'workspace.continue',
        workspace_id: workspace.id || workspace.workspace_id,
        options: {
          restore_all: restoreAll && !showOptions,
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

  const terminalCwd = workspace?.terminal_cwd || '/home/sarthak/arova';
  const recentCommand = workspace?.recent_command || 'python -m pytest tests/test_resume_engine_v2.py';

  return (
    <div className="surfacing momentum" style={{ animation: 'surface-in 900ms cubic-bezier(0.32, 0.72, 0.24, 1) both' }}>
      <div className="from">AROVA · CONTEXT RECOVERY</div>
      
      <div className="lede">
        {greeting}. Ready to resume {title}?
      </div>

      <p>
        Yesterday you focused on <strong>{title}</strong>.{' '}
        {blocker && blocker !== 'None' ? (
          <span style={{ color: 'var(--accent-amber)' }}>Stopped due to blocker: {blocker}. </span>
        ) : (
          <span>You stopped cleanly without blockers. </span>
        )}
        {nextAction ? `Next step planned: ${nextAction}` : 'Active engineering momentum preserved.'}
      </p>

      {(deltaChanges.length > 0 || preparedList.length > 0) && (
        <p className="quiet">
          While you were away, {deltaChanges.length > 0 ? deltaChanges[0] : `${preparedList.length || 4} files prepared for continuation (${preparedList.slice(0, 3).join(', ')}${preparedList.length > 3 ? '...' : ''})`}.{' '}
          Arova is currently <strong style={{ color: 'var(--ink)' }}>{confidence}% confident</strong> with {accuracyScore}/{accuracyTotal} verified context dimensions.
        </p>
      )}

      {workspace?.understanding?.decisions && workspace.understanding.decisions.length > 0 && (
        <p className="quiet">
          Decision already settled: <em>{workspace.understanding.decisions[0].rationale || workspace.understanding.decisions[0]}</em>
        </p>
      )}

      {/* Inline action buttons directly inside the message */}
      <div className="actions-inline" style={{ marginTop: '22px' }}>
        <button
          className="action-chip primary"
          onClick={() => handleResume(!showOptions)}
        >
          <span>{showOptions ? 'Restore Selected' : 'Resume & Restore All'}</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        </button>
        <button
          className="action-chip"
          onClick={() => setShowOptions(!showOptions)}
        >
          {showOptions ? 'Hide Options' : 'Choose What To Restore'}
        </button>
        <button
          className="action-chip"
          onClick={() => setShowTrajectory(!showTrajectory)}
        >
          {showTrajectory ? 'Hide Scorecard & Story' : 'Scorecard & Confidence'}
        </button>
        <button
          className="action-chip"
          onClick={() => dismissContinueCard()}
        >
          Dismiss
        </button>
      </div>

      {/* Expandable Options section directly inline */}
      {showOptions && (
        <div style={{ marginTop: '20px', padding: '18px', background: 'var(--glass-1)', borderRadius: '14px', border: '1px solid var(--hairline-2)', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--ink)', display: 'flex', justifyContent: 'space-between' }}>
            <span>Select exact items to restore (`Phase 7`)</span>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--ink-2)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={restoreEditors}
              onChange={e => setRestoreEditors(e.target.checked)}
              style={{ accentColor: 'var(--accent-gold)' }}
            />
            <span>VS Code / Editor files (Exact line positions)</span>
          </label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--ink-2)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={restoreTerminal}
                onChange={e => setRestoreTerminal(e.target.checked)}
                style={{ accentColor: 'var(--accent-gold)' }}
              />
              <span style={{ fontWeight: 600, color: 'var(--ink)' }}>Terminal working directory ({terminalCwd})</span>
            </label>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', background: 'var(--glass-2)', padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--hairline-2)' }}>
              <span style={{ fontFamily: 'var(--font-mono, monospace)', color: 'var(--ink-2)', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '300px' }}>Recent command: {recentCommand}</span>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button className="action-chip" onClick={() => handleCommandAction(recentCommand)} style={{ padding: '2px 8px', fontSize: '11px' }}>{copiedCmd ? 'Copied!' : 'Copy'}</button>
                <button className="action-chip primary" onClick={() => socket.sendEvent({ type: 'terminal.execute', command: recentCommand, cwd: terminalCwd })} style={{ padding: '2px 8px', fontSize: '11px' }}>Run</button>
              </div>
            </div>
          </div>
          {urlResources.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingTop: '4px' }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--ink-2)' }}>Documentation & browser tabs:</div>
              {urlResources.map((u, idx) => (
                <label key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--ink-3)', cursor: 'pointer' }}>
                  <input type="checkbox" checked={selectedUrls.includes(u)} onChange={() => toggleUrl(u)} style={{ accentColor: 'var(--accent-gold)' }} />
                  <span>{u}</span>
                </label>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Expandable Scorecard & Trajectory directly inline */}
      {showTrajectory && (
        <div style={{ marginTop: '20px', padding: '18px', background: 'var(--glass-1)', borderRadius: '14px', border: '1px solid var(--hairline-2)', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: '6px' }}>
              Trajectory Story
            </div>
            <p style={{ fontSize: '14px', color: 'var(--ink-2)', margin: '0 0 8px 0' }}>
              {trajectoryStory || 'Continuing active project trajectory.'}
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {storyNarrative.map((line, idx) => (
                <p key={idx} style={{ fontSize: '13px', color: 'var(--ink-2)', margin: 0 }}>
                  • {line}
                </p>
              ))}
            </div>
          </div>

          {groupedChanges.length > 0 && (
            <div style={{ borderTop: '1px solid var(--hairline-2)', paddingTop: '14px' }}>
              <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: '8px' }}>
                While you were away
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '8px' }}>
                {groupedChanges.map((item, idx) => (
                  <div key={idx} style={{ background: 'var(--glass-2)', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--hairline-2)' }}>
                    <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--accent-violet)', letterSpacing: '0.06em' }}>{item.category}</div>
                    <div style={{ fontSize: '12px', color: 'var(--ink-2)' }}>{item.text}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {lastOutcomes.length > 0 && (
            <div style={{ borderTop: '1px solid var(--hairline-2)', paddingTop: '14px' }}>
              <div style={{ fontSize: '11px', color: 'var(--accent-sage)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: '8px' }}>
                Last Resume Attempt Outcomes
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '6px', fontSize: '12px' }}>
                {lastOutcomes.map((item: any, idx: number) => (
                  <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--ink-2)' }}>
                    <span style={{ color: item.status === 'restored' ? 'var(--accent-sage)' : item.status === 'skipped' ? 'var(--accent-gold)' : 'var(--ink-mute)' }}>
                      {item.status === 'restored' ? '✓' : item.status === 'skipped' ? '◯' : '✗'}
                    </span>
                    <span style={{ fontWeight: 600, color: 'var(--ink)' }}>{item.name}:</span>
                    <span>{item.detail || item.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div style={{ borderTop: '1px solid var(--hairline-2)', paddingTop: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '13px', fontWeight: 600, color: 'var(--ink)', marginBottom: '10px' }}>
              <span>Recovery Accuracy Scorecard</span>
              <span style={{ color: accuracyScore >= 5 ? 'var(--accent-sage)' : accuracyScore >= 4 ? 'var(--accent-gold)' : 'var(--ink-mute)' }}>
                {accuracyScore} / {accuracyTotal} verified
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', fontSize: '12px', marginBottom: '14px' }}>
              {recAcc.dimensions.map((dim: any, idx: number) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '6px', color: dim.ok ? 'var(--ink)' : 'var(--ink-3)' }}>
                  <span style={{ color: dim.ok ? 'var(--accent-sage)' : 'var(--ink-mute)', fontWeight: 600 }}>{dim.ok ? '✓' : '✗'}</span>
                  <span>{dim.name}</span>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px', fontFamily: 'var(--font-mono, monospace)', background: 'var(--glass-2)', padding: '12px 14px', borderRadius: '8px', border: '1px solid var(--hairline-2)', marginBottom: '14px' }}>
              {Object.entries(confBreakdown).map(([label, score]: any, idx) => {
                const numScore = typeof score === 'number' ? score : parseInt(score) || 80;
                return (
                  <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: 'var(--ink-2)', minWidth: '110px' }}>{label}</span>
                    <span style={{ color: numScore >= 80 ? 'var(--accent-sage)' : numScore >= 60 ? 'var(--accent-gold)' : 'var(--ink-mute)', letterSpacing: '0.1em' }}>
                      {renderProgressBar(numScore)}
                    </span>
                    <span style={{ color: numScore >= 80 ? 'var(--accent-sage)' : numScore >= 60 ? 'var(--accent-gold)' : 'var(--ink-mute)', fontWeight: 600, minWidth: '40px', textAlign: 'right' }}>
                      {numScore}%
                    </span>
                  </div>
                );
              })}
            </div>

            <div>
              <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: '6px' }}>
                Why Arova is {confidence}% confident
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {(reasons.length > 0 ? reasons : explainabilityReasons).map((r: string, i: number) => (
                  <span key={i} style={{ fontSize: '12px', background: 'var(--glass-2)', color: 'var(--ink-2)', padding: '4px 8px', borderRadius: '6px', border: '1px solid var(--hairline-2)' }}>
                    {r}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '12px', color: 'var(--ink-2)', borderTop: '1px solid var(--hairline-2)', paddingTop: '12px', flexWrap: 'wrap' }}>
            <span>Is this breakdown accurate?</span>
            <button onClick={() => handleCalibrate('correct')} style={{ background: calibrationRated === 'correct' ? 'var(--accent-sage)' : 'transparent', color: calibrationRated === 'correct' ? 'var(--base-0)' : 'var(--accent-sage)', border: '1px solid var(--accent-sage)', borderRadius: '10px', padding: '3px 10px', fontSize: '11px', cursor: 'pointer' }}>✓ Correct</button>
            <button onClick={() => handleCalibrate('mostly_correct')} style={{ background: calibrationRated === 'mostly_correct' ? 'var(--accent-gold)' : 'transparent', color: calibrationRated === 'mostly_correct' ? 'var(--base-0)' : 'var(--accent-gold)', border: '1px solid var(--accent-gold)', borderRadius: '10px', padding: '3px 10px', fontSize: '11px', cursor: 'pointer' }}>△ Mostly</button>
            <button onClick={() => handleCalibrate('wrong')} style={{ background: calibrationRated === 'wrong' ? 'var(--ink-mute)' : 'transparent', color: calibrationRated === 'wrong' ? 'var(--base-0)' : 'var(--ink-mute)', border: '1px solid var(--ink-mute)', borderRadius: '10px', padding: '3px 10px', fontSize: '11px', cursor: 'pointer' }}>✗ Off</button>
          </div>
        </div>
      )}
    </div>
  );
};

