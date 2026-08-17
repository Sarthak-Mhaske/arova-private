import React, { useEffect, useState } from 'react';
import { SurfaceHeader, SurfaceSection, InfoRow, ActionButton, EmptyState, LoadingState } from '../ui/CoherenceComponents';
import { useCognitionState, useSurfaceState } from '../../state';
import { socket } from '../../runtime/socket';
import { MemoryGraphView } from './MemoryGraphView';
import { TimelineSurface } from './TimelineSurface';
import { JournalSurface } from './JournalSurface';

const formatRelativeTime = (timestamp: number) => {
  const diffMs = Date.now() - timestamp * 1000;
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
};

type MainTabType = 'vault' | 'timeline' | 'journal';
type VaultSubTabType = 'memories' | 'inbox' | 'pinned' | 'policy';

export const MemorySurface: React.FC = () => {
  const { closeSurface } = useSurfaceState();
  const { memories, pendingMemories, setPendingMemories, setMemories } = useCognitionState();
  const [isLoading, setIsLoading] = useState(true);
  const [isError] = useState(false);
  const [mainTab, setMainTab] = useState<MainTabType>('vault');
  const [vaultTab, setVaultTab] = useState<VaultSubTabType>('memories');
  const [viewMode, setViewMode] = useState<'graph' | 'list'>('graph');
  const [selectedPolicy, setSelectedPolicy] = useState<string>('review_queue');

  useEffect(() => {
    socket.sendEvent({ type: 'memory.query_request', req_id: 'mem_init' });
    socket.sendEvent({ type: 'config.get_request' });

    const handleEvent = (event: any) => {
      const ev = event.detail;
      if (ev.type === 'config.sync') {
        if (ev.config?.memory_policy?.tier2_mode) {
          setSelectedPolicy(ev.config.memory_policy.tier2_mode);
        } else if (ev.config && !ev.config.memory_policy?.tier2_mode) {
          setSelectedPolicy('review_queue');
        }
      }
    };
    window.addEventListener('arova-event', handleEvent);

    const t = setTimeout(() => {
      setIsLoading(false);
    }, 600);

    return () => {
      clearTimeout(t);
      window.removeEventListener('arova-event', handleEvent);
    };
  }, []);

  const handlePinToggle = (id: string, currentlyPinned: boolean) => {
    socket.sendEvent({ type: currentlyPinned ? 'memory.unpin' : 'memory.pin', memory_id: id });
    setMemories(memories.map(m => m.id === id ? { ...m, decay_score: currentlyPinned ? 0 : -1 } : m));
    setTimeout(() => socket.sendEvent({ type: 'memory.query_request', req_id: 'refresh' }), 300);
  };
  
  const handleForget = (id: string) => {
    socket.sendEvent({ type: 'memory.forget', memory_id: id });
    setMemories(memories.filter(m => m.id !== id));
    setTimeout(() => socket.sendEvent({ type: 'memory.query_request', req_id: 'refresh' }), 300);
  };
  
  const handleApproveInbox = (id: string) => {
    socket.sendEvent({ type: 'memory.approve', memory_id: id, duration: 'permanent' });
    setPendingMemories(pendingMemories.filter(m => m.id !== id));
    setTimeout(() => socket.sendEvent({ type: 'memory.query_request', req_id: 'refresh' }), 500);
  };
  
  const handleDiscardInbox = (id: string) => {
    socket.sendEvent({ type: 'memory.reject', memory_id: id });
    setPendingMemories(pendingMemories.filter(m => m.id !== id));
  };

  if (isError) {
    return (
      <div className="surface-content" style={{ padding: '42px', height: '100%', display: 'flex', flexDirection: 'column' }}>
        <SurfaceHeader title="Memory &amp; Cognition Hub" sub="Brain Hub" />
        <EmptyState title="Connection Lost" description="Failed to retrieve semantic memories from the local database. Ensure Arova Daemon is running." />
        <div style={{ marginTop: '16px', textAlign: 'center' }}>
          <ActionButton label="Retry" onClick={() => socket.sendEvent({ type: 'memory.query_request' })} />
        </div>
      </div>
    );
  }

  const pinnedMemories = memories.filter(m => m.decay_score === -1);
  const regularMemories = memories.filter(m => m.decay_score !== -1 && m.approval_state === 'saved');

  const vaultTabs = [
    { id: 'memories', label: 'All Knowledge', count: regularMemories.length },
    { id: 'inbox', label: 'Review Queue', count: pendingMemories.length },
    { id: 'pinned', label: 'Pinned Decisions', count: pinnedMemories.length },
    { id: 'policy', label: 'Memory Policy', count: 0 }
  ];

  return (
    <div className="surface-content" style={{ height: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}>
      
      {/* Top Hub Navigation Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px 28px 16px', borderBottom: '1px solid var(--hairline-2)', background: 'rgba(0,0,0,0.15)' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button 
            onClick={() => setMainTab('vault')}
            style={{
              padding: '10px 18px',
              border: 'none',
              background: mainTab === 'vault' ? 'var(--glass-2)' : 'transparent',
              color: mainTab === 'vault' ? 'var(--ink)' : 'var(--ink-3)',
              fontWeight: mainTab === 'vault' ? 600 : 500,
              fontSize: '14px',
              cursor: 'pointer',
              borderRadius: '10px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              transition: 'all 0.2s ease',
              boxShadow: mainTab === 'vault' ? 'var(--shadow-sm)' : 'none'
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3"></circle>
              <circle cx="5" cy="6" r="1.5"></circle>
              <circle cx="19" cy="6" r="1.5"></circle>
              <circle cx="5" cy="18" r="1.5"></circle>
              <circle cx="19" cy="18" r="1.5"></circle>
              <path d="M9.5 11 6 7M14.5 11 18 7M9.5 13 6 17M14.5 13 18 17"></path>
            </svg>
            Memory Vault ({regularMemories.length})
          </button>

          <button 
            onClick={() => setMainTab('timeline')}
            style={{
              padding: '10px 18px',
              border: 'none',
              background: mainTab === 'timeline' ? 'var(--glass-2)' : 'transparent',
              color: mainTab === 'timeline' ? 'var(--ink)' : 'var(--ink-3)',
              fontWeight: mainTab === 'timeline' ? 600 : 500,
              fontSize: '14px',
              cursor: 'pointer',
              borderRadius: '10px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              transition: 'all 0.2s ease',
              boxShadow: mainTab === 'timeline' ? 'var(--shadow-sm)' : 'none'
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            Activity Timeline
          </button>

          <button 
            onClick={() => setMainTab('journal')}
            style={{
              padding: '10px 18px',
              border: 'none',
              background: mainTab === 'journal' ? 'var(--glass-2)' : 'transparent',
              color: mainTab === 'journal' ? 'var(--ink)' : 'var(--ink-3)',
              fontWeight: mainTab === 'journal' ? 600 : 500,
              fontSize: '14px',
              cursor: 'pointer',
              borderRadius: '10px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              transition: 'all 0.2s ease',
              boxShadow: mainTab === 'journal' ? 'var(--shadow-sm)' : 'none'
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
            </svg>
            Developer Journal
          </button>
        </div>

        <button className="surface-close" onClick={() => closeSurface()} aria-label="Close">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <path d="M6 6l12 12M18 6 6 18"/>
          </svg>
        </button>
      </div>

      {/* TAB 1: MEMORY VAULT */}
      {mainTab === 'vault' && (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
          {/* Subtabs for Vault */}
          <div style={{ padding: '16px 28px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--hairline-2)' }}>
            <div style={{ display: 'flex', gap: '20px' }}>
              {vaultTabs.map(tab => (
                <div 
                  key={tab.id}
                  onClick={() => setVaultTab(tab.id as VaultSubTabType)}
                  style={{ 
                    fontSize: '13px', 
                    fontWeight: vaultTab === tab.id ? 600 : 500,
                    color: vaultTab === tab.id ? 'var(--ink)' : 'var(--ink-3)',
                    cursor: 'pointer',
                    paddingBottom: '12px',
                    position: 'relative',
                    transition: 'color 0.2s ease'
                  }}
                >
                  {tab.label} {tab.count > 0 && <span style={{ opacity: 0.6, marginLeft: '4px' }}>({tab.count})</span>}
                  {vaultTab === tab.id && (
                    <div style={{ position: 'absolute', bottom: '-1px', left: 0, right: 0, height: '2px', background: 'var(--accent-gold)' }} />
                  )}
                </div>
              ))}
            </div>

            {vaultTab === 'memories' && (
              <div style={{ display: 'flex', background: 'var(--glass-2)', borderRadius: '8px', padding: '2px', border: '1px solid var(--hairline-2)', marginBottom: '8px' }}>
                <button 
                  onClick={() => setViewMode('graph')}
                  style={{ 
                    padding: '4px 12px', fontSize: '12px', borderRadius: '6px', border: 'none', cursor: 'pointer',
                    background: viewMode === 'graph' ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
                    color: viewMode === 'graph' ? 'var(--ink)' : 'var(--ink-3)',
                    fontWeight: viewMode === 'graph' ? 600 : 400
                  }}
                >
                  2D Graph
                </button>
                <button 
                  onClick={() => setViewMode('list')}
                  style={{ 
                    padding: '4px 12px', fontSize: '12px', borderRadius: '6px', border: 'none', cursor: 'pointer',
                    background: viewMode === 'list' ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
                    color: viewMode === 'list' ? 'var(--ink)' : 'var(--ink-3)',
                    fontWeight: viewMode === 'list' ? 600 : 400
                  }}
                >
                  List
                </button>
              </div>
            )}
          </div>

          {/* Vault Content */}
          <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            {isLoading ? (
              <div style={{ padding: '42px' }}>
                <LoadingState message="Scanning semantic database..." />
              </div>
            ) : vaultTab === 'memories' && regularMemories.length === 0 ? (
              <div style={{ padding: '42px' }}>
                <EmptyState 
                  title="No Memories Yet" 
                  description="Arova will automatically synthesize facts and preferences as you converse."
                />
              </div>
            ) : vaultTab === 'inbox' && pendingMemories.length === 0 ? (
              <div style={{ padding: '42px' }}>
                <EmptyState 
                  title="Review Queue Empty" 
                  description="No memories are currently waiting for your review."
                />
              </div>
            ) : vaultTab === 'pinned' && pinnedMemories.length === 0 ? (
              <div style={{ padding: '42px' }}>
                <EmptyState 
                  title="Nothing Pinned" 
                  description="Pin architectural memories to make them permanently active."
                />
              </div>
            ) : vaultTab === 'memories' && viewMode === 'graph' ? (
              <div style={{ flex: 1, width: '100%', position: 'relative', overflow: 'hidden' }}>
                <MemoryGraphView 
                  memories={regularMemories} 
                  onPinToggle={handlePinToggle} 
                  onForget={handleForget} 
                />
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', flex: 1, overflowY: 'auto', padding: '24px 28px' }}>
                {vaultTab === 'inbox' && pendingMemories.map(m => (
                  <SurfaceSection key={m.id}>
                    <div style={{ fontSize: '15px', fontWeight: 500, color: 'var(--ink)', lineHeight: 1.5, marginBottom: '12px' }}>
                      {m.content}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '16px' }}>
                      <InfoRow label="Category" value={m.category} />
                      <InfoRow label="Reason" value={m.why_remembered || "Identified as personal context"} />
                    </div>
                    <div style={{ display: 'flex', gap: '12px' }}>
                      <ActionButton label="Approve" variant="primary" onClick={() => handleApproveInbox(m.id)} />
                      <ActionButton label="Discard" variant="danger" onClick={() => handleDiscardInbox(m.id)} />
                    </div>
                  </SurfaceSection>
                ))}
                
                {(vaultTab === 'memories' ? regularMemories : vaultTab === 'pinned' ? pinnedMemories : []).map(m => (
                  <SurfaceSection key={m.id}>
                    <div style={{ fontSize: '15px', fontWeight: 500, color: 'var(--ink)', lineHeight: 1.5, marginBottom: '12px' }}>
                      {m.content}
                    </div>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '14px' }}>
                      {m.why_remembered && <InfoRow label="Why" value={m.why_remembered} />}
                      <InfoRow label="Category" value={m.category} />
                      <InfoRow label="Continuity" value={`${Math.round((m.continuity_value || 0.5) * 100)}%`} />
                      <InfoRow label="Referenced" value={`${m.reinforcement_count} times`} />
                      <InfoRow label="Last Used" value={formatRelativeTime(m.last_reinforced_at)} />
                    </div>

                    <div style={{ display: 'flex', gap: '12px' }}>
                      <ActionButton 
                        label={m.decay_score === -1 ? 'Unpin' : 'Pin'} 
                        variant={m.decay_score === -1 ? 'primary' : 'secondary'}
                        onClick={() => handlePinToggle(m.id, m.decay_score === -1)} 
                      />
                      <ActionButton 
                        label="Forget" 
                        variant="danger" 
                        onClick={() => handleForget(m.id)} 
                      />
                    </div>
                  </SurfaceSection>
                ))}
                
                {vaultTab === 'policy' && (
                  <SurfaceSection>
                    <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--ink)', marginBottom: '14px' }}>
                      How should Arova persist personal memories?
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '20px' }}>
                      {[
                        { id: 'review_queue', label: 'Review Queue', desc: 'Place new memories into the inbox for explicit manual confirmation.' },
                        { id: 'auto_save', label: 'Save Automatically', desc: 'Synthesize and persist memories silently into the semantic database.' },
                        { id: 'ask', label: 'Ask Immediately', desc: 'Prompt for confirmation as soon as a key personal fact is detected.' }
                      ].map(p => (
                        <label key={p.id} style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer', color: 'var(--ink)', padding: '10px 14px', background: 'rgba(0,0,0,0.15)', borderRadius: '10px', border: '1px solid var(--hairline-2)' }}>
                          <input 
                            type="radio" 
                            name="memory_policy_settings" 
                            checked={selectedPolicy === p.id} 
                            onChange={() => setSelectedPolicy(p.id)}
                            style={{ accentColor: 'var(--accent-gold)' }}
                          />
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                            <span style={{ fontSize: '14px', fontWeight: 600 }}>{p.label}</span>
                            <span style={{ fontSize: '12px', color: 'var(--ink-3)' }}>{p.desc}</span>
                          </div>
                        </label>
                      ))}
                    </div>
                    <ActionButton 
                      label="Save Preference" 
                      variant="primary" 
                      onClick={() => {
                        socket.sendEvent({ type: 'memory.set_tier2_policy', mode: selectedPolicy });
                        setVaultTab('memories');
                      }} 
                    />
                  </SurfaceSection>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: ACTIVITY TIMELINE */}
      {mainTab === 'timeline' && (
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <TimelineSurface embedded />
        </div>
      )}

      {/* TAB 3: DEVELOPER JOURNAL */}
      {mainTab === 'journal' && (
        <div style={{ flex: 1, overflow: 'hidden', padding: '16px 28px 24px' }}>
          <JournalSurface embedded />
        </div>
      )}

    </div>
  );
};
