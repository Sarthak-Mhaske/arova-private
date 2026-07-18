import React, { useState, useEffect } from 'react';
import { socket } from '../../runtime/socket';

export const OnboardingFlow: React.FC<{ onComplete: () => void }> = ({ onComplete }) => {
  const [step, setStep] = useState(1);
  const [providers, setProviders] = useState<any[]>([]);
  const [recommendedStyle, setRecommendedStyle] = useState('hybrid');
  
  const [presenceStyle, setPresenceStyle] = useState('hybrid');
  const [intelligenceSource, setIntelligenceSource] = useState('configure_later');
  const [apiKey, setApiKey] = useState('');
  const [ollamaHost, setOllamaHost] = useState('http://localhost:11434');
  
  const [workspaceAwareness, setWorkspaceAwareness] = useState(true);
  const [memoryTier, setMemoryTier] = useState('conversations');
  
  const [testResult, setTestResult] = useState<{ success: boolean; latency_ms?: number; error?: string } | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    const handleEvent = (event: any) => {
      const { type, payload } = event.detail;
      if (type === 'provider.discovery') {
        setProviders(payload.providers || []);
        if (payload.recommended_presence_style) {
          setRecommendedStyle(payload.recommended_presence_style);
          setPresenceStyle(payload.recommended_presence_style);
        }
      } else if (type === 'provider.test_result') {
        setTesting(false);
        setTestResult(payload.result);
      }
    };
    
    window.addEventListener('runtime_event', handleEvent);
    
    // Request discovery
    setTimeout(() => {
      socket.sendEvent({ type: 'provider.discovery_request' });
    }, 500);

    return () => window.removeEventListener('runtime_event', handleEvent);
  }, []);

  const handleNext = () => setStep(s => s + 1);

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
    // Generate config updates
    const providersConfig: any = {};
    if (intelligenceSource === 'groq' && testResult?.success) {
      providersConfig.groq = { api_keys: [apiKey] };
    } else if (intelligenceSource === 'openai' && testResult?.success) {
      providersConfig.openai = { api_keys: [apiKey] };
    } else if (intelligenceSource === 'ollama' && testResult?.success) {
      providersConfig.ollama = { host: ollamaHost };
    }

    const appConfig = {
      presence_style: presenceStyle,
      privacy: {
        workspace_awareness: workspaceAwareness,
        memory_enabled: memoryTier !== 'temporary',
        crash_recovery: true
      },
      runtime: {
        continuity_decay: memoryTier === 'deep' ? 'slow' : 'standard'
      }
    };

    socket.sendEvent({
      type: 'config.update_request',
      config: appConfig,
      providers: providersConfig
    });

    onComplete();
  };

  const selectedProviderConfigured = providers.find(p => p.id === intelligenceSource)?.configured;

  return (
    <div style={{ padding: '3rem', maxWidth: '650px', margin: '4rem auto', background: '#111', color: '#fff', fontFamily: 'sans-serif', borderRadius: '16px', boxShadow: '0 20px 60px rgba(0,0,0,0.5)' }}>
      {step === 1 && (
        <div style={{ textAlign: 'center' }}>
          <h1 style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>Welcome to Arova</h1>
          <p style={{ color: '#aaa', fontSize: '1.2rem', lineHeight: '1.5' }}>
            A cognitive operating system that helps maintain<br/>continuity across your work, thoughts, and projects.
          </p>
          <button onClick={handleNext} style={{ marginTop: '3rem', padding: '12px 30px', background: '#fff', color: '#000', border: 'none', borderRadius: '8px', fontSize: '1.1rem', cursor: 'pointer' }}>Continue</button>
        </div>
      )}

      {step === 2 && (
        <div>
          <h2>Choose Presence Style</h2>
          <p style={{ color: '#aaa', marginBottom: '2rem' }}>How should Arova process cognition?</p>
          
          {[
            { id: 'instant', title: 'Instant', desc: 'Fastest responses using cloud intelligence.' },
            { id: 'hybrid', title: 'Hybrid', desc: 'Balanced local and cloud intelligence.' },
            { id: 'local', title: 'Local', desc: 'Runs entirely on your device. Maximum privacy.' }
          ].map(opt => (
            <div 
              key={opt.id}
              onClick={() => setPresenceStyle(opt.id)}
              style={{ 
                background: '#222', padding: '1.2rem', marginBottom: '1rem', borderRadius: '8px', cursor: 'pointer',
                border: presenceStyle === opt.id ? '2px solid #5a5' : '1px solid #333'
              }}
            >
              <h3 style={{ margin: 0, display: 'flex', justifyContent: 'space-between' }}>
                {opt.title}
                {recommendedStyle === opt.id && <span style={{ fontSize: '0.8rem', color: '#5a5', padding: '2px 8px', background: '#131', borderRadius: '4px' }}>Recommended</span>}
              </h3>
              <p style={{ color: '#aaa', margin: '8px 0 0 0' }}>{opt.desc}</p>
            </div>
          ))}
          
          <button onClick={handleNext} style={{ marginTop: '2rem', padding: '10px 24px', background: '#fff', color: '#000', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>Continue</button>
        </div>
      )}

      {step === 3 && (
        <div>
          <h2>Choose Intelligence Source</h2>
          <p style={{ color: '#aaa', marginBottom: '2rem' }}>Arova needs an intelligence engine to power its presence.</p>

          {[
            { id: 'groq', title: 'Groq (Recommended)', desc: 'Fast cloud inference. Data leaves your device.', cost: 'Determined by your Groq account usage.' },
            { id: 'openai', title: 'OpenAI', desc: 'Advanced reasoning. Data leaves your device.', cost: 'Determined by your OpenAI account usage.' },
            { id: 'ollama', title: 'Ollama', desc: 'Runs locally. Requires local hardware resources.', cost: 'No API charges.' },
            { id: 'configure_later', title: 'Configure Later', desc: 'Use Arova without AI responses for now.', cost: 'Free.' }
          ].filter(opt => {
            if (presenceStyle === 'local') return ['ollama', 'configure_later'].includes(opt.id);
            if (presenceStyle === 'instant') return ['groq', 'openai', 'configure_later'].includes(opt.id);
            return true;
          }).map(opt => {
            const disc = providers.find(p => p.id === opt.id);
            return (
              <div 
                key={opt.id}
                onClick={() => setIntelligenceSource(opt.id)}
                style={{ 
                  background: '#222', padding: '1.2rem', marginBottom: '1rem', borderRadius: '8px', cursor: 'pointer',
                  border: intelligenceSource === opt.id ? '2px solid #5a5' : '1px solid #333'
                }}
              >
                <h3 style={{ margin: 0, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  {opt.title}
                  {disc?.available && <span style={{ fontSize: '0.8rem', color: '#5a5' }}>✓ Ready</span>}
                </h3>
                <p style={{ color: '#aaa', margin: '8px 0 4px 0' }}>{opt.desc}</p>
                <p style={{ color: '#888', margin: 0, fontSize: '0.85rem' }}>Cost: {opt.cost}</p>
              </div>
            );
          })}

          <div style={{ display: 'flex', gap: '1rem', marginTop: '2rem' }}>
            <button onClick={() => setStep(2)} style={{ padding: '10px 24px', background: '#333', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>Back</button>
            <button onClick={() => {
              if (intelligenceSource === 'configure_later') setStep(5); // Skip setup
              else if (selectedProviderConfigured) setStep(5); // Skip setup if already configured
              else setStep(4);
            }} style={{ padding: '10px 24px', background: '#fff', color: '#000', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>Continue</button>
          </div>
        </div>
      )}

      {step === 4 && (
        <div>
          <h2>Connect {intelligenceSource === 'groq' ? 'Groq' : intelligenceSource === 'openai' ? 'OpenAI' : 'Ollama'}</h2>
          
          <div style={{ marginTop: '2rem' }}>
            {intelligenceSource === 'ollama' ? (
              <>
                <label style={{ display: 'block', color: '#aaa', marginBottom: '0.5rem' }}>Ollama Host URL</label>
                <input 
                  type="text" 
                  value={ollamaHost} 
                  onChange={e => setOllamaHost(e.target.value)}
                  style={{ width: '100%', padding: '12px', background: '#222', color: '#fff', border: '1px solid #444', borderRadius: '6px', marginBottom: '1rem' }}
                />
              </>
            ) : (
              <>
                <label style={{ display: 'block', color: '#aaa', marginBottom: '0.5rem' }}>API Key</label>
                <input 
                  type="password" 
                  value={apiKey} 
                  onChange={e => { setApiKey(e.target.value); setTestResult(null); }}
                  placeholder="Paste your API key here..."
                  style={{ width: '100%', padding: '12px', background: '#222', color: '#fff', border: '1px solid #444', borderRadius: '6px', marginBottom: '1rem' }}
                />
                <p style={{ fontSize: '0.9rem', color: '#888' }}>
                  Don't have a key?{' '}
                  <a href={intelligenceSource === 'groq' ? 'https://console.groq.com' : 'https://platform.openai.com'} target="_blank" style={{ color: '#5a5', textDecoration: 'none' }}>
                    Get a free API key →
                  </a>
                </p>
              </>
            )}

            <div style={{ marginTop: '2rem', padding: '1rem', background: '#1a1a1a', borderRadius: '8px' }}>
              <button 
                onClick={testConnection} 
                disabled={testing || (!apiKey && intelligenceSource !== 'ollama')}
                style={{ padding: '8px 16px', background: '#333', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', opacity: testing ? 0.5 : 1 }}
              >
                {testing ? 'Testing...' : 'Test Connection'}
              </button>
              
              {testResult && (
                <div style={{ marginTop: '1rem', color: testResult.success ? '#5a5' : '#a55' }}>
                  {testResult.success ? `✓ Connected (Latency: ${testResult.latency_ms}ms)` : `✗ ${testResult.error}`}
                </div>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', gap: '1rem', marginTop: '3rem' }}>
            <button onClick={() => setStep(3)} style={{ padding: '10px 24px', background: '#333', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>Back</button>
            <button 
              onClick={handleNext} 
              disabled={!testResult?.success}
              style={{ padding: '10px 24px', background: testResult?.success ? '#fff' : '#444', color: testResult?.success ? '#000' : '#888', border: 'none', borderRadius: '6px', cursor: testResult?.success ? 'pointer' : 'not-allowed' }}
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {step === 5 && (
        <div>
          <h2>Workspace Awareness</h2>
          <p style={{ color: '#aaa', marginBottom: '2rem' }}>Allow Arova to understand which applications you are using to improve continuity. All analysis remains local to your device.</p>
          
          {[
            { id: true, title: 'Enable', desc: 'Arova will sense context automatically.' },
            { id: false, title: 'Disable', desc: 'Arova will only know what you explicitly tell it.' }
          ].map(opt => (
            <div 
              key={opt.id ? 'yes' : 'no'}
              onClick={() => setWorkspaceAwareness(opt.id)}
              style={{ 
                background: '#222', padding: '1.2rem', marginBottom: '1rem', borderRadius: '8px', cursor: 'pointer',
                border: workspaceAwareness === opt.id ? '2px solid #5a5' : '1px solid #333'
              }}
            >
              <h3 style={{ margin: 0 }}>{opt.title}</h3>
              <p style={{ color: '#aaa', margin: '8px 0 0 0' }}>{opt.desc}</p>
            </div>
          ))}

          <div style={{ display: 'flex', gap: '1rem', marginTop: '3rem' }}>
            <button onClick={() => setStep(selectedProviderConfigured || intelligenceSource === 'configure_later' ? 3 : 4)} style={{ padding: '10px 24px', background: '#333', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>Back</button>
            <button onClick={handleNext} style={{ padding: '10px 24px', background: '#fff', color: '#000', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>Continue</button>
          </div>
        </div>
      )}

      {step === 6 && (
        <div>
          <h2>Memory & Continuity</h2>
          <p style={{ color: '#aaa', marginBottom: '2rem' }}>How should Arova remember you?</p>
          
          {[
            { id: 'temporary', title: 'Temporary', desc: 'Nothing persists after closing Arova.' },
            { id: 'conversations', title: 'Remember Conversations', desc: 'Threads persist across sessions.' },
            { id: 'deep', title: 'Long-Term Presence', desc: 'Threads and memories persist over time.' }
          ].map(opt => (
            <div 
              key={opt.id}
              onClick={() => setMemoryTier(opt.id)}
              style={{ 
                background: '#222', padding: '1.2rem', marginBottom: '1rem', borderRadius: '8px', cursor: 'pointer',
                border: memoryTier === opt.id ? '2px solid #5a5' : '1px solid #333'
              }}
            >
              <h3 style={{ margin: 0 }}>{opt.title}</h3>
              <p style={{ color: '#aaa', margin: '8px 0 0 0' }}>{opt.desc}</p>
            </div>
          ))}

          <div style={{ display: 'flex', gap: '1rem', marginTop: '3rem' }}>
            <button onClick={() => setStep(5)} style={{ padding: '10px 24px', background: '#333', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>Back</button>
            <button onClick={handleNext} style={{ padding: '10px 24px', background: '#fff', color: '#000', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>Continue</button>
          </div>
        </div>
      )}

      {step === 7 && (
        <div>
          <h2 style={{ fontSize: '2.5rem', marginBottom: '2rem', textAlign: 'center' }}>Arova is Ready</h2>
          
          <div style={{ background: '#1a1a1a', padding: '2rem', borderRadius: '12px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
              <div>
                <div style={{ color: '#888', fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '1px' }}>Presence Style</div>
                <div style={{ fontSize: '1.2rem', marginTop: '0.5rem', textTransform: 'capitalize' }}>{presenceStyle}</div>
              </div>
              <div>
                <div style={{ color: '#888', fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '1px' }}>Intelligence</div>
                <div style={{ fontSize: '1.2rem', marginTop: '0.5rem', textTransform: 'capitalize' }}>{intelligenceSource === 'configure_later' ? 'None (Configure Later)' : intelligenceSource}</div>
              </div>
              <div>
                <div style={{ color: '#888', fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '1px' }}>Workspace Awareness</div>
                <div style={{ fontSize: '1.2rem', marginTop: '0.5rem' }}>{workspaceAwareness ? 'Enabled' : 'Disabled'}</div>
              </div>
              <div>
                <div style={{ color: '#888', fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '1px' }}>Memory</div>
                <div style={{ fontSize: '1.2rem', marginTop: '0.5rem' }}>
                  {memoryTier === 'temporary' ? 'Temporary' : memoryTier === 'conversations' ? 'Remember Conversations' : 'Long-Term Presence'}
                </div>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '1rem', marginTop: '3rem', justifyContent: 'center' }}>
            <button onClick={() => setStep(6)} style={{ padding: '12px 30px', background: '#333', color: '#fff', border: 'none', borderRadius: '8px', fontSize: '1.1rem', cursor: 'pointer' }}>Back</button>
            <button onClick={handleComplete} style={{ padding: '12px 30px', background: '#5a5', color: '#fff', border: 'none', borderRadius: '8px', fontSize: '1.1rem', cursor: 'pointer', fontWeight: 'bold' }}>Enter Arova</button>
          </div>
        </div>
      )}
    </div>
  );
};
