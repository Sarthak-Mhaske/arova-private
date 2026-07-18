import React, { useState, useEffect } from 'react';
import { socket } from '../../runtime/socket';

export const OnboardingFlow: React.FC<{ onComplete: () => void }> = ({ onComplete }) => {
  const [step, setStep] = useState(1);
  const [intelligenceSource, setIntelligenceSource] = useState('groq');
  const [apiKey, setApiKey] = useState('');
  const [ollamaHost, setOllamaHost] = useState('http://localhost:11434');
  const [testResult, setTestResult] = useState<{ success: boolean; latency_ms?: number; error?: string } | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    const handleEvent = (event: any) => {
      const { type, payload } = event.detail;
      if (type === 'provider.test_result') {
        setTesting(false);
        setTestResult(payload.result);
      }
    };
    
    window.addEventListener('runtime_event', handleEvent);
    setTimeout(() => {
      socket.sendEvent({ type: 'provider.discovery_request' });
    }, 500);

    return () => window.removeEventListener('runtime_event', handleEvent);
  }, []);

  const testConnection = () => {
    setTesting(true);
    setTestResult(null);
    socket.sendEvent({ 
      type: 'provider.test', 
      provider: intelligenceSource, 
      api_key: apiKey,
      host: ollamaHost,
      req_id: Date.now().toString()
    });
  };

  const handleComplete = () => {
    const providersConfig: any = {};
    if (intelligenceSource === 'groq' && testResult?.success) {
      providersConfig.groq = { api_keys: [apiKey] };
    } else if (intelligenceSource === 'openai' && testResult?.success) {
      providersConfig.openai = { api_keys: [apiKey] };
    } else if (intelligenceSource === 'ollama' && testResult?.success) {
      providersConfig.ollama = { host: ollamaHost };
    }

    const appConfig = {
      presence_style: 'hybrid',
      privacy: {
        workspace_awareness: true,
        memory_enabled: true,
        crash_recovery: true
      },
      runtime: {
        continuity_decay: 'standard'
      }
    };

    socket.sendEvent({
      type: 'config.update_request',
      config: appConfig,
      providers: providersConfig
    });

    onComplete();
  };

  return (
    <div style={{ padding: '3rem', maxWidth: '580px', margin: '4rem auto', background: '#111', color: '#fff', fontFamily: 'sans-serif', borderRadius: '16px', border: '1px solid #282838', boxShadow: '0 20px 60px rgba(0,0,0,0.6)' }}>
      {step === 1 && (
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '13px', color: '#a881ff', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: '12px' }}>
            Phase 0 — Design Partner Edition
          </div>
          <h1 style={{ fontSize: '2.4rem', marginBottom: '1rem', fontWeight: 700, letterSpacing: '-0.02em' }}>Welcome to Arova</h1>
          <p style={{ color: '#aaa', fontSize: '1.15rem', lineHeight: '1.6', margin: '0 auto 2.5rem', maxWidth: '440px' }}>
            <strong>Never lose your train of thought again.</strong><br/>
            Arova remembers what you were doing, why you were doing it, and your settled decisions across projects.
          </p>
          <button onClick={() => setStep(2)} style={{ padding: '14px 36px', background: 'linear-gradient(135deg, #a881ff 0%, #7e52f5 100%)', color: '#fff', border: 'none', borderRadius: '10px', fontSize: '1.1rem', fontWeight: 600, cursor: 'pointer', boxShadow: '0 4px 20px rgba(126, 82, 245, 0.4)', transition: 'all 0.2s ease' }}>
            Get Started →
          </button>
        </div>
      )}

      {step === 2 && (
        <div>
          <div style={{ fontSize: '12px', color: '#a881ff', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: '6px' }}>Step 1 of 2</div>
          <h2 style={{ fontSize: '1.8rem', margin: '0 0 0.5rem 0' }}>Choose AI Provider</h2>
          <p style={{ color: '#aaa', marginBottom: '1.8rem', fontSize: '0.95rem' }}>Select the intelligence engine that will synthesize your workspace understanding.</p>

          {[
            { id: 'groq', title: 'Groq (Recommended)', desc: 'Ultra-fast cloud inference (<1s synthesis).' },
            { id: 'openai', title: 'OpenAI', desc: 'Industry-standard reasoning and trajectory analysis.' },
            { id: 'ollama', title: 'Ollama (Local)', desc: 'Runs entirely on your device with local models.' },
            { id: 'configure_later', title: 'Configure Later', desc: 'Enter Arova directly without AI synthesis.' }
          ].map(opt => (
            <div 
              key={opt.id}
              onClick={() => {
                setIntelligenceSource(opt.id);
                setTestResult(null);
              }}
              style={{ 
                background: intelligenceSource === opt.id ? 'rgba(168, 129, 255, 0.12)' : '#1a1a22',
                padding: '1.1rem', marginBottom: '0.8rem', borderRadius: '10px', cursor: 'pointer',
                border: intelligenceSource === opt.id ? '2px solid #a881ff' : '1px solid #2a2a36',
                transition: 'all 0.2s ease'
              }}
            >
              <h3 style={{ margin: 0, display: 'flex', justifyContent: 'space-between', fontSize: '1.05rem', color: '#fff' }}>
                {opt.title}
                {intelligenceSource === opt.id && <span style={{ fontSize: '0.8rem', color: '#a881ff', fontWeight: 600 }}>Selected</span>}
              </h3>
              <p style={{ color: '#99a', margin: '6px 0 0 0', fontSize: '0.88rem' }}>{opt.desc}</p>
            </div>
          ))}

          <div style={{ display: 'flex', gap: '1rem', marginTop: '2.2rem' }}>
            <button onClick={() => setStep(1)} style={{ padding: '12px 24px', background: '#222', color: '#ccc', border: '1px solid #333', borderRadius: '8px', cursor: 'pointer', fontWeight: 500 }}>Back</button>
            <button 
              onClick={() => {
                if (intelligenceSource === 'configure_later') {
                  handleComplete();
                } else {
                  setStep(3);
                }
              }} 
              style={{ flex: 1, padding: '12px 24px', background: '#fff', color: '#000', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 600 }}
            >
              Continue →
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div>
          <div style={{ fontSize: '12px', color: '#a881ff', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: '6px' }}>Step 2 of 2</div>
          <h2 style={{ fontSize: '1.8rem', margin: '0 0 0.5rem 0' }}>Connect {intelligenceSource === 'groq' ? 'Groq' : intelligenceSource === 'openai' ? 'OpenAI' : 'Ollama'}</h2>
          <p style={{ color: '#aaa', marginBottom: '1.8rem', fontSize: '0.95rem' }}>Verify your credentials to initialize persistent working memory.</p>

          <div style={{ marginTop: '1.5rem' }}>
            {intelligenceSource === 'ollama' ? (
              <>
                <label style={{ display: 'block', color: '#ccc', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: 500 }}>Ollama Host URL</label>
                <input 
                  type="text" 
                  value={ollamaHost} 
                  onChange={e => { setOllamaHost(e.target.value); setTestResult(null); }}
                  style={{ width: '100%', padding: '12px', background: '#1a1a22', color: '#fff', border: '1px solid #3a3a46', borderRadius: '8px', marginBottom: '1rem', fontSize: '0.95rem', boxSizing: 'border-box' }}
                />
              </>
            ) : (
              <>
                <label style={{ display: 'block', color: '#ccc', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: 500 }}>API Key</label>
                <input 
                  type="password" 
                  value={apiKey} 
                  onChange={e => { setApiKey(e.target.value); setTestResult(null); }}
                  placeholder="Paste your secret key..."
                  style={{ width: '100%', padding: '12px', background: '#1a1a22', color: '#fff', border: '1px solid #3a3a46', borderRadius: '8px', marginBottom: '0.8rem', fontSize: '0.95rem', boxSizing: 'border-box' }}
                />
                <p style={{ fontSize: '0.85rem', color: '#888', margin: 0 }}>
                  Don't have a key?{' '}
                  <a href={intelligenceSource === 'groq' ? 'https://console.groq.com/keys' : 'https://platform.openai.com/api-keys'} target="_blank" rel="noreferrer" style={{ color: '#a881ff', textDecoration: 'none' }}>
                    Get one free in 30 seconds →
                  </a>
                </p>
              </>
            )}

            <div style={{ marginTop: '1.8rem', padding: '1.2rem', background: '#17171e', borderRadius: '10px', border: '1px solid #252530', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontSize: '0.9rem', color: '#fff', fontWeight: 500 }}>Connection Status</div>
                <div style={{ fontSize: '0.85rem', color: testResult?.success ? '#4ade80' : testResult?.error ? '#f87171' : '#888', marginTop: '2px' }}>
                  {testing ? 'Testing connection...' : testResult?.success ? `✓ Verified (${testResult.latency_ms}ms response)` : testResult?.error ? `✗ ${testResult.error}` : 'Not tested yet'}
                </div>
              </div>
              <button 
                onClick={testConnection} 
                disabled={testing || (!apiKey && intelligenceSource !== 'ollama')}
                style={{ padding: '8px 16px', background: '#2a2a38', color: '#fff', border: '1px solid #3a3a4a', borderRadius: '6px', cursor: testing ? 'wait' : 'pointer', fontWeight: 500, fontSize: '0.85rem' }}
              >
                {testing ? 'Checking...' : 'Test Connection'}
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '1rem', marginTop: '2.5rem' }}>
            <button onClick={() => setStep(2)} style={{ padding: '12px 24px', background: '#222', color: '#ccc', border: '1px solid #333', borderRadius: '8px', cursor: 'pointer', fontWeight: 500 }}>Back</button>
            <button 
              onClick={handleComplete} 
              disabled={!testResult?.success && intelligenceSource !== 'ollama'}
              style={{ flex: 1, padding: '12px 24px', background: testResult?.success || intelligenceSource === 'ollama' ? 'linear-gradient(135deg, #a881ff 0%, #7e52f5 100%)' : '#262633', color: testResult?.success || intelligenceSource === 'ollama' ? '#fff' : '#666', border: 'none', borderRadius: '8px', cursor: testResult?.success || intelligenceSource === 'ollama' ? 'pointer' : 'not-allowed', fontWeight: 600, boxShadow: testResult?.success ? '0 4px 15px rgba(126, 82, 245, 0.4)' : 'none' }}
            >
              Enter Arova →
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
