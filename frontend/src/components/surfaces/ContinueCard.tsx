import React, { useState, useEffect, useMemo } from 'react';
import { socket } from '../../runtime/socket';
import { useAwarenessState } from '../../state';

interface ContinueCardProps {
  workspace: any | null;
}

interface EditorItem {
  id: string;
  name: string;
  path: string;
  directory: string;
  app: string;
  action_label: string;
}

interface TerminalItem {
  id: string;
  cwd: string;
  display_path: string;
  app: string;
  recent_command?: string;
  action_label: string;
}

interface BrowserItem {
  id: string;
  url: string;
  title: string;
  domain: string;
  app: string;
  action_label: string;
}

interface AppItem {
  id: string;
  name: string;
  window_title: string;
  app: string;
  action_label: string;
}

export const ContinueCard: React.FC<ContinueCardProps> = ({ workspace }) => {
  const { continueCardDismissed, dismissContinueCard } = useAwarenessState();
  const [showOptions, setShowOptions] = useState(false);
  const [selectedEditors, setSelectedEditors] = useState<string[]>([]);
  const [selectedTerminals, setSelectedTerminals] = useState<string[]>([]);
  const [selectedBrowsers, setSelectedBrowsers] = useState<string[]>([]);
  const [selectedApps, setSelectedApps] = useState<string[]>([]);
  const [copiedCmd, setCopiedCmd] = useState(false);
  const [restoring, setRestoring] = useState(false);

  // Extract structured, classified items from workspace
  const { editors, terminals, browsers, apps } = useMemo(() => {
    if (!workspace) return { editors: [], terminals: [], browsers: [], apps: [] };

    const isNoisePath = (p: string) => {
      const pLow = (p || '').toLowerCase();
      return [
        '/.cargo', '/index.crates.io', '/.rustup', '/.gemini', '/.npm', '/.nvm',
        '/.pyenv', '/.vscode', '/.cursor', '/.antigravity', '/node_modules',
        '/site-packages', '/__pycache__', '/venv', '/.venv', '/target/', '/dist/', '/build/',
        '\\appdata\\', '\\.cargo\\', '\\index.crates.io\\', '\\node_modules\\'
      ].some(k => pLow.includes(k));
    };

    // 1. If backend already sent structured categorized_items, clean and use them
    const backendCategories = workspace?.categorized_items;
    if (backendCategories && (backendCategories.editors || backendCategories.terminals || backendCategories.browsers || backendCategories.apps)) {
      const rawEditors = ((backendCategories.editors || []) as EditorItem[]).filter(e => !isNoisePath(e.path) && !isNoisePath(e.name));
      const rawBrowsers: BrowserItem[] = [];
      const seenTitles = new Set<string>();

      ((backendCategories.browsers || []) as BrowserItem[]).forEach(b => {
        const tKey = (b.title || '').toLowerCase().trim();
        const bDomain = (b.domain || '').toLowerCase().trim();
        const alreadyPresent = rawBrowsers.some(rb => 
          rb.url === b.url || 
          rb.title.toLowerCase().trim() === tKey ||
          (bDomain && rb.domain.toLowerCase().trim() === bDomain && (rb.title.toLowerCase().includes(tKey) || tKey.includes(rb.title.toLowerCase())))
        );
        if (!alreadyPresent && !seenTitles.has(tKey)) {
          seenTitles.add(tKey);
          rawBrowsers.push(b);
        }
      });

      return {
        editors: rawEditors.slice(0, 4),
        terminals: ((backendCategories.terminals || []) as TerminalItem[]).slice(0, 2),
        browsers: rawBrowsers.slice(0, 5),
        apps: ((backendCategories.apps || []) as AppItem[]).slice(0, 3)
      };
    }

    // 2. Otherwise parse robustly from reality resources
    const resourcesObj = workspace?.reality?.resources || {};
    const resourcesArr: string[] = workspace?.associated_resources || Object.keys(resourcesObj);

    const parsedEditors: EditorItem[] = [];
    const parsedTerminals: TerminalItem[] = [];
    const parsedBrowsers: BrowserItem[] = [];
    const parsedApps: AppItem[] = [];

    resourcesArr.forEach((resKey: string) => {
      const meta = resourcesObj[resKey] || {};
      const rType = meta?.type || '';
      const rCat = meta?.category || '';
      const identity = String(meta?.identity || resKey);
      const idLower = identity.toLowerCase();

      // Filter out Arova itself, frontend dev window, and internal dev processes
      if (
        idLower.includes('frontend - arova') ||
        idLower.includes('arova - arova') ||
        idLower.includes('arova desktop') ||
        idLower === 'arova' ||
        idLower === 'arovad' ||
        idLower === 'frontend' ||
        idLower.includes('npm run tauri') ||
        idLower.includes('tauri dev') ||
        idLower.includes('cargo tauri') ||
        idLower.includes('build_arovad') ||
        idLower.startsWith('arova v')
      ) {
        return;
      }
      if (['N/A', 'v2', 'Desktop', 'xprintidle', 'root'].includes(identity)) {
        return;
      }

      if (rCat === 'browser' || rType === 'browser' || rType === 'url' || identity.startsWith('http://') || identity.startsWith('https://')) {
        const cleanUrl = identity.replace(/^url:\/\//, '').trim();
        const uLower = cleanUrl.toLowerCase();
        const isJunk = [
          "newtab", "about:blank", "chrome://", "brave://", "edge://", "firefox://",
          "localhost:8765", "127.0.0.1:8765", "localhost:5173", "127.0.0.1:5173",
          "instagram.com", "facebook.com", "tiktok.com", "twitter.com", "x.com",
          "google.com/sorry", "google.com/search", "/accounts/setosid", "/servicelogin"
        ].some(skip => uLower.includes(skip));

        if (!isJunk) {
          let host = cleanUrl;
          try {
            host = new URL(cleanUrl).hostname;
          } catch {
            host = cleanUrl;
          }
          let bTitle = meta?.summary || meta?.title || host;
          for (const suffix of [" - Google Chrome", " - Brave", " - Mozilla Firefox", " - Microsoft Edge", " - Chromium"]) {
            if (bTitle.endsWith(suffix)) {
              bTitle = bTitle.slice(0, -suffix.length).trim();
            }
          }
          const bTitleLow = bTitle.toLowerCase().trim();
          if (!["new tab", "brave", "google chrome", "firefox", "home"].includes(bTitleLow)) {
            const alreadyExists = parsedBrowsers.some(b => 
              b.url === cleanUrl || 
              b.title.toLowerCase().trim() === bTitleLow ||
              (host && b.domain === host && (bTitleLow.includes(b.title.toLowerCase()) || b.title.toLowerCase().includes(bTitleLow)))
            );
            if (!alreadyExists) {
              const bApp = meta?.app || 'Browser';
              parsedBrowsers.push({
                id: cleanUrl,
                url: cleanUrl,
                title: bTitle,
                domain: host,
                app: bApp,
                action_label: `Open tab: ${bTitle}`
              });
            }
          }
        }
      } else if (rCat === 'terminal' || rType === 'terminal' || identity.startsWith('terminal://')) {
        const cleanCwd = identity.replace(/^terminal:\/\//, '');
        // Exclude internal dev build directories
        if (cleanCwd.endsWith('/arova/frontend') || cleanCwd.endsWith('/arova/release') || cleanCwd.endsWith('/arova/dist')) {
          return;
        }
        if (cleanCwd && !parsedTerminals.some(t => t.cwd === cleanCwd)) {
          parsedTerminals.push({
            id: cleanCwd,
            cwd: cleanCwd,
            display_path: cleanCwd.replace(/^\/home\/[^\/]+/, '~'),
            app: meta?.app || 'Terminal',
            recent_command: workspace?.recent_command || meta?.recent_command,
            action_label: `Restore terminal session (${cleanCwd.replace(/^\/home\/[^\/]+/, '~')})`
          });
        }
      } else if (rCat === 'editor' || rType === 'vscode' || rType === 'editor' || rType === 'file' || (identity.startsWith('/') && !identity.startsWith('http'))) {
        const cleanPath = identity.replace(/^file:\/\//, '').trim();
        if (isNoisePath(cleanPath)) return;

        const parts = cleanPath.split('/');
        let rawName = meta?.file_name || parts[parts.length - 1] || cleanPath;
        if (isNoisePath(rawName)) return;

        const wsTitle = workspace?.title || '';

        // Clean up any raw window titles
        if (rawName.includes(' - ') || rawName.toLowerCase().includes('antigravity')) {
          const subparts = rawName.split(' - ').map((s: string) => s.trim()).filter(Boolean);
          const cleaned = subparts.filter((sp: string) => {
            const pLow = sp.toLowerCase();
            if (['antigravity-ide', 'antigravity ide', 'antigravity', 'visual studio code', 'code', 'code - oss', 'cursor'].includes(pLow)) return false;
            if (wsTitle && pLow === wsTitle.toLowerCase()) return false;
            return true;
          });
          if (cleaned.length > 0) {
            rawName = cleaned[cleaned.length - 1];
          } else {
            rawName = wsTitle || parts[parts.length - 1] || cleanPath;
          }
        }

        // Avoid duplicate workspace project window title
        if (wsTitle && rawName.toLowerCase() === wsTitle.toLowerCase() && parsedEditors.some(e => e.name.toLowerCase() === wsTitle.toLowerCase())) {
          return;
        }

        const dir = parts.slice(-3).join('/');
        const editorApp = meta?.app || 'Antigravity IDE';
        if (rawName && !parsedEditors.some(e => e.path === cleanPath || e.name === rawName)) {
          parsedEditors.push({
            id: cleanPath,
            name: rawName,
            path: cleanPath,
            directory: dir ? `.../${dir}` : '',
            app: editorApp,
            action_label: meta?.summary || `Open ${rawName} in ${editorApp}`
          });
        }
      } else if (rCat === 'app' || rType === 'window') {
        const appName = meta?.app || identity;
        const aLower = String(appName).toLowerCase();
        if (!aLower.includes('arova') && !aLower.includes('frontend') && !aLower.includes('tauri')) {
          if (appName && !parsedApps.some(a => a.name === appName)) {
            parsedApps.push({
              id: identity,
              name: appName,
              window_title: meta?.title || identity,
              app: appName,
              action_label: `Launch ${appName}`
            });
          }
        }
      }
    });

    // Deduplicate bare project folder when specific files are present
    const hasFiles = parsedEditors.some(e => e.name && e.name.includes('.'));
    const finalEditors = hasFiles ? parsedEditors.filter(e => e.name.includes('.')) : parsedEditors;

    // Terminal CWD fallback if no terminal in resources
    if (parsedTerminals.length === 0 && workspace?.terminal_cwd) {
      const tCwd = workspace.terminal_cwd;
      if (!tCwd.endsWith('/arova/frontend')) {
        parsedTerminals.push({
          id: tCwd,
          cwd: tCwd,
          display_path: tCwd.replace(/^\/home\/[^\/]+/, '~'),
          app: 'Terminal',
          recent_command: workspace?.recent_command,
          action_label: `Restore terminal session (${tCwd.replace(/^\/home\/[^\/]+/, '~')})`
        });
      }
    }

    return {
      editors: finalEditors.slice(0, 4),
      terminals: parsedTerminals.slice(0, 2),
      browsers: parsedBrowsers.slice(0, 5),
      apps: parsedApps.slice(0, 3)
    };
  }, [workspace]);

  // Sync selected state initially
  useEffect(() => {
    if (workspace && (workspace.id || workspace.workspace_id)) {
      socket.sendEvent({
        type: 'dogfooding.record_acceptance',
        event: 'shown'
      });
      setSelectedEditors(editors.map(e => e.id));
      setSelectedTerminals(terminals.map(t => t.id));
      setSelectedBrowsers(browsers.map(b => b.id));
      setSelectedApps(apps.map(a => a.id));
    }
  }, [workspace?.id, workspace?.workspace_id, editors, terminals, browsers, apps]);

  useEffect(() => {
    if (!continueCardDismissed) {
      setRestoring(false);
    }
  }, [continueCardDismissed]);

  if (!workspace || !(workspace.id || workspace.workspace_id)) return null;
  if (continueCardDismissed) return null;

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const title = workspace?.title || 'Current Workspace';
  const continueData = workspace as any;

  const blocker = continueData?.current_blocker || workspace?.understanding?.momentum?.current_blocker || '';
  const goal = continueData?.current_goal || workspace?.understanding?.momentum?.goal || '';

  const toggleEditor = (id: string) => {
    setSelectedEditors(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
  };

  const toggleTerminal = (id: string) => {
    setSelectedTerminals(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
  };

  const toggleBrowser = (id: string) => {
    setSelectedBrowsers(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
  };

  const toggleApp = (id: string) => {
    setSelectedApps(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
  };

  const selectAll = () => {
    setSelectedEditors(editors.map(e => e.id));
    setSelectedTerminals(terminals.map(t => t.id));
    setSelectedBrowsers(browsers.map(b => b.id));
    setSelectedApps(apps.map(a => a.id));
  };

  const deselectAll = () => {
    setSelectedEditors([]);
    setSelectedTerminals([]);
    setSelectedBrowsers([]);
    setSelectedApps([]);
  };

  const totalSelected = selectedEditors.length + selectedTerminals.length + selectedBrowsers.length + selectedApps.length;

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
        restore_all: false,
        restore_vscode: selectedEditors.length > 0,
        restore_editors: selectedEditors.length > 0,
        selected_files: selectedEditors,
        restore_terminal: selectedTerminals.length > 0,
        selected_terminals: selectedTerminals,
        restore_chrome: selectedBrowsers.length > 0,
        restore_browsers: selectedBrowsers.length > 0,
        selected_urls: selectedBrowsers,
        selected_apps: selectedApps
      }
    });
    dismissContinueCard();
  };

  // Build natural summary text
  const summaryParts: string[] = [];
  if (editors.length > 0) summaryParts.push(`${editors.length} editor file${editors.length === 1 ? '' : 's'}`);
  if (terminals.length > 0) summaryParts.push(`${terminals.length} terminal session${terminals.length === 1 ? '' : 's'}`);
  if (browsers.length > 0) summaryParts.push(`${browsers.length} browser tab${browsers.length === 1 ? '' : 's'}`);
  if (apps.length > 0) summaryParts.push(`${apps.length} desktop application${apps.length === 1 ? '' : 's'}`);
  return (
    <div 
      className="surfacing momentum"
      style={{ 
        marginBottom: '28px',
        animation: 'surface-in 700ms cubic-bezier(0.32, 0.72, 0.24, 1) both'
      }}
    >
      {/* 1. Natural Arova Origin Indicator */}
      <div className="from">
        AROVA
      </div>

      {/* 2. Chat-Native Large Serif Title */}
      <div className="lede">
        {greeting}. Ready to resume <span style={{ color: 'var(--accent-gold)' }}>{title}</span>?
      </div>

      {/* 3. Natural Context Description */}
      <p style={{ margin: '0 0 16px 0', fontSize: '14.5px', lineHeight: '1.6', color: 'var(--ink-2)' }}>
        {goal && goal !== 'Active project' ? (
          <span>Goal: <strong>{goal}</strong>.{' '}</span>
        ) : null}
        <span>
          {summaryParts.length > 0 
            ? `Workspace state preserved: ${summaryParts.join(', ')}.`
            : 'Workspace state preserved.'}
        </span>
        {blocker && blocker !== 'None' && blocker !== 'No critical blockers right now.' ? (
          <span> Previous blocker: <span style={{ color: 'var(--accent-amber)' }}>{blocker}</span>.</span>
        ) : null}
      </p>

      {/* 4. Action Chips */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', marginBottom: showOptions ? '18px' : '0' }}>
        <button 
          onClick={handleResume}
          disabled={restoring || totalSelected === 0}
          className="action-chip primary"
          style={{ 
            padding: '8px 16px', 
            fontSize: '13px', 
            fontWeight: 600,
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px'
          }}
        >
          {restoring ? 'Restoring...' : `Resume Workspace (${totalSelected}) →`}
        </button>

        <button 
          onClick={() => setShowOptions(!showOptions)}
          className="action-chip"
          style={{ 
            padding: '8px 14px', 
            fontSize: '12.5px', 
            fontWeight: 500,
            cursor: 'pointer' 
          }}
        >
          {showOptions ? 'Hide Items' : `Choose Items (${totalSelected})`}
        </button>

        <button 
          onClick={() => dismissContinueCard()}
          className="action-chip"
          style={{ 
            padding: '8px 12px', 
            fontSize: '12px', 
            color: 'var(--ink-mute)',
            cursor: 'pointer' 
          }}
        >
          Dismiss
        </button>
      </div>

      {/* 5. Real Selectable Items (Shown when Choose Items is toggled) */}

      {/* 6. Granular Selector (Shown when 'Choose What To Restore' is clicked) */}
      {showOptions && (
        <div style={{ 
          marginTop: '16px',
          background: 'var(--glass-1)',
          border: '1px solid var(--hairline-2)',
          borderRadius: '16px',
          padding: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px'
        }}>
          {/* Quick Select / Deselect Bar */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '6px', borderBottom: '1px solid var(--hairline-2)' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--ink-mute)' }}>
              Select exact items to open
            </span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button onClick={selectAll} style={{ background: 'none', border: 'none', color: 'var(--accent-gold, #d4a878)', fontSize: '11.5px', cursor: 'pointer', padding: 0 }}>Select All</button>
              <span style={{ color: 'var(--ink-mute)', fontSize: '11.5px' }}>•</span>
              <button onClick={deselectAll} style={{ background: 'none', border: 'none', color: 'var(--ink-mute)', fontSize: '11.5px', cursor: 'pointer', padding: 0 }}>Deselect All</button>
            </div>
          </div>

          {/* Category 1: Workspace & Code Editors */}
          {editors.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--ink-mute)', textTransform: 'uppercase', letterSpacing: '0.08em', display: 'flex', justifyContent: 'space-between' }}>
                <span>Workspace & Editors</span>
                <span>{selectedEditors.length}/{editors.length}</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {editors.map((item) => {
                  const isChecked = selectedEditors.includes(item.id);
                  return (
                    <label 
                      key={item.id} 
                      style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '10px', 
                        fontSize: '13px', 
                        color: isChecked ? 'var(--ink)' : 'var(--ink-mute)', 
                        cursor: 'pointer',
                        padding: '6px 8px',
                        borderRadius: '6px',
                        background: isChecked ? 'rgba(255, 255, 255, 0.02)' : 'transparent',
                        transition: 'background 0.15s'
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleEditor(item.id)}
                        style={{ accentColor: 'var(--accent-gold)', width: '14px', height: '14px', cursor: 'pointer' }}
                      />
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', minWidth: 0, flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono, monospace)', fontSize: '12.5px', color: 'var(--ink)' }}>
                            {item.name}
                          </span>
                          <span style={{ fontSize: '10.5px', background: 'var(--hairline-2, rgba(120,110,95,0.12))', padding: '1px 6px', borderRadius: '4px', color: 'var(--ink)' }}>
                            {item.app}
                          </span>
                          {item.directory && (
                            <span style={{ fontSize: '11px', color: 'var(--ink-mute)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {item.directory}
                            </span>
                          )}
                        </div>
                        <span style={{ fontSize: '11.5px', color: 'var(--ink-mute)' }}>
                          {item.action_label?.startsWith('Open window:') 
                            ? `Open ${item.name} in ${item.app}` 
                            : item.action_label}
                        </span>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* Category 2: Terminal Sessions */}
          {terminals.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--ink-mute)', textTransform: 'uppercase', letterSpacing: '0.08em', display: 'flex', justifyContent: 'space-between' }}>
                <span>Terminal Environment</span>
                <span>{selectedTerminals.length}/{terminals.length}</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {terminals.map((item) => {
                  const isChecked = selectedTerminals.includes(item.id);
                  return (
                    <div key={item.id} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <label 
                        style={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          gap: '10px', 
                          fontSize: '13px', 
                          color: isChecked ? 'var(--ink)' : 'var(--ink-mute)', 
                          cursor: 'pointer',
                          padding: '6px 8px',
                          borderRadius: '6px',
                          background: isChecked ? 'var(--hairline)' : 'transparent',
                          transition: 'background 0.15s'
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleTerminal(item.id)}
                          style={{ accentColor: 'var(--accent-gold)', width: '14px', height: '14px', cursor: 'pointer' }}
                        />
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', minWidth: 0, flex: 1 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                            <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono, monospace)', fontSize: '12.5px', color: 'var(--ink)' }}>
                              {item.display_path}
                            </span>
                            <span style={{ fontSize: '10.5px', background: 'var(--hairline-2, rgba(120,110,95,0.12))', padding: '1px 6px', borderRadius: '4px', color: 'var(--ink)' }}>
                              {item.app}
                            </span>
                          </div>
                          <span style={{ fontSize: '11.5px', color: 'var(--ink-mute)' }}>
                            {item.action_label}
                          </span>
                        </div>
                      </label>
                      {item.recent_command && (
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', background: 'var(--hairline)', padding: '4px 8px', borderRadius: '6px', marginLeft: '24px' }}>
                          <span style={{ fontFamily: 'monospace', color: 'var(--ink-2)', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '320px' }}>
                            Recent: {item.recent_command}
                          </span>
                          <div style={{ display: 'flex', gap: '6px' }}>
                            <button className="action-chip" onClick={() => handleCommandAction(item.recent_command!)} style={{ padding: '2px 8px', fontSize: '11px' }}>
                              {copiedCmd ? 'Copied!' : 'Copy'}
                            </button>
                            <button className="action-chip primary" onClick={() => socket.sendEvent({ type: 'terminal.execute', command: item.recent_command, cwd: item.cwd })} style={{ padding: '2px 8px', fontSize: '11px' }}>
                              Run
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Category 3: Browser Tabs & Documentation */}
          {browsers.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--ink-mute)', textTransform: 'uppercase', letterSpacing: '0.08em', display: 'flex', justifyContent: 'space-between' }}>
                <span>Browser Tabs & Documentation</span>
                <span>{selectedBrowsers.length}/{browsers.length}</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {browsers.map((item) => {
                  const isChecked = selectedBrowsers.includes(item.id);
                  return (
                    <label 
                      key={item.id} 
                      style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '10px', 
                        fontSize: '12.5px', 
                        color: isChecked ? 'var(--ink-2)' : 'var(--ink-mute)', 
                        cursor: 'pointer',
                        padding: '6px 8px',
                        borderRadius: '6px',
                        background: isChecked ? 'var(--hairline)' : 'transparent',
                        transition: 'background 0.15s'
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleBrowser(item.id)}
                        style={{ accentColor: 'var(--accent-gold)', width: '14px', height: '14px', cursor: 'pointer' }}
                      />
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', minWidth: 0, flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <span style={{ fontWeight: 600, color: isChecked ? 'var(--ink)' : 'var(--ink-mute)' }}>
                            {item.title}
                          </span>
                          <span style={{ fontSize: '10.5px', background: 'var(--hairline-2, rgba(120,110,95,0.12))', padding: '1px 6px', borderRadius: '4px', color: 'var(--ink)' }}>
                            {item.domain}
                          </span>
                        </div>
                        <span style={{ fontSize: '11.5px', color: 'var(--ink-mute)' }}>
                          {item.action_label}
                        </span>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* Category 4: Desktop Applications */}
          {apps.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--ink-mute)', textTransform: 'uppercase', letterSpacing: '0.08em', display: 'flex', justifyContent: 'space-between' }}>
                <span>Desktop Applications</span>
                <span>{selectedApps.length}/{apps.length}</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {apps.map((item) => {
                  const isChecked = selectedApps.includes(item.id);
                  return (
                    <label 
                      key={item.id} 
                      style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '10px', 
                        fontSize: '12.5px', 
                        color: isChecked ? 'var(--ink-2)' : 'var(--ink-mute)', 
                        cursor: 'pointer',
                        padding: '6px 8px',
                        borderRadius: '6px',
                        background: isChecked ? 'var(--hairline)' : 'transparent',
                        transition: 'background 0.15s'
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleApp(item.id)}
                        style={{ accentColor: 'var(--accent-gold)', width: '14px', height: '14px', cursor: 'pointer' }}
                      />
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', minWidth: 0, flex: 1 }}>
                        <span style={{ fontWeight: 600, color: isChecked ? 'var(--ink)' : 'var(--ink-mute)' }}>
                          {item.name}
                        </span>
                        <span style={{ fontSize: '11.5px', color: 'var(--ink-mute)' }}>
                          {item.action_label}
                        </span>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
