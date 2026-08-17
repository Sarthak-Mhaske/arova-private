import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { socket } from '../../runtime/socket';
import { OrbShell } from '../orb/OrbShell';

interface OnboardingProps {
  onComplete: () => void;
}

export const OnboardingModal: React.FC<OnboardingProps> = ({ onComplete }) => {
  const [step, setStep] = useState<1 | 2 | 3 | 4 | 5>(1);

  // Form State
  const [termsAgreed, setTermsAgreed] = useState(false);
  const [permissions, setPermissions] = useState({
    workspace_tracking: true,
    browser_capture: true,
    voice_audio: true,
    desktop_automation: true
  });

  const [provider, setProvider] = useState<'groq' | 'openai' | 'gemini' | 'anthropic' | 'ollama'>('groq');
  const [apiKey, setApiKey] = useState('');
  const [ollamaHost, setOllamaHost] = useState('http://localhost:11434');
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [testError, setTestError] = useState<string | null>(null);

  const [theme, setTheme] = useState<'nocturne' | 'daylight'>('nocturne');
  const [autostart, setAutostart] = useState(true);

  useEffect(() => {
    const handleTestResult = (e: any) => {
      const ev = e.detail;
      if (ev && ev.type === 'provider.test_result') {
        if (ev.success) {
          setTestStatus('success');
          setTestError(null);
        } else {
          setTestStatus('error');
          setTestError(ev.error || 'Failed to connect with provider.');
        }
      }
    };
    window.addEventListener('arova-event', handleTestResult);
    return () => window.removeEventListener('arova-event', handleTestResult);
  }, []);

  const handleTestConnection = () => {
    if (!apiKey && provider !== 'ollama') {
      setTestStatus('error');
      setTestError('Please enter an API key.');
      return;
    }
    setTestStatus('testing');
    setTestError(null);
    socket.sendEvent({
      type: 'provider.test',
      provider,
      api_key: apiKey,
      host: ollamaHost,
      req_id: `onboarding_${provider}`
    });
  };

  const handleFinish = () => {
    // 1. Save provider config if provided
    if (apiKey || provider === 'ollama') {
      const providersPayload: any = {};
      if (provider === 'ollama') {
        providersPayload.ollama = { host: ollamaHost };
      } else {
        providersPayload[provider] = { api_keys: [apiKey] };
      }
      socket.sendEvent({
        type: 'config.update_request',
        config: {
          preferred_provider: provider,
          privacy: {
            workspace_awareness: permissions.workspace_tracking,
            browser_capture: permissions.browser_capture,
            memory_enabled: true
          }
        },
        providers: providersPayload
      });
    } else {
      socket.sendEvent({
        type: 'config.update_request',
        config: {
          privacy: {
            workspace_awareness: permissions.workspace_tracking,
            browser_capture: permissions.browser_capture,
            memory_enabled: true
          }
        }
      });
    }

    // 2. Set autostart preference
    socket.sendEvent({
      type: 'config.set_autostart',
      enabled: autostart
    });

    // 3. Mark onboarding complete in localStorage
    localStorage.setItem('arova_onboarding_completed', 'true');
    localStorage.setItem('arova_terms_agreed', 'true');
    localStorage.setItem('arova_autostart', autostart ? 'true' : 'false');

    onComplete();
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100000,
        background: 'radial-gradient(1200px 900px at 50% 40%, rgba(20, 16, 26, 0.95) 0%, rgba(8, 7, 12, 0.98) 100%)',
        backdropFilter: 'blur(40px) saturate(160%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#f4ece1',
        fontFamily: "'Inter', 'SF Pro Display', system-ui, sans-serif",
        userSelect: 'none',
        padding: '24px'
      }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 15 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
        style={{
          width: '680px',
          maxWidth: '96vw',
          maxHeight: '88vh',
          background: 'rgba(24, 20, 32, 0.85)',
          border: '1px solid rgba(232, 208, 164, 0.16)',
          borderRadius: '24px',
          boxShadow: '0 32px 100px rgba(0, 0, 0, 0.75), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}
      >
        {/* Top Progress Bar */}
        <div style={{ padding: '24px 32px 16px', borderBottom: '1px solid rgba(255, 255, 255, 0.06)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '28px', height: '28px', position: 'relative' }}>
              <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%) scale(0.12)' }}>
                <OrbShell />
              </div>
            </div>
            <span style={{ fontSize: '15px', fontWeight: 700, letterSpacing: '0.08em', color: '#e8d0a4', textTransform: 'uppercase' }}>
              Arova Setup
            </span>
          </div>

          <div style={{ display: 'flex', gap: '6px' }}>
            {[1, 2, 3, 4, 5].map(s => (
              <div
                key={s}
                style={{
                  width: '32px',
                  height: '4px',
                  borderRadius: '999px',
                  background: step >= s ? '#e8d0a4' : 'rgba(255, 255, 255, 0.12)',
                  transition: 'background 0.3s ease'
                }}
              />
            ))}
          </div>
        </div>

        {/* Content Body */}
        <div style={{ padding: '32px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <AnimatePresence mode="wait">
            {/* STEP 1: WELCOME */}
            {step === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                style={{ display: 'flex', flexDirection: 'column', gap: '18px', textAlign: 'center', alignItems: 'center' }}
              >
                <div style={{ width: '80px', height: '80px', margin: '8px 0', position: 'relative' }}>
                  <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%) scale(0.35)' }}>
                    <OrbShell />
                  </div>
                </div>

                <h2 style={{ fontSize: '26px', fontWeight: 700, margin: 0, color: '#fff' }}>
                  Welcome to Arova
                </h2>
                <p style={{ fontSize: '14px', lineHeight: '1.6', color: 'rgba(244, 236, 225, 0.75)', maxWidth: '520px', margin: 0 }}>
                  Arova acts as your mind-like ambient working memory. It observes your projects, terminal contexts, and research tabs locally so you never lose momentum or context when switching tasks.
                </p>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', width: '100%', marginTop: '12px', textAlign: 'left' }}>
                  <div style={{ padding: '16px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '14px' }}>
                    <div style={{ fontSize: '18px', marginBottom: '6px' }}>⚡</div>
                    <div style={{ fontWeight: 600, fontSize: '14px', color: '#fff' }}>Instant Session Resume</div>
                    <div style={{ fontSize: '12px', color: 'rgba(244, 236, 225, 0.6)', marginTop: '4px' }}>1-click restoration of all active editors, terminals, and research tabs.</div>
                  </div>

                  <div style={{ padding: '16px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '14px' }}>
                    <div style={{ fontSize: '18px', marginBottom: '6px' }}>🔒</div>
                    <div style={{ fontWeight: 600, fontSize: '14px', color: '#fff' }}>100% Local-First Memory</div>
                    <div style={{ fontSize: '12px', color: 'rgba(244, 236, 225, 0.6)', marginTop: '4px' }}>All working memory stays encrypted and stored locally on your device.</div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* STEP 2: PRIVACY POLICY & TERMS */}
            {step === 2 && (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
              >
                <div>
                  <h3 style={{ fontSize: '20px', fontWeight: 700, margin: 0, color: '#fff' }}>
                    Privacy Policy &amp; Terms of Service
                  </h3>
                  <p style={{ fontSize: '13px', color: 'rgba(244, 236, 225, 0.7)', marginTop: '4px', margin: 0 }}>
                    Please review our transparent privacy commitments before enabling monitoring.
                  </p>
                </div>

                <div
                  style={{
                    background: 'rgba(0, 0, 0, 0.35)',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    borderRadius: '12px',
                    padding: '16px',
                    fontSize: '13px',
                    lineHeight: '1.6',
                    color: 'rgba(244, 236, 225, 0.85)',
                    maxHeight: '220px',
                    overflowY: 'auto'
                  }}
                >
                  <div style={{ fontWeight: 600, color: '#e8d0a4', marginBottom: '6px' }}>1. Local-First Processing Guarantee</div>
                  <div>Arova is architected from the ground up as a private, local-first system. All raw telemetry, active window handles, terminal directories, and SQLite knowledge databases remain strictly on your local machine.</div>
                  
                  <div style={{ fontWeight: 600, color: '#e8d0a4', marginTop: '12px', marginBottom: '6px' }}>2. Absolute Exclusion of Sensitive Data</div>
                  <div>Arova automatically blocks and discards all authentication logins (OAuth, Okta, Microsoft, Google SSO), online banking, password managers, personal messaging (WhatsApp, Telegram), and health portals.</div>

                  <div style={{ fontWeight: 600, color: '#e8d0a4', marginTop: '12px', marginBottom: '6px' }}>3. Zero Third-Party Selling</div>
                  <div>We do not sell, rent, or monetize your working habits, telemetry, or code. AI inference queries are sent strictly to your chosen LLM provider (Groq, OpenAI, or local Ollama) using your own API keys.</div>
                </div>

                <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer', marginTop: '6px' }}>
                  <input
                    type="checkbox"
                    checked={termsAgreed}
                    onChange={e => setTermsAgreed(e.target.checked)}
                    style={{ width: '18px', height: '18px', accentColor: '#e8d0a4', cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: '13px', color: '#fff' }}>
                    I have read and agree to the <strong>Terms of Service</strong> and <strong>Privacy Policy</strong>.
                  </span>
                </label>
              </motion.div>
            )}

            {/* STEP 3: PERMISSIONS & MONITORING CONSENT */}
            {step === 3 && (
              <motion.div
                key="step3"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
              >
                <div>
                  <h3 style={{ fontSize: '20px', fontWeight: 700, margin: 0, color: '#fff' }}>
                    Configure Monitoring Permissions
                  </h3>
                  <p style={{ fontSize: '13px', color: 'rgba(244, 236, 225, 0.7)', marginTop: '4px', margin: 0 }}>
                    Choose which ambient signals Arova is permitted to observe to construct your working memory.
                  </p>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', cursor: 'pointer' }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '14px', color: '#fff' }}>📁 Workspace &amp; IDE Tracking</div>
                      <div style={{ fontSize: '12px', color: 'rgba(244, 236, 225, 0.6)', marginTop: '2px' }}>Observes active repositories in VS Code, Cursor, and Terminal working directories.</div>
                    </div>
                    <input
                      type="checkbox"
                      checked={permissions.workspace_tracking}
                      onChange={e => setPermissions(p => ({ ...p, workspace_tracking: e.target.checked }))}
                      style={{ width: '18px', height: '18px', accentColor: '#e8d0a4' }}
                    />
                  </label>

                  <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', cursor: 'pointer' }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '14px', color: '#fff' }}>🌐 Research Browser Capture</div>
                      <div style={{ fontSize: '12px', color: 'rgba(244, 236, 225, 0.6)', marginTop: '2px' }}>Captures relevant documentation and articles while filtering out noise and private data.</div>
                    </div>
                    <input
                      type="checkbox"
                      checked={permissions.browser_capture}
                      onChange={e => setPermissions(p => ({ ...p, browser_capture: e.target.checked }))}
                      style={{ width: '18px', height: '18px', accentColor: '#e8d0a4' }}
                    />
                  </label>

                  <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', cursor: 'pointer' }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '14px', color: '#fff' }}>🎙️ Voice Interaction &amp; Media Ducking</div>
                      <div style={{ fontSize: '12px', color: 'rgba(244, 236, 225, 0.6)', marginTop: '2px' }}>Enables 'Hey Arova' wake word and fluidly lowers background music volume when speaking.</div>
                    </div>
                    <input
                      type="checkbox"
                      checked={permissions.voice_audio}
                      onChange={e => setPermissions(p => ({ ...p, voice_audio: e.target.checked }))}
                      style={{ width: '18px', height: '18px', accentColor: '#e8d0a4' }}
                    />
                  </label>

                  <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', cursor: 'pointer' }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '14px', color: '#fff' }}>⚡ Desktop Task Automation</div>
                      <div style={{ fontSize: '12px', color: 'rgba(244, 236, 225, 0.6)', marginTop: '2px' }}>Allows Arova to launch applications, switch windows, and control music on voice command.</div>
                    </div>
                    <input
                      type="checkbox"
                      checked={permissions.desktop_automation}
                      onChange={e => setPermissions(p => ({ ...p, desktop_automation: e.target.checked }))}
                      style={{ width: '18px', height: '18px', accentColor: '#e8d0a4' }}
                    />
                  </label>
                </div>
              </motion.div>
            )}

            {/* STEP 4: AI INTELLIGENCE & API KEY */}
            {step === 4 && (
              <motion.div
                key="step4"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
              >
                <div>
                  <h3 style={{ fontSize: '20px', fontWeight: 700, margin: 0, color: '#fff' }}>
                    Connect Your AI Provider
                  </h3>
                  <p style={{ fontSize: '13px', color: 'rgba(244, 236, 225, 0.7)', marginTop: '4px', margin: 0 }}>
                    Arova uses fast LLM inference to summarize projects and execute actions. You can configure this now or in Settings later.
                  </p>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                  {[
                    { id: 'groq', name: 'Groq (Recommended)', badge: 'Ultra-Fast' },
                    { id: 'openai', name: 'OpenAI', badge: 'GPT-4o' },
                    { id: 'gemini', name: 'Google Gemini', badge: 'Flash' },
                    { id: 'anthropic', name: 'Anthropic', badge: 'Claude' },
                    { id: 'ollama', name: 'Ollama (Local)', badge: 'Offline' }
                  ].map(p => (
                    <button
                      key={p.id}
                      onClick={() => {
                        setProvider(p.id as any);
                        setTestStatus('idle');
                        setTestError(null);
                      }}
                      style={{
                        padding: '12px 10px',
                        borderRadius: '10px',
                        background: provider === p.id ? 'rgba(232, 208, 164, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                        border: provider === p.id ? '1px solid #e8d0a4' : '1px solid rgba(255, 255, 255, 0.08)',
                        color: provider === p.id ? '#e8d0a4' : '#fff',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'flex-start',
                        gap: '4px',
                        textAlign: 'left'
                      }}
                    >
                      <div style={{ fontWeight: 600, fontSize: '13px' }}>{p.name}</div>
                      <div style={{ fontSize: '11px', color: 'rgba(244, 236, 225, 0.5)' }}>{p.badge}</div>
                    </button>
                  ))}
                </div>

                {provider === 'ollama' ? (
                  <div>
                    <label style={{ fontSize: '12px', color: 'rgba(244, 236, 225, 0.7)', display: 'block', marginBottom: '6px', fontWeight: 500 }}>
                      Ollama Endpoint URL
                    </label>
                    <input
                      type="text"
                      value={ollamaHost}
                      onChange={e => setOllamaHost(e.target.value)}
                      placeholder="http://localhost:11434"
                      style={{
                        width: '100%',
                        padding: '12px 14px',
                        background: 'rgba(0, 0, 0, 0.3)',
                        border: '1px solid rgba(255, 255, 255, 0.12)',
                        borderRadius: '10px',
                        color: '#fff',
                        fontSize: '14px',
                        outline: 'none'
                      }}
                    />
                  </div>
                ) : (
                  <div>
                    <label style={{ fontSize: '12px', color: 'rgba(244, 236, 225, 0.7)', display: 'block', marginBottom: '6px', fontWeight: 500 }}>
                      {provider.toUpperCase()} API Key
                    </label>
                    <input
                      type="password"
                      value={apiKey}
                      onChange={e => setApiKey(e.target.value)}
                      placeholder={provider === 'groq' ? 'gsk_...' : provider === 'openai' ? 'sk-...' : 'API Key...'}
                      style={{
                        width: '100%',
                        padding: '12px 14px',
                        background: 'rgba(0, 0, 0, 0.3)',
                        border: '1px solid rgba(255, 255, 255, 0.12)',
                        borderRadius: '10px',
                        color: '#fff',
                        fontSize: '14px',
                        outline: 'none'
                      }}
                    />
                  </div>
                )}

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '4px' }}>
                  <button
                    onClick={handleTestConnection}
                    disabled={testStatus === 'testing'}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '8px',
                      background: 'rgba(255, 255, 255, 0.08)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      color: '#fff',
                      fontSize: '12px',
                      cursor: 'pointer',
                      fontWeight: 500
                    }}
                  >
                    {testStatus === 'testing' ? 'Testing...' : 'Test Connection'}
                  </button>

                  {testStatus === 'success' && (
                    <span style={{ fontSize: '12px', color: '#4caf50', fontWeight: 600 }}>✓ Connection verified</span>
                  )}
                  {testStatus === 'error' && (
                    <span style={{ fontSize: '12px', color: '#ff6b6b' }}>{testError}</span>
                  )}
                </div>
              </motion.div>
            )}

            {/* STEP 5: DEFAULTS & STARTUP */}
            {step === 5 && (
              <motion.div
                key="step5"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}
              >
                <div>
                  <h3 style={{ fontSize: '20px', fontWeight: 700, margin: 0, color: '#fff' }}>
                    Preferences &amp; System Startup
                  </h3>
                  <p style={{ fontSize: '13px', color: 'rgba(244, 236, 225, 0.7)', marginTop: '4px', margin: 0 }}>
                    Finalize your personal environment preferences.
                  </p>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {/* Theme Selector */}
                  <div>
                    <label style={{ fontSize: '12px', color: 'rgba(244, 236, 225, 0.7)', display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                      Visual Atmosphere
                    </label>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <button
                        onClick={() => {
                          setTheme('nocturne');
                          document.documentElement.setAttribute('data-theme', 'nocturne');
                        }}
                        style={{
                          padding: '14px',
                          borderRadius: '12px',
                          background: theme === 'nocturne' ? 'rgba(232, 208, 164, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                          border: theme === 'nocturne' ? '1px solid #e8d0a4' : '1px solid rgba(255, 255, 255, 0.08)',
                          color: '#fff',
                          cursor: 'pointer',
                          textAlign: 'left'
                        }}
                      >
                        <div style={{ fontWeight: 600, fontSize: '14px' }}>🌙 Nocturne</div>
                        <div style={{ fontSize: '12px', color: 'rgba(244, 236, 225, 0.5)', marginTop: '2px' }}>Deep cosmic dark theme with ambient violet glows.</div>
                      </button>

                      <button
                        onClick={() => {
                          setTheme('daylight');
                          document.documentElement.setAttribute('data-theme', 'daylight');
                        }}
                        style={{
                          padding: '14px',
                          borderRadius: '12px',
                          background: theme === 'daylight' ? 'rgba(232, 208, 164, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                          border: theme === 'daylight' ? '1px solid #e8d0a4' : '1px solid rgba(255, 255, 255, 0.08)',
                          color: '#fff',
                          cursor: 'pointer',
                          textAlign: 'left'
                        }}
                      >
                        <div style={{ fontWeight: 600, fontSize: '14px' }}>☀️ Daylight</div>
                        <div style={{ fontSize: '12px', color: 'rgba(244, 236, 225, 0.5)', marginTop: '2px' }}>Warm paper daylight atmosphere with soft amber warmth.</div>
                      </button>
                    </div>
                  </div>

                  {/* Autostart Toggle */}
                  <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', cursor: 'pointer' }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '14px', color: '#fff' }}>🚀 Launch Arova on System Startup</div>
                      <div style={{ fontSize: '12px', color: 'rgba(244, 236, 225, 0.6)', marginTop: '2px' }}>Automatically start in the background when your computer boots up.</div>
                    </div>
                    <input
                      type="checkbox"
                      checked={autostart}
                      onChange={e => setAutostart(e.target.checked)}
                      style={{ width: '20px', height: '20px', accentColor: '#e8d0a4' }}
                    />
                  </label>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Footer Navigation Controls */}
        <div style={{ padding: '20px 32px', borderTop: '1px solid rgba(255, 255, 255, 0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          {step > 1 ? (
            <button
              onClick={() => setStep((s: any) => (s - 1) as any)}
              style={{
                padding: '10px 20px',
                borderRadius: '999px',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: 'rgba(244, 236, 225, 0.8)',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: 500
              }}
            >
              Back
            </button>
          ) : (
            <div />
          )}

          <div style={{ display: 'flex', gap: '12px' }}>
            {step === 4 && (
              <button
                onClick={() => setStep(5)}
                style={{
                  padding: '10px 18px',
                  borderRadius: '999px',
                  background: 'none',
                  border: 'none',
                  color: 'rgba(244, 236, 225, 0.6)',
                  cursor: 'pointer',
                  fontSize: '13px'
                }}
              >
                Skip for now
              </button>
            )}

            {step < 5 ? (
              <button
                onClick={() => {
                  if (step === 2 && !termsAgreed) {
                    alert('Please accept the Terms of Service & Privacy Policy to continue.');
                    return;
                  }
                  setStep((s: any) => (s + 1) as any);
                }}
                style={{
                  padding: '10px 24px',
                  borderRadius: '999px',
                  background: '#e8d0a4',
                  border: 'none',
                  color: '#1a1620',
                  cursor: 'pointer',
                  fontSize: '13px',
                  fontWeight: 700,
                  boxShadow: '0 4px 16px rgba(232, 208, 164, 0.3)'
                }}
              >
                Continue →
              </button>
            ) : (
              <button
                onClick={handleFinish}
                style={{
                  padding: '12px 28px',
                  borderRadius: '999px',
                  background: 'linear-gradient(135deg, #e8d0a4 0%, #d4b47c 100%)',
                  border: 'none',
                  color: '#141119',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 700,
                  boxShadow: '0 6px 20px rgba(232, 208, 164, 0.4)'
                }}
              >
                Finish Setup &amp; Enter Arova
              </button>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
};
