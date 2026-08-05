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
    if (intelligenceSource === 'gemini' && apiKey) {
      providersConfig.gemini = { api_keys: [apiKey] };
    } else if (intelligenceSource === 'anthropic' && apiKey) {
      providersConfig.anthropic = { api_keys: [apiKey] };
    } else if (intelligenceSource === 'groq' && apiKey) {
      providersConfig.groq = { api_keys: [apiKey] };
    } else if (intelligenceSource === 'openai' && apiKey) {
      providersConfig.openai = { api_keys: [apiKey] };
    } else if (intelligenceSource === 'ollama') {
      providersConfig.ollama = { host: ollamaHost };
    }

    const appConfig = {
      presence_style: 'hybrid',
      preferred_provider: intelligenceSource,
      allow_fallback: true,
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
    <div style={{ padding: '3rem', maxWidth: '560px', margin: '4rem auto', background: '#111', color: '#fff', fontFamily: 'sans-serif', borderRadius: '16px', border: '1px solid #282838', boxShadow: '0 20px 60px rgba(0,0,0,0.6)' }}>
      {step === 1 && (
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '13px', color: '#a881ff', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: '12px' }}>
            Design Partner Beta
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
          <h2 style={{ fontSize: '1.8rem', margin: '0 0 0.5rem 0' }}>Choose Intelligence Engine</h2>
          <p style={{ color: '#aaa', marginBottom: '1.5rem', fontSize: '0.95rem' }}>Select your primary model provider to synthesize your workspace understanding.</p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.8rem', marginBottom: '1.8rem' }}>
            {[
              { id: 'gemini', title: 'Gemini 2.5 Pro', desc: 'Recommended' },
              { id: 'anthropic', title: 'Claude Sonnet 4', desc: 'Reasoning' },
              { id: 'openai', title: 'GPT-5', desc: 'Standard' },
              { id: 'groq', title: 'Groq Llama 3.3', desc: 'Fast Cloud' },
              { id: 'ollama', title: 'Ollama', desc: 'Local / Free' }
            ].map(opt => (
              <div 
                key={opt.id}
                onClick={() => {
                  setIntelligenceSource(opt.id);
                  setTestResult(null);
                }}
                style={{ 
                  background: intelligenceSource === opt.id ? 'rgba(168, 129, 255, 0.15)' : '#1a1a22',
                  padding: '0.8rem 1rem', borderRadius: '10px', cursor: 'pointer', textAlign: 'left',
                  border: intelligenceSource === opt.id ? '2px solid #a881ff' : '1px solid #2a2a36',
                  transition: 'all 0.2s ease'
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.95rem', color: '#fff' }}>{opt.title}</div>
                <div style={{ fontSize: '0.75rem', color: '#889', marginTop: '2px' }}>{opt.desc}</div>
              </div>
            ))}
          </div>

          <div style={{ background: '#16161e', padding: '1.2rem', borderRadius: '10px', border: '1px solid #262634', marginBottom: '2rem' }}>
            {intelligenceSource === 'ollama' ? (
              <>
                <label style={{ display: 'block', color: '#ccc', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: 500 }}>Ollama Host URL</label>
                <input 
                  type="text" 
                  value={ollamaHost} 
                  onChange={e => { setOllamaHost(e.target.value); setTestResult(null); }}
                  style={{ width: '100%', padding: '10px', background: '#20202a', color: '#fff', border: '1px solid #3a3a46', borderRadius: '8px', fontSize: '0.95rem', boxSizing: 'border-box' }}
                />
              </>
            ) : (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <label style={{ color: '#ccc', fontSize: '0.9rem', fontWeight: 500 }}>
                    {intelligenceSource === 'gemini' ? 'Gemini API Key' : intelligenceSource === 'anthropic' ? 'Anthropic API Key' : intelligenceSource === 'groq' ? 'Groq API Key' : 'OpenAI API Key'}
                  </label>
                </div>
                <input 
                  type="password" 
                  value={apiKey} 
                  onChange={e => { setApiKey(e.target.value); setTestResult(null); }}
                  placeholder={`Paste secret API key...`}
                  style={{ width: '100%', padding: '10px', background: '#20202a', color: '#fff', border: '1px solid #3a3a46', borderRadius: '8px', fontSize: '0.95rem', boxSizing: 'border-box' }}
                />
              </>
            )}

            {(apiKey || intelligenceSource === 'ollama') && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '1rem', paddingTop: '0.8rem', borderTop: '1px solid #222230' }}>
                <span style={{ fontSize: '0.85rem', color: testResult?.success ? '#4ade80' : testResult?.error ? '#f87171' : '#888' }}>
                  {testing ? 'Testing...' : testResult?.success ? `✓ Verified (${testResult.latency_ms}ms)` : testResult?.error ? `✗ ${testResult.error}` : ''}
                </span>
                <button onClick={testConnection} disabled={testing} style={{ padding: '6px 12px', background: '#2a2a38', color: '#ccc', border: '1px solid #3a3a4a', borderRadius: '6px', fontSize: '0.8rem', cursor: 'pointer' }}>
                  {testResult?.success ? 'Re-test' : 'Test Connection'}
                </button>
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: '1rem' }}>
            <button onClick={() => setStep(1)} style={{ padding: '12px 20px', background: '#222', color: '#ccc', border: '1px solid #333', borderRadius: '8px', cursor: 'pointer', fontWeight: 500 }}>Back</button>
            <button 
              onClick={handleComplete} 
              style={{ flex: 1, padding: '12px 24px', background: 'linear-gradient(135deg, #a881ff 0%, #7e52f5 100%)', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 600, boxShadow: '0 4px 15px rgba(126, 82, 245, 0.4)' }}
            >
              Enter Arova →
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
