import React, { useState, useRef } from 'react';
import { useCognitionState, useAwarenessState } from '../../state';
import { socket } from '../../runtime/socket';

export const CommandZone: React.FC = () => {
  const [val, setVal] = useState('');
  const [vocalize, setVocalize] = useState(false); // MUTED BY DEFAULT ALWAYS
  const [micActive, setMicActive] = useState(false); // MIC OFF BY DEFAULT
  const lastSubmitRef = useRef<{ text: string; ts: number }>({ text: '', ts: 0 });
  // TIER 1.3: @-mention autocomplete
  const [showMentions, setShowMentions] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [mentionStart, setMentionStart] = useState<number | null>(null);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const { activeWorkspace } = useAwarenessState();

  // Build suggestion list from verbatim RealityLayer.resources + search index fallback
  const resourcesObj = (activeWorkspace as any)?.reality?.resources || {};
  const allResources: string[] = Object.keys(resourcesObj).map((k: string) => {
    const r: any = resourcesObj[k];
    return r?.identity || k;
  });
  // Filter by mention query
  const filteredSuggestions = (() => {
    if (!showMentions) return [];
    const q = mentionQuery.toLowerCase();
    if (!q) return allResources.slice(0, 8);
    return allResources.filter(r => r.toLowerCase().includes(q)).slice(0, 8);
  })();

  const clearChat = () => {
    socket.sendEvent({ type: 'client.new_thread' });
    useCognitionState.getState().setItems([]);
    import('../../state/awarenessState').then(({ useAwarenessState }) => {
      useAwarenessState.getState().resetContinueCard();
    });
  };

  const fireInterrupt = () => {
    socket.sendEvent({ type: 'client.interrupt' });
  };

  const handleToggleSpeaker = () => {
    const nextState = !vocalize;
    setVocalize(nextState);
    if (!nextState) {
      // Speaker toggled OFF -> Immediately kill active TTS mid-sentence
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

  const activeAction = useCognitionState(s => s.activeAction);

  return (
    <div className="command-zone" style={{ position: 'relative' }}>
      {activeAction && (
        <div className="active-action-overlay">
          <span className="spinner">⚙️</span>
          <span className="action-text">{activeAction}...</span>
        </div>
      )}
      {/* TIER 1.3: @-mention autocomplete dropdown */}
      {showMentions && (
        <div style={{
          position: 'absolute',
          bottom: '62px',
          left: '12px',
          right: '12px',
          background: 'var(--glass-1, rgba(30,30,40,0.95))',
          border: '1px solid var(--hairline-2, rgba(255,255,255,0.1))',
          borderRadius: '12px',
          padding: '6px',
          maxHeight: '180px',
          overflowY: 'auto',
          zIndex: 50,
          backdropFilter: 'blur(12px)',
          boxShadow: '0 8px 24px rgba(0,0,0,0.4)'
        }}>
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
      <div className="command">
        <span className="leader"></span>
        <input 
          ref={inputRef}
          id="command-input"
          type="text" 
          placeholder="Ask about your current context… try @ to mention files"  
          value={val}
          onChange={handleChange}
          onKeyDown={handleInputKeyDown}
          autoComplete="off"
        />
        <div className="actions">
          <button 
            className={`cmd-btn ${vocalize ? 'active' : ''}`} 
            title={vocalize ? 'Speaker: ON (Arova will speak)' : 'Speaker: MUTED (Chat responses are quiet)'}
            onClick={handleToggleSpeaker}
          >
            {vocalize ? (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path>
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
      <div className="command-hint">
        <span><kbd>⌘K</kbd> invoke</span>
        <span><kbd>@</kbd> mention verbatim file</span>
        <span><kbd>esc</kbd> dismiss</span>
      </div>
    </div>
  );
};
