import React, { useState, useEffect } from 'react';
// import { AdvancedRouting } from './AdvancedRouting';
import { socket } from '../../runtime/socket';
import { useSurfaceState } from '../../state';

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
    [data-theme="nocturne"] .tune-btn.primary {
      background: linear-gradient(140deg, rgba(95, 82, 65, 0.95), rgba(75, 64, 50, 0.9));
      color: var(--accent-amber);
      box-shadow: inset 0 0 0 1px rgba(212, 188, 138, 0.28), inset 0 1px 0 rgba(255, 235, 200, 0.1);
    }
    .tune-select {
      appearance: none;
      background: var(--glass-2);
      border: 1px solid var(--glass-edge);
      color: var(--ink);
      padding: 14px 18px;
      padding-right: 42px;
      border-radius: 10px;
      font-size: 15px;
      font-family: inherit;
      cursor: pointer;
      outline: none;
      background-image: url("data:image/svg+xml;utf8,<svg viewBox='0 0 24 24' fill='none' stroke='%238a8478' stroke-width='2' stroke-linecap='round' xmlns='http://www.w3.org/2000/svg'><polyline points='6 9 12 15 18 9'/></svg>");
      background-repeat: no-repeat;
      background-position: right 16px center;
      background-size: 16px;
    }
    .tune-toggle {
      display: flex;
      align-items: center;
      gap: 12px;
      cursor: pointer;
    }
    .tune-toggle input {
      appearance: none;
      width: 40px;
      height: 22px;
      background: var(--glass-1);
      border: 1px solid var(--hairline-2);
      border-radius: 999px;
      position: relative;
      transition: 0.3s;
      cursor: pointer;
    }
    .tune-toggle input:checked {
      background: var(--accent-amber);
      border-color: var(--accent-amber);
    }
    .tune-toggle input::after {
      content: '';
      position: absolute;
      top: 2px;
      left: 2px;
      width: 16px;
      height: 16px;
      background: #fff;
      border-radius: 50%;
      transition: 0.3s;
      box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }
    .tune-toggle input:checked::after {
      transform: translateX(18px);
    }
    .tune-toggle span {
      font-size: 15px;
      color: var(--ink-2);
      line-height: 1.4;
    }
    .tune-group {
      margin-top: 24px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }
    .tune-label-row {
      display: flex;
      justify-content: space-between;
      margin-bottom: 12px;
      align-items: center;
    }
    .status-text {
      font-size: 13px;
      margin-top: 10px;
    }
    .status-ok { color: var(--accent-sage); }
    .status-err { color: #d68b8b; }
  `}</style>
);

export const SettingsLayout: React.FC = () => {
  const { closeSurface, openSurface } = useSurfaceState();
  const [config, setConfig] = useState({
    presence_style: 'hybrid',
    privacy: { workspace_awareness: true, memory_enabled: true, crash_recovery: true, browser_capture: true },
    runtime: { continuity_decay: 'standard', snapshot_retention: '30d' },
    preferred_provider: 'gemini',
    allow_fallback: true
  });
  
  const [autostartEnabled, setAutostartEnabled] = useState(true);

  const [providers, setProviders] = useState({
    groq: { api_keys: [''] },
    openai: { api_keys: [''] },
    ollama: { host: 'http://localhost:11434' }
  });

  // Local draft state — user edits here, saves explicitly
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

  const handleTogglePrivacy = (key: string, val: boolean) => {
    const updated = {
      ...config,
      privacy: {
        ...config.privacy,
        [key]: val
      }
    };
    setConfig(updated);
    socket.sendEvent({
      type: 'config.update_request',
      config: updated
    });
    setSaveStatus('Privacy settings updated.');
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
    const pollInterval = setInterval(() => {
      socket.sendEvent({ type: 'diagnostics.poll' });
    }, 2000);

    const handleEvent = (event: any) => {
      const ev = event.detail; // FIX #2: event.detail IS the event object directly
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
    socket.sendEvent({ type: 'config.get_request' });
    socket.sendEvent({ type: 'config.get_autostart' });
    socket.sendEvent({ type: 'diagnostics.poll' });
    return () => {
      clearInterval(pollInterval);
      window.removeEventListener('arova-event', handleEvent);
    };
  }, []);

  const saveConfig = (newConfig: any) => {
    setConfig(newConfig);
    socket.sendEvent({ type: 'config.update_request', config: newConfig });
  };

  // FIX #4: Save explicitly on button press, not on every keystroke
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
    setSaveStatus('Saving...');
    setTimeout(() => {
      setSaveStatus(null);
      setTestResult(null);
      socket.sendEvent({
        type: 'provider.test',
        provider: providerId,
        api_key: key,
        host: draftKeys.ollamaHost,
        req_id: providerId
      });
    }, 600);
  };

  const getModelStatus = (pId: string) => {
    if (pId === 'ollama') return providers.ollama?.host ? 'connected' : 'offline';
    const key = (providers as any)[pId]?.api_keys?.[0];
    return key ? 'connected' : 'missing_key';
  };

  const isDaemonConnected = diag?.health?.daemon_connected ?? true;
  const isDatabaseOk = diag?.health?.database_ok ?? true;
  const isWorkspaceReady = diag?.health?.workspace_engine_ready ?? true;
  const memoryCount = diag?.cognition?.memory_nodes ?? 0;

  return (
    <>
      <SettingsStyles />
      <div className="surface-head">
        <div>
          <div className="h">Configuration</div>
          <span className="sub">Presence · Memory · Providers</span>
        </div>
        <button className="surface-close" onClick={() => closeSurface()} aria-label="Close">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <path d="M6 6l12 12M18 6 6 18"/>
          </svg>
        </button>
      </div>

      <div className="tuning" style={{ paddingBottom: '40px' }}>
        {saveStatus && (
          <div style={{ padding: '10px 16px', background: 'rgba(76, 175, 80, 0.15)', border: '1px solid rgba(76, 175, 80, 0.3)', borderRadius: '10px', fontSize: '13px', color: '#4caf50', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>✓</span> {saveStatus}
          </div>
        )}

        {/* Real System Resource & Telemetry Status Card */}
        <div className="tune" style={{ border: '1px solid var(--hairline-2)', background: 'var(--glass-1)', borderRadius: '14px', padding: '20px 24px', marginBottom: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="lbl" style={{ color: 'var(--ink)', fontSize: '16px', fontWeight: 600 }}>System Resource &amp; Inference Status</div>
            <div style={{ fontSize: '12px', padding: '4px 10px', borderRadius: '6px', background: isDaemonConnected ? 'rgba(76, 175, 80, 0.15)' : 'rgba(255, 152, 0, 0.15)', color: isDaemonConnected ? '#4caf50' : '#ff9800', fontWeight: 600 }}>
              {isDaemonConnected ? 'Daemon Online' : 'Connecting...'}
            </div>
          </div>
          <div className="desc" style={{ marginTop: '4px', fontSize: '13px', color: 'var(--ink-3)' }}>Arova's ambient intelligence runs locally. Cloud inference is only invoked for deep cognition tasks.</div>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', marginTop: '16px', marginBottom: '18px' }}>
            <div style={{ padding: '12px 14px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--hairline-2)', borderRadius: '10px' }}>
              <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase' }}>Memories Persisted</div>
              <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--ink)', marginTop: '2px' }}>{memoryCount}</div>
            </div>
            <div style={{ padding: '12px 14px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--hairline-2)', borderRadius: '10px' }}>
              <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase' }}>Active Threads</div>
              <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--ink)', marginTop: '2px' }}>{diag?.cognition?.active_threads || 1}</div>
            </div>
            <div style={{ padding: '12px 14px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--hairline-2)', borderRadius: '10px' }}>
              <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase' }}>Routing Policy</div>
              <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--ink)', marginTop: '2px', textTransform: 'capitalize' }}>{config.presence_style || 'Hybrid'}</div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', borderTop: '1px solid var(--hairline-2)', paddingTop: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--ink)' }}>
              <span style={{ color: isDaemonConnected ? '#4caf50' : '#ff9800' }}>{isDaemonConnected ? '✓' : '•'}</span> Presence Active
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--ink)' }}>
              <span style={{ color: isDatabaseOk ? '#4caf50' : '#ff9800' }}>{isDatabaseOk ? '✓' : '•'}</span> Memory Storage Active
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--ink)' }}>
              <span style={{ color: isWorkspaceReady ? '#4caf50' : '#ff9800' }}>{isWorkspaceReady ? '✓' : '•'}</span> Environment Active
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--ink)' }}>
              <span style={{ color: isDaemonConnected ? '#4caf50' : '#ff9800' }}>{isDaemonConnected ? '✓' : '•'}</span> Cognitive Threads Active
            </div>
          </div>
        </div>
        
        {/* Presence Settings */}
        <div style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', padding: '20px 24px', marginBottom: '16px' }}>
          <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--ink)', marginBottom: '4px' }}>Presence &amp; Cognition</div>
          <div style={{ fontSize: '13px', color: 'var(--ink-3)', marginBottom: '16px' }}>How Arova interacts and maintains cognitive context across your active workspaces.</div>
          <select 
            className="tune-select"
            style={{ width: '100%', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--hairline-2)', borderRadius: '10px', padding: '14px 18px' }}
            value={config.presence_style} 
            onChange={(e) => saveConfig({...config, presence_style: e.target.value})}
          >
            <option value="instant">Instant Presence (Cloud Accelerated)</option>
            <option value="hybrid">Hybrid Presence (Cloud + Local Edge)</option>
            <option value="local">Local Presence (Offline Only)</option>
          </select>
        </div>

        {/* Workspace Awareness */}
        <div style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', padding: '20px 24px', marginBottom: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--ink)', marginBottom: '4px' }}>Workspace Awareness</div>
            <div style={{ fontSize: '13px', color: 'var(--ink-3)' }}>Allow Arova to infer context from your active applications. Runs purely on your local machine.</div>
          </div>
          <label className="tune-toggle">
            <input 
              type="checkbox" 
              checked={config.privacy.workspace_awareness} 
              onChange={(e) => saveConfig({...config, privacy: {...config.privacy, workspace_awareness: e.target.checked}})}
            />
          </label>
        </div>

        {/* Memory Management */}
        <div style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', padding: '20px 24px', marginBottom: '28px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--ink)', marginBottom: '4px' }}>Memory &amp; Persistence</div>
              <div style={{ fontSize: '13px', color: 'var(--ink-3)' }}>Manage your long-term episodic persistence and active cognitive threads.</div>
            </div>
            <label className="tune-toggle">
              <input 
                type="checkbox" 
                checked={config.privacy.memory_enabled} 
                onChange={(e) => saveConfig({...config, privacy: {...config.privacy, memory_enabled: e.target.checked}})}
              />
            </label>
          </div>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', paddingTop: '12px', borderTop: '1px solid var(--hairline-2)' }}>
            <button className="tune-btn primary" style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid var(--hairline-2)', padding: '8px 18px' }} onClick={() => openSurface('memory')}>View Memories</button>
            <button className="tune-btn" style={{ background: 'transparent', border: '1px solid var(--hairline-2)', padding: '8px 18px' }} onClick={handleExportMemories}>Export Memories</button>
            <button className="tune-btn" style={{ background: 'transparent', border: '1px solid rgba(214, 139, 139, 0.3)', color: '#d68b8b', padding: '8px 18px' }} onClick={handleClearThreads}>Clear Continuity Threads</button>
          </div>
        </div>

        {/* AI Providers & Connectivity Section (Sleek High-IQ PM Design) */}
        <div className="tune" style={{ background: 'transparent', border: 'none', padding: 0 }}>
          {/* Header Row */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <div>
              <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--ink)', letterSpacing: '-0.02em' }}>AI Providers</div>
              <div style={{ fontSize: '14px', color: 'var(--ink-3)', marginTop: '4px' }}>Configure your AI connections and set your preferred model</div>
            </div>
            <button 
              className="tune-btn"
              style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid var(--hairline-2)', padding: '10px 18px', borderRadius: '10px', fontSize: '13px', fontWeight: 500 }}
              onClick={() => {
                ['gemini', 'openai', 'anthropic', 'groq', 'ollama'].forEach(id => saveAndTestModel(id));
              }}
            >
              Test All Connections
            </button>
          </div>

          {/* Preferred AI Card */}
          <div style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', padding: '20px 24px', marginBottom: '16px' }}>
            <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--ink)', marginBottom: '4px' }}>Preferred AI</div>
            <div style={{ fontSize: '13px', color: 'var(--ink-3)', marginBottom: '16px' }}>Arova will use this provider as the default for all AI interactions</div>
            <select 
              className="tune-select"
              style={{ width: '100%', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--hairline-2)', borderRadius: '10px', padding: '14px 18px' }}
              value={config.preferred_provider || 'gemini'} 
              onChange={(e) => {
                const val = e.target.value;
                saveConfig({ ...config, preferred_provider: val });
              }}
            >
              <option value="gemini">Google AI (Gemini 2.5 Pro)</option>
              <option value="openai">OpenAI (GPT-5)</option>
              <option value="anthropic">Anthropic (Claude Sonnet 4)</option>
              <option value="groq">Groq (Llama 3.3 Fast Cloud)</option>
              <option value="ollama">Ollama (Local / Offline)</option>
            </select>
          </div>

          {/* Allow Fallback Card */}
          <div style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', padding: '20px 24px', marginBottom: '28px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
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
            </label>
          </div>

          {/* AI Providers Header & Counter */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', padding: '0 4px' }}>
            <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--ink)' }}>AI Providers</div>
            <div style={{ fontSize: '13px', display: 'flex', gap: '12px' }}>
              <span style={{ color: '#4caf50', fontWeight: 500 }}>
                {[ 'gemini', 'openai', 'groq', 'anthropic', 'ollama' ].filter(id => getModelStatus(id) === 'connected').length} Connected
              </span>
              <span style={{ color: 'var(--ink-3)' }}>|</span>
              <span style={{ color: '#ff9800', fontWeight: 500 }}>
                {[ 'gemini', 'openai', 'groq', 'anthropic', 'ollama' ].filter(id => getModelStatus(id) !== 'connected').length} Not Connected
              </span>
            </div>
          </div>

          {/* AI Providers Cards List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '32px' }}>
            {[
              { id: 'gemini', name: 'Google AI', icon: 'google', placeholder: 'AIzaSy...' },
              { id: 'openai', name: 'OpenAI', icon: 'openai', placeholder: 'sk-...' },
              { id: 'anthropic', name: 'Anthropic', icon: 'anthropic', placeholder: 'sk-ant-...' },
              { id: 'groq', name: 'Groq', icon: 'groq', placeholder: 'gsk_...' },
              { id: 'ollama', name: 'Ollama (Local)', icon: 'ollama', isLocal: true, placeholder: 'http://localhost:11434' }
            ].map(p => {
              const status = getModelStatus(p.id);
              const isConnected = status === 'connected';
              const isExpanded = (draftKeys as any)[`expanded_${p.id}`];

              return (
                <div key={p.id} style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', overflow: 'hidden' }}>
                  {/* Card Row Header */}
                  <div style={{ padding: '20px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
                    {/* Left: Icon + Name + Status Pill */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', minWidth: '220px' }}>
                      <div style={{ width: '44px', height: '44px', borderRadius: '12px', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--hairline-2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {p.icon === 'google' && (
                          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
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
                          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" color="#ffffff">
                            <path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0813 4.7792-2.7582a.794.794 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4954 4.4953z"/>
                          </svg>
                        )}
                        {p.icon === 'anthropic' && (
                          <span style={{ fontWeight: 800, fontSize: '18px', color: '#f5dcb4', letterSpacing: '-0.05em' }}>A\</span>
                        )}
                        {p.icon === 'groq' && (
                          <span style={{ fontWeight: 900, fontSize: '20px', color: '#f4511e' }}>G</span>
                        )}
                        {p.icon === 'ollama' && (
                          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="1.8">
                            <circle cx="12" cy="12" r="8"/>
                            <circle cx="9" cy="10" r="1" fill="#fff"/>
                            <circle cx="15" cy="10" r="1" fill="#fff"/>
                            <path d="M10 14q2 2 4 0"/>
                          </svg>
                        )}
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--ink)' }}>{p.name}</div>
                        <div style={{ fontSize: '12px', fontWeight: 500, color: isConnected ? '#4caf50' : '#ff9800', marginTop: '2px' }}>
                          {isConnected ? 'Connected' : 'Not Connected'}
                        </div>
                      </div>
                    </div>

                    {/* Metadata Columns */}
                    <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px', fontSize: '13px' }}>
                      <div>
                        <div style={{ color: 'var(--ink-3)', fontSize: '12px', marginBottom: '2px' }}>
                          {isConnected ? 'Last Checked' : p.isLocal ? 'URL' : 'API Key'}
                        </div>
                        <div style={{ color: isConnected ? 'var(--ink)' : '#ff9800', fontWeight: 500 }}>
                          {isConnected ? (testResult?.req_id === p.id ? 'Just now' : 'Verified') : p.isLocal ? 'http://localhost:11434' : 'Not Set'}
                        </div>
                      </div>

                      <div>
                        <div style={{ color: 'var(--ink-3)', fontSize: '12px', marginBottom: '2px' }}>Latency</div>
                        <div style={{ color: isConnected ? 'var(--ink)' : 'var(--ink-3)', fontWeight: 500 }}>
                          {testResult?.req_id === p.id && testResult?.success ? `${testResult.latency_ms}ms` : '-'}
                        </div>
                      </div>

                      <div>
                        <div style={{ color: 'var(--ink-3)', fontSize: '12px', marginBottom: '2px' }}>Status</div>
                        <div style={{ color: isConnected ? '#4caf50' : '#ff9800', fontWeight: 500 }}>
                          {isConnected ? 'Healthy' : 'Not Set'}
                        </div>
                      </div>
                    </div>

                    {/* Right Actions */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <button 
                        className="tune-btn"
                        style={{ background: isConnected ? 'rgba(255,255,255,0.06)' : 'var(--accent-amber)', color: isConnected ? 'var(--ink)' : '#000', border: isConnected ? '1px solid var(--hairline-2)' : 'none', fontWeight: 600, padding: '8px 16px' }}
                        onClick={() => {
                          if (isConnected) {
                            saveAndTestModel(p.id);
                          } else {
                            setDraftKeys((d: any) => ({ ...d, [`expanded_${p.id}`]: true }));
                          }
                        }}
                      >
                        {isConnected ? 'Test Connection' : 'Connect'}
                      </button>
                      <button 
                        style={{ background: 'none', border: 'none', color: 'var(--ink-3)', cursor: 'pointer', fontSize: '18px', padding: '4px' }}
                        onClick={() => setDraftKeys((d: any) => ({ ...d, [`expanded_${p.id}`]: !isExpanded }))}
                      >
                        ⋮
                      </button>
                    </div>
                  </div>

                  {/* Expandable Key/URL Config Input */}
                  {isExpanded && (
                    <div style={{ padding: '16px 24px', borderTop: '1px solid var(--hairline-2)', background: 'rgba(0,0,0,0.2)' }}>
                      <div style={{ marginBottom: '12px' }}>
                        <label style={{ fontSize: '12px', color: 'var(--ink-3)', display: 'block', marginBottom: '6px', fontWeight: 500 }}>
                          {p.isLocal ? 'Ollama Host Endpoint' : `${p.name} Secret API Key`}
                        </label>
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
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
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

          {/* Footer Card — "How it works" */}
          <div style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', padding: '20px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--ink)', marginBottom: '4px' }}>How it works</div>
              <div style={{ fontSize: '13px', color: 'var(--ink-3)', maxWidth: '520px' }}>
                Arova selects the best available model from your connected providers automatically based on performance and reliability.
              </div>
              <button className="tune-btn" style={{ marginTop: '12px', fontSize: '12px' }}>Learn more</button>
            </div>
            <div style={{ textAlign: 'right', fontSize: '13px' }}>
              <div style={{ color: 'var(--ink-3)', marginBottom: '4px' }}>Need help?</div>
              <a href="#help" style={{ color: '#4caf50', textDecoration: 'none', fontWeight: 500 }}>View documentation or get support</a>
            </div>
          </div>
        </div>

        {/* System Diagnostics & Health Status Cards */}
        <div style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', padding: '20px 24px', marginBottom: '16px' }}>
          <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--ink)', marginBottom: '4px' }}>System Diagnostics &amp; Health</div>
          <div style={{ fontSize: '13px', color: 'var(--ink-3)', marginBottom: '16px' }}>Instant diagnostic status for local daemon and cognitive substrates.</div>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', fontFamily: 'monospace', fontSize: '13px' }}>
            <div style={{ padding: '12px 14px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--hairline-2)', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: '#4caf50', fontWeight: 'bold' }}>✓</span> UI Engine Active
            </div>
            <div style={{ padding: '12px 14px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--hairline-2)', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: diag?.health?.daemon_connected || diag ? '#4caf50' : '#d68b8b', fontWeight: 'bold' }}>
                {diag?.health?.daemon_connected || diag ? '✓' : '✗'}
              </span> Daemon Connected
            </div>
            <div style={{ padding: '12px 14px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--hairline-2)', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: diag?.health?.database_ok || diag ? '#4caf50' : '#d68b8b', fontWeight: 'bold' }}>
                {diag?.health?.database_ok || diag ? '✓' : '✗'}
              </span> SQLite Database OK
            </div>
            <div style={{ padding: '12px 14px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--hairline-2)', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: diag?.health?.memory_loaded || diag ? '#4caf50' : '#d68b8b', fontWeight: 'bold' }}>
                {diag?.health?.memory_loaded || diag ? '✓' : '✗'}
              </span> Memory Engine Ready
            </div>
            <div style={{ padding: '12px 14px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--hairline-2)', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: diag?.health?.workspace_engine_ready || diag ? '#4caf50' : '#d68b8b', fontWeight: 'bold' }}>
                {diag?.health?.workspace_engine_ready || diag ? '✓' : '✗'}
              </span> Workspace Observer
            </div>
            <div style={{ padding: '12px 14px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--hairline-2)', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: diag?.health?.wake_word_ready || diag ? '#4caf50' : '#d68b8b', fontWeight: 'bold' }}>
                {diag?.health?.wake_word_ready || diag ? '✓' : '✗'}
              </span> Wake Word Engine
            </div>
          </div>
        </div>

        {/* System Startup & Privacy Permissions */}
        <div style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', padding: '20px 24px', marginBottom: '16px' }}>
          <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--ink)', marginBottom: '4px' }}>System Startup &amp; Privacy Permissions</div>
          <div style={{ fontSize: '13px', color: 'var(--ink-3)', marginBottom: '18px' }}>Manage operating system startup behavior and ambient telemetry collection preferences.</div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <label className="tune-toggle" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', background: 'rgba(0,0,0,0.15)', borderRadius: '12px', border: '1px solid var(--hairline-2)' }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--ink)' }}>🚀 Launch Arova on System Startup</div>
                <div style={{ fontSize: '12px', color: 'var(--ink-3)', marginTop: '2px' }}>Automatically start the background cognition engine when you log in.</div>
              </div>
              <input 
                type="checkbox" 
                checked={autostartEnabled} 
                onChange={e => handleToggleAutostart(e.target.checked)} 
              />
            </label>

            <label className="tune-toggle" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', background: 'rgba(0,0,0,0.15)', borderRadius: '12px', border: '1px solid var(--hairline-2)' }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--ink)' }}>📁 Workspace &amp; IDE Tracking</div>
                <div style={{ fontSize: '12px', color: 'var(--ink-3)', marginTop: '2px' }}>Discovers active projects in VS Code, Cursor, and Terminal working directories.</div>
              </div>
              <input 
                type="checkbox" 
                checked={config.privacy.workspace_awareness !== false} 
                onChange={e => handleTogglePrivacy('workspace_awareness', e.target.checked)} 
              />
            </label>

            <label className="tune-toggle" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', background: 'rgba(0,0,0,0.15)', borderRadius: '12px', border: '1px solid var(--hairline-2)' }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--ink)' }}>🌐 Selective Research Browser Tab Capture</div>
                <div style={{ fontSize: '12px', color: 'var(--ink-3)', marginTop: '2px' }}>Captures relevant documentation while strictly blocking authentication, passwords, and banking.</div>
              </div>
              <input 
                type="checkbox" 
                checked={config.privacy.browser_capture !== false} 
                onChange={e => handleTogglePrivacy('browser_capture', e.target.checked)} 
              />
            </label>
          </div>
        </div>

        {/* About & Diagnostics Export */}
        <div style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', padding: '20px 24px' }}>
          <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--ink)', marginBottom: '4px' }}>About Arova &amp; Snapshot Export</div>
          <div style={{ fontSize: '13px', color: 'var(--ink-3)', marginBottom: '16px' }}>System build parameters and diagnostic bundle generator.</div>
          
          <div style={{ fontSize: '13px', color: 'var(--ink-2)', lineHeight: '1.8', marginBottom: '16px', background: 'rgba(0,0,0,0.2)', padding: '16px', borderRadius: '10px', fontFamily: 'monospace', border: '1px solid var(--hairline-2)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Product:</span> <strong style={{ color: 'var(--ink)' }}>Arova Cognitive Substrate</strong></div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Version:</span> <strong style={{ color: 'var(--ink)' }}>0.1.0-beta</strong></div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Edition:</span> <strong style={{ color: 'var(--ink)' }}>Design Partner Beta</strong></div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Daemon Engine:</span> <strong style={{ color: 'var(--ink)' }}>arovad standalone (PyInstaller)</strong></div>
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <button 
              className="tune-btn"
              style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid var(--hairline-2)', padding: '10px 20px', fontWeight: 600 }}
              onClick={() => {
                socket.sendEvent({ type: 'debug.export_bundle', req_id: Date.now().toString() });
                alert('Exported comprehensive debug bundle to ~/.arova/arova-debug.zip');
              }}
            >
              Export Debug Bundle (.zip)
            </button>
          </div>
        </div>

      </div>
    </>
  );
};
