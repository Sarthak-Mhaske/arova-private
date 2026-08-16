import React, { useState, useRef, useEffect, useMemo } from 'react';
import { SurfaceHead } from './SurfaceHead';
import { socket } from '../../runtime/socket';

interface JournalEntry {
  id: string;
  timestamp: number;
  dateStr: string;
  category: 'build' | 'decision' | 'blocker' | 'reflection';
  content: string;
}

interface JournalInsight {
  id: string;
  text: string;
  category: 'build' | 'decision' | 'blocker' | 'reflection';
}

const CATEGORIES: { 
  id: JournalEntry['category']; 
  label: string; 
  renderIcon: () => React.ReactNode; 
  tint: string; 
  bg: string;
}[] = [
  { 
    id: 'build', 
    label: 'What I Built', 
    tint: '#34d399',
    bg: 'rgba(52, 211, 153, 0.12)',
    renderIcon: () => (
      <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
      </svg>
    )
  },
  { 
    id: 'decision', 
    label: 'Architecture Decision', 
    tint: '#f59e0b',
    bg: 'rgba(245, 158, 11, 0.12)',
    renderIcon: () => (
      <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
        <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
      </svg>
    )
  },
  { 
    id: 'blocker', 
    label: 'Blocker & Next Step', 
    tint: '#fb7185',
    bg: 'rgba(251, 113, 133, 0.12)',
    renderIcon: () => (
      <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
    )
  },
  { 
    id: 'reflection', 
    label: 'Daily Reflection', 
    tint: '#c084fc',
    bg: 'rgba(192, 132, 252, 0.12)',
    renderIcon: () => (
      <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
      </svg>
    )
  }
];

