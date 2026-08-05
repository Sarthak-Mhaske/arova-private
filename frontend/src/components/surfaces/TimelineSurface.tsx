import React, { useEffect, useState } from 'react';
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

export const TimelineSurface: React.FC = () => {
  const { openSurface } = useSurfaceState();
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [importantOnly, setImportantOnly] = useState(false);
  const [narrativeMode, setNarrativeMode] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchTimeline = () => {
    socket.sendEvent({
      type: 'timeline.get_request',
      limit: 50,
      req_id: `tl_${Date.now()}`
    });
  };

  useEffect(() => {
    // Request initial timeline state
    fetchTimeline();

    // 10s periodic refresh for live updates
    const interval = setInterval(fetchTimeline, 10000);

    const handleFocusOrVisible = () => {
      if (document.visibilityState === 'visible') {
        fetchTimeline();
      }
    };

    const handleEvent = (e: CustomEvent) => {
      const payload = e.detail;
      
      if (payload.type === 'timeline.query_response') {
        setEvents(payload.events || []);
        setIsLoading(false);
      } else if (payload.type === 'TIMELINE_EVENT') {
        const newEvent = payload.event;
        if (newEvent) {
          setEvents(prev => [newEvent, ...prev]);
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
  }, []);

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

  return (
    <div className="surface-content" style={{ padding: '42px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <SurfaceHeader 
          title="Cognitive Timeline" 
          sub="Transparent view of Arova's internal cognition and state transitions" 
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
          <span>⚡ View Canonical Activity Stream</span>
          <span>→</span>
        </button>
      </div>
      
      <div style={{ display: 'flex', gap: '16px', marginBottom: '24px' }}>
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

      {isLoading ? (
        <LoadingState message="Fetching cognitive history..." />
      ) : events.length === 0 ? (
        <EmptyState 
          title="No Timeline Events" 
          description="Arova hasn't processed any cognitive events yet."
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', overflowY: 'auto', paddingRight: '12px' }}>
          {filteredEvents.map(event => {
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
      )}
    </div>
  );
};
