import React, { useEffect, useState } from 'react';
import { SurfaceHeader, SurfaceSection, InfoRow, ActionButton, EmptyState, LoadingState } from '../ui/CoherenceComponents';
import { useCognitionState } from '../../state';
import { socket } from '../../runtime/socket';
import { MemoryGraphView } from './MemoryGraphView';

const formatRelativeTime = (timestamp: number) => {
  const diffMs = Date.now() - timestamp * 1000;
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
};

type TabType = 'memories' | 'inbox' | 'pinned' | 'settings';

export const MemorySurface: React.FC = () => {
  const { memories, pendingMemories, setPendingMemories, setMemories } = useCognitionState();
  const [isLoading, setIsLoading] = useState(true);
  const [isError] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>('memories');
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
          setSelectedPolicy('review_queue'); // Default if not explicitly set
        }
      }
    };
    window.addEventListener('arova-event', handleEvent);

    const t = setTimeout(() => {
      setIsLoading(false);
    }, 800);

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
        <SurfaceHeader title="What I hold of you" sub="Memory" />
        <EmptyState title="Connection Lost" description="Failed to retrieve semantic memories from the local database. Ensure Arova Daemon is running." />
        <div style={{ marginTop: '16px', textAlign: 'center' }}>
          <ActionButton label="Retry" onClick={() => socket.sendEvent({ type: 'memory.query_request' })} />
        </div>
      </div>
    );
  }

  const pinnedMemories = memories.filter(m => m.decay_score === -1);
  const regularMemories = memories.filter(m => m.decay_score !== -1 && m.approval_state === 'saved');

  const tabs = [
    { id: 'memories', label: 'Memories', count: regularMemories.length },
    { id: 'inbox', label: 'Inbox', count: pendingMemories.length },
    { id: 'pinned', label: 'Pinned', count: pinnedMemories.length },
    { id: 'settings', label: 'Settings', count: 0 }
  ];

  return (
    <div className="surface-content" style={{ height: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}>
      
      {/* Header and Tabs */}
      <div style={{ padding: '28px 36px 0 36px', zIndex: 10 }}>
        <div>
          <SurfaceHeader title="What I hold of you" sub={`Memory · ${regularMemories.length} semantic nodes`} />
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', borderBottom: '1px solid var(--hairline-2)', paddingBottom: '12px' }}>
            <div style={{ display: 'flex', gap: '24px' }}>
              {tabs.map(tab => (
                <div 
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as TabType)}
                  style={{ 
                    fontSize: '14px', 
                    fontWeight: activeTab === tab.id ? 600 : 500,
                    color: activeTab === tab.id ? 'var(--ink)' : 'var(--ink-3)',
                    cursor: 'pointer',
                    position: 'relative',
                    transition: 'color 0.2s ease'
                  }}
                >
                  {tab.label} {tab.count > 0 && <span style={{ opacity: 0.5, marginLeft: '4px' }}>({tab.count})</span>}
                  {activeTab === tab.id && (
                    <div style={{ position: 'absolute', bottom: '-13px', left: 0, right: 0, height: '2px', background: 'var(--ink)' }} />
                  )}
                </div>
              ))}
            </div>
            
            {activeTab === 'memories' && (
              <div style={{ display: 'flex', background: 'var(--glass-2)', borderRadius: '6px', padding: '2px', border: '1px solid var(--hairline-2)' }}>
                <button 
                  onClick={() => setViewMode('graph')}
                  style={{ 
                    padding: '4px 12px', fontSize: '12px', borderRadius: '4px', border: 'none', cursor: 'pointer',
                    background: viewMode === 'graph' ? 'var(--glass-hover)' : 'transparent',
                    color: viewMode === 'graph' ? 'var(--ink)' : 'var(--ink-3)'
                  }}
                >
                  Graph
                </button>
                <button 
                  onClick={() => setViewMode('list')}
                  style={{ 
                    padding: '4px 12px', fontSize: '12px', borderRadius: '4px', border: 'none', cursor: 'pointer',
                    background: viewMode === 'list' ? 'var(--glass-hover)' : 'transparent',
                    color: viewMode === 'list' ? 'var(--ink)' : 'var(--ink-3)'
                  }}
                >
                  List
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* Content Area */}
      {isLoading ? (
        <div style={{ padding: '0 42px 42px 42px' }}>
          <LoadingState message="Scanning semantic database..." />
        </div>
      ) : activeTab === 'memories' && regularMemories.length === 0 ? (
        <div style={{ padding: '0 42px 42px 42px' }}>
          <EmptyState 
            title="No Memories Yet" 
            description="Arova will automatically extract facts and preferences as you converse."
          />
        </div>
      ) : activeTab === 'inbox' && pendingMemories.length === 0 ? (
        <div style={{ padding: '0 42px 42px 42px' }}>
          <EmptyState 
            title="Inbox Empty" 
            description="No memories are currently waiting for your review."
          />
        </div>
      ) : activeTab === 'pinned' && pinnedMemories.length === 0 ? (
        <div style={{ padding: '0 42px 42px 42px' }}>
          <EmptyState 
            title="Nothing Pinned" 
            description="Pin memories to prevent them from ever decaying."
          />
        </div>
      ) : activeTab === 'memories' && viewMode === 'graph' ? (
        <div style={{ flex: 1, minHeight: '680px', width: '100%', position: 'relative', overflow: 'hidden', padding: '0 24px 24px 24px' }}>
           <MemoryGraphView 
            memories={regularMemories} 
            onPinToggle={handlePinToggle} 
            onForget={handleForget} 
          />
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', flex: 1, overflowY: 'auto', padding: '0 42px 42px 42px', zIndex: 1, position: 'relative' }}>
          
          {activeTab === 'inbox' && pendingMemories.map(m => (
            <SurfaceSection key={m.id}>
              <div style={{ fontSize: '16px', fontWeight: 500, color: 'var(--ink)', lineHeight: 1.5, marginBottom: '12px' }}>
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
          
          {(activeTab === 'memories' ? regularMemories : activeTab === 'pinned' ? pinnedMemories : []).map(m => (
            <SurfaceSection key={m.id}>
              <div style={{ fontSize: '16px', fontWeight: 500, color: 'var(--ink)', lineHeight: 1.5, marginBottom: '12px' }}>
                {m.content}
              </div>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '16px' }}>
                <div style={{ fontSize: '13px', color: 'var(--ink-2)', marginBottom: '8px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Metadata
                </div>
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
          
          {activeTab === 'settings' && (
            <SurfaceSection>
              <div style={{ fontSize: '16px', fontWeight: 500, color: 'var(--ink)', marginBottom: '16px' }}>
                How should Arova handle personal memories?
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '24px' }}>
                {[
                  { id: 'review_queue', label: 'Review later', desc: 'Inbox' },
                  { id: 'auto_save', label: 'Save automatically', desc: '' },
                  { id: 'ask', label: 'Ask every time', desc: '' }
                ].map(p => (
                  <label key={p.id} style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', color: 'var(--ink)' }}>
                    <input 
                      type="radio" 
                      name="memory_policy_settings" 
                      checked={selectedPolicy === p.id} 
                      onChange={() => setSelectedPolicy(p.id)}
                      style={{ accentColor: 'var(--accent-gold)' }}
                    />
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontSize: '14px', fontWeight: 500 }}>{p.label}</span>
                      {p.desc && <span style={{ fontSize: '12px', color: 'var(--ink-3)' }}>{p.desc}</span>}
                    </div>
                  </label>
                ))}
              </div>
              <ActionButton 
                label="Save Preference" 
                variant="primary" 
                onClick={() => {
                  socket.sendEvent({ type: 'memory.set_tier2_policy', mode: selectedPolicy });
                  setActiveTab('memories');
                }} 
              />
            </SurfaceSection>
          )}
        </div>
      )}
    </div>
  );
};