export const JournalSurface: React.FC = () => {
  const [entries, setEntries] = useState<JournalEntry[]>(() => {
    try {
      const stored = localStorage.getItem('arova_dev_journal');
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  const [insights, setInsights] = useState<JournalInsight[]>([
    { id: 'ins_1', text: 'Document any key technical choices or tradeoffs made in this session.', category: 'decision' },
    { id: 'ins_2', text: 'Clear any open blockers or write down your starting step for tomorrow.', category: 'blocker' },
    { id: 'ins_3', text: 'Take a calm breath. What progress are you proud of today?', category: 'reflection' }
  ]);

  const [activeCategory, setActiveCategory] = useState<JournalEntry['category']>('build');
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [content, setContent] = useState('');
  const [savedStatus, setSavedStatus] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    socket.sendEvent({ type: 'journal.query' });

    const handleJournalEvents = (e: CustomEvent) => {
      const payload = e.detail;
      if (payload.type === 'journal.query_response' || payload.type === 'journal.sync') {
        if (Array.isArray(payload.entries) && payload.entries.length > 0) {
          setEntries(payload.entries);
          try {
            localStorage.setItem('arova_dev_journal', JSON.stringify(payload.entries));
          } catch {
            // silent
          }
        }
        if (Array.isArray(payload.insights) && payload.insights.length > 0) {
          setInsights(payload.insights);
        }
      }
    };

    window.addEventListener('arova-event', handleJournalEvents as EventListener);
    setTimeout(() => {
      textareaRef.current?.focus();
    }, 80);

    return () => {
      window.removeEventListener('arova-event', handleJournalEvents as EventListener);
    };
  }, []);

  const saveEntry = () => {
    if (!content.trim()) return;

    const newEntry: JournalEntry = {
      id: `j_${Date.now()}`,
      timestamp: Date.now(),
      dateStr: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      category: activeCategory,
      content: content.trim()
    };

    const updated = [newEntry, ...entries];
    setEntries(updated);
    try {
      localStorage.setItem('arova_dev_journal', JSON.stringify(updated));
    } catch {
      // silent
    }

    socket.sendEvent({
      type: 'journal.entry_added',
      entry: newEntry,
      category: activeCategory,
      text: content.trim()
    });

    setContent('');
    setSavedStatus('Saved to Arova Memory & ~/.arova/journal');
    setTimeout(() => setSavedStatus(null), 3500);
  };

  const deleteEntry = (id: string) => {
    const updated = entries.filter(e => e.id !== id);
    setEntries(updated);
    try {
      localStorage.setItem('arova_dev_journal', JSON.stringify(updated));
    } catch {
      // silent
    }
    socket.sendEvent({
      type: 'journal.delete_entry',
      id
    });
  };

  const exportMarkdown = () => {
    if (entries.length === 0) return;
    const md = entries.map(e => {
      const cat = CATEGORIES.find(c => c.id === e.category)?.label || e.category;
      return `### [${cat}] — ${new Date(e.timestamp).toLocaleDateString()} ${e.dateStr}\n\n${e.content}\n\n---\n`;
    }).join('\n');

    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `arova-journal-${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const filteredEntries = useMemo(() => {
    return entries.filter(e => {
      const matchesCat = filterCategory === 'all' || e.category === filterCategory;
      const matchesQuery = !searchQuery || e.content.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesCat && matchesQuery;
    });
  }, [entries, filterCategory, searchQuery]);

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      height: '100%', 
      width: '100%', 
      gap: '16px',
      overflow: 'hidden',
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif"
    }}>
      {/* Top Surface Header */}
      <SurfaceHead 
        title="Developer Journal & Log" 
        sub={`${new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' })} · Serene workspace reflections & persistent architectural memory`} 
      />

      {/* Arova Ambient Insights Bar */}
      {insights.length > 0 && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: '10px 16px',
          borderRadius: '12px',
          background: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          overflowX: 'auto',
          scrollbarWidth: 'none'
        }}>
          <span style={{ 
            fontSize: '11px', 
            textTransform: 'uppercase', 
            letterSpacing: '0.08em', 
            color: '#fbbf24', 
            fontWeight: 700,
            whiteSpace: 'nowrap',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="#fbbf24" strokeWidth="2.4"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
            AROVA INSIGHT
          </span>
          <div style={{ display: 'flex', gap: '8px', flex: 1, overflowX: 'auto', scrollbarWidth: 'none' }}>
            {insights.map(ins => (
              <button
                key={ins.id}
                onClick={() => {
                  setActiveCategory(ins.category);
                  if (!content) setContent(ins.text + '\n\n');
                  textareaRef.current?.focus();
                }}
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '8px',
                  padding: '5px 12px',
                  fontSize: '12.5px',
                  fontWeight: 450,
                  color: '#f3f4f6',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  textAlign: 'left',
                  transition: 'all 150ms ease'
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = '#fbbf24';
                  e.currentTarget.style.background = 'rgba(251, 191, 36, 0.1)';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.1)';
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
                }}
              >
                {ins.text}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Main Wide 2-Column Layout */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'minmax(520px, 1.25fr) minmax(380px, 1fr)', 
        gap: '20px', 
        flex: 1, 
        overflow: 'hidden' 
      }}>
        {/* Left Side: Notion-Grade Writing Document */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
          background: 'rgba(26, 22, 18, 0.65)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '16px',
          padding: '20px 24px',
          overflow: 'hidden'
        }}>
          {/* Category Chips */}
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {CATEGORIES.map(cat => {
              const isSelected = activeCategory === cat.id;
              return (
                <button
                  key={cat.id}
                  onClick={() => {
                    setActiveCategory(cat.id);
                    textareaRef.current?.focus();
                  }}
                  style={{
                    padding: '7px 14px',
                    borderRadius: '9px',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    border: isSelected ? `1.5px solid ${cat.tint}` : '1px solid rgba(255, 255, 255, 0.12)',
                    background: isSelected ? cat.bg : 'rgba(255, 255, 255, 0.03)',
                    color: isSelected ? '#ffffff' : '#d1d5db',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '7px',
                    transition: 'all 150ms ease'
                  }}
                >
                  <span style={{ color: cat.tint, display: 'grid', placeItems: 'center' }}>
                    {cat.renderIcon()}
                  </span>
                  <span>{cat.label}</span>
                </button>
              );
            })}
          </div>

          {/* Distraction-Free Notion Document Area */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
            <textarea
              ref={textareaRef}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder={`Write down your ${CATEGORIES.find(c => c.id === activeCategory)?.label.toLowerCase()}...\n\n• What did you accomplish or change?\n• Any subtle trade-off or architectural insight?\n• Next step when you return?`}
              style={{
                flex: 1,
                width: '100%',
                background: 'transparent',
                border: 'none',
                color: '#ffffff',
                fontSize: '14.5px',
                fontFamily: 'inherit',
                lineHeight: 1.65,
                resize: 'none',
                outline: 'none',
                padding: '4px 0',
                letterSpacing: '-0.005em'
              }}
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                  e.preventDefault();
                  saveEntry();
                }
              }}
            />
          </div>

          {/* Editor Footer Actions */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            paddingTop: '14px'
          }}>
            <span style={{ 
              fontSize: '12px', 
              color: savedStatus ? '#34d399' : '#9ca3af',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}>
              {savedStatus ? (
                <>
                  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="#34d399" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                  {savedStatus}
                </>
              ) : (
                'Press ⌘+Enter to save to Arova Memory'
              )}
            </span>
            <button
              onClick={saveEntry}
              disabled={!content.trim()}
              style={{
                padding: '9px 24px',
                borderRadius: '999px',
                background: content.trim() ? '#fbbf24' : 'rgba(255, 255, 255, 0.06)',
                color: content.trim() ? '#18120c' : '#6b7280',
                fontWeight: 700,
                fontSize: '13px',
                border: 'none',
                cursor: content.trim() ? 'pointer' : 'default',
                transition: 'all 150ms ease',
                boxShadow: content.trim() ? '0 4px 16px rgba(251, 191, 36, 0.35)' : 'none'
              }}
            >
              Save Reflection
            </button>
          </div>
        </div>

        {/* Right Side: Memory Journal Archive & Records */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
          background: 'rgba(26, 22, 18, 0.65)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '16px',
          padding: '20px 22px',
          overflow: 'hidden'
        }}>
          {/* Filter & Export Bar */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
            <div style={{ display: 'flex', gap: '5px', overflowX: 'auto', scrollbarWidth: 'none' }}>
              {['all', 'build', 'decision', 'blocker', 'reflection'].map(cat => (
                <button
                  key={cat}
                  onClick={() => setFilterCategory(cat)}
                  style={{
                    padding: '5px 10px',
                    borderRadius: '7px',
                    fontSize: '11.5px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    border: 'none',
                    background: filterCategory === cat ? 'rgba(255, 255, 255, 0.15)' : 'transparent',
                    color: filterCategory === cat ? '#ffffff' : '#9ca3af',
                    textTransform: 'capitalize'
                  }}
                >
                  {cat}
                </button>
              ))}
            </div>
            {entries.length > 0 && (
              <button
                onClick={exportMarkdown}
                title="Export all journal entries as Markdown (.md) file"
                style={{
                  background: 'transparent',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  borderRadius: '7px',
                  padding: '4px 10px',
                  fontSize: '11.5px',
                  fontWeight: 500,
                  color: '#e5e7eb',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px'
                }}
              >
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
                .md Export
              </button>
            )}
          </div>

          {/* Search Box */}
          <div style={{ position: 'relative' }}>
            <input
              type="text"
              placeholder="Search reflections & memory logs..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '9px 12px 9px 34px',
                borderRadius: '10px',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                color: '#ffffff',
                fontSize: '12.5px',
                outline: 'none'
              }}
            />
            <svg 
              viewBox="0 0 24 24" 
              width="14" 
              height="14" 
              fill="none" 
              stroke="#9ca3af" 
              strokeWidth="2" 
              style={{ position: 'absolute', left: '11px', top: '11px' }}
            >
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
          </div>

          {/* Entries Feed */}
          <div style={{ 
            flex: 1, 
            overflowY: 'auto', 
            display: 'flex', 
            flexDirection: 'column', 
            gap: '10px',
            paddingRight: '4px'
          }}>
            {filteredEntries.length === 0 ? (
              <div style={{ 
                textAlign: 'center', 
                padding: '50px 14px', 
                color: '#9ca3af', 
                fontSize: '13px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '10px'
              }}>
                <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="#6b7280" strokeWidth="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                <span>{searchQuery ? 'No reflections matching your search' : 'No reflections logged yet. Write your thoughts on the left.'}</span>
              </div>
            ) : (
              filteredEntries.map(entry => {
                const cat = CATEGORIES.find(c => c.id === entry.category) || CATEGORIES[0];
                return (
                  <div
                    key={entry.id}
                    style={{
                      padding: '13px 15px',
                      borderRadius: '12px',
                      background: 'rgba(255, 255, 255, 0.04)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ color: cat.tint, fontWeight: 650, fontSize: '11.5px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ display: 'grid', placeItems: 'center' }}>{cat.renderIcon()}</span>
                        <span>{cat.label}</span>
                      </span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ color: '#9ca3af', fontSize: '11.5px', fontWeight: 500 }}>{entry.dateStr}</span>
                        <button
                          onClick={() => deleteEntry(entry.id)}
                          title="Delete entry"
                          style={{
                            background: 'none',
                            border: 'none',
                            color: '#9ca3af',
                            cursor: 'pointer',
                            padding: '2px',
                            display: 'grid',
                            placeItems: 'center'
                          }}
                        >
                          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                        </button>
                      </div>
                    </div>
                    <div style={{ 
                      fontSize: '13.5px', 
                      lineHeight: 1.55, 
                      color: '#f9fafb', 
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      fontWeight: 450
                    }}>
                      {entry.content}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
