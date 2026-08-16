import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSurfaceState, SurfaceType } from '../../state';
import { OrbShell } from '../orb/OrbShell';

const RailStyles = () => (
  <style>{`
    .child-glyph {
      margin-left: 16px;
      width: calc(100% - 16px) !important;
    }
    .child-glyph .glyph-mark {
      transform: scale(0.82);
    }
    .rail-glyph.child-glyph:hover .glyph-mark {
      transform: scale(0.92);
    }
    .rail-glyph.child-glyph.active .glyph-mark {
      transform: scale(0.92);
    }
  `}</style>
);

interface RailItem {
  id: SurfaceType;
  label: string;
  icon: React.ReactNode;
  liveColor?: 'violet' | 'gold' | 'sage' | 'ice-blue';
}

interface RailGroupData {
  id: SurfaceType;
  title: string;
  icon: React.ReactNode;
  items: RailItem[];
}

const GROUPS: RailGroupData[] = [
  {
    id: 'cognition',
    title: 'Cognition',
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round"><path d="M4 6h16M4 12h10M4 18h14"/></svg>,
    items: [
      { id: 'timeline', label: 'Timeline', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> },
      { id: 'threads', label: 'Threads', liveColor: 'ice-blue', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg> },
      { id: 'memory', label: 'Memory', liveColor: 'violet', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round"><circle cx="12" cy="12" r="3"/><circle cx="5" cy="6" r="1.5"/><circle cx="19" cy="6" r="1.5"/><circle cx="5" cy="18" r="1.5"/><circle cx="19" cy="18" r="1.5"/><path d="M9.5 11 6 7M14.5 11 18 7M9.5 13 6 17M14.5 13 18 17"/></svg> },
      { id: 'journal', label: 'Journal', liveColor: 'gold', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg> },
      { id: 'context', label: 'Context', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg> }
    ]
  },
  {
    id: 'environment', // Kept internal ID for compatibility but changed title
    title: 'Awareness',
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>,
    items: [
      { id: 'awareness', label: 'Visibility', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg> },
      { id: 'workspace', label: 'Workspace', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg> },
      { id: 'attention', label: 'Attention', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="22"/><line x1="2" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="22" y2="12"/></svg> }
    ]
  },
  {
    id: 'runtime',
    title: 'Runtime',
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>,
    items: [
      { id: 'diagnostics', label: 'Diagnostics', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg> },
      { id: 'agents', label: 'Agents', liveColor: 'sage', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round"><circle cx="12" cy="6" r="2.5"/><circle cx="6" cy="16" r="2.5"/><circle cx="18" cy="16" r="2.5"/><path d="M12 8.5 8 13.5M12 8.5l4 5M8 16h8"/></svg> },
      { id: 'plans', label: 'Plans', liveColor: 'gold', icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round"><path d="M4 6h16M4 12h12M4 18h8"/></svg> }
    ]
  }
];

const RailGlyph: React.FC<{ surface: SurfaceType; label: string; icon: React.ReactNode; isActive?: boolean; isChild?: boolean; liveColor?: 'violet' | 'gold' | 'sage' | 'ice-blue' }> = ({ surface, label, icon, isActive, isChild, liveColor }) => {
  const { openSurface } = useSurfaceState();
  return (
    <button className={`rail-glyph ${isActive ? 'active' : ''} ${isChild ? 'child-glyph' : ''}`} onClick={() => openSurface(surface)}>
      <div className="glyph-mark">
        {icon}
        {liveColor && <span className={`live ${liveColor === 'ice-blue' ? '' : liveColor}`}></span>}
      </div>
      <div className="glyph-label" style={isChild ? { marginLeft: '8px' } : undefined}>
        {label}
      </div>
    </button>
  );
};

const AccordionGroup: React.FC<{ 
  group: RailGroupData; 
  isExpanded: boolean; 
  onToggle: () => void;
}> = ({ group, isExpanded, onToggle }) => {
  const { activeSurface, openSurface } = useSurfaceState();
  const isGroupActive = activeSurface === group.id || group.items.some(i => i.id === activeSurface);

  return (
    <div className="rail-group" style={{ width: '100%' }}>
      <button 
        className={`rail-glyph ${isGroupActive ? 'active' : ''}`} 
        onClick={(e) => {
          e.stopPropagation();
          openSurface(group.id);
          onToggle();
        }}
        onMouseEnter={() => {
          if (!isExpanded) onToggle();
        }}
      >
        <div className="glyph-mark">
          {group.icon}
        </div>
        <div className="glyph-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span>{group.title}</span>
        </div>
      </button>

      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            style={{ overflow: 'hidden' }}
          >
            <div className="rail-group-items" style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingTop: '8px' }}>
              {group.items.map(item => (
                <RailGlyph
                  key={item.id}
                  surface={item.id}
                  label={item.label}
                  icon={item.icon}
                  liveColor={item.liveColor}
                  isActive={activeSurface === item.id}
                  isChild={true}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export const SpatialRail: React.FC = () => {
  const { activeSurface } = useSurfaceState();
  const [expandedGroupId, setExpandedGroupId] = useState<string | null>(null);

  return (
    <>
      <RailStyles />
      <nav 
        className="rail" 
        id="rail"
        onMouseLeave={() => setExpandedGroupId(null)}
      >
        <div className="rail-brand" style={{ position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%) scale(0.13)', pointerEvents: 'none' }}>
            <OrbShell />
          </div>
        </div>

        <RailGlyph
          surface="presence"
          label="Presence"
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round"><circle cx="12" cy="12" r="3.5"/></svg>}
          isActive={activeSurface === 'presence' || activeSurface === null}
          liveColor="ice-blue"
        />

        <div className="rail-divider"></div>

        {GROUPS.map(group => (
          <AccordionGroup 
            key={group.id} 
            group={group} 
            isExpanded={expandedGroupId === group.id}
            onToggle={() => setExpandedGroupId(expandedGroupId === group.id ? null : group.id)}
          />
        ))}

        <div className="rail-divider"></div>

        <RailGlyph
          surface="settings"
          label="Settings"
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/></svg>}
          isActive={activeSurface === 'settings'}
        />
      </nav>
    </>
  );
};
