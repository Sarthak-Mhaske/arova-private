import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { socket } from '../../runtime/socket';
import { OrbShell } from '../orb/OrbShell';

interface OnboardingProps {
  onComplete: () => void;
}

const PROVIDER_URLS: Record<string, string> = {
  groq: 'https://console.groq.com/keys',
  openai: 'https://platform.openai.com/api-keys',
  gemini: 'https://aistudio.google.com/app/apikey',
  anthropic: 'https://console.anthropic.com/settings/keys',
  ollama: 'https://ollama.com/download'
};

const openExternalUrl = async (url: string) => {
  try {
    const { openUrl } = await import('@tauri-apps/plugin-opener');
    await openUrl(url);
  } catch {
    socket.sendEvent({
      type: 'client.open_url',
      url
    });
    try {
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch {
      // fallback
    }
  }
};

/* --- Bespoke Precision Vector SVGs --- */
const Icons = {
  Sparkle: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v18M3 12h18M6.5 6.5l11 11M17.5 6.5l-11 11"/>
    </svg>
  ),
  Shield: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      <path d="m9 12 2 2 4-4"/>
    </svg>
  ),
  FolderCode: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      <polyline points="10 13 8 15 10 17"/>
      <polyline points="14 13 16 15 14 17"/>
    </svg>
  ),
  Globe: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <line x1="2" y1="12" x2="22" y2="12"/>
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
    </svg>
  ),
  Mic: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
      <line x1="12" y1="19" x2="12" y2="23"/>
      <line x1="8" y1="23" x2="16" y2="23"/>
    </svg>
  ),
  Terminal: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="4 17 10 11 4 5"/>
      <line x1="12" y1="19" x2="20" y2="19"/>
    </svg>
  ),
  External: () => (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
      <polyline points="15 3 21 3 21 9"/>
      <line x1="10" y1="14" x2="21" y2="3"/>
    </svg>
  ),
  Moon: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  ),
  Sun: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5"/>
      <line x1="12" y1="1" x2="12" y2="3"/>
      <line x1="12" y1="21" x2="12" y2="23"/>
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
      <line x1="1" y1="12" x2="3" y2="12"/>
      <line x1="21" y1="12" x2="23" y2="12"/>
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
    </svg>
  ),
  Rocket: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/>
      <path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/>
    </svg>
  ),
  Lock: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
    </svg>
  )
};

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
  const [ollamaHost, setOllamaHost] = useState('');
  const [theme, setTheme] = useState<'nocturne' | 'daylight'>('nocturne');
  const [autostart, setAutostart] = useState(true);

  // Live Audio Meter Simulation for mic testing
  const [micActivity, setMicActivity] = useState(0);
  const micIntervalRef = useRef<any>(null);
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [testError, setTestError] = useState<string | null>(null);
  const [testLatency, setTestLatency] = useState<number | null>(null);

  useEffect(() => {
    if (step === 3 && permissions.voice_audio) {
      micIntervalRef.current = setInterval(() => {
        setMicActivity(Math.floor(Math.random() * 35) + 15);
      }, 160);
    } else {
      if (micIntervalRef.current) clearInterval(micIntervalRef.current);
      setMicActivity(0);
    }
    return () => {
      if (micIntervalRef.current) clearInterval(micIntervalRef.current);
    };
  }, [step, permissions.voice_audio]);

  useEffect(() => {
    const handleTestResult = (e: any) => {
      const ev = e.detail;
      if (ev && ev.type === 'provider.test_result') {
        const isSuccess = Boolean(ev.success || ev.result?.success);
        if (isSuccess) {
          setTestStatus('success');
          setTestLatency(ev.result?.latency_ms || null);
          setTestError(null);
        } else {
          setTestStatus('error');
          setTestLatency(null);
          const errMsg = ev.error || ev.result?.error || 'Connection failed. Please check your API key.';
          setTestError(errMsg);
        }
      }
    };
    window.addEventListener('arova-event', handleTestResult);
    return () => window.removeEventListener('arova-event', handleTestResult);
  }, []);

  const handleTestConnection = () => {
    const cleanKey = apiKey.trim().replace(/^['"]|['"]$/g, '');
    if (provider === 'ollama') {
      if (!ollamaHost.trim()) {
        setTestStatus('error');
        setTestError('Please enter your Ollama endpoint (e.g. http://127.0.0.1:11434).');
        return;
      }
    } else if (!cleanKey) {
      setTestStatus('error');
      setTestError('Please enter an API key.');
      return;
    }
    setTestStatus('testing');
    setTestError(null);

    // Timeout safety: reset status if daemon or network stalls
    setTimeout(() => {
      setTestStatus(prev => {
        if (prev === 'testing') {
          setTestError('Connection timed out. Please check network connectivity.');
          return 'error';
        }
        return prev;
      });
    }, 12000);

    socket.sendEvent({
      type: 'provider.test',
      provider,
      api_key: cleanKey,
      host: ollamaHost.trim(),
      req_id: `onboarding_${provider}_${Date.now()}`
    });
  };

  const handleFinish = () => {
    const cleanKey = apiKey.trim().replace(/^['"]|['"]$/g, '');
    if (cleanKey || provider === 'ollama') {
      const providersPayload: any = {};
      if (provider === 'ollama') {
        providersPayload.ollama = { host: ollamaHost.trim() };
      } else {
        providersPayload[provider] = { api_keys: [cleanKey] };
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

    const consentRecord = {
      version: '1.0.0',
      agreed_at: new Date().toISOString(),
      timestamp: Math.floor(Date.now() / 1000),
      terms_accepted: true,
      privacy_policy_accepted: true,
      permissions: {
        workspace_tracking: permissions.workspace_tracking,
        browser_capture: permissions.browser_capture,
        voice_audio: permissions.voice_audio,
        desktop_automation: permissions.desktop_automation
      },
      provider,
      autostart,
      theme,
      system_signature: 'arova-local-consent-v1'
    };

    // Save consent agreement copy to system daemon & cache
    socket.sendEvent({
      type: 'onboarding.accepted',
      consent: consentRecord
    });

    localStorage.setItem('arova_onboarding_completed', 'true');
    localStorage.setItem('arova_terms_agreed', 'true');
    localStorage.setItem('arova_onboarding_agreement', JSON.stringify(consentRecord));
    localStorage.setItem('arova_autostart', autostart ? 'true' : 'false');

    onComplete();
  };

  const stepTitles = [
    'Welcome to Arova',
    'Privacy & Data Transparency',
    'Ambient Telemetry Grants',
    'Intelligence Engine Setup',
    'Atmosphere & Integration'
  ];

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100000,
        background: 'radial-gradient(1400px 900px at 50% 30%, rgba(18, 15, 22, 0.72) 0%, rgba(10, 8, 12, 0.88) 100%)',
        backdropFilter: 'blur(48px) saturate(180%)',
        WebkitBackdropFilter: 'blur(48px) saturate(180%)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        color: 'var(--ink, #fbf7f0)',
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif",
        userSelect: 'none',
        padding: '36px 48px',
        overflow: 'hidden'
      }}
    >
      {/* Top Ambient Navigation Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', maxWidth: '1080px', margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ width: '28px', height: '28px', position: 'relative' }}>
            <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%) scale(0.14)' }}>
              <OrbShell />
            </div>
          </div>
          <div>
            <div style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.35em', textTransform: 'uppercase', color: 'var(--accent-amber, #d97706)' }}>
              A R O V A
            </div>
            <div style={{ fontSize: '12px', color: 'var(--ink-mute, #857d70)', marginTop: '2px' }}>
              {stepTitles[step - 1]}
            </div>
          </div>
        </div>

        {/* Step Numbers & Micro Indicators */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '12px', color: 'var(--ink-mute, #857d70)', fontVariantNumeric: 'tabular-nums', letterSpacing: '0.05em' }}>
            0{step} <span style={{ opacity: 0.4 }}>/</span> 05
          </span>
          <div style={{ display: 'flex', gap: '5px' }}>
            {[1, 2, 3, 4, 5].map(s => (
              <div
                key={s}
                style={{
                  width: step === s ? '24px' : '6px',
                  height: '4px',
                  borderRadius: '999px',
                  background: step >= s ? 'var(--accent-amber, #d97706)' : 'rgba(255, 235, 200, 0.12)',
                  transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
                }}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Main Focus Card Stage */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '24px 0', minHeight: 0 }}>
        <motion.div
          key={step}
          initial={{ opacity: 0, y: 16, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -16, scale: 0.98 }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          style={{
            width: '100%',
            maxWidth: '860px',
            maxHeight: '70vh',
            background: 'var(--glass-1, rgba(28, 24, 20, 0.65))',
            border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.10))',
            borderRadius: '24px',
            padding: '36px 44px',
            boxShadow: '0 32px 80px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.06)',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column'
          }}
        >
          {/* STEP 1: WELCOME */}
          {step === 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '24px' }}>
              <div style={{ width: '80px', height: '80px', position: 'relative', margin: '8px 0' }}>
                <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%) scale(0.38)' }}>
                  <OrbShell />
                </div>
              </div>

              <div>
                <h1 style={{ fontSize: '28px', fontWeight: 600, margin: 0, color: 'var(--ink, #fbf7f0)', letterSpacing: '-0.02em' }}>
                  Persistent Working Memory for Knowledge Work
                </h1>
                <p style={{ fontSize: '15px', lineHeight: '1.6', color: 'var(--ink-2, #ded6ca)', maxWidth: '620px', margin: '10px auto 0' }}>
                  Arova runs silently alongside your tools, automatically preserving your mental state, active projects, terminals, and documentation so you can resume flow in seconds.
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '14px', width: '100%', textAlign: 'left', marginTop: '8px' }}>
                <div style={{ padding: '18px 20px', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.06))', borderRadius: '14px' }}>
                  <div style={{ color: 'var(--accent-amber, #d97706)', marginBottom: '8px' }}><Icons.Sparkle /></div>
                  <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--ink, #fff)', marginBottom: '4px' }}>Zero-Friction Resume</div>
                  <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', lineHeight: '1.5' }}>1-click restoration of active VS Code, Cursor, terminal windows, and research tabs.</div>
                </div>

                <div style={{ padding: '18px 20px', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.06))', borderRadius: '14px' }}>
                  <div style={{ color: 'var(--accent-sage, #16a34a)', marginBottom: '8px' }}><Icons.Shield /></div>
                  <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--ink, #fff)', marginBottom: '4px' }}>100% Local Substrate</div>
                  <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', lineHeight: '1.5' }}>All raw process telemetry and memory snapshots remain strictly on your machine.</div>
                </div>

                <div style={{ padding: '18px 20px', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.06))', borderRadius: '14px' }}>
                  <div style={{ color: 'var(--accent-violet, #7c3aed)', marginBottom: '8px' }}><Icons.Lock /></div>
                  <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--ink, #fff)', marginBottom: '4px' }}>Zero Telemetry Leak</div>
                  <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', lineHeight: '1.5' }}>Passwords, banking portals, and sensitive keys are blocked before indexing.</div>
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: PRIVACY POLICY & TERMS */}
          {step === 2 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div>
                <h2 style={{ fontSize: '22px', fontWeight: 600, margin: 0, color: 'var(--ink, #fbf7f0)' }}>
                  Privacy Architecture &amp; Terms
                </h2>
                <p style={{ fontSize: '14px', color: 'var(--ink-3, #b8b0a2)', marginTop: '4px', margin: 0 }}>
                  We believe software that tracks your working memory must have unwavering privacy guarantees.
                </p>
              </div>

              <div
                style={{
                  background: 'rgba(0, 0, 0, 0.32)',
                  border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))',
                  borderRadius: '16px',
                  padding: '22px 26px',
                  fontSize: '13px',
                  lineHeight: '1.7',
                  color: 'var(--ink-2, #ded6ca)',
                  maxHeight: '260px',
                  overflowY: 'auto'
                }}
              >
                <div style={{ fontWeight: 600, color: 'var(--accent-amber, #d97706)', marginBottom: '4px' }}>1. Local-First Processing Guarantee</div>
                <div>Arova operates as a local-first system. Process inspection, window handles, terminal directories, and episodic memory records reside exclusively in your local SQLite database on your device.</div>
                
                <div style={{ fontWeight: 600, color: 'var(--accent-amber, #d97706)', marginTop: '14px', marginBottom: '4px' }}>2. Absolute Exclusion of Sensitive Data</div>
                <div>Arova automatically filters out authentication endpoints (OAuth, Okta, Microsoft, Google SSO), banking portals, password managers, personal messaging (WhatsApp, Telegram), and sensitive local files (.env, private keys).</div>

                <div style={{ fontWeight: 600, color: 'var(--accent-amber, #d97706)', marginTop: '14px', marginBottom: '4px' }}>3. Zero Telemetry Selling</div>
                <div>We do not monetize or sell your working habits. LLM inference queries are sent directly to your configured provider using your personal developer API key.</div>
              </div>

              <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer', padding: '6px 0' }}>
                <input
                  type="checkbox"
                  checked={termsAgreed}
                  onChange={e => setTermsAgreed(e.target.checked)}
                  style={{ width: '18px', height: '18px', accentColor: 'var(--accent-amber, #d97706)', cursor: 'pointer' }}
                />
                <span style={{ fontSize: '13px', color: 'var(--ink, #fff)' }}>
                  I accept the <strong>Terms of Service</strong> and agree to the <strong>Privacy Commitments</strong>.
                </span>
              </label>
            </div>
          )}

          {/* STEP 3: AMBIENT TELEMETRY GRANTS */}
          {step === 3 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div>
                <h2 style={{ fontSize: '22px', fontWeight: 600, margin: 0, color: 'var(--ink, #fbf7f0)' }}>
                  Ambient Telemetry Grants
                </h2>
                <p style={{ fontSize: '14px', color: 'var(--ink-3, #b8b0a2)', marginTop: '4px', margin: 0 }}>
                  Customize which ambient signals Arova is authorized to observe.
                </p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {/* Workspace Tracking */}
                <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))', borderRadius: '14px', cursor: 'pointer' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    <div style={{ color: 'var(--accent-amber, #d97706)' }}><Icons.FolderCode /></div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--ink, #fff)' }}>Workspace &amp; IDE Tracking</div>
                      <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', marginTop: '2px' }}>Observes active repositories in VS Code, Cursor, and Terminal working directories.</div>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={permissions.workspace_tracking}
                    onChange={e => setPermissions(p => ({ ...p, workspace_tracking: e.target.checked }))}
                    style={{ width: '18px', height: '18px', accentColor: 'var(--accent-amber, #d97706)' }}
                  />
                </label>

                {/* Selective Browser Capture */}
                <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))', borderRadius: '14px', cursor: 'pointer' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    <div style={{ color: 'var(--accent-ice, #0284c7)' }}><Icons.Globe /></div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--ink, #fff)' }}>Selective Research Browser Capture</div>
                      <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', marginTop: '2px' }}>Captures relevant documentation while strictly blocking authentication, passwords, and banking.</div>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={permissions.browser_capture}
                    onChange={e => setPermissions(p => ({ ...p, browser_capture: e.target.checked }))}
                    style={{ width: '18px', height: '18px', accentColor: 'var(--accent-amber, #d97706)' }}
                  />
                </label>

                {/* Voice Interaction & Mic Meter */}
                <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))', borderRadius: '14px', cursor: 'pointer' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    <div style={{ color: 'var(--accent-sage, #16a34a)' }}><Icons.Mic /></div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--ink, #fff)' }}>Voice Interaction &amp; Media Ducking</div>
                      <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', marginTop: '2px' }}>Enables 'Hey Arova' wake word and fluidly lowers background music volume when speaking.</div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    {permissions.voice_audio && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '3px', height: '14px' }}>
                        <span style={{ width: '3px', height: `${Math.min(14, micActivity * 0.3)}px`, background: '#16a34a', borderRadius: '2px', transition: 'height 0.1s ease' }} />
                        <span style={{ width: '3px', height: `${Math.min(14, micActivity * 0.6)}px`, background: '#16a34a', borderRadius: '2px', transition: 'height 0.1s ease' }} />
                        <span style={{ width: '3px', height: `${Math.min(14, micActivity * 0.4)}px`, background: '#16a34a', borderRadius: '2px', transition: 'height 0.1s ease' }} />
                      </div>
                    )}
                    <input
                      type="checkbox"
                      checked={permissions.voice_audio}
                      onChange={e => setPermissions(p => ({ ...p, voice_audio: e.target.checked }))}
                      style={{ width: '18px', height: '18px', accentColor: 'var(--accent-amber, #d97706)' }}
                    />
                  </div>
                </label>

                {/* Cross-Platform Task Automation */}
                <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))', borderRadius: '14px', cursor: 'pointer' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    <div style={{ color: 'var(--accent-violet, #7c3aed)' }}><Icons.Terminal /></div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--ink, #fff)' }}>Cross-Platform Task Automation</div>
                      <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', marginTop: '2px' }}>Allows Arova to launch applications, switch windows, and control music on command.</div>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={permissions.desktop_automation}
                    onChange={e => setPermissions(p => ({ ...p, desktop_automation: e.target.checked }))}
                    style={{ width: '18px', height: '18px', accentColor: 'var(--accent-amber, #d97706)' }}
                  />
                </label>
              </div>
            </div>
          )}

          {/* STEP 4: AI PROVIDERS & DIRECT 1-CLICK EXTERNAL OPENER */}
          {step === 4 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div>
                <h2 style={{ fontSize: '22px', fontWeight: 600, margin: 0, color: 'var(--ink, #fbf7f0)' }}>
                  Connect Intelligence Engine
                </h2>
                <p style={{ fontSize: '14px', color: 'var(--ink-3, #b8b0a2)', marginTop: '4px', margin: 0 }}>
                  Select your provider and add your API key. Direct links open your browser instantly.
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '10px' }}>
                {[
                  { id: 'groq', name: 'Groq', tag: 'Fastest 70B' },
                  { id: 'openai', name: 'OpenAI', tag: 'GPT-4o' },
                  { id: 'gemini', name: 'Gemini', tag: '2.0 Flash' },
                  { id: 'anthropic', name: 'Claude', tag: '3.5 Sonnet' },
                  { id: 'ollama', name: 'Ollama', tag: 'Local Offline' }
                ].map(p => (
                  <button
                    key={p.id}
                    onClick={() => {
                      setProvider(p.id as any);
                      setTestStatus('idle');
                      setTestError(null);
                    }}
                    style={{
                      padding: '14px 12px',
                      borderRadius: '12px',
                      background: provider === p.id ? 'rgba(217, 119, 6, 0.16)' : 'rgba(255, 255, 255, 0.03)',
                      border: provider === p.id ? '1px solid var(--accent-amber, #d97706)' : '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))',
                      color: provider === p.id ? 'var(--accent-amber, #d97706)' : 'var(--ink, #fff)',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '4px',
                      textAlign: 'center'
                    }}
                  >
                    <span style={{ fontWeight: 600, fontSize: '14px' }}>{p.name}</span>
                    <span style={{ fontSize: '11px', color: 'var(--ink-3, #b8b0a2)' }}>{p.tag}</span>
                  </button>
                ))}
              </div>

              {/* API Key Form Card */}
              <div style={{ background: 'rgba(0, 0, 0, 0.28)', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))', borderRadius: '16px', padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <label style={{ fontSize: '13px', color: 'var(--ink-2, #ded6ca)', fontWeight: 500 }}>
                    {provider === 'ollama' ? 'Ollama Endpoint' : `${provider.toUpperCase()} API Key`}
                  </label>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      openExternalUrl(PROVIDER_URLS[provider]);
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      fontSize: '12px',
                      color: 'var(--accent-amber, #d97706)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      padding: 0
                    }}
                  >
                    Get {provider.charAt(0).toUpperCase() + provider.slice(1)} Key <Icons.External />
                  </button>
                </div>

                {provider === 'ollama' ? (
                  <input
                    type="text"
                    value={ollamaHost}
                    onChange={e => setOllamaHost(e.target.value)}
                    placeholder="http://127.0.0.1:11434 (leave empty if not using local Ollama)"
                    style={{
                      width: '100%',
                      padding: '12px 16px',
                      background: 'rgba(0, 0, 0, 0.35)',
                      border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.12))',
                      borderRadius: '10px',
                      color: 'var(--ink, #fff)',
                      fontSize: '14px',
                      outline: 'none'
                    }}
                  />
                ) : (
                  <input
                    type="password"
                    value={apiKey}
                    onChange={e => setApiKey(e.target.value)}
                    placeholder={provider === 'groq' ? 'gsk_...' : provider === 'openai' ? 'sk-...' : 'Paste your secret key...'}
                    style={{
                      width: '100%',
                      padding: '12px 16px',
                      background: 'rgba(0, 0, 0, 0.35)',
                      border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.12))',
                      borderRadius: '10px',
                      color: 'var(--ink, #fff)',
                      fontSize: '14px',
                      outline: 'none'
                    }}
                  />
                )}

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '14px' }}>
                  <button
                    onClick={handleTestConnection}
                    disabled={testStatus === 'testing'}
                    style={{
                      padding: '8px 18px',
                      borderRadius: '8px',
                      background: 'rgba(255, 255, 255, 0.08)',
                      border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.15))',
                      color: 'var(--ink, #fff)',
                      fontSize: '12px',
                      cursor: 'pointer',
                      fontWeight: 600
                    }}
                  >
                    {testStatus === 'testing' ? 'Testing Connection...' : 'Test Connection'}
                  </button>

                  {testStatus === 'success' && (
                    <span style={{ fontSize: '12px', color: '#4ade80', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                      ✓ Connected {testLatency ? `· ${testLatency}ms latency` : ''}
                    </span>
                  )}
                  {testStatus === 'error' && (
                    <span style={{ fontSize: '12px', color: '#f87171', maxWidth: '300px', textAlign: 'right' }}>{testError}</span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* STEP 5: VISUAL THEME & STARTUP AUTO-LAUNCH */}
          {step === 5 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div>
                <h2 style={{ fontSize: '22px', fontWeight: 600, margin: 0, color: 'var(--ink, #fbf7f0)' }}>
                  Atmosphere &amp; System Integration
                </h2>
                <p style={{ fontSize: '14px', color: 'var(--ink-3, #b8b0a2)', marginTop: '4px', margin: 0 }}>
                  Personalize your visual theme and startup behavior.
                </p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <label style={{ fontSize: '13px', color: 'var(--ink-3, #b8b0a2)', display: 'block', marginBottom: '10px', fontWeight: 500 }}>
                    Visual Ambiance
                  </label>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                    <button
                      onClick={() => {
                        setTheme('nocturne');
                        document.documentElement.setAttribute('data-theme', 'nocturne');
                      }}
                      style={{
                        padding: '18px 20px',
                        borderRadius: '14px',
                        background: theme === 'nocturne' ? 'rgba(217, 119, 6, 0.16)' : 'rgba(255, 255, 255, 0.02)',
                        border: theme === 'nocturne' ? '1px solid var(--accent-amber, #d97706)' : '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))',
                        color: 'var(--ink, #fff)',
                        cursor: 'pointer',
                        textAlign: 'left'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, fontSize: '14px' }}>
                        <Icons.Moon /> Nocturne
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', marginTop: '4px' }}>Cosmic obsidian dark theme with violet ambient glows.</div>
                    </button>

                    <button
                      onClick={() => {
                        setTheme('daylight');
                        document.documentElement.setAttribute('data-theme', 'daylight');
                      }}
                      style={{
                        padding: '18px 20px',
                        borderRadius: '14px',
                        background: theme === 'daylight' ? 'rgba(217, 119, 6, 0.16)' : 'rgba(255, 255, 255, 0.02)',
                        border: theme === 'daylight' ? '1px solid var(--accent-amber, #d97706)' : '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))',
                        color: 'var(--ink, #fff)',
                        cursor: 'pointer',
                        textAlign: 'left'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, fontSize: '14px' }}>
                        <Icons.Sun /> Daylight
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', marginTop: '4px' }}>Warm paper daylight atmosphere with soft amber warmth.</div>
                    </button>
                  </div>
                </div>

                {/* Autostart Toggle */}
                <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))', borderRadius: '14px', cursor: 'pointer' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    <div style={{ color: 'var(--accent-amber, #d97706)' }}><Icons.Rocket /></div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--ink, #fff)' }}>Launch Arova on System Startup</div>
                      <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', marginTop: '2px' }}>Automatically starts background memory tracking when you log in.</div>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={autostart}
                    onChange={e => setAutostart(e.target.checked)}
                    style={{ width: '18px', height: '18px', accentColor: 'var(--accent-amber, #d97706)' }}
                  />
                </label>
              </div>
            </div>
          )}
        </motion.div>
      </div>

      {/* Bottom Floating Navigation Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', maxWidth: '860px', margin: '0 auto' }}>
        {step > 1 ? (
          <button
            onClick={() => setStep((s: any) => (s - 1) as any)}
            style={{
              padding: '10px 22px',
              borderRadius: '999px',
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.12))',
              color: 'var(--ink-2, #ded6ca)',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: 500,
              transition: 'all 0.2s ease'
            }}
          >
            Back
          </button>
        ) : (
          <div />
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          {step === 4 && (
            <button
              onClick={() => setStep(5)}
              style={{
                padding: '10px 18px',
                borderRadius: '999px',
                background: 'none',
                border: 'none',
                color: 'var(--ink-3, #b8b0a2)',
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
                  alert('Please accept the Terms of Service & Privacy Commitments to proceed.');
                  return;
                }
                setStep((s: any) => (s + 1) as any);
              }}
              style={{
                padding: '11px 26px',
                borderRadius: '999px',
                background: 'var(--accent-amber, #d97706)',
                border: 'none',
                color: '#141119',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: 600,
                boxShadow: '0 4px 18px rgba(217, 119, 6, 0.35)',
                transition: 'all 0.2s ease'
              }}
            >
              Continue →
            </button>
          ) : (
            <button
              onClick={handleFinish}
              style={{
                padding: '12px 30px',
                borderRadius: '999px',
                background: 'linear-gradient(135deg, #faecd4 0%, #d4b47c 100%)',
                border: 'none',
                color: '#141119',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: 700,
                boxShadow: '0 6px 24px rgba(232, 208, 164, 0.45)',
                transition: 'all 0.2s ease'
              }}
            >
              Enter Arova
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
