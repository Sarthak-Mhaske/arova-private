import React, { useState, useRef } from 'react';
import { useCognitionState, useAwarenessState } from '../../state';
import { socket } from '../../runtime/socket';

interface ModelOption {
  id: string;
  name: string;
  provider: string;
  category: 'fast' | 'frontier' | 'local';
  goodAt: string;
  tag: string;
}

const MODEL_OPTIONS: ModelOption[] = [
  // Fast & Coding (Groq LPU)
  { id: 'qwen-3.6-27b', name: 'Qwen 3.6 27B', provider: 'Groq LPU', category: 'fast', goodAt: 'Fast multilingual reasoning & active code refactoring', tag: 'Fast / Code' },
  { id: 'openai/gpt-oss-120b', name: 'GPT OSS 120B', provider: 'Groq LPU', category: 'fast', goodAt: 'High-throughput enterprise code generation & API reasoning', tag: 'Enterprise Code' },
  { id: 'llama-3.1-8b-instant', name: 'Llama 3.1 8B Instant', provider: 'Groq LPU', category: 'fast', goodAt: 'Sub-second conversation & quick questions', tag: 'Sub-Second' },
  { id: 'deepseek-r1-distill-llama-70b', name: 'DeepSeek R1 Distill 70B', provider: 'Groq LPU', category: 'fast', goodAt: 'Complex math proofing & algorithmic logic on LPU', tag: 'Math / Logic' },
  
  // Deep Frontier Reasoning
  { id: 'gpt-5.6-sol', name: 'GPT-5.6 Sol', provider: 'OpenAI', category: 'frontier', goodAt: 'Flagship creative intelligence, multimodal assets & architecture', tag: 'Flagship' },
  { id: 'o3', name: 'OpenAI o3', provider: 'OpenAI', category: 'frontier', goodAt: 'Deep test-time compute thought chains & hard problem solving', tag: 'Deep Thought' },
  { id: 'claude-sonnet-5', name: 'Claude Sonnet 5', provider: 'Anthropic', category: 'frontier', goodAt: 'Software engineering, multi-file AST diffs & rich markdown', tag: 'Code Specialist' },
  { id: 'claude-fable-5', name: 'Claude Fable 5', provider: 'Anthropic', category: 'frontier', goodAt: 'Multi-step autonomous business strategy & technical audits', tag: 'Strategy' },
  { id: 'gemini-3.1-pro', name: 'Gemini 3.1 Pro', provider: 'Google AI', category: 'frontier', goodAt: '2M token full repo context analysis & continuous video understanding', tag: '2M Context' },
  { id: 'gemini-3.7-flash', name: 'Gemini 3.7 Flash', provider: 'Google AI', category: 'frontier', goodAt: 'Fast live developer feedback loop & hybrid reasoning', tag: 'Fast Hybrid' },
  
  // Local & Private
  { id: 'gpt-oss:120b', name: 'GPT OSS 120B (Local)', provider: 'Ollama', category: 'local', goodAt: '100% private on-device open weights for enterprise privacy', tag: 'Private' },
  { id: 'qwen3:32b', name: 'Qwen 3 32B (Local)', provider: 'Ollama', category: 'local', goodAt: 'Local offline coding & chat without cloud connectivity', tag: 'Offline' }
];

