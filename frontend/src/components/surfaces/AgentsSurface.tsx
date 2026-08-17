import React, { useState, useEffect } from 'react';
import { useSurfaceState } from '../../state';
import { socket } from '../../runtime/socket';

interface AgentRole {
  id: string;
  name: string;
  status: string;
  statusColor: string;
  description: string;
  capabilities: string[];
  liveMetric: string;
  actionLabel: string;
}

interface ActivityLog {
  id: string;
  agentId: string;
  timestamp: string;
  message: string;
  output?: string;
}

export const AgentsSurface: React.FC = () => {
  const { closeSurface } = useSurfaceState();
  const [roster, setRoster] = useState<AgentRole[]>([]);
  const [runningAgentId, setRunningAgentId] = useState<string | null>(null);
  const [researchQuery, setResearchQuery] = useState<string>('');
  const [activityLogs, setActivityLogs] = useState<ActivityLog[]>([]);

  useEffect(() => {
    // Request roster from backend
    socket.sendEvent({ type: 'agents.get_roster' });

    const handleMessage = (msg: any) => {
      if (msg.type === 'agents.roster_sync') {
        setRoster(msg.roster || []);
      } else if (msg.type === 'agents.task_started') {
        setRunningAgentId(msg.agent_id);
        const timeStr = new Date().toLocaleTimeString();
        setActivityLogs(prev => [
          {
            id: String(Date.now()),
            agentId: msg.agent_id,
            timestamp: timeStr,
            message: `Dispatched task to ${msg.agent_id}...`
          },
          ...prev.slice(0, 19)
        ]);
      } else if (msg.type === 'agents.task_completed') {
        setRunningAgentId(null);
        const timeStr = new Date().toLocaleTimeString();
        setActivityLogs(prev => [
          {
            id: String(Date.now()),
            agentId: msg.agent_id,
            timestamp: timeStr,
            message: `Task completed by ${msg.agent_id}.`,
            output: msg.output
          },
          ...prev.slice(0, 19)
        ]);
      }
    };

    const cleanup = socket.onMessage(handleMessage);
    return () => cleanup();
  }, []);

  const handleTriggerAgent = (agentId: string) => {
    setRunningAgentId(agentId);
    socket.sendEvent({
      type: 'agents.trigger_task',
      agent_id: agentId,
      input: agentId === 'research_specialist' ? researchQuery : ''
    });
    if (agentId === 'research_specialist') {
      setResearchQuery('');
    }
  };

  return (
    <div className="surface-content" style={{ padding: '28px 32px', height: '100%', display: 'flex', flexDirection: 'column', overflowY: 'auto', boxSizing: 'border-box' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--ink, #fff)', letterSpacing: '-0.01em', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>Autonomous Agent Swarm</span>
            <span style={{ fontSize: '11px', fontWeight: 600, padding: '2px 7px', borderRadius: '4px', background: 'rgba(76, 175, 80, 0.15)', color: '#4caf50' }}>
              Live Telemetry
            </span>
          </div>
          <div style={{ fontSize: '12.5px', color: 'var(--ink-3)', marginTop: '2px' }}>
            Specialized background workers coordinating code integrity, live web research, and reality indexing.
          </div>
        </div>

        <button 
          data-close
          onClick={() => closeSurface()}
          style={{ background: 'transparent', border: 'none', color: 'var(--ink-3)', cursor: 'pointer', padding: '6px', borderRadius: '6px' }}
        >
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      {/* Agents Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px', marginBottom: '24px' }}>
        {roster.map(agent => {
          const isRunning = runningAgentId === agent.id;

          return (
            <div
              key={agent.id}
              style={{
                background: 'var(--glass-1, rgba(255,255,255,0.03))',
                border: '1px solid var(--hairline-2, rgba(255,255,255,0.08))',
                borderRadius: '12px',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: '12px'
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '4px' }}>
                  <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--ink, #fff)' }}>{agent.name}</span>
                  <span style={{ fontSize: '11px', color: agent.statusColor, fontWeight: 500 }}>
                    {agent.status}
                  </span>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--ink-3)', lineHeight: '1.4' }}>
                  {agent.description}
                </div>

                {/* Capabilities Badges */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '10px' }}>
                  {agent.capabilities.map(cap => (
                    <span 
                      key={cap}
                      style={{ fontSize: '10.5px', padding: '2px 6px', borderRadius: '4px', background: 'rgba(255,255,255,0.05)', color: 'var(--ink-2, #ccc)' }}
                    >
                      {cap}
                    </span>
                  ))}
                </div>
              </div>

              {/* Action Trigger Area */}
              <div style={{ borderTop: '1px solid var(--hairline-2, rgba(255,255,255,0.06))', paddingTop: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {agent.id === 'research_specialist' && (
                  <input 
                    type="text"
                    placeholder="Search topic / query..."
                    value={researchQuery}
                    onChange={(e) => setResearchQuery(e.target.value)}
                    style={{
                      background: 'rgba(0,0,0,0.2)',
                      border: '1px solid var(--hairline-2, rgba(255,255,255,0.1))',
                      borderRadius: '6px',
                      padding: '6px 10px',
                      fontSize: '11.5px',
                      color: 'var(--ink, #fff)',
                      outline: 'none'
                    }}
                  />
                )}
                
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '11px', color: 'var(--ink-3)', fontFamily: 'var(--font-mono, monospace)' }}>
                    {agent.liveMetric}
                  </span>
                  <button
                    onClick={() => handleTriggerAgent(agent.id)}
                    disabled={isRunning}
                    style={{
                      background: isRunning ? 'rgba(255,255,255,0.05)' : 'rgba(224, 186, 117, 0.12)',
                      color: isRunning ? 'var(--ink-3)' : 'var(--accent-gold, #e0ba75)',
                      border: '1px solid rgba(224, 186, 117, 0.25)',
                      borderRadius: '6px',
                      padding: '4px 10px',
                      fontSize: '11px',
                      fontWeight: 600,
                      cursor: isRunning ? 'not-allowed' : 'pointer'
                    }}
                  >
                    {isRunning ? 'Running...' : agent.actionLabel}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Live Activity Stream */}
      <div style={{ background: 'var(--glass-1, rgba(255,255,255,0.02))', border: '1px solid var(--hairline-2, rgba(255,255,255,0.06))', borderRadius: '12px', padding: '16px', flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--ink, #fff)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#4caf50' }}></span>
          <span>Agent Execution Console & Activity Stream</span>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {activityLogs.length > 0 ? (
            activityLogs.map(log => (
              <div 
                key={log.id}
                style={{ padding: '8px 12px', background: 'rgba(0,0,0,0.25)', borderRadius: '8px', borderLeft: '3px solid var(--accent-gold, #e0ba75)', fontSize: '12px', fontFamily: 'var(--font-mono, monospace)' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--ink-3)', fontSize: '10.5px' }}>
                  <span>[{log.timestamp}] {log.agentId}</span>
                </div>
                <div style={{ color: 'var(--ink, #fff)', marginTop: '2px' }}>{log.message}</div>
                {log.output && (
                  <pre style={{ margin: '6px 0 0 0', padding: '6px 8px', background: 'rgba(0,0,0,0.4)', borderRadius: '4px', fontSize: '11px', color: 'var(--ink-2, #ccc)', whiteSpace: 'pre-wrap', maxHeight: '160px', overflowY: 'auto' }}>
                    {log.output}
                  </pre>
                )}
              </div>
            ))
          ) : (
            <div style={{ color: 'var(--ink-3)', fontSize: '12px', textAlign: 'center', padding: '24px 0' }}>
              No recent agent dispatches. Click an action above to trigger a background agent run.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
