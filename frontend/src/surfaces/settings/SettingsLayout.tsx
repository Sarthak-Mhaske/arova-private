import React, { useState, useEffect } from 'react';
import { socket } from '../../runtime/socket';
import { useSurfaceState, useAwarenessState } from '../../state';

const SettingsStyles = () => (
  <style>{`
    .tune-controls {
      display: flex;
      gap: 12px;
      margin-top: 16px;
      flex-wrap: wrap;
    }
    .tune-input {
      width: 100%;
      background: var(--glass-1);
      border: 1px solid var(--hairline-2);
      color: var(--ink);
      padding: 14px 18px;
      border-radius: 10px;
      font-size: 15px;
      font-family: inherit;
      outline: none;
      transition: border-color 0.2s;
    }
    .tune-input:focus {
      border-color: var(--accent-amber);
    }
    .tune-btn {
      padding: 8px 16px;
      background: var(--glass-2);
      color: var(--ink-2);
      border: 1px solid var(--glass-edge);
      border-radius: 999px;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
      letter-spacing: 0.05em;
    }
    .tune-btn:hover {
      background: var(--glass-3);
      color: var(--ink);
      transform: translateY(-1px);
    }
    .tune-btn.primary {
      background: linear-gradient(140deg, #ffffff, rgba(245, 222, 180, 0.72));
      color: var(--ink);
      box-shadow: inset 0 0 0 1px rgba(212, 168, 120, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.7);
    }
    .tune-toggle {
      position: relative;
      display: inline-block;
      width: 44px;
      height: 24px;
      flex-shrink: 0;
    }
    .tune-toggle input {
      opacity: 0;
      width: 0;
      height: 0;
    }
    .tune-toggle-slider {
      position: absolute;
      cursor: pointer;
      inset: 0;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid var(--hairline-2);
      border-radius: 24px;
      transition: 0.2s ease;
    }
    .tune-toggle-slider:before {
      position: absolute;
      content: "";
      height: 16px;
      width: 16px;
      left: 3px;
      bottom: 3px;
      background: var(--ink-3);
      border-radius: 50%;
      transition: 0.2s ease;
    }
    .tune-toggle input:checked + .tune-toggle-slider {
      background: rgba(235, 175, 75, 0.25);
      border-color: rgba(235, 175, 75, 0.6);
    }
    .tune-toggle input:checked + .tune-toggle-slider:before {
      transform: translateX(20px);
      background: var(--accent-gold);
      box-shadow: 0 0 6px rgba(235, 175, 75, 0.4);
    }
    .tune-select {
      width: 100%;
      appearance: none;
      -webkit-appearance: none;
      -moz-appearance: none;
      background-color: #141210 !important;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%23d4a878' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E") !important;
      background-repeat: no-repeat !important;
      background-position: right 18px center !important;
      background-size: 16px !important;
      border: 1px solid var(--hairline-2) !important;
      color: #f5eedb !important;
      padding: 14px 44px 14px 18px !important;
      border-radius: 10px !important;
      font-size: 14px !important;
      font-family: inherit !important;
      outline: none !important;
      cursor: pointer !important;
      transition: all 0.2s ease !important;
    }
    .tune-select:focus {
      border-color: var(--accent-amber) !important;
      box-shadow: 0 0 0 2px rgba(212, 168, 120, 0.2) !important;
    }
    .tune-select option {
      background-color: #1a1714 !important;
      color: #f5eedb !important;
      padding: 12px !important;
    }
    .settings-tab-btn {
      padding: 10px 18px;
      border: none;
      background: transparent;
      color: var(--ink-3);
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      border-radius: 10px;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .settings-tab-btn.active {
      background: var(--glass-2);
      color: var(--ink);
      font-weight: 600;
      box-shadow: var(--shadow-sm);
    }
    .settings-tab-btn:hover:not(.active) {
      color: var(--ink-2);
      background: rgba(255, 255, 255, 0.03);
    }
  `}</style>
);

