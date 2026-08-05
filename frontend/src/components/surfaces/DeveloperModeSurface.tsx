import React, { useEffect, useState } from 'react';
import { socket } from '../../runtime/socket';

export const DeveloperModeSurface: React.FC = () => {
  const [debugState, setDebugState] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'kpi' | 'events' | 'workspace' | 'search' | 'resources' | 'restore' | 'traffic'>('kpi');

  useEffect(() => {
    const handleDebugState = (e: CustomEvent) => {
      const type = e.detail.type;
      if (type === 'dogfooding.debug_state') {
        setDebugState(e.detail.state);
      }
    };

    window.addEventListener('arova-event', handleDebugState as EventListener);
    socket.sendEvent({ type: 'dogfooding.get_debug_state' });

    const interval = setInterval(() => {
      socket.sendEvent({ type: 'dogfooding.get_debug_state' });
    }, 3000);

    return () => {
      window.removeEventListener('arova-event', handleDebugState as EventListener);
      clearInterval(interval);
    };
  }, []);

  const kpi = debugState?.kpi_metrics || {
    resume_attempts: 0,
    successful_resumes: 0,
    manual_searches_after_resume: 0,
    manual_file_opens: 0,
    avg_time_to_first_productive_action_sec: 0.0,
    restores_cancelled: 0
  };

  const capturedEvents = debugState?.captured_events || [];
  const activeWs = debugState?.active_workspace || {};
  const whyChose = debugState?.why_chose_workspace || [];
  const searchIndex = debugState?.search_index_contents || [];
  const resources = debugState?.resource_registry || [];
  const restorePlan = debugState?.restore_plan || {};
  const traffic = debugState?.event_bus_traffic || { active_subscribers: 0 };

  return (
    <div className="surface-content" style={{ padding: '36px', height: '100%', display: 'flex', flexDirection: 'column', gap: '20px', background: 'rgba(12, 12, 18, 0.96)', color: '#fff', overflowY: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(168, 129, 255, 0.3)', paddingBottom: '16px' }}>
        <div>
          <div style={{ fontSize: '11px', color: '#ffd700', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ffd700', display: 'inline-block', boxShadow: '0 0 8px #ffd700' }} />
            Internal Dogfooding Overlay (Triggered by Ctrl+Shift+D)
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: '#fff', marginTop: '4px' }}>
            Developer Mode
          </div>
        </div>
        <button
          onClick={() => socket.sendEvent({ type: 'dogfooding.get_debug_state' })}
          style={{ background: 'rgba(168, 129, 255, 0.2)', border: '1px solid #a881ff', color: '#fff', borderRadius: '8px', padding: '6px 14px', fontSize: '12px', cursor: 'pointer' }}
        >
          ↻ Refresh State
        </button>
      </div>

      {/* MANDATORY DOGFOODING RULE BANNER */}
      <div style={{ background: 'rgba(255, 215, 0, 0.12)', border: '1px solid #ffd700', borderRadius: '12px', padding: '14px 18px', display: 'flex', alignItems: 'center', gap: '12px', color: '#fff', fontSize: '13px', lineHeight: '1.4' }}>
        <span style={{ fontSize: '20px' }}>⚠️</span>
        <div>
          <strong style={{ color: '#ffd700' }}>MANDATORY TEAM DOGFOODING RULE:</strong> You are not allowed to manually search first. You must ask Arova first. If it fails or forces you to fall back to manual VS Code / Chrome search, report it immediately as a bug.
        </div>
      </div>

      {/* ONE DASHBOARD - THE EXACT 6 CORE NUMBERS */}
      <div style={{ background: 'linear-gradient(135deg, rgba(168, 129, 255, 0.1) 0%, rgba(20, 20, 30, 0.9) 100%)', border: '1px solid rgba(168, 129, 255, 0.35)', borderRadius: '14px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px', boxShadow: '0 8px 32px rgba(0,0,0,0.5)' }}>
        <div style={{ fontSize: '14px', fontWeight: 700, color: '#a881ff', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          🎯 Core Dogfooding KPI Dashboard (`Today`)
        </div>
        
        {kpi.resume_attempts === 0 && (kpi.continue_card_shown_count || 0) === 0 ? (
          <div style={{ padding: '16px', background: 'rgba(255,255,255,0.03)', borderRadius: '10px', color: 'rgba(255,255,255,0.7)', fontStyle: 'italic', fontSize: '13px', textAlign: 'center' }}>
            No resume data collected yet. Start working inside Arova and click Resume to begin collecting live telemetry.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.6)', textAlign: 'left' }}>
                <th style={{ padding: '8px 12px' }}>Metric</th>
                <th style={{ padding: '8px 12px', textAlign: 'right' }}>Today</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <td style={{ padding: '10px 12px', fontWeight: 500 }}>Resume attempts</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, color: '#fff', fontSize: '15px' }}>{kpi.resume_attempts}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <td style={{ padding: '10px 12px', fontWeight: 500 }}>Successful resumes</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, color: '#00e676', fontSize: '15px' }}>{kpi.successful_resumes}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <td style={{ padding: '10px 12px', fontWeight: 500 }}>Resume Acceptance Rate</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, color: '#00e676', fontSize: '15px' }}>
                  {kpi.resume_acceptance_rate || 0}% <span style={{ fontSize: '11px', color: '#888' }}>({kpi.resume_clicked_count || 0}/{kpi.continue_card_shown_count || 0})</span>
                </td>
              </tr>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <td style={{ padding: '10px 12px', fontWeight: 500 }}>Manual searches after resume</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, color: kpi.manual_searches_after_resume > 5 ? '#ff6b6b' : '#ffd700', fontSize: '15px' }}>{kpi.manual_searches_after_resume}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <td style={{ padding: '10px 12px', fontWeight: 500 }}>Manual file opens</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, color: kpi.manual_file_opens > 6 ? '#ff6b6b' : '#ffd700', fontSize: '15px' }}>{kpi.manual_file_opens}</td>
              </tr>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <td style={{ padding: '10px 12px', fontWeight: 500 }}>Average time to first productive action</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, color: kpi.avg_time_to_first_productive_action_sec <= 60 ? '#00e676' : '#ff6b6b', fontSize: '15px' }}>{kpi.avg_time_to_first_productive_action_sec} sec</td>
              </tr>
              <tr>
                <td style={{ padding: '10px 12px', fontWeight: 500 }}>Restores cancelled</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, color: '#a881ff', fontSize: '15px' }}>{kpi.restores_cancelled}</td>
              </tr>
            </tbody>
          </table>
        )}
      </div>

      {/* TABS NAVIGATION FOR THE 8 DOGFOODING INSPECTION SECTIONS */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '8px', flexWrap: 'wrap' }}>
        {[
          { id: 'kpi', label: '1. KPI Metrics & Analytics' },
          { id: 'events', label: `2. Captured Events (${capturedEvents.length})` },
          { id: 'workspace', label: '3. Active Workspace & Reasoning' },
          { id: 'search', label: `4. Search Index (${searchIndex.length})` },
          { id: 'resources', label: `5. Resource Registry (${resources.length})` },
          { id: 'restore', label: '6. Restore Plan' },
          { id: 'traffic', label: '7. Event Bus Traffic' },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            style={{
              background: activeTab === tab.id ? 'rgba(168, 129, 255, 0.3)' : 'rgba(255,255,255,0.05)',
              color: activeTab === tab.id ? '#fff' : 'rgba(255,255,255,0.7)',
              border: '1px solid',
              borderColor: activeTab === tab.id ? '#a881ff' : 'rgba(255,255,255,0.1)',
              borderRadius: '8px',
              padding: '6px 12px',
              fontSize: '12px',
              fontWeight: activeTab === tab.id ? 600 : 400,
              cursor: 'pointer'
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* TAB CONTENT */}
      <div style={{ flex: 1, overflowY: 'auto', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '16px' }}>
        {activeTab === 'kpi' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <h4 style={{ margin: '0 0 6px 0', color: '#ffd700' }}>North Star & Expanded Dogfooding Metrics</h4>
              <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.85)', lineHeight: '1.5' }}>
                Formula: <code>(Time to Productivity &lt;= 60s) AND (No Manual Search) AND (No Manual Reopening)</code>.
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div style={{ background: 'rgba(255,255,255,0.04)', padding: '14px', borderRadius: '8px' }}>
                <div style={{ fontSize: '12px', color: '#ffd700', fontWeight: 700, marginBottom: '6px' }}>CONFIDENCE CALIBRATION</div>
                <div style={{ fontSize: '13px', color: '#fff' }}>
                  ✓ Correct: <strong>{kpi.confidence_calibration?.correct_count || 0}</strong><br/>
                  △ Mostly Correct: <strong>{kpi.confidence_calibration?.mostly_correct_count || 0}</strong><br/>
                  ✗ Wrong: <strong>{kpi.confidence_calibration?.wrong_count || 0}</strong>
                </div>
              </div>

              <div style={{ background: 'rgba(255,255,255,0.04)', padding: '14px', borderRadius: '8px' }}>
                <div style={{ fontSize: '12px', color: '#00e676', fontWeight: 700, marginBottom: '6px' }}>POST-RESTORE UTILIZATION</div>
                <div style={{ fontSize: '13px', color: '#fff' }}>
                  Files Edited: <strong>{kpi.restoration_utilization?.restoration_edited_count || 0}</strong><br/>
                  Wasted (Closed): <strong>{kpi.restoration_utilization?.restoration_wasted_count || 0}</strong>
                </div>
              </div>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.04)', padding: '14px', borderRadius: '8px' }}>
              <div style={{ fontSize: '12px', color: '#a881ff', fontWeight: 700, marginBottom: '6px' }}>SEARCH ANALYTICS (Ctrl+Space)</div>
              <div style={{ fontSize: '13px', color: '#fff', display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                <span>Total Queries: <strong>{kpi.search_analytics?.total_queries || 0}</strong></span>
                <span>Click-Through: <strong>{kpi.search_analytics?.click_through_rate || 0}%</strong></span>
                <span>Avg Click Time: <strong>{kpi.search_analytics?.avg_time_to_click_sec || 0}s</strong></span>
                <span>2nd Search Rate: <strong>{kpi.search_analytics?.needed_second_search_rate || 0}%</strong></span>
              </div>
            </div>

            <div style={{ background: 'rgba(255,107,107,0.08)', border: '1px solid rgba(255,107,107,0.3)', padding: '14px', borderRadius: '8px' }}>
              <div style={{ fontSize: '12px', color: '#ff6b6b', fontWeight: 700, marginBottom: '8px' }}>RESUME FAILURE REASONS TALLY</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {kpi.failure_reasons && Object.entries(kpi.failure_reasons).map(([reason, count]: any, i: number) => (
                  <span key={i} style={{ background: 'rgba(0,0,0,0.4)', padding: '6px 10px', borderRadius: '6px', fontSize: '12px', color: '#fff' }}>
                    {reason.replace(/_/g, ' ')}: <strong style={{ color: count > 0 ? '#ff6b6b' : '#888' }}>{count}</strong>
                  </span>
                ))}
              </div>
            </div>

            <pre style={{ background: 'rgba(0,0,0,0.5)', padding: '12px', borderRadius: '8px', fontSize: '12px', color: '#00e676', overflowX: 'auto' }}>
              {JSON.stringify(kpi, null, 2)}
            </pre>
          </div>
        )}

        {activeTab === 'events' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <h4 style={{ margin: 0, color: '#a881ff' }}>Last 50 Canonical Activity Events</h4>
            {capturedEvents.length === 0 ? (
              <div style={{ fontSize: '13px', color: '#888', fontStyle: 'italic' }}>No events captured in current buffer yet.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {capturedEvents.slice().reverse().map((ev: any, idx: number) => (
                  <div key={idx} style={{ background: 'rgba(255,255,255,0.04)', padding: '8px 12px', borderRadius: '6px', fontSize: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <span style={{ color: '#ffd700', fontWeight: 600 }}>[{ev.source_plugin || 'system'}]</span>{' '}
                      <span style={{ color: '#fff', fontWeight: 500 }}>{ev.event_type}</span>
                    </div>
                    <div style={{ color: 'rgba(255,255,255,0.5)', fontFamily: 'monospace' }}>
                      seq:{ev.sequence} | {new Date((ev.timestamp || 0) * 1000).toLocaleTimeString()}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'workspace' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <h4 style={{ margin: '0 0 6px 0', color: '#ffd700' }}>Why Resume Chose This Workspace:</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', background: 'rgba(255, 215, 0, 0.08)', borderLeft: '3px solid #ffd700', padding: '10px 14px', borderRadius: '0 8px 8px 0', fontSize: '13px' }}>
                {whyChose.map((reason: string, i: number) => (
                  <div key={i}>• {reason}</div>
                ))}
              </div>
            </div>

            <div>
              <h4 style={{ margin: '0 0 6px 0', color: '#a881ff' }}>Active Workspace State:</h4>
              <pre style={{ background: 'rgba(0,0,0,0.5)', padding: '12px', borderRadius: '8px', fontSize: '12px', color: '#c4a6ff', overflowX: 'auto' }}>
                {JSON.stringify(activeWs, null, 2)}
              </pre>
            </div>
          </div>
        )}

        {activeTab === 'search' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <h4 style={{ margin: 0, color: '#a881ff' }}>Unified Search Index (`UniversalSearchIndex` Contents)</h4>
            {searchIndex.length === 0 ? (
              <div style={{ fontSize: '13px', color: '#888', fontStyle: 'italic' }}>Search index currently idle.</div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '8px' }}>
                {searchIndex.map((item: any, idx: number) => (
                  <div key={idx} style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', padding: '10px', borderRadius: '8px', fontSize: '12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span style={{ color: '#ffd700', fontWeight: 600 }}>[{item.kind}]</span>
                      <span style={{ color: 'rgba(255,255,255,0.5)' }}>{new Date((item.timestamp || 0) * 1000).toLocaleTimeString()}</span>
                    </div>
                    <div style={{ fontWeight: 600, color: '#fff' }}>{item.title}</div>
                    <div style={{ color: 'rgba(255,255,255,0.7)', marginTop: '4px', fontSize: '11px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.summary}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'resources' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <h4 style={{ margin: 0, color: '#a881ff' }}>Resource Registry (`ResourceRegistry` Normalized Items)</h4>
            {resources.length === 0 ? (
              <div style={{ fontSize: '13px', color: '#888', fontStyle: 'italic' }}>No resources registered in normalized store.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {resources.map((r: any, idx: number) => (
                  <div key={idx} style={{ background: 'rgba(255,255,255,0.04)', padding: '8px 12px', borderRadius: '6px', fontSize: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <span style={{ color: r.type === 'file' ? '#a881ff' : r.type === 'terminal' ? '#ffd700' : '#00e676', fontWeight: 600, marginRight: '8px' }}>
                        [{r.type.toUpperCase()}]
                      </span>
                      <span style={{ color: '#fff', fontWeight: 500 }}>{r.display_name || r.resource_id}</span>
                    </div>
                    <div>
                      <span style={{ color: r.exists ? '#00e676' : '#ff6b6b', fontSize: '11px', fontWeight: 600 }}>
                        {r.exists ? '✓ Exists' : '✗ Missing'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'restore' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <h4 style={{ margin: 0, color: '#a881ff' }}>Restore Plan (`RestoreOutcomeSummary`)</h4>
            <pre style={{ background: 'rgba(0,0,0,0.5)', padding: '12px', borderRadius: '8px', fontSize: '12px', color: '#c4a6ff', overflowX: 'auto' }}>
              {JSON.stringify(restorePlan, null, 2)}
            </pre>
          </div>
        )}

        {activeTab === 'traffic' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <h4 style={{ margin: 0, color: '#a881ff' }}>Event Bus Traffic (`RuntimeEventBus`)</h4>
            <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.85)' }}>
              Active subscribers attached to EventBus: <strong style={{ color: '#00e676' }}>{traffic.active_subscribers}</strong>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
