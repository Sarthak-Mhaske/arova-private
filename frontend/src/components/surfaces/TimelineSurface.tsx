import React, { useEffect, useState, useRef, useCallback } from 'react';
import { SurfaceHeader, EmptyState, LoadingState } from '../ui/CoherenceComponents';
import { socket } from '../../runtime/socket';
import { useSurfaceState } from '../../state';

interface TimelineEvent {
  id: string;
  category: string;
  title: string;
  description: string;
  source: string;
  importance: number;
  correlation_id?: string;
  metadata: Record<string, any>;
  timestamp: number;
}

/** Group events by calendar day for transparent history display */
function groupByDay(events: TimelineEvent[]): { label: string; dateKey: string; events: TimelineEvent[] }[] {
  const groups: Map<string, TimelineEvent[]> = new Map();
  const now = new Date();
  const todayKey = now.toDateString();
  const yesterdayKey = new Date(now.getTime() - 86400000).toDateString();

  for (const ev of events) {
    const d = new Date(ev.timestamp * 1000);
    const key = d.toDateString();
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(ev);
  }

  return Array.from(groups.entries()).map(([key, evts]) => {
    let label = key;
    if (key === todayKey) label = 'Today';
    else if (key === yesterdayKey) label = 'Yesterday';
    else {
      const d = new Date(evts[0].timestamp * 1000);
      label = d.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
    }
    return { label, dateKey: key, events: evts };
  });
}