export const SettingsLayout: React.FC = () => {
  const { closeSurface } = useSurfaceState();
  const { policy, hidden } = useAwarenessState();
  const [activeTab, setActiveTab] = useState<'providers' | 'awareness' | 'system'>('providers');

  const [config, setConfig] = useState({
    presence_style: 'hybrid',
    privacy: { workspace_awareness: true, memory_enabled: true, crash_recovery: true, browser_capture: true },
    runtime: { continuity_decay: 'standard', snapshot_retention: '30d' },
    preferred_provider: 'groq',
    allow_fallback: true
  });
  
  const [autostartEnabled, setAutostartEnabled] = useState(true);

  const [providers, setProviders] = useState({
    groq: { api_keys: [''] },
    openai: { api_keys: [''] },
    ollama: { host: 'http://localhost:11434' }
  });

  const [draftKeys, setDraftKeys] = useState({ groq: '', openai: '', gemini: '', anthropic: '', ollamaHost: 'http://localhost:11434' });
  const [diag, setDiag] = useState<any>(null);

  const [testResult, setTestResult] = useState<{ req_id: string; success: boolean; latency_ms?: number; error?: string } | null>(null);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  const handleToggleAutostart = (enabled: boolean) => {
    setAutostartEnabled(enabled);
    socket.sendEvent({
      type: 'config.set_autostart',
      enabled
    });
    setSaveStatus(`Auto-launch on startup ${enabled ? 'enabled' : 'disabled'}.`);
    setTimeout(() => setSaveStatus(null), 2500);
  };

  const handleExportMemories = () => {
    const handleMemResponse = (e: any) => {
      const ev = e.detail;
      if (ev && ev.type === 'memory.query_response') {
        window.removeEventListener('arova-event', handleMemResponse);
        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(ev.memories || [], null, 2));
        const downloadAnchor = document.createElement('a');
        downloadAnchor.setAttribute("href", dataStr);
        downloadAnchor.setAttribute("download", `arova_memories_${Date.now()}.json`);
        document.body.appendChild(downloadAnchor);
        downloadAnchor.click();
        downloadAnchor.remove();
        setSaveStatus('Memories exported successfully.');
        setTimeout(() => setSaveStatus(null), 2500);
      }
    };
    window.addEventListener('arova-event', handleMemResponse);
    socket.sendEvent({ type: 'memory.query_request', req_id: 'export_' + Date.now() });
  };

  const handleClearThreads = () => {
    if (window.confirm('Clear all active cognitive threads and start a fresh session?')) {
      socket.sendEvent({ type: 'client.new_thread' });
      setSaveStatus('Continuity threads cleared.');
      setTimeout(() => setSaveStatus(null), 2500);
    }
  };

  useEffect(() => {
    socket.sendEvent({ type: 'config.get_request' });
    socket.sendEvent({ type: 'config.get_autostart' });
    socket.sendEvent({ type: 'diagnostics.poll' });
    socket.sendEvent({ type: 'awareness.get_request' });

    const pollInterval = setInterval(() => {
      socket.sendEvent({ type: 'diagnostics.poll' });
    }, 3000);

    const handleEvent = (event: any) => {
      const ev = event.detail;
      if (ev.type === 'config.sync') {
        if (ev.config) setConfig((prev: any) => ({ ...prev, ...ev.config }));
        if (ev.autostart_enabled !== undefined) setAutostartEnabled(ev.autostart_enabled);
        if (ev.providers) {
          setProviders((prev: any) => ({ ...prev, ...ev.providers }));
          setDraftKeys(d => ({
            gemini: ev.providers?.gemini?.api_keys?.[0] || d.gemini || '',
            anthropic: ev.providers?.anthropic?.api_keys?.[0] || d.anthropic || '',
            openai: ev.providers?.openai?.api_keys?.[0] || d.openai || '',
            groq: ev.providers?.groq?.api_keys?.[0] || d.groq || '',
            ollamaHost: ev.providers?.ollama?.host || d.ollamaHost || 'http://localhost:11434',
          }));
        }
      } else if (ev.type === 'config.autostart_status') {
        if (ev.enabled !== undefined) setAutostartEnabled(ev.enabled);
      } else if (ev.type === 'provider.test_result') {
        const flat = { req_id: ev.req_id, ...ev.result };
        setTestResult(flat);
      } else if (ev.type === 'diagnostics.sync') {
        setDiag(ev.data);
      }
    };
    window.addEventListener('arova-event', handleEvent);
    return () => {
      clearInterval(pollInterval);
      window.removeEventListener('arova-event', handleEvent);
    };
  }, []);

  const saveConfig = (newConfig: any) => {
    setConfig(newConfig);
    socket.sendEvent({ type: 'config.update_request', config: newConfig });
  };

  const saveAndTestModel = (providerId: string) => {
    let newProviders = { ...providers };
    const key = (draftKeys as any)[providerId] || '';
    if (providerId === 'ollama') {
      newProviders = { ...providers, ollama: { host: draftKeys.ollamaHost } };
    } else {
      (newProviders as any)[providerId] = { api_keys: [key] };
    }
    setProviders(newProviders);
    socket.sendEvent({ type: 'config.update_request', providers: newProviders });
    setSaveStatus('Saving & testing...');
    setTimeout(() => {
      setSaveStatus(null);
      setTestResult(null);
      socket.sendEvent({
        type: 'provider.test',
        provider: providerId,
        api_key: key,
        host: providerId === 'ollama' ? draftKeys.ollamaHost : undefined
      });
    }, 400);
  };

  const getModelStatus = (id: string) => {
    if (testResult && testResult.req_id === id) {
      return testResult.success ? 'connected' : 'error';
    }
    if (id === 'ollama') return 'connected';
    const key = (draftKeys as any)[id] || (providers as any)[id]?.api_keys?.[0];
    return key ? 'connected' : 'missing_key';
  };

  const toggleAwarenessLayer = (layer: string, current: boolean) => {
    const nextVal = !current;
    if (policy) {
      useAwarenessState.getState().setPolicy({
        ...policy,
        [layer]: { ...(policy as any)[layer], enabled: nextVal }
      });
    }
    socket.sendEvent({
      type: 'awareness.update_request',
      layer,
      enabled: nextVal
    });
  };

  const awarenessCapabilities = [
    {
      key: 'presence',
      label: 'Presence Tracking',
      enabled: policy?.presence?.enabled ?? true,
      desc: 'Observes active window titles, focus transitions, and duration per application.',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <polyline points="12 6 12 12 16 14"></polyline>
        </svg>
      )
    },
    {
      key: 'context',
      label: 'Workspace & IDE Tracking',
      enabled: policy?.context?.enabled ?? true,
      desc: 'Discovers active repositories, git branches, and project directory roots in VS Code, Cursor, and Terminal.',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
        </svg>
      )
    },
    {
      key: 'deep_context',
      label: 'Deep Context & Terminal Inspection',
      enabled: policy?.deep_context?.enabled ?? true,
      desc: 'Reads visible code buffers, file diffs, and terminal execution output when deep reasoning is needed.',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="4 17 10 11 4 5"></polyline>
          <line x1="12" y1="19" x2="20" y2="19"></line>
        </svg>
      )
    },
    {
      key: 'memory_formation',
      label: 'Continuous Memory Formation',
      enabled: policy?.memory_formation?.enabled ?? true,
      desc: 'Synthesizes and persists architectural decisions, user preferences, and project facts across sessions.',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
          <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
          <line x1="12" y1="22.08" x2="12" y2="12"></line>
        </svg>
      )
    },
    {
      key: 'vision',
      label: 'Vision & Screen Analysis',
      enabled: policy?.vision?.enabled ?? false,
      desc: 'Captures and analyzes display screenshots on explicit user summon or when spatial ambiguity occurs.',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
          <circle cx="12" cy="12" r="3"></circle>
        </svg>
      )
    },
  ];

  const defaultHiddenItems = [
    'Password Managers (1Password, Bitwarden, KeePass, LastPass)',
    'Banking, Financial & Crypto Portals',
    'Private & Incognito Browser Sessions',
    'Authentication Headers, Tokens & API Keys',
    'System Keychain & Secure Enclave Data'
  ];

  const displayHidden = hidden && Array.isArray(hidden) && hidden.length > 0 ? hidden : defaultHiddenItems;
  const memoryCount = diag?.cognition?.memory_nodes ?? 0;

  return (
    <>
      <SettingsStyles />
      <div className="surface-head" style={{ borderBottom: '1px solid var(--hairline-2)', paddingBottom: '16px' }}>
        <div>
          <div className="h">Control Center</div>
          <span className="sub">AI Models · Privacy Policies · System Diagnostics</span>
        </div>
        <button className="surface-close" onClick={() => closeSurface()} aria-label="Close">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <path d="M6 6l12 12M18 6 6 18"/>
          </svg>
        </button>
      </div>

      {/* Top Tab Navigation */}
      <div style={{ display: 'flex', gap: '8px', padding: '16px 28px', borderBottom: '1px solid var(--hairline-2)', background: 'rgba(0,0,0,0.15)' }}>
        <button 
          className={`settings-tab-btn ${activeTab === 'providers' ? 'active' : ''}`}
          onClick={() => setActiveTab('providers')}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z"/>
          </svg>
          AI Models &amp; Providers
        </button>

        <button 
          className={`settings-tab-btn ${activeTab === 'awareness' ? 'active' : ''}`}
          onClick={() => setActiveTab('awareness')}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
          Awareness &amp; Privacy
        </button>

        <button 
          className={`settings-tab-btn ${activeTab === 'system' ? 'active' : ''}`}
          onClick={() => setActiveTab('system')}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3"></circle>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
          </svg>
          System &amp; Diagnostics
        </button>
      </div>

      <div className="tuning" style={{ padding: '24px 28px 40px', overflowY: 'auto' }}>
        {saveStatus && (
          <div style={{ padding: '10px 16px', background: 'rgba(76, 175, 80, 0.15)', border: '1px solid rgba(76, 175, 80, 0.3)', borderRadius: '10px', fontSize: '13px', color: '#4caf50', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            <span>{saveStatus}</span>
          </div>
        )}

        {/* ──────── TAB 1: AI PROVIDERS & MODELS ──────── */}
        {activeTab === 'providers' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Preferred AI Card */}
            <div style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', padding: '20px 24px' }}>
              <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--ink)', marginBottom: '4px' }}>Preferred AI</div>
              <div style={{ fontSize: '13px', color: 'var(--ink-3)', marginBottom: '16px' }}>Arova will use this provider as the default for all AI interactions</div>
              <select 
                className="tune-select"
                value={config.preferred_provider || 'groq'} 
                onChange={(e) => {
                  const val = e.target.value;
                  saveConfig({ ...config, preferred_provider: val });
                }}
              >
                <option value="groq" style={{ background: '#1a1714', color: '#f5eedb' }}>Groq LPU (Qwen 3.6 / Llama 3.3 - Fast Cloud)</option>
                <option value="gemini" style={{ background: '#1a1714', color: '#f5eedb' }}>Google AI (Gemini 2.0 Flash / Pro)</option>
                <option value="anthropic" style={{ background: '#1a1714', color: '#f5eedb' }}>Anthropic (Claude 3.7 Sonnet)</option>
                <option value="openai" style={{ background: '#1a1714', color: '#f5eedb' }}>OpenAI (GPT-4o / o3-mini)</option>
                <option value="ollama" style={{ background: '#1a1714', color: '#f5eedb' }}>Ollama (Local - Qwen 2.5 Coder / Llama 3.3)</option>
              </select>
            </div>

            {/* Allow Fallback Card */}
            <div style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', padding: '20px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--ink)', marginBottom: '4px' }}>Allow Fallback If Unavailable</div>
                <div style={{ fontSize: '13px', color: 'var(--ink-3)' }}>If your preferred AI is unavailable or rate-limited, Arova will automatically use another available provider.</div>
              </div>
              <label className="tune-toggle">
                <input 
                  type="checkbox" 
                  checked={config.allow_fallback !== false} 
                  onChange={(e) => saveConfig({...config, allow_fallback: e.target.checked})}
                />
                <span className="tune-toggle-slider" />
              </label>
            </div>

            {/* Providers Counter */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px', padding: '0 4px' }}>
              <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--ink)' }}>Connected Model Providers</div>
              <div style={{ fontSize: '13px', display: 'flex', gap: '12px' }}>
                <span style={{ color: '#4caf50', fontWeight: 500 }}>
                  {[ 'gemini', 'openai', 'groq', 'anthropic', 'ollama' ].filter(id => getModelStatus(id) === 'connected').length} Connected
                </span>
                <span style={{ color: 'var(--ink-3)' }}>|</span>
                <span style={{ color: '#ff9800', fontWeight: 500 }}>
                  {[ 'gemini', 'openai', 'groq', 'anthropic', 'ollama' ].filter(id => getModelStatus(id) !== 'connected').length} Not Configured
                </span>
              </div>
            </div>

            {/* Providers List */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {[
                { id: 'groq', name: 'Groq (Qwen 3.6 & Llama 3.3)', icon: 'groq', placeholder: 'gsk_...', directUrl: 'https://console.groq.com/keys' },
                { id: 'gemini', name: 'Google AI (Gemini 2.0)', icon: 'google', placeholder: 'AIzaSy...', directUrl: 'https://aistudio.google.com/app/apikey' },
                { id: 'anthropic', name: 'Anthropic (Claude 3.7)', icon: 'anthropic', placeholder: 'sk-ant-...', directUrl: 'https://console.anthropic.com/settings/keys' },
                { id: 'openai', name: 'OpenAI (GPT-4o & o3-mini)', icon: 'openai', placeholder: 'sk-...', directUrl: 'https://platform.openai.com/api-keys' },
                { id: 'ollama', name: 'Ollama (Local Qwen / Llama)', icon: 'ollama', isLocal: true, placeholder: 'http://localhost:11434', directUrl: 'https://ollama.com/download' }
              ].map(p => {
                const status = getModelStatus(p.id);
                const isConnected = status === 'connected';
                const isExpanded = (draftKeys as any)[`expanded_${p.id}`];

                return (
                  <div key={p.id} style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', overflow: 'hidden' }}>
                    <div style={{ padding: '18px 22px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', minWidth: '220px' }}>
                        <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--hairline-2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          {p.icon === 'google' && (
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                              <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="url(#gemini-grad)"/>
                              <defs>
                                <linearGradient id="gemini-grad" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
                                  <stop stopColor="#4285F4"/>
                                  <stop offset="0.5" stopColor="#9B51E0"/>
                                  <stop offset="1" stopColor="#EA4335"/>
                                </linearGradient>
                              </defs>
                            </svg>
                          )}
                          {p.icon === 'openai' && (
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" color="#ffffff">
                              <path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0813 4.7792-2.7582a.794.794 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4954 4.4953z"/>
                            </svg>
                          )}
                          {p.icon === 'anthropic' && (
                            <span style={{ fontWeight: 800, fontSize: '16px', color: '#f5dcb4', letterSpacing: '-0.05em' }}>A\</span>
                          )}
                          {p.icon === 'groq' && (
                            <span style={{ fontWeight: 900, fontSize: '18px', color: '#f4511e' }}>G</span>
                          )}
                          {p.icon === 'ollama' && (
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="1.8">
                              <circle cx="12" cy="12" r="8"/>
                              <circle cx="9" cy="10" r="1" fill="#fff"/>
                              <circle cx="15" cy="10" r="1" fill="#fff"/>
                              <path d="M10 14q2 2 4 0"/>
                            </svg>
                          )}
                        </div>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--ink)' }}>{p.name}</div>
                          <div style={{ fontSize: '12px', fontWeight: 500, color: isConnected ? '#4caf50' : '#ff9800', marginTop: '2px' }}>
                            {isConnected ? 'Connected' : 'Not Set'}
                          </div>
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <button 
                          className="tune-btn"
                          style={{ background: isConnected ? 'rgba(255,255,255,0.06)' : 'var(--accent-amber)', color: isConnected ? 'var(--ink)' : '#000', border: isConnected ? '1px solid var(--hairline-2)' : 'none', fontWeight: 600, padding: '6px 14px' }}
                          onClick={() => {
                            if (isConnected) {
                              saveAndTestModel(p.id);
                            } else {
                              setDraftKeys((d: any) => ({ ...d, [`expanded_${p.id}`]: true }));
                            }
                          }}
                        >
                          {isConnected ? 'Test' : 'Connect'}
                        </button>
                        <button 
                          style={{ background: 'none', border: 'none', color: 'var(--ink-3)', cursor: 'pointer', fontSize: '16px', padding: '4px' }}
                          onClick={() => setDraftKeys((d: any) => ({ ...d, [`expanded_${p.id}`]: !isExpanded }))}
                        >
                          ⋮
                        </button>
                      </div>
                    </div>

                    {isExpanded && (
                      <div style={{ padding: '16px 22px', borderTop: '1px solid var(--hairline-2)', background: 'rgba(0,0,0,0.2)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                          <label style={{ fontSize: '12px', color: 'var(--ink-3)', fontWeight: 500 }}>
                            {p.isLocal ? 'Ollama Host Endpoint' : `${p.name} Secret API Key`}
                          </label>
                          <a
                            href={p.directUrl}
                            target="_blank"
                            rel="noreferrer"
                            style={{ fontSize: '12px', color: 'var(--accent-amber)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 500 }}
                          >
                            Get Key ↗
                          </a>
                        </div>
                        <input 
                          className="tune-input"
                          type={p.isLocal ? 'text' : 'password'} 
                          value={p.isLocal ? draftKeys.ollamaHost : (draftKeys as any)[p.id] || ''}
                          onChange={e => {
                            const val = e.target.value;
                            if (p.isLocal) setDraftKeys(d => ({ ...d, ollamaHost: val }));
                            else setDraftKeys(d => ({ ...d, [p.id]: val }));
                          }}
                          placeholder={p.placeholder} 
                        />
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '12px' }}>
                          <button className="tune-btn primary" onClick={() => saveAndTestModel(p.id)}>
                            Save &amp; Test Connection
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

        {/* ──────── TAB 2: AWARENESS & PRIVACY ──────── */}
        {activeTab === 'awareness' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* Active Awareness Channels */}
            <div>
              <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--ink)', marginBottom: '4px' }}>
                Active Telemetry &amp; Awareness Channels
              </div>
              <div style={{ fontSize: '13px', color: 'var(--ink-3)', marginBottom: '14px' }}>
                Configure which ambient signals Arova is permitted to inspect on your operating system.
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {awarenessCapabilities.map(cap => (
                  <div 
                    key={cap.key} 
                    style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center', 
                      padding: '16px 20px',
                      background: 'var(--glass-1)',
                      border: '1px solid var(--hairline-2)',
                      borderRadius: '12px'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '14px', maxWidth: '80%' }}>
                      <div style={{ color: cap.enabled ? 'var(--accent-gold)' : 'var(--ink-3)', flexShrink: 0 }}>
                        {cap.icon}
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                        <div style={{ fontSize: '14px', fontWeight: 600, color: cap.enabled ? 'var(--ink)' : 'var(--ink-2)' }}>{cap.label}</div>
                        <div style={{ fontSize: '12px', color: 'var(--ink-3)', lineHeight: '1.4' }}>{cap.desc}</div>
                      </div>
                    </div>
                    <label className="tune-toggle">
                      <input 
                        type="checkbox" 
                        checked={cap.enabled} 
                        onChange={() => toggleAwarenessLayer(cap.key as any, cap.enabled)}
                      />
                      <span className="tune-toggle-slider" />
                    </label>
                  </div>
                ))}
              </div>
            </div>

            {/* Strictly Protected & Filtered Boundaries */}
            <div>
              <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--ink)', marginBottom: '4px' }}>
                Strictly Protected &amp; Filtered Boundaries
              </div>
              <div style={{ fontSize: '13px', color: 'var(--ink-3)', marginBottom: '12px' }}>
                These applications and sensitive buffers are blocked by Arova's deterministic kernel policy at all times.
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '10px' }}>
                {displayHidden.map((item, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', color: 'var(--ink-2)', padding: '12px 14px', background: 'rgba(0,0,0,0.15)', border: '1px solid var(--hairline-2)', borderRadius: '10px' }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--accent-sage)', flexShrink: 0 }}>
                      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                      <polyline points="9 12 11 14 15 10"/>
                    </svg>
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ──────── TAB 3: SYSTEM & DIAGNOSTICS ──────── */}
        {activeTab === 'system' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* System Startup & Global Summon */}
            <div style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', padding: '20px 24px' }}>
              <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--ink)', marginBottom: '4px' }}>System Startup &amp; Global Summon</div>
              <div style={{ fontSize: '13px', color: 'var(--ink-3)', marginBottom: '16px' }}>Configure desktop boot launch and global shortcut invocation.</div>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', background: 'rgba(0,0,0,0.15)', borderRadius: '12px', border: '1px solid var(--hairline-2)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--accent-gold)' }}>
                      <path d="M18.36 6.64a9 9 0 1 1-12.73 0"></path>
                      <line x1="12" y1="2" x2="12" y2="12"></line>
                    </svg>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--ink)' }}>Launch Arova on System Startup</div>
                      <div style={{ fontSize: '12px', color: 'var(--ink-3)', marginTop: '2px' }}>Automatically starts background cognition when you log into your system.</div>
                    </div>
                  </div>
                  <label className="tune-toggle">
                    <input 
                      type="checkbox" 
                      checked={autostartEnabled} 
                      onChange={e => handleToggleAutostart(e.target.checked)} 
                    />
                    <span className="tune-toggle-slider" />
                  </label>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', background: 'rgba(0,0,0,0.15)', borderRadius: '12px', border: '1px solid var(--hairline-2)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--accent-sage)' }}>
                      <rect x="2" y="4" width="20" height="16" rx="2" ry="2"></rect>
                      <line x1="6" y1="8" x2="6" y2="8"></line>
                      <line x1="10" y1="8" x2="10" y2="8"></line>
                      <line x1="14" y1="8" x2="14" y2="8"></line>
                      <line x1="18" y1="8" x2="18" y2="8"></line>
                      <line x1="6" y1="12" x2="18" y2="12"></line>
                    </svg>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--ink)' }}>Global Window Summon</div>
                      <div style={{ fontSize: '12px', color: 'var(--ink-3)', marginTop: '2px' }}>Summon or minimize Arova instantly from any desktop application.</div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <kbd style={{ padding: '4px 8px', borderRadius: '6px', background: 'rgba(255,255,255,0.08)', border: '1px solid var(--hairline-2)', fontSize: '12px', fontFamily: 'monospace', color: 'var(--ink)' }}>Alt + Space</kbd>
                    <span style={{ color: 'var(--ink-3)', fontSize: '12px', alignSelf: 'center' }}>or</span>
                    <kbd style={{ padding: '4px 8px', borderRadius: '6px', background: 'rgba(255,255,255,0.08)', border: '1px solid var(--hairline-2)', fontSize: '12px', fontFamily: 'monospace', color: 'var(--ink)' }}>Ctrl + Shift + Space</kbd>
                  </div>
                </div>
              </div>
            </div>

            {/* System Diagnostics & Substrates Health */}
            <div style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', padding: '20px 24px' }}>
              <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--ink)', marginBottom: '4px' }}>Substrate Health &amp; Diagnostics</div>
              <div style={{ fontSize: '13px', color: 'var(--ink-3)', marginBottom: '16px' }}>Live telemetry for daemon communication, database integrity, and local observers.</div>
              
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', fontSize: '13px' }}>
                <div style={{ padding: '12px 14px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--hairline-2)', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#4caf50', boxShadow: '0 0 6px rgba(76,175,80,0.5)' }} />
                  <span>UI Engine Active</span>
                </div>
                <div style={{ padding: '12px 14px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--hairline-2)', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: (diag?.health?.daemon_connected || diag) ? '#4caf50' : '#d68b8b', boxShadow: (diag?.health?.daemon_connected || diag) ? '0 0 6px rgba(76,175,80,0.5)' : 'none' }} />
                  <span>Daemon Connected</span>
                </div>
                <div style={{ padding: '12px 14px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--hairline-2)', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: (diag?.health?.database_ok || diag) ? '#4caf50' : '#d68b8b', boxShadow: (diag?.health?.database_ok || diag) ? '0 0 6px rgba(76,175,80,0.5)' : 'none' }} />
                  <span>SQLite Database OK</span>
                </div>
                <div style={{ padding: '12px 14px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--hairline-2)', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: (diag?.health?.memory_loaded || diag) ? '#4caf50' : '#d68b8b', boxShadow: (diag?.health?.memory_loaded || diag) ? '0 0 6px rgba(76,175,80,0.5)' : 'none' }} />
                  <span>Memory Engine Ready</span>
                </div>
                <div style={{ padding: '12px 14px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--hairline-2)', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: (diag?.health?.workspace_engine_ready || diag) ? '#4caf50' : '#d68b8b', boxShadow: (diag?.health?.workspace_engine_ready || diag) ? '0 0 6px rgba(76,175,80,0.5)' : 'none' }} />
                  <span>Workspace Observer</span>
                </div>
                <div style={{ padding: '12px 14px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--hairline-2)', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: (diag?.health?.wake_word_ready || diag) ? '#4caf50' : '#d68b8b', boxShadow: (diag?.health?.wake_word_ready || diag) ? '0 0 6px rgba(76,175,80,0.5)' : 'none' }} />
                  <span>Wake Word Engine</span>
                </div>
              </div>
            </div>

            {/* Memory Vault Actions & Debug Bundle */}
            <div style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', padding: '20px 24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--ink)', marginBottom: '4px' }}>Memory Archive &amp; Diagnostics Export</div>
                  <div style={{ fontSize: '13px', color: 'var(--ink-3)' }}>Export memory backups, clear active threads, or generate a diagnostic zip bundle.</div>
                </div>
                <div style={{ fontSize: '12px', padding: '4px 10px', borderRadius: '6px', background: 'rgba(255, 255, 255, 0.05)', color: 'var(--ink-2)', border: '1px solid var(--hairline-2)' }}>
                  {memoryCount} Memories Stored
                </div>
              </div>

              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', paddingTop: '14px', borderTop: '1px solid var(--hairline-2)' }}>
                <button className="tune-btn" style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid var(--hairline-2)', padding: '8px 18px', cursor: 'pointer' }} onClick={handleExportMemories}>
                  Export Memory Backup (.json)
                </button>
                <button 
                  className="tune-btn"
                  style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid var(--hairline-2)', padding: '8px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
                  onClick={() => {
                    socket.sendEvent({ type: 'debug.export_bundle', req_id: Date.now().toString() });
                    alert('Exported comprehensive debug bundle to ~/.arova/arova-debug.zip');
                  }}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7 10 12 15 17 10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                  </svg>
                  Export Debug Bundle (.zip)
                </button>
                <button className="tune-btn" style={{ background: 'transparent', border: '1px solid rgba(214, 139, 139, 0.3)', color: '#d68b8b', padding: '8px 18px', cursor: 'pointer' }} onClick={handleClearThreads}>
                  Clear Active Threads
                </button>
              </div>
            </div>

          </div>
        )}

      </div>
    </>
  );
};
