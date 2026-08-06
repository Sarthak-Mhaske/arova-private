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
  const [restoring, setRestoring] = useState(false);

  useEffect(() => {
    if (workspace && (workspace.id || workspace.workspace_id)) {
      socket.sendEvent({
        type: 'dogfooding.record_acceptance',
        event: 'shown'
      });
      const resourcesArr = (workspace as any).associated_resources || [];
      const urlResources: string[] = resourcesArr.filter((k: string) => k.startsWith('http') || k.startsWith('https'));
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

  const confidence = workspace?.confidence_score !== undefined ? workspace?.confidence_score : (workspace?.understanding?.confidence?.score ?? (associated_resources.length > 0 ? 85 : 0));
  
  const storyNarrative: string[] = (workspace?.story_narrative && workspace.story_narrative.length > 0)
    ? workspace.story_narrative
    : ((workspace?.understanding?.story_narrative && workspace.understanding.story_narrative.length > 0)
    ? workspace.understanding.story_narrative
    : (associated_resources.length > 0 ? [
        `Active focus on working set: ${preparedList.slice(0, 3).join(', ')}`,
        `Tracked workspace environment: ${title}`
      ] : [
        'No active working set items captured yet.',
        'Open your browser, editor, or terminal to track your workspace context.'
      ]));
      
  const whatChanged = '';
  const deltaChanges = continueData?.delta_changes || [];
  
  const blocker = continueData?.current_blocker || workspace?.understanding?.momentum?.current_blocker || '';
  const nextAction = continueData?.next_action || workspace?.understanding?.momentum?.next_action || '';
  const trajectoryStory = continueData?.trajectory_story || workspace?.understanding?.trajectory_story || '';

  const urlResources: string[] = associated_resources.filter((k: string) => k.startsWith('http') || k.startsWith('https') || k.includes('youtube'));

  const resourceSummaries = continueData?.resource_summaries || workspace?.resource_summaries || {};

  const formatUrlContext = (u: string): string => {
    // Check if we have an authentic page/video title recorded in resource_summaries
    const exactTitle = resourceSummaries[u];
    if (exactTitle && typeof exactTitle === 'string' && exactTitle.trim() && exactTitle !== u) {
      let cleanT = exactTitle.trim();
      // Clean up common suffix clutter
      cleanT = cleanT.replace(/ - YouTube Music$/i, ' (YouTube Music)')
                     .replace(/ - YouTube$/i, ' (YouTube)');
      if (cleanT.length > 60) cleanT = cleanT.slice(0, 57) + '...';
      return cleanT;
    }

    try {
      const parsed = new URL(u);
      const host = parsed.hostname.replace(/^www\./, '').toLowerCase();

      // 1. Google / Search Engines
      if (host.includes('google.com') || host.includes('bing.com') || host.includes('duckduckgo.com')) {
        const query = parsed.searchParams.get('q') || parsed.searchParams.get('query');
        if (query) {
          const cleanQ = decodeURIComponent(query.replace(/\+/g, ' '));
          return `Search: "${cleanQ.length > 45 ? cleanQ.slice(0, 42) + '...' : cleanQ}"`;
        }
        return `Web Search`;
      }

      // 2. YouTube
      if (host.includes('youtube.com') || host.includes('youtu.be')) {
        const v = parsed.searchParams.get('v');
        return v ? `YouTube Video: ${v}` : `YouTube`;
      }

      // 3. GitHub
      if (host.includes('github.com')) {
        const parts = parsed.pathname.split('/').filter(Boolean);
        if (parts.length >= 2) {
          return `GitHub: ${parts[0]}/${parts[1]}`;
        }
        return `GitHub`;
      }

      // 4. Stack Overflow
      if (host.includes('stackoverflow.com')) {
        const parts = parsed.pathname.split('/').filter(Boolean);
        if (parts.length >= 2 && parts[0] === 'questions') {
          const rawTitle = parts[2] ? parts[2].replace(/-/g, ' ') : parts[1];
          const cleanT = decodeURIComponent(rawTitle);
          return `Stack Overflow: ${cleanT.length > 40 ? cleanT.slice(0, 37) + '...' : cleanT}`;
        }
        return `Stack Overflow`;
      }

      // 5. Localhost / Local Dev
      if (host.includes('localhost') || host === '127.0.0.1') {
        return `Local App: localhost${parsed.port ? ':' + parsed.port : ''}`;
      }

      // Default: Domain + Path
      let label = host + (parsed.pathname !== '/' ? parsed.pathname : '');
      if (label.length > 55) label = label.slice(0, 52) + '...';
      return label;
    } catch {
      return u.length > 55 ? u.slice(0, 52) + '...' : u;
    }
  };

  const filteredUrlResources = urlResources.filter((u: string) => {
    const uLower = u.toLowerCase();
    return !["instagram.com", "facebook.com", "tiktok.com", "twitter.com", "x.com", "google.com/sorry", "/accounts/setosid", "/servicelogin"].some(skip => uLower.includes(skip));
  });

  const confBreakdown = continueData?.confidence_breakdown || {
    "Repository": workspace?.interpretation?.repo_paths?.length > 0 ? 100 : 0,
    "Open files": preparedList.length > 0 ? 100 : 0,
    "Goal": workspace?.understanding?.momentum?.goal ? 100 : 0,
    "Blocker": workspace?.understanding?.momentum?.current_blocker ? 100 : 0,
    "Browser docs": urlResources.length > 0 ? 100 : 0,
    "Terminal": 0
  };

  const recAcc = {
    dimensions: Object.entries(confBreakdown).map(([k, v]) => ({
      name: k,
      label: k,
      ok: (v as number) >= 50
    }))
  };
  const accuracyScore = recAcc.dimensions.filter((d: any) => d.ok).length;
  const accuracyTotal = recAcc.dimensions.length;

  const rawChanges: { category: string; text: string }[] = workspace?.understanding?.grouped_changes || [
    ...(whatChanged ? [{ category: 'PROJECT', text: whatChanged }] : []),
    ...(deltaChanges.length > 0 ? [{ category: 'CODE', text: deltaChanges[0] }] : (preparedList.length > 0 ? [{ category: 'CODE', text: `${preparedList.length} items observed in working set (${preparedList.slice(0, 3).join(', ')})` }] : [])),
    ...(workspace?.understanding?.decisions?.[0] ? [{ category: 'DECISION', text: workspace?.understanding?.decisions[0]?.title || workspace?.understanding?.decisions[0] }] : []),
    ...(blocker ? [{ category: 'BLOCKER', text: blocker }] : []),
    ...(nextAction ? [{ category: 'NEXT', text: nextAction }] : [])
  ];
  const groupedChanges = rawChanges.filter(item => item.text);

  const lastOutcomes = workspace?.last_restore_outcomes?.items || [];
  const explainabilityReasons: string[] = workspace?.understanding?.explainability_reasons || workspace?.explainability_reasons || (associated_resources.length > 0 ? [`Active working set verified across ${preparedList.length} items`] : ['No activity observed yet']);
  const reasons = workspace?.understanding?.confidence?.reasons || explainabilityReasons;

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

  const terminalCwd = workspace?.terminal_cwd;
  const recentCommand = workspace?.recent_command;

  return (
    <div className="continue-card glass-panel" style={{ padding: '24px', borderRadius: '18px', border: '1px solid var(--hairline-2)', background: 'var(--glass-2)', marginBottom: '32px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
        <div>
          <div style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--ink-mute)', fontWeight: 600, marginBottom: '4px' }}>
            AROVA · CONTEXT RECOVERY
          </div>
          <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--ink)', margin: 0 }}>
            {greeting}. Ready to resume {title}?
          </h3>
        </div>
        {confidence !== null && (
          <div style={{ padding: '4px 10px', borderRadius: '12px', background: confidence >= 85 ? 'rgba(74, 222, 128, 0.12)' : 'rgba(250, 204, 21, 0.12)', color: confidence >= 85 ? 'var(--accent-sage)' : 'var(--accent-gold)', fontSize: '12px', fontWeight: 600, border: `1px solid ${confidence >= 85 ? 'rgba(74, 222, 128, 0.25)' : 'rgba(250, 204, 21, 0.25)'}` }}>
            {confidence}% Confident
          </div>
        )}
      </div>

      {/* Story Narrative bullet points */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px', color: 'var(--ink-2)', marginBottom: '18px' }}>
        {storyNarrative.map((item, idx) => (
          <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: 'var(--accent-gold)' }}>•</span>
            <span>{item}</span>
          </div>
        ))}
      </div>

      {reasons.length > 0 && (
        <div style={{ fontSize: '12px', color: 'var(--ink-mute)', marginBottom: '20px', fontStyle: 'italic' }}>
          While you were away, {preparedList.length} files observed in working set ({preparedList.slice(0, 3).join(', ')}...). Arova is currently {confidence}% confident with {accuracyScore}/{accuracyTotal} verified context dimensions.
        </div>
      )}

      {/* Primary Actions */}
      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
        <button 
          className="action-chip primary" 
          onClick={handleResume}
          disabled={restoring}
          style={{ padding: '8px 18px', fontSize: '13px', fontWeight: 600 }}
        >
          {restoring ? 'Restoring Context...' : 'Restore Selected'}
        </button>
        
        <button 
          className="action-chip" 
          onClick={() => setShowOptions(!showOptions)}
          style={{ padding: '8px 14px', fontSize: '13px' }}
        >
          {showOptions ? 'Hide Options' : 'Customize Restoration'}
        </button>

        <button 
          className="action-chip" 
          onClick={() => setShowTrajectory(!showTrajectory)}
          style={{ padding: '8px 14px', fontSize: '13px' }}
        >
          {showTrajectory ? 'Hide Scorecard & Story' : 'Why Arova is Confident'}
        </button>

        <button 
          className="action-chip" 
          style={{ padding: '8px 14px', fontSize: '13px', marginLeft: 'auto', color: 'var(--ink-mute)' }}
          onClick={() => dismissContinueCard()}
        >
          Dismiss
        </button>
      </div>

      {/* Expandable Options section directly inline */}
      {showOptions && (
        <div style={{ marginTop: '20px', padding: '18px', background: 'var(--glass-1)', borderRadius: '14px', border: '1px solid var(--hairline-2)', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--ink)', display: 'flex', justifyContent: 'space-between' }}>
            <span>Select exact items to restore</span>
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
          {terminalCwd && (
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
              {recentCommand && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', background: 'var(--glass-2)', padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--hairline-2)' }}>
                  <span style={{ fontFamily: 'var(--font-mono, monospace)', color: 'var(--ink-2)', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '300px' }}>Recent command: {recentCommand}</span>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button className="action-chip" onClick={() => handleCommandAction(recentCommand)} style={{ padding: '2px 8px', fontSize: '11px' }}>{copiedCmd ? 'Copied!' : 'Copy'}</button>
                    <button className="action-chip primary" onClick={() => socket.sendEvent({ type: 'terminal.execute', command: recentCommand, cwd: terminalCwd })} style={{ padding: '2px 8px', fontSize: '11px' }}>Run</button>
                  </div>
                </div>
              )}
            </div>
          )}
          {filteredUrlResources.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingTop: '4px' }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--ink-2)' }}>Documentation & browser tabs:</div>
              {filteredUrlResources.map((u, idx) => {
                const displayLabel = formatUrlContext(u);
                return (
                  <label key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--ink-3)', cursor: 'pointer', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={u}>
                    <input type="checkbox" checked={selectedUrls.includes(u)} onChange={() => toggleUrl(u)} style={{ accentColor: 'var(--accent-gold)', flexShrink: 0 }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{displayLabel}</span>
                  </label>
                );
              })}
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

