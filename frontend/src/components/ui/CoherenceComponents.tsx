import React from 'react';

import { useSurfaceState } from '../../state';

// =====================================
// SURFACE HEADER
// =====================================
export const SurfaceHeader: React.FC<{ title: string; sub: string }> = ({ title, sub }) => {
  const { closeSurface } = useSurfaceState();
  return (
    <div style={{ marginBottom: '32px', paddingBottom: '16px', borderBottom: '1px solid var(--glass-edge)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <div>
        <h2 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--ink)', margin: '0 0 8px 0' }}>{title}</h2>
        <div style={{ fontSize: '14px', color: 'var(--ink-2)', letterSpacing: '0.02em' }}>{sub}</div>
      </div>
      <button 
        data-close 
        aria-label="Close"
        onClick={() => closeSurface()}
        style={{ background: 'transparent', border: 'none', color: 'var(--ink)', cursor: 'pointer', padding: '8px', opacity: 0.7 }}
        onMouseOver={e => e.currentTarget.style.opacity = '1'}
        onMouseOut={e => e.currentTarget.style.opacity = '0.7'}
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    </div>
  );
};

// =====================================
// SURFACE SECTION
// =====================================
export const SurfaceSection: React.FC<{ title?: string; children: React.ReactNode }> = ({ title, children }) => (
  <div style={{ 
    background: 'var(--glass-1)', 
    padding: '24px', 
    borderRadius: '16px', 
    border: '1px solid var(--glass-edge)',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    marginBottom: '20px'
  }}>
    {title && (
      <div style={{ fontSize: '14px', color: 'var(--ink-2)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {title}
      </div>
    )}
    {children}
  </div>
);

// =====================================
// METRIC CARD
// =====================================
export const MetricCard: React.FC<{ label: string; value: React.ReactNode; accent?: boolean }> = ({ label, value, accent }) => (
  <div style={{ 
    background: 'var(--glass-2)', 
    padding: '16px', 
    borderRadius: '12px',
    border: '1px solid var(--hairline-2)',
    flex: 1
  }}>
    <div style={{ fontSize: '12px', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
      {label}
    </div>
    <div style={{ fontSize: '18px', color: accent ? 'var(--accent-amber)' : 'var(--ink)' }}>
      {value}
    </div>
  </div>
);

// =====================================
// INFO ROW
// =====================================
export const InfoRow: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '12px', background: 'var(--glass-2)', borderRadius: '8px' }}>
    <span style={{ color: 'var(--ink-3)', fontSize: '14px' }}>{label}</span>
    <span style={{ color: 'var(--ink)', fontSize: '14px', fontWeight: 500 }}>{value}</span>
  </div>
);

// =====================================
// STATUS PILL
// =====================================
export const StatusPill: React.FC<{ state: 'active' | 'idle' | 'error' | 'warning' | string; label: string }> = ({ state, label }) => {
  let bg = 'var(--glass-2)';
  let color = 'var(--ink-2)';
  let border = 'var(--glass-edge)';

  if (state === 'active') {
    color = '#4caf50';
    border = 'rgba(76, 175, 80, 0.3)';
  } else if (state === 'warning') {
    color = 'var(--accent-amber)';
    border = 'rgba(255, 170, 0, 0.3)';
  } else if (state === 'error') {
    color = '#f44336';
    border = 'rgba(244, 67, 54, 0.3)';
  }

  return (
    <span style={{ 
      fontSize: '12px', 
      padding: '4px 10px', 
      borderRadius: '12px',
      background: bg,
      color: color,
      border: `1px solid ${border}`,
      textTransform: 'uppercase',
      letterSpacing: '0.05em',
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
      whiteSpace: 'nowrap'
    }}>
      {label}
    </span>
  );
};

// =====================================
// ACTION BUTTON
// =====================================
export const ActionButton: React.FC<{ onClick: () => void; label: string; variant?: 'primary' | 'secondary' | 'danger' }> = ({ onClick, label, variant = 'secondary' }) => {
  let bg = 'var(--glass-2)';
  let color = 'var(--ink)';
  let border = 'var(--glass-edge)';

  if (variant === 'primary') {
    bg = 'rgba(255, 170, 0, 0.1)';
    color = 'var(--accent-amber)';
    border = 'var(--accent-amber)';
  } else if (variant === 'danger') {
    bg = 'transparent';
    color = '#e55';
    border = 'rgba(238, 85, 85, 0.3)';
  }

  return (
    <button 
      onClick={onClick}
      style={{
        padding: '8px 16px',
        borderRadius: '8px',
        border: `1px solid ${border}`,
        background: bg,
        color: color,
        fontSize: '14px',
        fontWeight: variant === 'primary' ? 500 : 400,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        display: 'inline-block'
      }}
    >
      {label}
    </button>
  );
};

// =====================================
// EMPTY STATE
// =====================================
export const EmptyState: React.FC<{ title: string; description: string }> = ({ title, description }) => (
  <div style={{
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '64px 32px',
    background: 'var(--glass-1)',
    borderRadius: '16px',
    border: '1px dashed var(--glass-edge)',
    textAlign: 'center'
  }}>
    <div style={{ fontSize: '18px', fontWeight: 500, color: 'var(--ink)', marginBottom: '8px' }}>{title}</div>
    <div style={{ fontSize: '14px', color: 'var(--ink-3)', maxWidth: '280px', lineHeight: 1.5 }}>{description}</div>
  </div>
);

// =====================================
// LOADING STATE
// =====================================
export const LoadingState: React.FC<{ message?: string }> = ({ message = 'Loading...' }) => (
  <div style={{
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '64px 32px',
    color: 'var(--ink-3)',
    fontSize: '14px',
    gap: '16px'
  }}>
    <div className="spinner" style={{
      width: '24px',
      height: '24px',
      border: '2px solid var(--glass-edge)',
      borderTopColor: 'var(--accent-amber)',
      borderRadius: '50%',
      animation: 'spin 1s linear infinite'
    }} />
    <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    {message}
  </div>
);
