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
      // STRICT: Only real observed URLs - never inject fake fallback docs
      const urlResources: string[] = Object.keys(resourcesObj).filter(k => k.startsWith('http') || resourcesObj[k]?.type === 'url' || resourcesObj[k]?.type === 'browser');
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
  
  // === TIER 0.1: STRICT EMPIRICAL CONFIDENCE — NO THEATER FALLBACKS ===
  // Never default to 94. Only use real stored scores or honest 0.
  const confLayer = workspace?.understanding?.confidence_layer || {};
  const rawConfidence = workspace?.understanding?.confidence?.score;
  const rawOverallConf = confLayer.overall?.score ?? confLayer.goal?.score;
  const confidence: number = typeof rawConfidence === 'number' ? rawConfidence
    : typeof rawOverallConf === 'number' ? rawOverallConf
    : typeof workspace?.confidence_score === 'number' ? workspace.confidence_score
    : 0; // honest 0 if no data - will show humility instead of fake 94%

  const isLowConfidence = confidence > 0 && confidence < 70;
  const isNoConfidence = confidence === 0;
  const isHighConfidence = confidence >= 85;

  // Only show stored reasons, never fabricate
  const storedReasons: string[] = workspace?.understanding?.confidence?.reasons || [];
  const storedExplainability: string[] = workspace?.understanding?.explainability_reasons || [];
  const explainabilityReasons: string[] = storedExplainability.length > 0 ? storedExplainability
    : storedReasons.length > 0 ? storedReasons
    : isNoConfidence ? ["Not enough observations yet — confidence will build as you work"]
    : [`Confidence: ${confidence}% (${confidence >= 85 ? 'High' : confidence >= 70 ? 'Medium' : 'Low — please verify'})`];
  const reasons = storedReasons;
  
  const resourcesObj = workspace?.reality?.resources || {};
  const preparedList = Object.keys(resourcesObj).map(k => k.split('/').pop() || k).slice(0, 6);

  // Strict per-dimension scores — null if not observed, never fake 100/92/65
  const repoConf: number | null = typeof confLayer.repository?.score === 'number' ? confLayer.repository.score : null;
  const blockerConf: number | null = typeof confLayer.blocker?.score === 'number' ? confLayer.blocker.score : null;
  const resourcesConf: number | null = typeof confLayer.resources?.score === 'number' ? confLayer.resources.score : null;
  const goalConf: number | null = typeof confLayer.goal?.score === 'number' ? confLayer.goal.score : null;

  // Only build breakdown from real stored values — no fake 61/95/94 defaults
  const hasAnyConf = repoConf !== null || blockerConf !== null || resourcesConf !== null || goalConf !== null;
  const confBreakdown: Record<string, number> | null = hasAnyConf ? {
    ...(repoConf !== null ? { "Repository": repoConf } : {}),
    ...(resourcesConf !== null ? { "Open files": resourcesConf } : {}),
    ...(goalConf !== null ? { "Goal": goalConf } : {}),
    ...(blockerConf !== null ? { "Blocker": blockerConf } : {}),
  } : null;

  // Recovery accuracy: only from real confidence or real recovery_accuracy — never fake true/false
  const storedRecAcc = workspace?.understanding?.recovery_accuracy;
  const recAcc = storedRecAcc || (hasAnyConf ? {
    dimensions: [
      { name: 'Repository', ok: repoConf !== null ? repoConf >= 70 : false },
      { name: 'Files', ok: resourcesConf !== null ? resourcesConf >= 60 : false },
      { name: 'Goal', ok: goalConf !== null ? goalConf >= 70 : false },
      { name: 'Blocker', ok: blockerConf !== null ? blockerConf >= 70 : false },
    ].filter(d => {
      // Only include dimensions where we actually have a score
      const key = d.name.toLowerCase();
      if (key === 'repository') return repoConf !== null;
      if (key === 'files') return resourcesConf !== null;
      if (key === 'goal') return goalConf !== null;
      if (key === 'blocker') return blockerConf !== null;
      return true;
    })
  } : null);
  const accuracyScore = recAcc ? recAcc.dimensions.filter((d: any) => d.ok).length : 0;
  const accuracyTotal = recAcc ? recAcc.dimensions.length : 0;

  // While you were away: ONLY real data, never fabricate "Updated architecture" or "4 files prepared"
  const storedGrouped = workspace?.understanding?.grouped_changes;
  const groupedChanges: { category: string; text: string }[] = storedGrouped ? storedGrouped.filter((item: any) => item.text && item.text.trim())
    : (() => {
        const real: { category: string; text: string }[] = [];
        if (whatChanged && whatChanged.trim() && whatChanged !== 'Initial workspace observations established.') {
          real.push({ category: 'PROJECT', text: whatChanged });
        }
        if (deltaChanges.length > 0 && deltaChanges[0]?.trim()) {
          real.push({ category: 'CODE', text: deltaChanges[0] });
        }
        const dec = workspace?.understanding?.decisions?.[0];
        if (dec) {
          const decText = typeof dec === 'string' ? dec : (dec.title || dec.rationale || '');
          if (decText?.trim()) real.push({ category: 'DECISION', text: decText });
        }
        if (blocker && blocker.trim() && blocker !== 'None' && blocker !== 'No critical blockers right now.') {
          real.push({ category: 'BLOCKER', text: blocker });
        }
        if (nextAction && nextAction.trim()) {
          real.push({ category: 'NEXT', text: nextAction });
        }
        return real;
      })();

  const lastOutcomes = workspace?.last_restore_outcomes?.items || [];

  // Strict: only real observed URLs - never inject fake sqlite docs
  const urlResources: string[] = Object.keys(resourcesObj).filter(k => k.startsWith('http') || resourcesObj[k]?.type === 'url' || resourcesObj[k]?.type === 'browser');

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

  // Strict: no fake fallback CWD/command — show honest empty state if not observed
  const terminalCwd: string | null = workspace?.terminal_cwd || null;
  const recentCommand: string | null = workspace?.recent_command || null;

  return (
    <div className="surfacing momentum" style={{ animation: 'surface-in 900ms cubic-bezier(0.32, 0.72, 0.24, 1) both' }}>
      <div className="from">AROVA · CONTEXT RECOVERY</div>
      
      <div className="lede">
        {greeting}. Ready to resume {title}?
        {isLowConfidence && confidence > 0 && !isNoConfidence && (
          <span style={{ display: 'block', fontSize: '13px', color: 'var(--accent-amber)', marginTop: '6px', fontWeight: 500 }}>
            I think this is right — please verify ({confidence}% confidence)
          </span>
        )}
        {isNoConfidence && (
          <span style={{ display: 'block', fontSize: '13px', color: 'var(--ink-3)', marginTop: '6px', fontWeight: 500 }}>
            Fresh session — confidence building…
          </span>
        )}
      </div>

      <p>
        Yesterday you focused on <strong>{title}</strong>.{' '}
        {blocker && blocker !== 'None' && blocker !== 'No critical blockers right now.' ? (
          <span style={{ color: 'var(--accent-amber)' }}>{isLowConfidence ? `Possible blocker: ${blocker}. ` : `Stopped due to blocker: ${blocker}. `}</span>
        ) : (
          <span>You stopped cleanly without blockers. </span>
        )}
        {nextAction ? (isLowConfidence ? `Suggested next: ${nextAction}` : `Next step planned: ${nextAction}`) : 'Active engineering momentum preserved.'}
      </p>

      {(deltaChanges.length > 0 || preparedList.length > 0) ? (
        <p className="quiet">
          {deltaChanges.length > 0 ? deltaChanges[0] : `${preparedList.length} file${preparedList.length !== 1 ? 's' : ''} prepared for continuation (${preparedList.slice(0, 3).join(', ')}${preparedList.length > 3 ? '...' : ''})`}.{' '}
          {isNoConfidence ? (
            <span>Building confidence as you work…</span>
          ) : isLowConfidence ? (
            <span>Arova is <strong style={{ color: 'var(--accent-amber)' }}>{confidence}% confident</strong> — please verify before resuming. {accuracyTotal > 0 && `${accuracyScore}/${accuracyTotal} dimensions verified.`}</span>
          ) : (
            <span>Arova is <strong style={{ color: 'var(--ink)' }}>{confidence}% confident</strong>{accuracyTotal > 0 && ` with ${accuracyScore}/${accuracyTotal} verified context dimensions.`}</span>
          )}
        </p>
      ) : isNoConfidence ? (
        <p className="quiet">Fresh workspace — confidence will build as Arova observes your work.</p>
      ) : null}

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
              <span style={{ fontWeight: 600, color: 'var(--ink)' }}>Terminal working directory {terminalCwd ? `(${terminalCwd})` : '(no CWD observed)'}</span>
            </label>
            {recentCommand ? (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', background: 'var(--glass-2)', padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--hairline-2)' }}>
                <span style={{ fontFamily: 'var(--font-mono, monospace)', color: 'var(--ink-2)', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '300px' }}>Recent command: {recentCommand}</span>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button className="action-chip" onClick={() => handleCommandAction(recentCommand)} style={{ padding: '2px 8px', fontSize: '11px' }}>{copiedCmd ? 'Copied!' : 'Copy'}</button>
                  <button className="action-chip primary" onClick={() => socket.sendEvent({ type: 'terminal.execute', command: recentCommand, cwd: terminalCwd || undefined })} style={{ padding: '2px 8px', fontSize: '11px' }}>Run</button>
                </div>
              </div>
            ) : (
              <div style={{ fontSize: '12px', color: 'var(--ink-3)', fontStyle: 'italic', paddingLeft: '28px' }}>No recent terminal command observed</div>
            )}
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
              <span style={{ color: accuracyTotal === 0 ? 'var(--ink-mute)' : accuracyScore === accuracyTotal ? 'var(--accent-sage)' : accuracyScore >= Math.ceil(accuracyTotal/2) ? 'var(--accent-gold)' : 'var(--ink-mute)' }}>
                {accuracyTotal === 0 ? 'No verified dimensions yet' : `${accuracyScore} / ${accuracyTotal} verified`}
              </span>
            </div>
            {recAcc && recAcc.dimensions.length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', fontSize: '12px', marginBottom: '14px' }}>
                {recAcc.dimensions.map((dim: any, idx: number) => (
                  <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '6px', color: dim.ok ? 'var(--ink)' : 'var(--ink-3)' }}>
                    <span style={{ color: dim.ok ? 'var(--accent-sage)' : 'var(--ink-mute)', fontWeight: 600 }}>{dim.ok ? '✓' : '✗'}</span>
                    <span>{dim.name}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: '12px', color: 'var(--ink-3)', fontStyle: 'italic', marginBottom: '14px' }}>No recovery dimensions scored yet — verify after first restore</div>
            )}
            {confBreakdown ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px', fontFamily: 'var(--font-mono, monospace)', background: 'var(--glass-2)', padding: '12px 14px', borderRadius: '8px', border: '1px solid var(--hairline-2)', marginBottom: '14px' }}>
                {Object.entries(confBreakdown).map(([label, score]: any, idx) => {
                  const numScore = typeof score === 'number' ? score : parseInt(score) || 0;
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
            ) : (
              <div style={{ fontSize: '12px', color: 'var(--ink-3)', fontStyle: 'italic', background: 'var(--glass-2)', padding: '12px 14px', borderRadius: '8px', border: '1px solid var(--hairline-2)', marginBottom: '14px' }}>
                No confidence breakdown yet — scores appear after observing your work
              </div>
            )}

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

