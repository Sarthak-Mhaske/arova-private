import React, { useEffect, useState } from 'react';
import { useCognitionState, useSurfaceState } from '../../state';
import { socket } from '../../runtime/socket';

const PROVIDER_MODEL_NAMES: Record<string, string> = {
  groq: 'GPT OSS 120B / Qwen 3.6 (Groq LPU)',
  openai: 'GPT-5.6 Sol / o3 (OpenAI)',
  gemini: 'Gemini 3.1 Pro / 3.7 Flash (Google AI)',
  anthropic: 'Claude Sonnet 5 / Fable 5 (Anthropic)',
  ollama: 'GPT OSS 120B / Qwen 3 (Local Ollama)',
  lmstudio: 'LM Studio (Local)',
  openrouter: 'Frontier Swarm (OpenRouter)',
  mock: 'Local Simulation Engine'
};

export const CognitionSurface: React.FC = () => {
  const { threads, memories, lastExecutionMetadata } = useCognitionState();
  const { openSurface } = useSurfaceState();
  const [preferredProvider, setPreferredProvider] = useState<string>('gemini');

  useEffect(() => {
    const handleConfigSync = (e: any) => {
      const ev = e.detail;
      if (ev && ev.type === 'config.sync' && ev.config?.preferred_provider) {
        setPreferredProvider(ev.config.preferred_provider);
      }
    };
    window.addEventListener('arova-event', handleConfigSync);
    socket.sendEvent({ type: 'config.get_request' });
    socket.sendEvent({ type: 'memory.query_request', req_id: 'cog_init' });

    return () => {
      window.removeEventListener('arova-event', handleConfigSync);
    };
  }, []);

  const activeModelDisplay = lastExecutionMetadata?.model_name 
    ? lastExecutionMetadata.model_name 
    : (PROVIDER_MODEL_NAMES[preferredProvider] || 'Gemini 2.5 Pro (Google AI)');

  return (
    <div className="surface-content" style={{ padding: '32px 36px', height: '100%', display: 'flex', flexDirection: 'column', overflowY: 'auto', boxSizing: 'border-box' }}>
      {/* Surface Header */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--ink)', letterSpacing: '-0.02em' }}>Cognition Overview</div>
        <div style={{ fontSize: '13px', color: 'var(--ink-3)', marginTop: '4px', lineHeight: '1.5' }}>
          Live summary of active cognitive threads, episodic memory storage, and model execution state.
        </div>
      </div>

      {/* Top Telemetry Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '14px', marginBottom: '24px' }}>
        <div style={{ padding: '18px 20px', background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px' }}>
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', letterSpacing: '0.08em', fontWeight: 600, textTransform: 'uppercase' }}>Active Threads</div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: 'var(--ink)', marginTop: '4px' }}>{threads.length}</div>
        </div>

        <div style={{ padding: '18px 20px', background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px' }}>
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', letterSpacing: '0.08em', fontWeight: 600, textTransform: 'uppercase' }}>Saved Memories</div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: 'var(--ink)', marginTop: '4px' }}>{memories.length}</div>
        </div>

        <div style={{ padding: '18px 20px', background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px' }}>
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', letterSpacing: '0.08em', fontWeight: 600, textTransform: 'uppercase' }}>Active AI Model</div>
          <div style={{ fontSize: '15px', fontWeight: 600, color: '#4caf50', marginTop: '6px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {activeModelDisplay}
          </div>
        </div>
      </div>

      {/* Main Content Grid (Stack on smaller screens) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '18px', marginBottom: '24px' }}>
        {/* Cognitive Threads Section */}
        <div style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', padding: '20px 24px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--ink)' }}>Cognitive Threads</div>
            <button 
              style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid var(--hairline-2)', color: 'var(--ink-2)', padding: '4px 12px', borderRadius: '6px', fontSize: '12px', cursor: 'pointer', fontWeight: 500, transition: 'all 0.2s' }}
              onClick={() => openSurface('threads')}
            >
              Manage →
            </button>
          </div>

          {threads.length === 0 ? (
            <div style={{ fontSize: '13px', color: 'var(--ink-3)', fontStyle: 'italic', padding: '16px', textAlign: 'center', background: 'var(--glass-2)', border: '1px solid var(--hairline-2)', borderRadius: '10px' }}>
              No background threads active. Standard conversational context enabled.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {threads.slice(0, 5).map((t: any, i: number) => (
                <div key={i} style={{ padding: '12px 14px', background: 'var(--glass-2)', border: '1px solid var(--hairline-2)', borderRadius: '10px', fontSize: '13px', color: 'var(--ink)', lineHeight: '1.4' }}>
                  {t.title || t.summary || `Thread ${t.id || i + 1}`}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Episodic Memory Section */}
        <div style={{ background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '14px', padding: '20px 24px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ fontWeight: 600, fontSize: '15px', color: 'var(--ink)' }}>Episodic Memory</div>
            <button 
              style={{ background: 'var(--glass-2)', border: '1px solid var(--hairline-2)', color: 'var(--ink-2)', padding: '4px 12px', borderRadius: '6px', fontSize: '12px', cursor: 'pointer', fontWeight: 500, transition: 'all 0.2s' }}
              onClick={() => openSurface('memory')}
            >
              View All →
            </button>
          </div>

          {memories.length === 0 ? (
            <div style={{ fontSize: '13px', color: 'var(--ink-3)', fontStyle: 'italic', padding: '16px', textAlign: 'center', background: 'var(--glass-2)', border: '1px solid var(--hairline-2)', borderRadius: '10px' }}>
              Episodic memory empty or sync pending. Memories form automatically as you converse.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {memories.slice(0, 5).map((m: any, i: number) => (
                <div key={i} style={{ padding: '12px 14px', background: 'var(--glass-2)', border: '1px solid var(--hairline-2)', borderRadius: '10px', fontSize: '13px', color: 'var(--ink)', lineHeight: '1.5', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {m.text || m.summary || m.content || `Memory ${i + 1}`}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
