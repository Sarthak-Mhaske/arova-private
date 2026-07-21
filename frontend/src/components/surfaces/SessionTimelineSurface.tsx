import React, { useEffect, useState } from 'react';
import { SurfaceHeader, EmptyState, LoadingState } from '../ui/CoherenceComponents';
import { socket } from '../../runtime/socket';
import { useSurfaceState } from '../../state';

interface CanonicalActivityEvent {
  event_id: string;
  event_type: string;
  timestamp: number;
  source_plugin: string;
  normalized_payload: Record<string, any>;
  raw_payload?: Record<string, any>;
  provenance?: Record<string, any>;
  sequence?: number;
}

export const SessionTimelineSurface: React.FC = () => {
  const { openSurface } = useSurfaceState();
  const [canonicalEvents, setCanonicalEvents] = useState<CanonicalActivityEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    // Request canonical activity events from Phase 6 nervous system
    socket.sendEvent({
      type: 'timeline.get_canonical_events',
      limit: 100
    });

    const handleEvent = (e: CustomEvent) => {
      const payload = e.detail;
      if (payload.type === 'timeline.canonical_events') {
        setCanonicalEvents(payload.events || []);
        setIsLoading(false);
      } else if (payload.type === 'capture.event_ingested') {
        const newEvent = payload.event;
        if (newEvent) {
          setCanonicalEvents(prev => [newEvent, ...prev.filter(ev => ev.event_id !== newEvent.event_id)]);
        }
      }
    };

    window.addEventListener('arova-event', handleEvent as EventListener);
    return () => {
      window.removeEventListener('arova-event', handleEvent as EventListener);
    };
  }, []);

  const getSourceBadge = (source: string) => {
    switch (source?.toLowerCase()) {
      case 'vscode': return { bg: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6', label: 'VS CODE' };
      case 'terminal': return { bg: 'rgba(16, 185, 129, 0.15)', color: '#10b981', label: 'TERMINAL' };
      case 'chrome':
      case 'browser': return { bg: 'rgba(168, 85, 247, 0.15)', color: '#a855f7', label: 'BROWSER' };
      case 'git': return { bg: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', label: 'GIT' };
      default: return { bg: 'rgba(255, 255, 255, 0.1)', color: '#aaa', label: (source || 'OS').toUpperCase() };
    }
  };

  const sources = ['ALL', 'vscode', 'terminal', 'chrome', 'git', 'os'];
  const filteredEvents = canonicalEvents.filter(ev => {
    if (!selectedSource || selectedSource === 'ALL') return true;
    return ev.source_plugin?.toLowerCase() === selectedSource;
  });

  return (
    <div className="surface-content" style={{ padding: '42px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <SurfaceHeader 
          title="Session Timeline — Canonical Nervous System" 
          sub="Chronological event stream captured by Phase 6 activity adapters (`VS Code -> Terminal -> Browser -> Git`)" 
        />
        <button
          onClick={() => openSurface('timeline')}
          style={{
            background: 'rgba(255, 255, 255, 0.06)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            color: 'rgba(255, 255, 255, 0.8)',
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
          <span>← Back to Cognitive Timeline</span>
        </button>
      </div>
      
      {/* Source Filter Tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', overflowX: 'auto' }}>
        {sources.map(src => {
          const isSelected = (src === 'ALL' && selectedSource === null) || src === selectedSource;
          return (
            <button
              key={src}
              onClick={() => setSelectedSource(src === 'ALL' ? null : src)}
              style={{
                background: isSelected ? 'rgba(255,255,255,0.18)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${isSelected ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.08)'}`,
                borderRadius: '16px',
                padding: '6px 14px',
                color: isSelected ? '#fff' : 'rgba(255,255,255,0.6)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 160ms ease'
              }}
            >
              {src.toUpperCase()}
            </button>
          );
        })}
      </div>

      {isLoading ? (
        <LoadingState message="Connecting to Canonical Activity Capture Engine..." />
      ) : canonicalEvents.length === 0 ? (
        <EmptyState 
          title="No Activity Stream Events Yet" 
          description="As soon as you interact with VS Code, Terminal, Chrome, or Git, canonical events will appear here in real time."
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', overflowY: 'auto', paddingRight: '12px', flex: 1 }}>
          {filteredEvents.map((event, index) => {
            const timeStr = new Date(event.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            const badge = getSourceBadge(event.source_plugin);
            const isExpanded = expandedId === event.event_id;
            const title = event.normalized_payload?.title || event.normalized_payload?.resource_path || event.normalized_payload?.command || `Event (${event.event_type})`;
            const summary = event.normalized_payload?.summary || event.normalized_payload?.command || '';

            return (
              <React.Fragment key={event.event_id}>
                <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
                  {/* Timestamp & Sequence */}
                  <div style={{ width: '80px', color: 'rgba(255,255,255,0.5)', fontSize: '11px', paddingTop: '6px', textAlign: 'right' }}>
                    <div>{timeStr}</div>
                    {event.sequence !== undefined && (
                      <div style={{ fontSize: '9px', color: 'rgba(255,255,255,0.3)' }}>#{event.sequence}</div>
                    )}
                  </div>
                  
                  {/* Visual Node & Connector */}
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <div style={{ 
                      width: '14px', height: '14px', borderRadius: '50%', 
                      backgroundColor: badge.color,
                      boxShadow: `0 0 10px ${badge.color}60`,
                      border: '2px solid rgba(20,20,30,1)'
                    }} />
                    {index < filteredEvents.length - 1 && (
                      <div style={{ width: '2px', height: '44px', backgroundColor: 'rgba(255,255,255,0.12)', margin: '4px 0' }} />
                    )}
                  </div>
                  
                  {/* Event Content Card */}
                  <div 
                    onClick={() => setExpandedId(isExpanded ? null : event.event_id)}
                    style={{ 
                      flex: 1,
                      backgroundColor: isExpanded ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.03)', 
                      border: isExpanded ? '1px solid rgba(255,255,255,0.2)' : '1px solid rgba(255,255,255,0.06)',
                      borderRadius: '10px', 
                      padding: '14px',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      marginBottom: index < filteredEvents.length - 1 ? '4px' : '20px'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{
                          background: badge.bg,
                          color: badge.color,
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontSize: '10px',
                          fontWeight: 700,
                          letterSpacing: '0.04em'
                        }}>
                          {badge.label}
                        </span>
                        <span style={{ color: '#fff', fontWeight: 600, fontSize: '14px' }}>
                          {title}
                        </span>
                      </div>
                      <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.4)' }}>
                        {isExpanded ? '▲ Hide Details' : '▼ Details'}
                      </span>
                    </div>

                    {summary && summary !== title && (
                      <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: '13px', marginTop: '6px', lineHeight: '1.4' }}>
                        {summary}
                      </div>
                    )}

                    {isExpanded && (
                      <div style={{ 
                        marginTop: '12px', 
                        padding: '12px', 
                        backgroundColor: 'rgba(0,0,0,0.3)', 
                        borderRadius: '8px',
                        borderLeft: `3px solid ${badge.color}`
                      }}>
                        <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          Normalized Payload & Provenance (`Phase 6 & 8`)
                        </div>
                        <pre style={{ margin: 0, fontSize: '11px', color: 'rgba(255,255,255,0.85)', whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
                          {JSON.stringify({
                            normalized_payload: event.normalized_payload,
                            provenance: event.provenance,
                            event_type: event.event_type,
                            event_id: event.event_id
                          }, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              </React.Fragment>
            );
          })}
        </div>
      )}
    </div>
  );
};
