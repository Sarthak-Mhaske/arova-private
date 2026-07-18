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
  const { closeSurface } = useSurfaceState();
  const [config, setConfig] = useState({
    presence_style: 'hybrid',
    privacy: { workspace_awareness: true, memory_enabled: true, crash_recovery: true },
    runtime: { continuity_decay: 'standard', snapshot_retention: '30d' }
  });
  
  const [providers, setProviders] = useState({
    groq: { api_keys: [''] },
    openai: { api_keys: [''] },
    ollama: { host: 'http://localhost:11434' }
  });

  // Local draft state — user edits here, saves explicitly
  const [draftKeys, setDraftKeys] = useState({ groq: '', openai: '', ollamaHost: 'http://localhost:11434' });

  const [testResult, setTestResult] = useState<{ req_id: string; success: boolean; latency_ms?: number; error?: string } | null>(null);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  useEffect(() => {
    // FIX #1: event name was 'runtime_event', eventRouter dispatches 'arova-event'
    const handleEvent = (event: any) => {
      const ev = event.detail; // FIX #2: event.detail IS the event object directly
      if (ev.type === 'config.sync') {
        if (ev.config) setConfig((prev: any) => ({ ...prev, ...ev.config }));
        if (ev.providers) {
          setProviders((prev: any) => ({ ...prev, ...ev.providers }));
          // Populate draft keys from saved config
          setDraftKeys(d => ({
            groq: ev.providers?.groq?.api_keys?.[0] || d.groq,
            openai: ev.providers?.openai?.api_keys?.[0] || d.openai,
            ollamaHost: ev.providers?.ollama?.host || d.ollamaHost,
          }));
        }
      } else if (ev.type === 'provider.test_result') {
        // FIX #3: backend sends { req_id, result: { success, latency_ms } } — flatten it
        const flat = { req_id: ev.req_id, ...ev.result };
        setTestResult(flat);
      }
    };
    window.addEventListener('arova-event', handleEvent);
    socket.sendEvent({ type: 'config.get_request' });
    return () => window.removeEventListener('arova-event', handleEvent);
  }, []);

  const saveConfig = (newConfig: any) => {
    setConfig(newConfig);
    socket.sendEvent({ type: 'config.update_request', config: newConfig });
  };

  // FIX #4: Save explicitly on button press, not on every keystroke
  const saveAndTestProvider = (providerId: string) => {
    let newProviders: any;
    if (providerId === 'groq') {
      newProviders = { ...providers, groq: { api_keys: [draftKeys.groq] } };
    } else if (providerId === 'openai') {
      newProviders = { ...providers, openai: { api_keys: [draftKeys.openai] } };
    } else {
      newProviders = { ...providers, ollama: { host: draftKeys.ollamaHost } };
    }
    setProviders(newProviders);
    // Save to disk first, then test
    socket.sendEvent({ type: 'config.update_request', providers: newProviders });
    setSaveStatus('Saving...');
    // Small delay to allow hot-reload to complete before testing
    setTimeout(() => {
      setSaveStatus(null);
      const key = providerId === 'groq' ? draftKeys.groq : providerId === 'openai' ? draftKeys.openai : '';
      const host = providerId === 'ollama' ? draftKeys.ollamaHost : '';
      setTestResult(null);
      socket.sendEvent({
        type: 'provider.test',
        provider: providerId,
        api_key: key,
        host: host,
        req_id: providerId
      });
    }, 600);
  };

  const isConfigured = (pId: string) => {
    if (pId === 'ollama') return !!providers.ollama.host;
    if (pId === 'groq') return !!providers.groq.api_keys[0];
    if (pId === 'openai') return !!providers.openai.api_keys[0];
    return false;
  };

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

        {/* Phase 7C: Trial Manager */}
        <div className="tune" style={{ border: '1px solid var(--accent-amber)', background: 'rgba(255, 170, 0, 0.05)' }}>
          <div className="lbl" style={{ color: 'var(--accent-amber)' }}>Cloud Inference Usage</div>
          <div className="desc">Arova's ambient intelligence runs locally. Cloud inference is only used for deep cognition.</div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '16px', marginBottom: '20px' }}>
            <div style={{ flex: 1, height: '6px', background: 'var(--glass-2)', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ width: '86%', height: '100%', background: 'var(--accent-amber)' }} />
            </div>
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--ink)' }}>43 / 50 <span style={{ color: 'var(--ink-3)', fontWeight: 400 }}>AI Responses Used</span></div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', color: 'var(--ink)' }}>
              <span style={{ color: '#4caf50' }}>✓</span> Presence Active
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', color: 'var(--ink)' }}>
              <span style={{ color: '#4caf50' }}>✓</span> Memory Active
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', color: 'var(--ink)' }}>
              <span style={{ color: '#4caf50' }}>✓</span> Environment Active
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', color: 'var(--ink)' }}>
              <span style={{ color: '#4caf50' }}>✓</span> Threads Active
            </div>
          </div>
        </div>
        
        {/* Presence Settings */}
        <div className="tune">
          <div className="lbl">Presence & Cognition</div>
          <div className="desc">How Arova interacts across your workspaces.</div>
          <select 
            className="tune-select"
            value={config.presence_style} 
            onChange={(e) => saveConfig({...config, presence_style: e.target.value})}
          >
            <option value="instant">Instant Presence (Cloud)</option>
            <option value="hybrid">Hybrid Presence (Cloud + Local)</option>
            <option value="local">Local Presence (Offline Only)</option>
          </select>
        </div>

        {/* Workspace Awareness */}
        <div className="tune">
          <div className="lbl">Workspace Awareness</div>
          <div className="desc">Allow Arova to infer context from your active applications. Runs purely locally.</div>
          <label className="tune-toggle">
            <input 
              type="checkbox" 
              checked={config.privacy.workspace_awareness} 
              onChange={(e) => saveConfig({...config, privacy: {...config.privacy, workspace_awareness: e.target.checked}})}
            />
            <span>Enable Screen & Context Awareness</span>
          </label>
        </div>

        {/* Memory Management */}
        <div className="tune">
          <div className="lbl">Memory Management</div>
          <div className="desc">Manage your long-term persistence and cognitive threads.</div>
          <label className="tune-toggle" style={{ marginBottom: '16px' }}>
            <input 
              type="checkbox" 
              checked={config.privacy.memory_enabled} 
              onChange={(e) => saveConfig({...config, privacy: {...config.privacy, memory_enabled: e.target.checked}})}
            />
            <span>Enable Background Memory Formation</span>
          </label>
          <div className="tune-controls">
            <button className="tune-btn primary">View Memories</button>
            <button className="tune-btn">Export Memories</button>
            <button className="tune-btn" style={{ color: '#d68b8b' }}>Clear Continuity Threads</button>
          </div>
        </div>

        {/* Providers */}
        <div className="tune">
          <div className="lbl">Providers</div>
          <div className="desc">Direct connection to intelligence sources. Usually managed automatically by your Presence Style.</div>
          
          <div className="tune-group">
            {/* Groq */}
            <div>
              <div className="tune-label-row">
                <span style={{ fontSize: '15px', fontWeight: 500 }}>Groq</span>
                <span className={`status-text ${isConfigured('groq') ? 'status-ok' : ''}`}>
                  {isConfigured('groq') ? 'Connected' : 'Not Configured'}
                </span>
              </div>
              <input 
                className="tune-input"
                type="password" 
                value={draftKeys.groq}
                onChange={e => setDraftKeys(d => ({ ...d, groq: e.target.value }))}
                placeholder="gsk_..." 
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '12px' }}>
                <button className="tune-btn primary" onClick={() => saveAndTestProvider('groq')}>Save &amp; Verify</button>
                {saveStatus && testResult?.req_id !== 'groq' && <span className="status-text" style={{ color: 'var(--ink-3)' }}>{saveStatus}</span>}
                {testResult?.req_id === 'groq' && (
                  <span className={`status-text ${testResult?.success ? 'status-ok' : 'status-err'}`}>
                    {testResult?.success ? `✓ Valid (${testResult.latency_ms}ms)` : `✗ ${testResult?.error}`}
                  </span>
                )}
              </div>
            </div>

            {/* OpenAI */}
            <div>
              <div className="tune-label-row">
                <span style={{ fontSize: '15px', fontWeight: 500 }}>OpenAI</span>
                <span className={`status-text ${isConfigured('openai') ? 'status-ok' : ''}`}>
                  {isConfigured('openai') ? 'Connected' : 'Not Configured'}
                </span>
              </div>
              <input 
                className="tune-input"
                type="password" 
                value={draftKeys.openai}
                onChange={e => setDraftKeys(d => ({ ...d, openai: e.target.value }))}
                placeholder="sk-..." 
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '12px' }}>
                <button className="tune-btn primary" onClick={() => saveAndTestProvider('openai')}>Save &amp; Verify</button>
                {testResult?.req_id === 'openai' && (
                  <span className={`status-text ${testResult?.success ? 'status-ok' : 'status-err'}`}>
                    {testResult?.success ? `✓ Valid (${testResult.latency_ms}ms)` : `✗ ${testResult?.error}`}
                  </span>
                )}
              </div>
            </div>

            {/* Ollama */}
            <div>
              <div className="tune-label-row">
                <span style={{ fontSize: '15px', fontWeight: 500 }}>Ollama (Local)</span>
                <span className={`status-text ${isConfigured('ollama') ? 'status-ok' : ''}`}>
                  {isConfigured('ollama') ? 'Running' : 'Offline'}
                </span>
              </div>
              <input 
                className="tune-input"
                type="text" 
                value={draftKeys.ollamaHost}
                onChange={e => setDraftKeys(d => ({ ...d, ollamaHost: e.target.value }))}
                placeholder="http://localhost:11434" 
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '12px' }}>
                <button className="tune-btn primary" onClick={() => saveAndTestProvider('ollama')}>Save &amp; Ping</button>
                {testResult?.req_id === 'ollama' && (
                  <span className={`status-text ${testResult?.success ? 'status-ok' : 'status-err'}`}>
                    {testResult?.success ? `✓ Connected (${testResult.latency_ms}ms)` : `✗ ${testResult?.error}`}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Runtime Diagnostics */}
        <div className="tune">
          <div className="lbl">Runtime Diagnostics</div>
          <div className="desc">System health and recovery parameters.</div>
          
          <label className="tune-toggle" style={{ marginBottom: '16px' }}>
            <input 
              type="checkbox" 
              checked={config.privacy.crash_recovery} 
              onChange={(e) => saveConfig({...config, privacy: {...config.privacy, crash_recovery: e.target.checked}})}
            />
            <span>Automatic Session Recovery</span>
          </label>

          <div style={{ fontSize: '14px', color: 'var(--ink-2)', lineHeight: '2.0', marginBottom: '24px', background: 'var(--glass-1)', padding: '16px 20px', borderRadius: '12px', border: '1px solid var(--hairline-2)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Inference Core</span>
              <strong style={{ color: isConfigured('groq') || isConfigured('openai') ? 'var(--accent-sage)' : isConfigured('ollama') ? 'var(--ink)' : '#d68b8b' }}>
                {isConfigured('groq') ? 'Cloud (Groq)' : isConfigured('openai') ? 'Cloud (OpenAI)' : isConfigured('ollama') ? 'Local (Ollama)' : 'Offline'}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Continuity Decay</span>
              <strong>Standard (30d)</strong>
            </div>
          </div>

          <button className="tune-btn">Export Raw Cognitive Snapshot</button>
        </div>

      </div>
    </>
  );
};
