import React, { useState, useRef } from 'react';
import { useCognitionState } from '../../state';
import { socket } from '../../runtime/socket';

export const CommandZone: React.FC = () => {
  const [val, setVal] = useState('');
  const [vocalize, setVocalize] = useState(false); // MUTED BY DEFAULT ALWAYS
  const [micActive, setMicActive] = useState(false); // MIC OFF BY DEFAULT
  const lastSubmitRef = useRef<{ text: string; ts: number }>({ text: '', ts: 0 });

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
      return;
    }
    
    const payload = {
      type: 'user.message',
      text: trimmed,
      vocalize
    };
    console.log('[CommandZone] Sending user.message (vocalize=' + vocalize + '):', payload);
    socket.sendEvent(payload);
    setVal('');
  };

  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
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
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setVal(e.target.value);
  };

  const activeAction = useCognitionState(s => s.activeAction);

  return (
    <div className="command-zone">
      {activeAction && (
        <div className="active-action-overlay">
          <span className="spinner">⚙️</span>
          <span className="action-text">{activeAction}...</span>
        </div>
      )}
      <div className="command">
        <span className="leader"></span>
        <input 
          id="command-input"
          type="text" 
          placeholder="speak to arova, or invoke…"  
          value={val}
          onChange={handleChange}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
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
        <span><kbd>@</kbd> context</span>
        <span><kbd>esc</kbd> dismiss</span>
      </div>
    </div>
  );
};
