import React, { useState, useEffect, useRef } from 'react';
import { useSurfaceState } from '../../state';
import { socket } from '../../runtime/socket';

interface SearchResultItem {
  id: string;
  title: string;
  summary: string;
  keywords: string[];
  timestamp: number;
  kind: 'Decision' | 'Question' | 'Workspace' | 'Conversation' | 'BrowserTab' | 'File' | string;
  workspace_id?: string;
  payload?: any;
}

const KIND_BADGES: { [key: string]: { label: string; bg: string; color: string } } = {
  Decision: { label: 'DECISION', bg: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' },
  Question: { label: 'QUESTION', bg: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' },
  Workspace: { label: 'WORKSPACE', bg: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6' },
  File: { label: 'FILE', bg: 'rgba(16, 185, 129, 0.15)', color: '#10b981' },
  BrowserTab: { label: 'BROWSER', bg: 'rgba(168, 85, 247, 0.15)', color: '#a855f7' },
  Conversation: { label: 'CHAT', bg: 'rgba(99, 102, 241, 0.15)', color: '#6366f1' }
};

export const CommandPaletteSurface: React.FC = () => {
  const { closeSurface, openSurface } = useSurfaceState();
  const [query, setQuery] = useState('');
  const [selectedKind, setSelectedKind] = useState<string | null>(null);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Focus input immediately on open
    setTimeout(() => {
      inputRef.current?.focus();
    }, 50);

    // Initial search request (recent items)
    socket.sendEvent({ type: 'search.query', query: '', kind: selectedKind });

    const handleSearchResults = (e: CustomEvent) => {
      const payload = e.detail;
      if (payload.type === 'search.results') {
        setResults(payload.results || []);
        setSelectedIndex(0);
      }
    };

    window.addEventListener('arova-event', handleSearchResults as EventListener);
    return () => {
      window.removeEventListener('arova-event', handleSearchResults as EventListener);
    };
  }, []);

  useEffect(() => {
    socket.sendEvent({ type: 'search.query', query, kind: selectedKind });
  }, [query, selectedKind]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      closeSurface();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, results.length));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + Math.max(1, results.length)) % Math.max(1, results.length));
    } else if (e.key === 'Enter' && results[selectedIndex]) {
      e.preventDefault();
      handleSelect(results[selectedIndex]);
    }
  };

  const handleSelect = (item: SearchResultItem) => {
    if (item.kind === 'Workspace' || item.workspace_id) {
      socket.sendEvent({
        type: 'workspace.continue',
        workspace_id: item.workspace_id || item.id,
        options: { restore_vscode: true, restore_terminal: true }
      });
      openSurface('workspace');
    } else if (item.kind === 'Decision' || item.kind === 'Question') {
      openSurface('memory');
    } else if (item.kind === 'File') {
      socket.sendEvent({
        type: 'intention.thread_action',
        action: 'open_file',
        payload: { path: item.payload?.resource_path || item.title }
      });
      closeSurface();
    } else {
      closeSurface();
    }
  };

  const categories = ['ALL', 'Decision', 'Question', 'Workspace', 'File', 'BrowserTab', 'Conversation'];

  return (
    <div className="surface-content" style={{ padding: '0', display: 'flex', flexDirection: 'column', height: '100%', maxHeight: '560px' }}>
      {/* Search Header Bar */}
      <div style={{
        padding: '20px 24px',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        display: 'flex',
        alignItems: 'center',
        gap: '12px'
      }}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ opacity: 0.6 }}>
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type to search memories, decisions, workspaces, or files (`Ctrl+Space` to dismiss)..."
          style={{
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: '#fff',
            fontSize: '16px',
            width: '100%',
            fontFamily: 'inherit'
          }}
        />
        <button
          onClick={() => closeSurface()}
          style={{
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '6px',
            padding: '4px 10px',
            color: 'rgba(255,255,255,0.6)',
            fontSize: '12px',
            cursor: 'pointer'
          }}
        >
          ESC
        </button>
      </div>

      {/* Category Filter Chips */}
      <div style={{
        padding: '12px 24px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        gap: '8px',
        overflowX: 'auto'
      }}>
        {categories.map((cat) => {
          const isSelected = (cat === 'ALL' && selectedKind === null) || cat === selectedKind;
          const badgeInfo = KIND_BADGES[cat] || { label: cat.toUpperCase() };
          return (
            <button
              key={cat}
              onClick={() => setSelectedKind(cat === 'ALL' ? null : cat)}
              style={{
                background: isSelected ? 'rgba(255,255,255,0.16)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${isSelected ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.08)'}`,
                borderRadius: '16px',
                padding: '4px 12px',
                color: isSelected ? '#fff' : 'rgba(255,255,255,0.6)',
                fontSize: '11px',
                fontWeight: 600,
                letterSpacing: '0.04em',
                cursor: 'pointer',
                transition: 'all 160ms ease'
              }}
            >
              {badgeInfo.label || cat}
            </button>
          );
        })}
      </div>

      {/* Results List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px' }}>
        {results.length === 0 ? (
          <div style={{ padding: '40px 0', textAlign: 'center', color: 'rgba(255,255,255,0.4)', fontSize: '14px' }}>
            No matching cognitive objects found. Try searching for "SQLite", "supervisor", or "asyncio".
          </div>
        ) : (
          results.map((item, index) => {
            const badge = KIND_BADGES[item.kind] || { label: item.kind.toUpperCase(), bg: 'rgba(255,255,255,0.1)', color: '#fff' };
            const isSelected = index === selectedIndex;
            return (
              <div
                key={item.id}
                onClick={() => handleSelect(item)}
                onMouseEnter={() => setSelectedIndex(index)}
                style={{
                  padding: '14px 16px',
                  borderRadius: '10px',
                  background: isSelected ? 'rgba(255,255,255,0.08)' : 'transparent',
                  border: isSelected ? '1px solid rgba(255,255,255,0.15)' : '1px solid transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                  transition: 'background 140ms ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{
                    background: badge.bg,
                    color: badge.color,
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '10px',
                    fontWeight: 700,
                    letterSpacing: '0.05em'
                  }}>
                    {badge.label}
                  </span>
                  <span style={{ color: '#fff', fontWeight: 600, fontSize: '14px', flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {item.title}
                  </span>
                  <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: '11px' }}>
                    {item.kind === 'Workspace' ? 'Jump to Workspace ->' : 'Select ->'}
                  </span>
                </div>
                <div style={{ color: 'rgba(255,255,255,0.65)', fontSize: '13px', lineHeight: '1.4' }}>
                  {item.summary}
                </div>
                {item.keywords && item.keywords.length > 0 && (
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '2px' }}>
                    {item.keywords.slice(0, 5).map((kw, i) => (
                      <span key={i} style={{ background: 'rgba(255,255,255,0.04)', padding: '2px 6px', borderRadius: '4px', color: 'rgba(255,255,255,0.4)', fontSize: '11px' }}>
                        #{kw}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Footer Info */}
      <div style={{
        padding: '10px 24px',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        color: 'rgba(255,255,255,0.4)',
        fontSize: '11px'
      }}>
        <span>Universal Search Index across 6 categories (`Phase 6`)</span>
        <span>↑↓ Navigate • ENTER Select • ESC Close</span>
      </div>
    </div>
  );
};
