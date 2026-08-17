import React from 'react';
import { useSurfaceState, SurfaceType } from '../../state';
import { OrbShell } from '../orb/OrbShell';

interface RailItem {
  id: SurfaceType;
  label: string;
  icon: React.ReactNode;
  liveColor?: 'violet' | 'gold' | 'sage' | 'ice-blue';
}

const RAIL_ITEMS: RailItem[] = [
  {
    id: 'threads',
    label: 'Chat & Threads',
    liveColor: 'ice-blue',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
    )
  },
  {
    id: 'memory',
    label: 'Brain & Memory',
    liveColor: 'violet',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8">
        <circle cx="12" cy="12" r="3"/>
        <circle cx="5" cy="6" r="1.5"/>
        <circle cx="19" cy="6" r="1.5"/>
        <circle cx="5" cy="18" r="1.5"/>
        <circle cx="19" cy="18" r="1.5"/>
        <path d="M9.5 11 6 7M14.5 11 18 7M9.5 13 6 17M14.5 13 18 17"/>
      </svg>
    )
  },
  {
    id: 'workspace',
    label: 'Workspace Context',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8">
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
      </svg>
    )
  },
  {
    id: 'settings',
    label: 'Control Center',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
    )
  }
];

export const SpatialRail: React.FC = () => {
  const { activeSurface, openSurface } = useSurfaceState();

  return (
    <nav className="rail" id="rail">
      <div 
        className="rail-brand" 
        style={{ position: 'relative', overflow: 'hidden', cursor: 'pointer' }}
        onClick={() => openSurface('presence')}
        title="Ambient Presence"
      >
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%) scale(0.13)', pointerEvents: 'none' }}>
          <OrbShell />
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%', padding: '0 8px' }}>
        {RAIL_ITEMS.map(item => {
          const isActive = activeSurface === item.id || 
            (item.id === 'memory' && (activeSurface === 'timeline' || activeSurface === 'journal')) ||
            (item.id === 'settings' && activeSurface === 'awareness');

          return (
            <button 
              key={item.id}
              className={`rail-glyph ${isActive ? 'active' : ''}`}
              onClick={() => openSurface(item.id)}
              style={{ width: '100%' }}
            >
              <div className="glyph-mark">
                {item.icon}
                {item.liveColor && <span className={`live ${item.liveColor === 'ice-blue' ? '' : item.liveColor}`}></span>}
              </div>
              <div className="glyph-label">
                {item.label}
              </div>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
