import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
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

/* --- Sleek SVG Icons --- */
const Icons = {
  Sparkle: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v18M3 12h18M6.5 6.5l11 11M17.5 6.5l-11 11"/>
    </svg>
  ),
  Shield: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      <path d="m9 12 2 2 4-4"/>
    </svg>
  ),
  FolderCode: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      <polyline points="10 13 8 15 10 17"/>
      <polyline points="14 13 16 15 14 17"/>
    </svg>
  ),
  Globe: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <line x1="2" y1="12" x2="22" y2="12"/>
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
    </svg>
  ),
  Mic: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
      <line x1="12" y1="19" x2="12" y2="23"/>
      <line x1="8" y1="23" x2="16" y2="23"/>
    </svg>
  ),
  Terminal: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
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
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  ),
  Sun: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
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
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/>
      <path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/>
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
  const [ollamaHost, setOllamaHost] = useState('http://localhost:11434');
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [testError, setTestError] = useState<string | null>(null);

  const [theme, setTheme] = useState<'nocturne' | 'daylight'>('nocturne');
  const [autostart, setAutostart] = useState(true);

  // Live Audio Meter Simulation for mic testing
  const [micActivity, setMicActivity] = useState(0);
  const micIntervalRef = useRef<any>(null);

  useEffect(() => {
    if (step === 3 && permissions.voice_audio) {
      micIntervalRef.current = setInterval(() => {
        setMicActivity(Math.floor(Math.random() * 40) + 15);
      }, 180);
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
        if (ev.success) {
          setTestStatus('success');
          setTestError(null);
        } else {
          setTestStatus('error');
          setTestError(ev.error || 'Connection failed.');
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

    socket.sendEvent({
      type: 'config.set_autostart',
      enabled: autostart
    });

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
        background: 'radial-gradient(1200px 900px at 50% 40%, rgba(18, 15, 22, 0.94) 0%, rgba(8, 7, 10, 0.98) 100%)',
        backdropFilter: 'blur(36px) saturate(160%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--ink, #fbf7f0)',
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif",
        userSelect: 'none',
        padding: '24px'
      }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        style={{
          width: '700px',
          maxWidth: '96vw',
          maxHeight: '88vh',
          background: 'var(--glass-2, rgba(32, 26, 22, 0.88))',
          border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.12))',
          borderRadius: '20px',
          boxShadow: '0 32px 100px rgba(0, 0, 0, 0.8), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}
      >
        {/* Header with Brand and Step Pill Indicators */}
        <div style={{ padding: '22px 28px 16px', borderBottom: '1px solid var(--hairline, rgba(255, 235, 200, 0.06))', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '26px', height: '26px', position: 'relative' }}>
              <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%) scale(0.12)' }}>
                <OrbShell />
              </div>
            </div>
            <span style={{ fontSize: '13px', fontWeight: 600, letterSpacing: '0.12em', color: 'var(--accent-amber, #d97706)', textTransform: 'uppercase' }}>
              Arova Initial Setup
            </span>
          </div>

          <div style={{ display: 'flex', gap: '6px' }}>
            {[1, 2, 3, 4, 5].map(s => (
              <div
                key={s}
                style={{
                  width: '28px',
                  height: '3px',
                  borderRadius: '999px',
                  background: step >= s ? 'var(--accent-amber, #d97706)' : 'var(--hairline-2, rgba(255, 235, 200, 0.12))',
                  transition: 'background 0.3s ease'
                }}
              />
            ))}
          </div>
        </div>

        {/* Content Body */}
        <div style={{ padding: '28px 32px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <AnimatePresence mode="wait">
            {/* STEP 1: WELCOME & CAPABILITIES */}
            {step === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                style={{ display: 'flex', flexDirection: 'column', gap: '20px', alignItems: 'center', textAlign: 'center' }}
              >
                <div style={{ width: '70px', height: '70px', position: 'relative', margin: '4px 0' }}>
                  <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%) scale(0.32)' }}>
                    <OrbShell />
                  </div>
                </div>

                <div>
                  <h2 style={{ fontSize: '24px', fontWeight: 600, margin: 0, color: 'var(--ink, #fbf7f0)', letterSpacing: '-0.02em' }}>
                    Mind-Like Ambient Working Memory
                  </h2>
                  <p style={{ fontSize: '14px', lineHeight: '1.6', color: 'var(--ink-2, #ded6ca)', maxWidth: '540px', marginTop: '8px', margin: '8px auto 0' }}>
                    Arova runs unobtrusively in the background, anchoring your active projects, terminals, and research context so you can resume flow state instantly with zero mental friction.
                  </p>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', width: '100%', textAlign: 'left', marginTop: '6px' }}>
                  <div style={{ padding: '16px', background: 'var(--glass-1, rgba(255, 255, 255, 0.03))', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))', borderRadius: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-amber, #d97706)', marginBottom: '4px' }}>
                      <Icons.Sparkle />
                      <span style={{ fontWeight: 600, fontSize: '13px', color: 'var(--ink, #fff)' }}>Instant Working State Resume</span>
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', lineHeight: '1.5' }}>1-click restoration of all active editors, terminals, and curated research tabs.</div>
                  </div>

                  <div style={{ padding: '16px', background: 'var(--glass-1, rgba(255, 255, 255, 0.03))', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))', borderRadius: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-sage, #16a34a)', marginBottom: '4px' }}>
                      <Icons.Shield />
                      <span style={{ fontWeight: 600, fontSize: '13px', color: 'var(--ink, #fff)' }}>Local SQLite Knowledge Substrate</span>
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', lineHeight: '1.5' }}>All telemetry and cognitive memory stay encrypted on your local filesystem.</div>
                  </div>
                </div>

                <div style={{ padding: '10px 14px', background: 'rgba(217, 119, 6, 0.08)', border: '1px solid rgba(217, 119, 6, 0.25)', borderRadius: '10px', fontSize: '12px', color: 'var(--ink-2, #ded6ca)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-amber, #d97706)' }} />
                  Global Summon Shortcut: <strong style={{ color: 'var(--ink, #fff)' }}>Ctrl + Space</strong> (or <strong style={{ color: 'var(--ink, #fff)' }}>⌘ + Space</strong> on macOS)
                </div>
              </motion.div>
            )}

            {/* STEP 2: PRIVACY POLICY & LOCAL ARCHITECTURE */}
            {step === 2 && (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
              >
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: 600, margin: 0, color: 'var(--ink, #fbf7f0)' }}>
                    Privacy Policy &amp; Terms of Service
                  </h3>
                  <p style={{ fontSize: '13px', color: 'var(--ink-3, #b8b0a2)', marginTop: '4px', margin: 0 }}>
                    Transparent architectural commitments before monitoring is enabled.
                  </p>
                </div>

                <div
                  style={{
                    background: 'rgba(0, 0, 0, 0.35)',
                    border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))',
                    borderRadius: '12px',
                    padding: '16px 20px',
                    fontSize: '13px',
                    lineHeight: '1.65',
                    color: 'var(--ink-2, #ded6ca)',
                    maxHeight: '220px',
                    overflowY: 'auto'
                  }}
                >
                  <div style={{ fontWeight: 600, color: 'var(--accent-amber, #d97706)', marginBottom: '4px' }}>1. Local-First Processing Guarantee</div>
                  <div>Arova is designed as a local-first system. Window handles, terminal directories, and episodic SQLite memories reside exclusively on your machine.</div>
                  
                  <div style={{ fontWeight: 600, color: 'var(--accent-amber, #d97706)', marginTop: '12px', marginBottom: '4px' }}>2. Absolute Exclusion of Sensitive Data</div>
                  <div>Arova automatically filters out authentication endpoints (OAuth, Okta, Microsoft, Google SSO), banking portals, password managers, personal messaging (WhatsApp, Telegram), and sensitive local files (.env, keys).</div>

                  <div style={{ fontWeight: 600, color: 'var(--accent-amber, #d97706)', marginTop: '12px', marginBottom: '4px' }}>3. Zero Telemetry Monetization</div>
                  <div>We do not sell, track, or commercialize your working habits. LLM inference queries are routed strictly to your configured provider using your personal API key.</div>
                </div>

                <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer', padding: '8px 0' }}>
                  <input
                    type="checkbox"
                    checked={termsAgreed}
                    onChange={e => setTermsAgreed(e.target.checked)}
                    style={{ width: '17px', height: '17px', accentColor: 'var(--accent-amber, #d97706)', cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: '13px', color: 'var(--ink, #fff)' }}>
                    I have read and agree to the <strong>Terms of Service</strong> and <strong>Privacy Policy</strong>.
                  </span>
                </label>
              </motion.div>
            )}

            {/* STEP 3: GRANULAR PERMISSIONS & LIVE MIC TEST */}
            {step === 3 && (
              <motion.div
                key="step3"
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}
              >
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: 600, margin: 0, color: 'var(--ink, #fbf7f0)' }}>
                    Telemetry &amp; Ambient Permissions
                  </h3>
                  <p style={{ fontSize: '13px', color: 'var(--ink-3, #b8b0a2)', marginTop: '4px', margin: 0 }}>
                    Select which ambient signals Arova is authorized to observe.
                  </p>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {/* Workspace Tracking */}
                  <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', background: 'var(--glass-1, rgba(255, 255, 255, 0.03))', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))', borderRadius: '12px', cursor: 'pointer' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ color: 'var(--accent-amber, #d97706)' }}><Icons.FolderCode /></div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--ink, #fff)' }}>Workspace &amp; IDE Tracking</div>
                        <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', marginTop: '2px' }}>Observes active repositories in VS Code, Cursor, and Terminal working directories.</div>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={permissions.workspace_tracking}
                      onChange={e => setPermissions(p => ({ ...p, workspace_tracking: e.target.checked }))}
                      style={{ width: '17px', height: '17px', accentColor: 'var(--accent-amber, #d97706)' }}
                    />
                  </label>

                  {/* Browser Capture */}
                  <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', background: 'var(--glass-1, rgba(255, 255, 255, 0.03))', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))', borderRadius: '12px', cursor: 'pointer' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ color: 'var(--accent-ice, #0284c7)' }}><Icons.Globe /></div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--ink, #fff)' }}>Selective Research Browser Capture</div>
                        <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', marginTop: '2px' }}>Captures relevant documentation while strictly blocking authentication, passwords, and banking.</div>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={permissions.browser_capture}
                      onChange={e => setPermissions(p => ({ ...p, browser_capture: e.target.checked }))}
                      style={{ width: '17px', height: '17px', accentColor: 'var(--accent-amber, #d97706)' }}
                    />
                  </label>

                  {/* Voice & Live Mic Test */}
                  <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', background: 'var(--glass-1, rgba(255, 255, 255, 0.03))', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))', borderRadius: '12px', cursor: 'pointer' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ color: 'var(--accent-sage, #16a34a)' }}><Icons.Mic /></div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--ink, #fff)' }}>Voice Interaction &amp; Media Ducking</div>
                        <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', marginTop: '2px' }}>Enables 'Hey Arova' wake word and fluidly lowers background music volume when speaking.</div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      {permissions.voice_audio && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '3px', height: '14px' }}>
                          <span style={{ width: '2px', height: `${Math.min(14, micActivity * 0.3)}px`, background: '#16a34a', borderRadius: '2px' }} />
                          <span style={{ width: '2px', height: `${Math.min(14, micActivity * 0.6)}px`, background: '#16a34a', borderRadius: '2px' }} />
                          <span style={{ width: '2px', height: `${Math.min(14, micActivity * 0.4)}px`, background: '#16a34a', borderRadius: '2px' }} />
                        </div>
                      )}
                      <input
                        type="checkbox"
                        checked={permissions.voice_audio}
                        onChange={e => setPermissions(p => ({ ...p, voice_audio: e.target.checked }))}
                        style={{ width: '17px', height: '17px', accentColor: 'var(--accent-amber, #d97706)' }}
                      />
                    </div>
                  </label>

                  {/* Desktop Automation */}
                  <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', background: 'var(--glass-1, rgba(255, 255, 255, 0.03))', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))', borderRadius: '12px', cursor: 'pointer' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ color: 'var(--accent-violet, #7c3aed)' }}><Icons.Terminal /></div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--ink, #fff)' }}>Cross-Platform Task Automation</div>
                        <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', marginTop: '2px' }}>Allows Arova to launch applications, switch windows, and control music on voice command.</div>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={permissions.desktop_automation}
                      onChange={e => setPermissions(p => ({ ...p, desktop_automation: e.target.checked }))}
                      style={{ width: '17px', height: '17px', accentColor: 'var(--accent-amber, #d97706)' }}
                    />
                  </label>
                </div>
              </motion.div>
            )}

            {/* STEP 4: AI PROVIDERS & DIRECT 1-CLICK LINKS */}
            {step === 4 && (
              <motion.div
                key="step4"
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}
              >
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: 600, margin: 0, color: 'var(--ink, #fbf7f0)' }}>
                    Connect LLM Inference Provider
                  </h3>
                  <p style={{ fontSize: '13px', color: 'var(--ink-3, #b8b0a2)', marginTop: '4px', margin: 0 }}>
                    Select your preferred AI engine and enter your API key. Direct links provided below.
                  </p>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                  {[
                    { id: 'groq', name: 'Groq', badge: 'Ultra-Fast Llama-3.3 70B', recommended: true },
                    { id: 'openai', name: 'OpenAI', badge: 'GPT-4o / GPT-4o-mini' },
                    { id: 'gemini', name: 'Google Gemini', badge: 'Gemini 2.0 Flash' },
                    { id: 'anthropic', name: 'Anthropic', badge: 'Claude 3.5 Sonnet' },
                    { id: 'ollama', name: 'Ollama', badge: 'Local / Offline' }
                  ].map(p => (
                    <button
                      key={p.id}
                      onClick={() => {
                        setProvider(p.id as any);
                        setTestStatus('idle');
                        setTestError(null);
                      }}
                      style={{
                        padding: '12px 14px',
                        borderRadius: '10px',
                        background: provider === p.id ? 'rgba(217, 119, 6, 0.14)' : 'var(--glass-1, rgba(255, 255, 255, 0.03))',
                        border: provider === p.id ? '1px solid var(--accent-amber, #d97706)' : '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))',
                        color: provider === p.id ? 'var(--accent-amber, #d97706)' : 'var(--ink, #fff)',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'flex-start',
                        gap: '2px',
                        textAlign: 'left'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                        <span style={{ fontWeight: 600, fontSize: '13px' }}>{p.name}</span>
                        {p.recommended && (
                          <span style={{ fontSize: '9px', fontWeight: 700, padding: '2px 5px', borderRadius: '4px', background: 'var(--accent-amber, #d97706)', color: '#000' }}>
                            FASTEST
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--ink-3, #b8b0a2)' }}>{p.badge}</div>
                    </button>
                  ))}
                </div>

                {/* Direct Link + Input Field */}
                <div style={{ background: 'rgba(0, 0, 0, 0.25)', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))', borderRadius: '12px', padding: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <label style={{ fontSize: '12px', color: 'var(--ink-2, #ded6ca)', fontWeight: 500 }}>
                      {provider === 'ollama' ? 'Ollama Host Address' : `${provider.toUpperCase()} API Key`}
                    </label>
                    <a
                      href={PROVIDER_URLS[provider]}
                      target="_blank"
                      rel="noreferrer"
                      style={{ fontSize: '12px', color: 'var(--accent-amber, #d97706)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 500 }}
                    >
                      Get {provider.charAt(0).toUpperCase() + provider.slice(1)} Key <Icons.External />
                    </a>
                  </div>

                  {provider === 'ollama' ? (
                    <input
                      type="text"
                      value={ollamaHost}
                      onChange={e => setOllamaHost(e.target.value)}
                      placeholder="http://localhost:11434"
                      style={{
                        width: '100%',
                        padding: '10px 14px',
                        background: 'rgba(0, 0, 0, 0.3)',
                        border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.12))',
                        borderRadius: '8px',
                        color: 'var(--ink, #fff)',
                        fontSize: '13px',
                        outline: 'none'
                      }}
                    />
                  ) : (
                    <input
                      type="password"
                      value={apiKey}
                      onChange={e => setApiKey(e.target.value)}
                      placeholder={provider === 'groq' ? 'gsk_...' : provider === 'openai' ? 'sk-...' : 'Enter key...'}
                      style={{
                        width: '100%',
                        padding: '10px 14px',
                        background: 'rgba(0, 0, 0, 0.3)',
                        border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.12))',
                        borderRadius: '8px',
                        color: 'var(--ink, #fff)',
                        fontSize: '13px',
                        outline: 'none'
                      }}
                    />
                  )}

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '10px' }}>
                    <button
                      onClick={handleTestConnection}
                      disabled={testStatus === 'testing'}
                      style={{
                        padding: '6px 14px',
                        borderRadius: '8px',
                        background: 'var(--glass-2, rgba(255, 255, 255, 0.08))',
                        border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.15))',
                        color: 'var(--ink, #fff)',
                        fontSize: '12px',
                        cursor: 'pointer',
                        fontWeight: 500
                      }}
                    >
                      {testStatus === 'testing' ? 'Testing Connection...' : 'Test Connection'}
                    </button>

                    {testStatus === 'success' && (
                      <span style={{ fontSize: '12px', color: 'var(--accent-sage, #16a34a)', fontWeight: 600 }}>✓ Verified connected</span>
                    )}
                    {testStatus === 'error' && (
                      <span style={{ fontSize: '12px', color: '#e57373' }}>{testError}</span>
                    )}
                  </div>
                </div>
              </motion.div>
            )}

            {/* STEP 5: VISUAL THEME & AUTOSTART PREFERENCES */}
            {step === 5 && (
              <motion.div
                key="step5"
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
              >
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: 600, margin: 0, color: 'var(--ink, #fbf7f0)' }}>
                    Atmosphere &amp; System Integration
                  </h3>
                  <p style={{ fontSize: '13px', color: 'var(--ink-3, #b8b0a2)', marginTop: '4px', margin: 0 }}>
                    Tailor your visual ambiance and boot startup behavior.
                  </p>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div>
                    <label style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', display: 'block', marginBottom: '8px', fontWeight: 500 }}>
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
                          background: theme === 'nocturne' ? 'rgba(217, 119, 6, 0.14)' : 'var(--glass-1, rgba(255, 255, 255, 0.03))',
                          border: theme === 'nocturne' ? '1px solid var(--accent-amber, #d97706)' : '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))',
                          color: 'var(--ink, #fff)',
                          cursor: 'pointer',
                          textAlign: 'left'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, fontSize: '13px' }}>
                          <Icons.Moon /> Nocturne
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--ink-3, #b8b0a2)', marginTop: '4px' }}>Deep warm obsidian dark theme with violet ambient glows.</div>
                      </button>

                      <button
                        onClick={() => {
                          setTheme('daylight');
                          document.documentElement.setAttribute('data-theme', 'daylight');
                        }}
                        style={{
                          padding: '14px',
                          borderRadius: '12px',
                          background: theme === 'daylight' ? 'rgba(217, 119, 6, 0.14)' : 'var(--glass-1, rgba(255, 255, 255, 0.03))',
                          border: theme === 'daylight' ? '1px solid var(--accent-amber, #d97706)' : '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))',
                          color: 'var(--ink, #fff)',
                          cursor: 'pointer',
                          textAlign: 'left'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, fontSize: '13px' }}>
                          <Icons.Sun /> Daylight
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--ink-3, #b8b0a2)', marginTop: '4px' }}>Warm paper daylight atmosphere with soft amber warmth.</div>
                      </button>
                    </div>
                  </div>

                  {/* Autostart Toggle */}
                  <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', background: 'var(--glass-1, rgba(255, 255, 255, 0.03))', border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.08))', borderRadius: '12px', cursor: 'pointer' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ color: 'var(--accent-amber, #d97706)' }}><Icons.Rocket /></div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--ink, #fff)' }}>Launch Arova on System Startup</div>
                        <div style={{ fontSize: '12px', color: 'var(--ink-3, #b8b0a2)', marginTop: '2px' }}>Automatically starts the cognition daemon when you log in.</div>
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
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Footer Navigation */}
        <div style={{ padding: '18px 28px', borderTop: '1px solid var(--hairline, rgba(255, 235, 200, 0.06))', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          {step > 1 ? (
            <button
              onClick={() => setStep((s: any) => (s - 1) as any)}
              style={{
                padding: '8px 18px',
                borderRadius: '999px',
                background: 'var(--glass-1, rgba(255, 255, 255, 0.04))',
                border: '1px solid var(--hairline-2, rgba(255, 235, 200, 0.1))',
                color: 'var(--ink-2, #ded6ca)',
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
                  padding: '8px 16px',
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
                    alert('Please accept the Terms of Service & Privacy Policy to continue.');
                    return;
                  }
                  setStep((s: any) => (s + 1) as any);
                }}
                style={{
                  padding: '9px 22px',
                  borderRadius: '999px',
                  background: 'var(--accent-amber, #d97706)',
                  border: 'none',
                  color: '#141119',
                  cursor: 'pointer',
                  fontSize: '13px',
                  fontWeight: 600,
                  boxShadow: '0 4px 14px rgba(217, 119, 6, 0.3)'
                }}
              >
                Continue
              </button>
            ) : (
              <button
                onClick={handleFinish}
                style={{
                  padding: '10px 24px',
                  borderRadius: '999px',
                  background: 'linear-gradient(135deg, #e8d0a4 0%, #d4b47c 100%)',
                  border: 'none',
                  color: '#141119',
                  cursor: 'pointer',
                  fontSize: '13px',
                  fontWeight: 700,
                  boxShadow: '0 4px 18px rgba(232, 208, 164, 0.4)'
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