export const CommandZone: React.FC = () => {
  const [val, setVal] = useState('');
  const [vocalize, setVocalize] = useState(false); // MUTED BY DEFAULT ALWAYS
  const [micActive, setMicActive] = useState(false); // MIC OFF BY DEFAULT
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>(() => {
    return localStorage.getItem('arova_preferred_model') || 'auto';
  });
  const [showModelMenu, setShowModelMenu] = useState(false);
  const lastSubmitRef = useRef<{ text: string; ts: number }>({ text: '', ts: 0 });
  // TIER 1.3: @-mention autocomplete
  const [showMentions, setShowMentions] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [mentionStart, setMentionStart] = useState<number | null>(null);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const modelMenuRef = useRef<HTMLDivElement>(null);
  const { activeWorkspace } = useAwarenessState();

  const handleSelectModel = (modelId: string) => {
    setSelectedModel(modelId);
    localStorage.setItem('arova_preferred_model', modelId);
    setShowModelMenu(false);
  };

  // Build suggestion list from verbatim RealityLayer.resources + search index fallback
  const allResources = React.useMemo(() => {
    const resourcesObj = (activeWorkspace as any)?.reality?.resources || {};
    return Object.keys(resourcesObj).map((k: string) => {
      const r: any = resourcesObj[k];
      return r?.identity || k;
    });
  }, [activeWorkspace]);
  
  // Filter by mention query
  const filteredSuggestions = React.useMemo(() => {
    if (!showMentions) return [];
    const q = mentionQuery.toLowerCase();
    if (!q) return allResources.slice(0, 50);
    return allResources.filter(r => r.toLowerCase().includes(q)).slice(0, 50);
  }, [showMentions, mentionQuery, allResources]);

  const clearChat = () => {
    socket.sendEvent({ type: 'client.new_thread' });
    useCognitionState.getState().setItems([]);
    useCognitionState.getState().setActiveAction(null);
    import('../../state/orbState').then(({ useOrbState }) => {
      useOrbState.getState().setMode('idle', '');
    });
    import('../../state/awarenessState').then(({ useAwarenessState }) => {
      useAwarenessState.getState().resetContinueCard();
    });
  };

  const fireInterrupt = () => {
    socket.sendEvent({ type: 'client.interrupt' });
  };

  const handleToggleSpeaker = () => {
    if (isSpeaking) {
      fireInterrupt();
      setIsSpeaking(false);
      return;
    }
    const nextState = !vocalize;
    setVocalize(nextState);
    if (!nextState) {
      fireInterrupt();
    }
  };

  const handleToggleMic = () => {
    const nextState = !micActive;
    setMicActive(nextState);
    socket.sendEvent({
      type: 'voice.set_mic',
      enabled: nextState
    });
  };

  const extractMentions = (text: string): string[] => {
    const re = /@([\w./\-\:]+)/g;
    const out: string[] = [];
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      out.push(m[1]);
    }
    return out;
  };

  const submit = () => {
    const trimmed = val.trim();
    if (!trimmed) return;
    
    // Rigid duplicate guard: block identical text within 3 seconds
    const now = Date.now();
    if (trimmed === lastSubmitRef.current.text && (now - lastSubmitRef.current.ts) < 3000) {
      console.warn('[CommandZone] Duplicate submit blocked:', trimmed);
      return;
    }
    lastSubmitRef.current = { text: trimmed, ts: now };
    
    if (trimmed === '/clear') {
      clearChat();
      setVal('');
      setShowMentions(false);
      return;
    }
    
    const mentions = extractMentions(val);
    const payload: any = {
      type: 'user.message',
      text: val.trim(),
      vocalize,
      mentions
    };
    console.log('[CommandZone] Sending user.message (vocalize=' + vocalize + ', mentions=' + mentions.length + '):', payload);
    socket.sendEvent(payload);
    setVal('');
    setShowMentions(false);
  };

  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showMentions) {
          setShowMentions(false);
          e.preventDefault();
          return;
        }
        fireInterrupt();
        const input = document.getElementById('command-input');
        if (input) input.blur();
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        const input = document.getElementById('command-input');
        if (input) input.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [showMentions]);

  React.useEffect(() => {
    const handleArovaEvent = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail && detail.type === 'voice.mic_state') {
        setMicActive(Boolean(detail.enabled));
      } else if (detail && detail.type === 'voice.speaker_state') {
        setIsSpeaking(Boolean(detail.speaking));
      } else if (detail && detail.type === 'voice.partial_transcript') {
        if (detail.transcript) {
          setVal(detail.transcript);
        }
      }
    };
    window.addEventListener('arova-event', handleArovaEvent);
    return () => window.removeEventListener('arova-event', handleArovaEvent);
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newVal = e.target.value;
    setVal(newVal);
    
    // Detect @ mention trigger: last @ before cursor
    const cursor = e.target.selectionStart ?? newVal.length;
    const beforeCursor = newVal.slice(0, cursor);
    const atIdx = beforeCursor.lastIndexOf('@');
    if (atIdx !== -1) {
      const afterAt = beforeCursor.slice(atIdx + 1);
      // If after @ contains space or newline, not a mention
      if (!afterAt.includes(' ') && !afterAt.includes('\n')) {
        setMentionStart(atIdx);
        setMentionQuery(afterAt);
        setShowMentions(true);
        setSelectedIdx(0);
        // Optional: emit search.query for semantic search
        if (afterAt.length >= 1) {
          socket.sendEvent({ type: 'search.query', query: afterAt });
        }
        return;
      }
    }
    setShowMentions(false);
  };

  const handleSelectMention = (suggestion: string) => {
    if (mentionStart === null) return;
    const before = val.slice(0, mentionStart);
    const after = val.slice(mentionStart + 1 + mentionQuery.length);
    // Use basename for display, but keep full path as mention token for grounding
    const token = suggestion.includes('/') ? suggestion : suggestion;
    const newVal = `${before}@${token} ${after}`.replace(/\s+/g, ' ');
    setVal(newVal);
    setShowMentions(false);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  React.useEffect(() => {
    if (showMentions && dropdownRef.current) {
      const selectedEl = dropdownRef.current.children[selectedIdx + 1] as HTMLElement;
      if (selectedEl && typeof selectedEl.scrollIntoView === 'function') {
        selectedEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }
  }, [selectedIdx, showMentions]);

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (showMentions && filteredSuggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIdx(prev => (prev + 1) % filteredSuggestions.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIdx(prev => (prev - 1 + filteredSuggestions.length) % filteredSuggestions.length);
        return;
      }
      if (e.key === 'Tab' || (e.key === 'Enter' && showMentions && filteredSuggestions.length > 0 && mentionQuery.length >= 0)) {
        // If dropdown visible, Enter selects instead of submitting (unless no suggestions)
        if (showMentions && filteredSuggestions.length > 0) {
          // Only intercept if user is actively picking (query length 0-? or selected)
          // If they typed full mention and hit Enter, we still want to select if dropdown open
          // We check if mentionQuery is substring of selected suggestion
          const sel = filteredSuggestions[selectedIdx];
          if (sel && (mentionQuery === '' || sel.toLowerCase().includes(mentionQuery.toLowerCase()))) {
            e.preventDefault();
            handleSelectMention(sel);
            return;
          }
        }
      }
      if (e.key === 'Escape') {
        setShowMentions(false);
        return;
      }
    }
    if (e.key === 'Enter' && !showMentions && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    } else if (e.key === 'Enter' && showMentions) {
      // If dropdown still open but we didn't handle above, allow submit
      // Close dropdown then submit on next Enter
      if (filteredSuggestions.length === 0) {
        setShowMentions(false);
      }
    }
  };

  const modelDisplayLabel = React.useMemo(() => {
    if (selectedModel === 'auto') return 'Auto (Dynamic)';
    const found = MODEL_OPTIONS.find(m => m.id === selectedModel);
    if (!found) return selectedModel;
    return found.name;
  }, [selectedModel]);

  const activeAction = useCognitionState(s => s.activeAction);

  return (
    <div className="command-zone">
      {activeAction && (
        <div className="active-action-overlay">
          <svg className="spinner" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <circle cx="12" cy="12" r="10" strokeDasharray="32" strokeDashoffset="12"/>
          </svg>
          <span className="action-text">{activeAction}...</span>
        </div>
      )}

      {/* TIER 1.3: @-mention autocomplete dropdown */}
      {showMentions && (
        <div 
          ref={dropdownRef}
          style={{
            position: 'absolute',
            bottom: '62px',
            left: '12px',
            right: '12px',
            background: 'var(--glass-1, rgba(30,30,40,0.95))',
            border: '1px solid var(--hairline-2, rgba(255,255,255,0.1))',
            borderRadius: '12px',
            padding: '6px',
            maxHeight: '240px',
            overflowY: 'auto',
            pointerEvents: 'auto',
            zIndex: 50,
            backdropFilter: 'blur(12px)',
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)'
          }}
        >
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', padding: '4px 8px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            {mentionQuery ? `Mention matching "${mentionQuery}"` : 'Your verbatim workspace resources — @ to ground'}
          </div>
          {filteredSuggestions.length > 0 ? filteredSuggestions.map((s, idx) => (
            <div
              key={s + idx}
              onClick={() => handleSelectMention(s)}
              style={{
                padding: '8px 10px',
                borderRadius: '8px',
                cursor: 'pointer',
                background: idx === selectedIdx ? 'var(--glass-2, rgba(255,255,255,0.08))' : 'transparent',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                border: idx === selectedIdx ? '1px solid var(--accent-gold, #c9a86a)' : '1px solid transparent'
              }}
            >
              <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: '13px', color: 'var(--ink, #fff)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s}</span>
              <span style={{ fontSize: '11px', color: 'var(--ink-3)', marginLeft: '8px' }}>↩</span>
            </div>
          )) : (
            <div style={{ padding: '8px 10px', fontSize: '12px', color: 'var(--ink-3)', fontStyle: 'italic' }}>
              No matching resources. Try typing a file name (e.g., @runtime.py)
            </div>
          )}
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', padding: '6px 8px 2px', borderTop: '1px solid var(--hairline-2)', marginTop: '4px' }}>
            ↑↓ navigate · Enter select · Esc close · <span style={{ color: 'var(--accent-gold)' }}>Verbatim grounding</span>
          </div>
        </div>
      )}

      {/* Row containing the Chat Bar and the Wide & Small Model Pill on the RIGHT */}
      <div 
        className="command-row"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          width: 'min(720px, calc(100% - 40px))',
          margin: '0 auto',
          position: 'relative'
        }}
      >
        {/* Main Command Bar */}
        <div className="command" style={{ flex: 1, width: 'auto' }}>
          <span className="leader"></span>
          <input 
            ref={inputRef}
            id="command-input"
            type="text" 
            placeholder="Ask Arova about your work, decisions, or understanding..."  
            value={val}
            onChange={handleChange}
            onKeyDown={handleInputKeyDown}
            autoComplete="off"
          />
          <div className="actions">
            <button 
              className={`cmd-btn ${isSpeaking ? 'active speaker-speaking' : vocalize ? 'active' : ''}`} 
              title={isSpeaking ? 'Arova is speaking — click to stop speech instantly' : vocalize ? 'Speaker: ON (Arova will speak)' : 'Speaker: MUTED (Chat responses are quiet)'}
              onClick={handleToggleSpeaker}
            >
              {vocalize || isSpeaking ? (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                  <path d="M15.54 8.46a5 5 0 0 1 0 7.07M19.07 4.93a10 10 0 0 1 0 14.14"></path>
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                  <line x1="23" y1="9" x2="17" y2="15"></line><line x1="17" y1="9" x2="23" y2="15"></line>
                </svg>
              )}
            </button>
            <button 
              className={`cmd-btn ${micActive ? 'active mic-on' : ''}`} 
              title={micActive ? 'Microphone: ON (Listening for voice/wake word)' : 'Microphone: MUTED'}
              onClick={handleToggleMic}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
                <rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v4"/>
              </svg>
            </button>
            <button 
              className="cmd-btn" 
              title="New Chat (Save Current Thread)"
              onClick={clearChat}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
                <path d="M12 5v14M5 12h14" />
              </svg>
            </button>
            <button className="cmd-btn send" title="Send" onClick={submit}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>
              </svg>
            </button>
          </div>
        </div>

        {/* Wide & Small Pill Button (Outside & to the RIGHT of chat bar - Zero Emojis) */}
        <div style={{ position: 'relative', flexShrink: 0 }}>
          <button
            className="model-switcher-pill-btn"
            onClick={() => { setShowModelMenu(prev => !prev); setShowMentions(false); }}
            title={`Active Model: ${selectedModel === 'auto' ? 'Auto Dynamic Routing' : selectedModel}. Click to change.`}
            style={{
              height: '34px',
              padding: '0 13px',
              borderRadius: '999px',
              background: selectedModel === 'auto' ? 'var(--glass-3, rgba(45, 38, 30, 0.8))' : 'rgba(224, 186, 117, 0.15)',
              border: selectedModel === 'auto' ? '1px solid var(--glass-edge, rgba(255, 235, 200, 0.12))' : '1px solid rgba(224, 186, 117, 0.4)',
              backdropFilter: 'blur(40px) saturate(180%)',
              WebkitBackdropFilter: 'blur(40px) saturate(180%)',
              boxShadow: 'var(--shadow-md, 0 4px 16px rgba(0,0,0,0.25))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              cursor: 'pointer',
              transition: 'all 0.2s cubic-bezier(0.22, 1, 0.36, 1)',
              color: selectedModel === 'auto' ? 'var(--ink-2, #ccc)' : 'var(--accent-gold, #e0ba75)'
            }}
          >
            <span style={{
              fontSize: '11px',
              fontWeight: 600,
              letterSpacing: '-0.01em',
              whiteSpace: 'nowrap',
              color: selectedModel === 'auto' ? 'var(--ink-2, #ccc)' : 'var(--accent-gold, #e0ba75)'
            }}>
              {modelDisplayLabel}
            </span>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.6 }}>
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>

          {/* Model Selector Popover - Clean Minimal (No Emojis) */}
          {showModelMenu && (
            <div 
              ref={modelMenuRef}
              style={{
                position: 'absolute',
                bottom: '44px',
                right: '0',
                width: '320px',
                maxHeight: '440px',
                background: 'rgba(22, 19, 16, 0.96)',
                border: '1px solid var(--hairline-2, rgba(255,255,255,0.12))',
                borderRadius: '16px',
                padding: '12px',
                overflowY: 'auto',
                pointerEvents: 'auto',
                zIndex: 70,
                backdropFilter: 'blur(24px)',
                WebkitBackdropFilter: 'blur(24px)',
                boxShadow: '0 16px 40px rgba(0,0,0,0.6)',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '6px', borderBottom: '1px solid var(--hairline-2)' }}>
                <div>
                  <div style={{ fontSize: '12.5px', fontWeight: 600, color: 'var(--ink, #fff)' }}>Inference Model Routing</div>
                  <div style={{ fontSize: '10.5px', color: 'var(--ink-3)' }}>Select preferred model or auto-route</div>
                </div>
                <button 
                  onClick={() => setShowModelMenu(false)}
                  style={{ background: 'transparent', border: 'none', color: 'var(--ink-3)', cursor: 'pointer', padding: '2px', display: 'flex', alignItems: 'center' }}
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              </div>

              {/* Auto Mode Card */}
              <div
                onClick={() => handleSelectModel('auto')}
                style={{
                  padding: '8px 10px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  background: selectedModel === 'auto' ? 'rgba(224, 186, 117, 0.15)' : 'var(--glass-1, rgba(255,255,255,0.03))',
                  border: selectedModel === 'auto' ? '1px solid var(--accent-gold, #e0ba75)' : '1px solid var(--hairline-2)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  transition: 'all 0.15s ease'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--ink, #fff)' }}>Auto-Route (Cognitive Routing)</span>
                    <span style={{ fontSize: '9.5px', padding: '1px 5px', borderRadius: '3px', background: 'rgba(224, 186, 117, 0.25)', color: 'var(--accent-gold)', fontWeight: 600 }}>Default</span>
                  </div>
                  <div style={{ fontSize: '10.5px', color: 'var(--ink-3)', marginTop: '2px', lineHeight: 1.3 }}>
                    Routes across Groq LPU, Gemini & OpenAI based on intent depth
                  </div>
                </div>
                {selectedModel === 'auto' && (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--accent-gold, #e0ba75)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                )}
              </div>

              {/* Categorized Models - Clean Typography */}
              {[
                { cat: 'fast', label: 'Ultra-Fast & Coding (Groq LPU)', color: '#4caf50' },
                { cat: 'frontier', label: 'Deep Frontier Reasoning', color: '#29b6f6' },
                { cat: 'local', label: 'Local & Private (Ollama)', color: '#ab47bc' }
              ].map(group => {
                const items = MODEL_OPTIONS.filter(m => m.category === group.cat);
                return (
                  <div key={group.cat} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ fontSize: '10px', fontWeight: 600, color: group.color, textTransform: 'uppercase', letterSpacing: '0.05em', padding: '2px 2px' }}>
                      {group.label}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {items.map(m => {
                        const isSelected = selectedModel === m.id;
                        return (
                          <div
                            key={m.id}
                            onClick={() => handleSelectModel(m.id)}
                            style={{
                              padding: '6px 10px',
                              borderRadius: '7px',
                              cursor: 'pointer',
                              background: isSelected ? 'rgba(224, 186, 117, 0.15)' : 'var(--glass-1, rgba(255,255,255,0.03))',
                              border: isSelected ? '1px solid var(--accent-gold, #e0ba75)' : '1px solid var(--hairline-2)',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '1px',
                              transition: 'all 0.15s ease'
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '11.5px', fontWeight: 600, color: isSelected ? 'var(--accent-gold)' : 'var(--ink, #fff)' }}>{m.name}</span>
                              <span style={{ fontSize: '9.5px', padding: '1px 4px', borderRadius: '3px', background: 'rgba(255,255,255,0.06)', color: 'var(--ink-3)' }}>{m.tag}</span>
                            </div>
                            <div style={{ fontSize: '10.5px', color: 'var(--ink-3)', lineHeight: '1.25' }}>
                              {m.goodAt}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
      <div className="command-hint" style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
        <span 
          style={{ cursor: 'pointer' }}
          onClick={() => {
            import('../../state').then(({ useSurfaceState }) => {
              useSurfaceState.getState().openSurface('command_palette');
            });
          }}
        >
          <kbd>⌘K</kbd> COMMANDS
        </span>
        <span 
          style={{ cursor: 'pointer' }}
          onClick={() => {
            if (inputRef.current) {
              inputRef.current.focus();
              setVal(prev => prev ? `${prev} @` : '@');
              setShowMentions(true);
            }
          }}
        >
          <kbd>@</kbd> CONTEXT
        </span>
        <span 
          style={{ cursor: 'pointer' }}
          onClick={() => {
            import('../../state').then(({ useSurfaceState }) => {
              useSurfaceState.getState().openSurface('memory', 'journal');
            });
          }}
        >
          <kbd>⌘J</kbd> JOURNAL
        </span>
        <span 
          style={{ cursor: 'pointer' }}
          onClick={() => {
            import('../../state').then(({ useSurfaceState }) => {
              useSurfaceState.getState().closeSurface();
            });
          }}
        >
          <kbd>ESC</kbd> DISMISS
        </span>
      </div>
    </div>
  );
};