export const TimelineSurface: React.FC<{ embedded?: boolean }> = ({ embedded }) => {
  const { openSurface } = useSurfaceState();
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [timeInsights, setTimeInsights] = useState<any>(null);
  const [totalStored, setTotalStored] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [importantOnly, setImportantOnly] = useState(false);
  const [narrativeMode, setNarrativeMode] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [visibleCount, setVisibleCount] = useState(60);
  const scrollRef = useRef<HTMLDivElement>(null);

  const fetchTimeline = useCallback(() => {
    socket.sendEvent({
      type: 'timeline.get_request',
      // No limit — request full history from backend
      req_id: `tl_${Date.now()}`
    });
  }, []);

  useEffect(() => {
    fetchTimeline();
    const interval = setInterval(fetchTimeline, 15000);

    const handleFocusOrVisible = () => {
      if (document.visibilityState === 'visible') {
        fetchTimeline();
      }
    };

    const handleEvent = (e: CustomEvent) => {
      const payload = e.detail;
      
      if (payload.type === 'timeline.query_response') {
        setEvents(payload.events || []);
        if (payload.time_insights) {
          setTimeInsights(payload.time_insights);
        }
        if (typeof payload.total_stored === 'number') {
          setTotalStored(payload.total_stored);
        }
        setIsLoading(false);
      } else if (payload.type === 'TIMELINE_EVENT') {
        const newEvent = payload.event;
        if (newEvent) {
          setEvents(prev => [newEvent, ...prev]);
          setTotalStored(prev => prev + 1);
        }
      }
    };

    window.addEventListener('arova-event', handleEvent as EventListener);
    window.addEventListener('focus', handleFocusOrVisible);
    document.addEventListener('visibilitychange', handleFocusOrVisible);

    return () => {
      clearInterval(interval);
      window.removeEventListener('arova-event', handleEvent as EventListener);
      window.removeEventListener('focus', handleFocusOrVisible);
      document.removeEventListener('visibilitychange', handleFocusOrVisible);
    };
  }, [fetchTimeline]);

  // Infinite scroll — load more events when user scrolls near bottom
  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distanceFromBottom < 200) {
      setVisibleCount(prev => Math.min(prev + 60, events.length));
    }
  }, [events.length]);

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'environment':
      case 'state_transition': return 'var(--accent-blue)';
      case 'memory': return 'var(--accent-purple)';
      case 'routing': return 'var(--accent-orange)';
      case 'runtime': return 'var(--ink-3)';
      case 'cognition':
      case 'attention':
      case 'continuity': return 'var(--accent-green)';
      default: return 'var(--ink-2)';
    }
  };

  const filteredEvents = events.filter(e => importantOnly ? e.importance >= 0.5 : true);
  const displayedEvents = filteredEvents.slice(0, visibleCount);
  const dayGroups = groupByDay(displayedEvents);

  // Compute date range for transparency
  const oldestTimestamp = events.length > 0 ? events[events.length - 1]?.timestamp : null;
  const newestTimestamp = events.length > 0 ? events[0]?.timestamp : null;
  const dateRangeStr = oldestTimestamp && newestTimestamp
    ? `${new Date(oldestTimestamp * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} — ${new Date(newestTimestamp * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`
    : '';

  return (
    <div className="surface-content" style={{ padding: embedded ? '16px 28px 40px' : '42px', height: '100%', display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
      {!embedded && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <SurfaceHeader 
            title="Cognitive Timeline" 
            sub="Transparent view of Arova's internal cognition, time insights, and state transitions" 
          />
          <button
            onClick={() => openSurface('session_timeline')}
            style={{
              background: 'linear-gradient(135deg, rgba(168, 129, 255, 0.2) 0%, rgba(126, 82, 245, 0.2) 100%)',
              border: '1px solid rgba(168, 129, 255, 0.4)',
              color: '#c4a6ff',
              padding: '8px 16px',
              borderRadius: '20px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
            <span>View Canonical Activity Stream</span>
            <span>→</span>
          </button>
        </div>
      )}

      {/* Transparent Time Insights Banner */}
      {timeInsights && (
        <div style={{
          background: 'rgba(20, 18, 28, 0.8)',
          border: '1px solid var(--hairline-2)',
          borderRadius: '12px',
          padding: '16px 20px',
          marginBottom: '20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '24px',
          flexWrap: 'wrap'
        }}>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '4px' }}>Active Focus Duration Today</div>
            <div style={{ fontSize: '20px', fontWeight: 700, color: '#60a5fa' }}>{timeInsights.total_active_time}</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '4px' }}>Total Events Stored</div>
            <div style={{ fontSize: '20px', fontWeight: 700, color: '#34d399' }}>{totalStored.toLocaleString()}</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '4px' }}>History Range</div>
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--ink-1)' }}>{dateRangeStr || '—'}</div>
          </div>
          {timeInsights.category_breakdown && (
            <div>
              <div style={{ fontSize: '11px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '4px' }}>Time Allocation</div>
              <div style={{ fontSize: '13px', color: 'var(--ink-1)', fontWeight: 500, display: 'flex', gap: '12px' }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
                  <span>Code: <strong style={{ color: '#d4a878' }}>{timeInsights.category_breakdown.coding}%</strong></span>
                </span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
                  <span>CLI: <strong style={{ color: '#60a5fa' }}>{timeInsights.category_breakdown.terminal}%</strong></span>
                </span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
                  <span>Web: <strong style={{ color: '#a78bfa' }}>{timeInsights.category_breakdown.browsing}%</strong></span>
                </span>
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Filters + transparency count */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '20px', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <label style={{ color: 'var(--ink-1)', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input 
              type="checkbox" 
              checked={importantOnly} 
              onChange={e => setImportantOnly(e.target.checked)} 
            />
            Show Important Only
          </label>
          <label style={{ color: 'var(--ink-1)', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input 
              type="checkbox" 
              checked={narrativeMode} 
              onChange={e => setNarrativeMode(e.target.checked)} 
            />
            Narrative Mode
          </label>
        </div>
        {!isLoading && events.length > 0 && (
          <div style={{ fontSize: '12px', color: 'var(--ink-3)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            <span>
              Showing {displayedEvents.length.toLocaleString()} of {filteredEvents.length.toLocaleString()} events
              {filteredEvents.length < events.length ? ` (${events.length.toLocaleString()} total)` : ''}
              {' · '}Persisted to disk
            </span>
          </div>
        )}
      </div>

      {isLoading ? (
        <LoadingState message="Fetching cognitive history..." />
      ) : events.length === 0 ? (
        <EmptyState 
          title="No Timeline Events" 
          description="Arova hasn't processed any cognitive events yet."
        />
      ) : (
        <div 
          ref={scrollRef}
          onScroll={handleScroll}
          style={{ display: 'flex', flexDirection: 'column', overflowY: 'auto', paddingRight: '12px', flex: 1 }}
        >
          {dayGroups.map(group => (
            <div key={group.dateKey}>
              {/* Day separator */}
              <div style={{ 
                display: 'flex', alignItems: 'center', gap: '12px', 
                margin: '8px 0 20px 0',
                position: 'sticky', top: 0, zIndex: 2,
                padding: '6px 0',
                background: 'var(--bg-1, #0d0b14)'
              }}>
                <div style={{ 
                  fontSize: '12px', fontWeight: 700, color: 'var(--ink-2)',
                  textTransform: 'uppercase', letterSpacing: '0.06em',
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '6px',
                  padding: '4px 10px',
                  whiteSpace: 'nowrap'
                }}>
                  {group.label}
                </div>
                <div style={{ flex: 1, height: '1px', background: 'rgba(255,255,255,0.06)' }} />
                <div style={{ fontSize: '11px', color: 'var(--ink-3)', whiteSpace: 'nowrap' }}>
                  {group.events.length} event{group.events.length !== 1 ? 's' : ''}
                </div>
              </div>

              {group.events.map(event => {
                const timeStr = new Date(event.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                const isExpanded = expandedId === event.id;
                
                return (
                  <div key={event.id} style={{ display: 'flex', marginBottom: '24px' }}>
                    <div style={{ width: '60px', color: 'var(--ink-2)', fontSize: '12px', paddingTop: '4px' }}>
                      {timeStr}
                    </div>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginRight: '16px' }}>
                      <div style={{ 
                        width: '12px', height: '12px', borderRadius: '50%', 
                        backgroundColor: getCategoryColor(event.category),
                        boxShadow: `0 0 10px ${getCategoryColor(event.category)}40`
                      }} />
                      <div style={{ width: '2px', flex: 1, backgroundColor: 'var(--ink-3)', marginTop: '8px', minHeight: '40px' }} />
                    </div>
                    
                    <div style={{ flex: 1 }}>
                      <div 
                        onClick={() => setExpandedId(isExpanded ? null : event.id)}
                        style={{ 
                          backgroundColor: narrativeMode ? 'transparent' : 'var(--bg-2)', 
                          border: narrativeMode ? 'none' : '1px solid var(--ink-3)',
                          borderRadius: '8px', 
                          padding: narrativeMode ? '0 0 16px 0' : '16px',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease'
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                          <div style={{ color: narrativeMode ? 'var(--ink-1)' : 'var(--ink-0)', fontWeight: 500, fontSize: narrativeMode ? '14px' : '15px' }}>
                            {narrativeMode ? event.description : event.title}
                          </div>
                          {event.importance >= 0.8 && (
                            <div style={{ fontSize: '11px', color: 'var(--accent-orange)', border: '1px solid var(--accent-orange)', padding: '2px 6px', borderRadius: '4px' }}>
                              Critical
                            </div>
                          )}
                        </div>
                        
                        {!narrativeMode && (
                          <>
                            <div style={{ color: 'var(--ink-1)', fontSize: '13px', marginTop: '8px', marginBottom: '12px' }}>
                              {event.description}
                            </div>
                            
                            <div style={{ fontSize: '12px', color: 'var(--ink-2)', display: 'flex', gap: '16px' }}>
                              <span style={{ opacity: 0.7 }}>Source: {event.source}</span>
                              {event.correlation_id && <span style={{ opacity: 0.7 }}>Thread: {event.correlation_id.slice(0,8)}</span>}
                            </div>
                          </>
                        )}

                        {isExpanded && (
                          <div style={{ 
                            marginTop: '16px', 
                            padding: '12px', 
                            backgroundColor: 'rgba(0,0,0,0.2)', 
                            borderRadius: '6px',
                            borderLeft: `2px solid ${getCategoryColor(event.category)}`
                          }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                              <div style={{ color: 'var(--ink-0)', fontSize: '12px', fontWeight: 600 }}>
                                Why did Arova do this?
                              </div>
                              {event.title.startsWith('App Active:') && event.metadata?.app_name && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    window.dispatchEvent(new CustomEvent('arova-send', {
                                      detail: { type: 'environment.ignore_app', app_name: event.metadata.app_name }
                                    }));
                                    // Optimistically remove this and any other events from this app
                                    setEvents(prev => prev.filter(ev => !(ev.title.startsWith('App Active:') && ev.metadata?.app_name === event.metadata.app_name)));
                                  }}
                                  style={{ 
                                    backgroundColor: 'transparent', 
                                    border: '1px solid var(--accent-red)', 
                                    color: 'var(--accent-red)', 
                                    padding: '4px 8px', 
                                    borderRadius: '4px', 
                                    cursor: 'pointer',
                                    fontSize: '11px',
                                    transition: 'all 0.2s ease'
                                  }}
                                  onMouseOver={(e) => { e.currentTarget.style.backgroundColor = 'var(--accent-red)'; e.currentTarget.style.color = 'white'; }}
                                  onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = 'var(--accent-red)'; }}
                                >
                                  Stop tracking this app
                                </button>
                              )}
                            </div>
                            <pre style={{ margin: 0, fontSize: '11px', color: 'var(--ink-1)', whiteSpace: 'pre-wrap' }}>
                              {JSON.stringify(event.metadata, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ))}

          {/* Load more indicator */}
          {displayedEvents.length < filteredEvents.length && (
            <div 
              style={{ 
                padding: '16px', textAlign: 'center', cursor: 'pointer',
                color: 'var(--accent-blue)', fontSize: '13px', fontWeight: 600,
                background: 'rgba(96, 165, 250, 0.06)',
                border: '1px solid rgba(96, 165, 250, 0.15)',
                borderRadius: '8px',
                marginBottom: '20px',
                transition: 'all 0.2s ease'
              }}
              onClick={() => setVisibleCount(prev => Math.min(prev + 100, filteredEvents.length))}
            >
              Load more · {(filteredEvents.length - displayedEvents.length).toLocaleString()} remaining events
            </div>
          )}

          {/* End of history marker */}
          {displayedEvents.length >= filteredEvents.length && filteredEvents.length > 0 && (
            <div style={{ 
              padding: '12px 16px', textAlign: 'center', 
              color: 'var(--ink-3)', fontSize: '12px',
              borderTop: '1px solid rgba(255,255,255,0.06)',
              marginTop: '8px'
            }}>
              End of recorded history · {events.length.toLocaleString()} total events stored on disk
            </div>
          )}
        </div>
      )}
    </div>
  );
};
