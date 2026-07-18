import React, { useState } from 'react';
import { useCognitionState } from '../../state';
import { socket } from '../../runtime/socket';

export const CommandZone: React.FC = () => {
  const [val, setVal] = useState('');
  const [vocalize, setVocalize] = useState(true);

  const clearChat = () => {
    socket.sendEvent({ type: 'client.new_thread' });
    useCognitionState.getState().setItems([]);
  };

  const submit = () => {
    if (!val.trim()) return;
    
    if (val.trim() === '/clear') {
      clearChat();
      setVal('');
      return;
    }
    
    const payload = {
      type: 'user.message',
      text: val.trim(),
      vocalize
    };
    console.log('[CommandZone] Attempting to send payload:', payload);
    socket.sendEvent(payload);
    setVal('');
  };

  const fireInterrupt = () => {
    socket.sendEvent({ type: 'client.interrupt' });
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
    const newVal = e.target.value;
    if (val === '' && newVal.length > 0) {
       fireInterrupt();
    }
    setVal(newVal);
  };

  return (
    <div className="command-zone">
      <div className="command">
        <span className="leader"></span>
        <input 
          id="command-input"
          type="text" 
          placeholder="speak to arova, or invoke…"  
          value={val}
          onChange={handleChange}
          onKeyDown={e => {
            if (e.key === 'Enter') submit();
          }}
        />
        <div className="actions">
          <button 
            className={`cmd-btn ${vocalize ? 'active' : ''}`} 
            title={vocalize ? 'Vocalization: ON' : 'Vocalization: OFF'}
            onClick={() => setVocalize(!vocalize)}
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
          <button className="cmd-btn" title="Voice Input">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v4"/>
            </svg>
          </button>
          <button 
            className="cmd-btn" 
            title="Clear Chat"
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
