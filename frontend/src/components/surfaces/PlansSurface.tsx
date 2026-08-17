import React, { useState, useEffect } from 'react';
import { useSurfaceState, useAwarenessState } from '../../state';
import { socket } from '../../runtime/socket';

interface PlanStep {
  id: string;
  title: string;
  detail: string;
  completed: boolean;
  action_type?: string;
  last_result?: string;
}

interface Plan {
  id: string;
  title: string;
  goal: string;
  created_at: number;
  status: string;
  steps: PlanStep[];
}

export const PlansSurface: React.FC = () => {
  const { closeSurface } = useSurfaceState();
  const { activeWorkspace } = useAwarenessState();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [activePlanId, setActivePlanId] = useState<string>('');
  const [newGoalInput, setNewGoalInput] = useState<string>('');
  const [executingStepId, setExecutingStepId] = useState<string | null>(null);
  const [stepLogs, setStepLogs] = useState<Record<string, string>>({});

  useEffect(() => {
    // Request plans from backend
    socket.sendEvent({ type: 'planner.get_plans' });

    const handleMessage = (msg: any) => {
      if (msg.type === 'planner.plans_sync') {
        const syncedPlans = msg.plans || [];
        setPlans(syncedPlans);
        if (syncedPlans.length > 0 && !activePlanId) {
          setActivePlanId(syncedPlans[0].id);
        }
      } else if (msg.type === 'planner.step_execution_started') {
        setExecutingStepId(msg.step_id);
      } else if (msg.type === 'planner.step_execution_completed') {
        setExecutingStepId(null);
        if (msg.output && msg.step_id) {
          setStepLogs(prev => ({ ...prev, [msg.step_id]: msg.output }));
        }
      }
    };

    const cleanup = socket.onMessage(handleMessage);
    return () => cleanup();
  }, [activePlanId]);

  const activePlan = plans.find(p => p.id === activePlanId) || plans[0];

  const handleCreatePlan = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newGoalInput.trim()) return;
    socket.sendEvent({
      type: 'planner.create_plan',
      goal: newGoalInput.trim()
    });
    setNewGoalInput('');
  };

  const handleSyncWorkspaceGoal = () => {
    const ws = activeWorkspace as any;
    const nextAction = ws?.understanding?.momentum?.next_action || 'Complete active project features & verify build';
    const title = ws?.title || 'Active Workspace';
    socket.sendEvent({
      type: 'planner.create_plan',
      goal: nextAction,
      title: `${title} — ${nextAction.slice(0, 35)}...`
    });
  };

  const handleToggleStep = (planId: string, stepId: string) => {
    socket.sendEvent({
      type: 'planner.toggle_step',
      plan_id: planId,
      step_id: stepId
    });
  };

  const handleExecuteStep = (planId: string, stepId: string) => {
    setExecutingStepId(stepId);
    socket.sendEvent({
      type: 'planner.execute_step',
      plan_id: planId,
      step_id: stepId
    });
  };

  const handleDeletePlan = (planId: string) => {
    socket.sendEvent({
      type: 'planner.delete_plan',
      plan_id: planId
    });
    if (activePlanId === planId) {
      const remaining = plans.filter(p => p.id !== planId);
      setActivePlanId(remaining.length > 0 ? remaining[0].id : '');
    }
  };

  const completedCount = activePlan?.steps?.filter(s => s.completed).length || 0;
  const totalCount = activePlan?.steps?.length || 0;
  const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <div className="surface-content" style={{ padding: '28px 32px', height: '100%', display: 'flex', flexDirection: 'column', overflowY: 'auto', boxSizing: 'border-box' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--ink, #fff)', letterSpacing: '-0.01em', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>Milestone Execution Plans</span>
            <span style={{ fontSize: '11px', fontWeight: 600, padding: '2px 7px', borderRadius: '4px', background: 'rgba(224, 186, 117, 0.15)', color: 'var(--accent-gold, #e0ba75)' }}>
              Interactive
            </span>
          </div>
          <div style={{ fontSize: '12.5px', color: 'var(--ink-3)', marginTop: '2px' }}>
            Hierarchical goal decomposition with real-time environment action verification.
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

      {/* Goal Creator Bar */}
      <form onSubmit={handleCreatePlan} style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
        <input 
          type="text"
          placeholder="Enter a new project objective (e.g. 'Audit security headers & optimize build bundle')..."
          value={newGoalInput}
          onChange={(e) => setNewGoalInput(e.target.value)}
          style={{
            flex: 1,
            background: 'var(--glass-1, rgba(255,255,255,0.04))',
            border: '1px solid var(--hairline-2, rgba(255,255,255,0.1))',
            borderRadius: '8px',
            padding: '10px 14px',
            color: 'var(--ink, #fff)',
            fontSize: '13px',
            outline: 'none'
          }}
        />
        <button 
          type="submit"
          style={{
            background: 'var(--accent-gold, #e0ba75)',
            color: '#1a1714',
            fontWeight: 600,
            fontSize: '12.5px',
            border: 'none',
            borderRadius: '8px',
            padding: '0 16px',
            cursor: 'pointer',
            whiteSpace: 'nowrap'
          }}
        >
          + Create Plan
        </button>
        <button 
          type="button"
          onClick={handleSyncWorkspaceGoal}
          title="Import active momentum goal from current workspace signals"
          style={{
            background: 'var(--glass-2, rgba(255,255,255,0.06))',
            color: 'var(--ink-2, #ccc)',
            border: '1px solid var(--hairline-2, rgba(255,255,255,0.12))',
            borderRadius: '8px',
            padding: '0 12px',
            fontSize: '12px',
            cursor: 'pointer',
            whiteSpace: 'nowrap'
          }}
        >
          Sync Active Context
        </button>
      </form>

      {/* Plans Navigation Tabs if Multiple */}
      {plans.length > 1 && (
        <div style={{ display: 'flex', gap: '6px', overflowX: 'auto', paddingBottom: '8px', marginBottom: '14px' }}>
          {plans.map(p => (
            <button
              key={p.id}
              onClick={() => setActivePlanId(p.id)}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: activePlan?.id === p.id ? 600 : 400,
                background: activePlan?.id === p.id ? 'var(--glass-2, rgba(255,255,255,0.12))' : 'var(--glass-1, rgba(255,255,255,0.03))',
                border: activePlan?.id === p.id ? '1px solid var(--accent-gold, #e0ba75)' : '1px solid var(--hairline-2)',
                color: activePlan?.id === p.id ? 'var(--accent-gold, #e0ba75)' : 'var(--ink-3)',
                cursor: 'pointer',
                whiteSpace: 'nowrap'
              }}
            >
              {p.title}
            </button>
          ))}
        </div>
      )}

      {/* Active Plan Detail Card */}
      {activePlan ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Card Header & Progress */}
          <div style={{ background: 'var(--glass-1, rgba(255,255,255,0.03))', border: '1px solid var(--hairline-2, rgba(255,255,255,0.08))', borderRadius: '12px', padding: '16px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--ink, #fff)' }}>{activePlan.title}</div>
                <div style={{ fontSize: '12px', color: 'var(--ink-3)', marginTop: '2px' }}>Goal: {activePlan.goal}</div>
              </div>
              <button 
                onClick={() => handleDeletePlan(activePlan.id)}
                title="Delete Plan"
                style={{ background: 'transparent', border: 'none', color: 'var(--ink-3)', cursor: 'pointer', fontSize: '12px' }}
              >
                Delete
              </button>
            </div>

            {/* Progress Bar */}
            <div style={{ marginTop: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--ink-3)', marginBottom: '6px' }}>
                <span>{completedCount} of {totalCount} checkpoints completed</span>
                <span style={{ fontWeight: 600, color: progressPercent === 100 ? '#4caf50' : 'var(--accent-gold)' }}>{progressPercent}%</span>
              </div>
              <div style={{ width: '100%', height: '4px', borderRadius: '2px', background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
                <div style={{ width: `${progressPercent}%`, height: '100%', background: progressPercent === 100 ? '#4caf50' : 'var(--accent-gold)', transition: 'width 0.3s ease' }} />
              </div>
            </div>
          </div>

          {/* Steps List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {activePlan.steps?.map((step, idx) => {
              const isExecuting = executingStepId === step.id;
              const logResult = stepLogs[step.id] || step.last_result;

              return (
                <div
                  key={step.id}
                  style={{
                    background: step.completed ? 'rgba(255,255,255,0.015)' : 'var(--glass-1, rgba(255,255,255,0.03))',
                    border: step.completed ? '1px solid rgba(255,255,255,0.04)' : '1px solid var(--hairline-2, rgba(255,255,255,0.08))',
                    borderRadius: '10px',
                    padding: '12px 16px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      {/* Checkbox */}
                      <input 
                        type="checkbox"
                        checked={step.completed}
                        onChange={() => handleToggleStep(activePlan.id, step.id)}
                        style={{ cursor: 'pointer', accentColor: 'var(--accent-gold, #e0ba75)', width: '15px', height: '15px' }}
                      />
                      <div>
                        <span style={{ fontSize: '13px', fontWeight: 500, color: step.completed ? 'var(--ink-3)' : 'var(--ink, #fff)', textDecoration: step.completed ? 'line-through' : 'none' }}>
                          {idx + 1}. {step.title}
                        </span>
                        {step.detail && (
                          <div style={{ fontSize: '11.5px', color: 'var(--ink-3)', marginTop: '2px' }}>
                            {step.detail}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Action Execution Button */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {!step.completed && (
                        <button
                          onClick={() => handleExecuteStep(activePlan.id, step.id)}
                          disabled={isExecuting}
                          style={{
                            background: isExecuting ? 'rgba(255,255,255,0.05)' : 'rgba(224, 186, 117, 0.12)',
                            color: isExecuting ? 'var(--ink-3)' : 'var(--accent-gold, #e0ba75)',
                            border: '1px solid rgba(224, 186, 117, 0.25)',
                            borderRadius: '6px',
                            padding: '4px 10px',
                            fontSize: '11px',
                            fontWeight: 600,
                            cursor: isExecuting ? 'not-allowed' : 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}
                        >
                          {isExecuting ? 'Running...' : 'Execute'}
                        </button>
                      )}
                      {step.completed && (
                        <span style={{ fontSize: '11px', color: '#4caf50', fontWeight: 500 }}>Completed</span>
                      )}
                    </div>
                  </div>

                  {/* Real Live Step Execution Log if available */}
                  {logResult && (
                    <div style={{ marginTop: '4px', padding: '6px 10px', background: 'rgba(0,0,0,0.3)', borderRadius: '6px', fontSize: '11px', color: 'var(--ink-2, #bbb)', fontFamily: 'var(--font-mono, monospace)' }}>
                      <span style={{ color: 'var(--accent-gold)' }}>Output:</span> {logResult}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--ink-3)', fontSize: '13px' }}>
          No active goal plans. Type an objective above or click "Sync Active Context".
        </div>
      )}
    </div>
  );
};
