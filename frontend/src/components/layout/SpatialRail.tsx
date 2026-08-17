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
  targetTab?: string;
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
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <path d="M4 6h16M4 12h10M4 18h14"/>
      </svg>
    ),
    items: [
      { 
        id: 'threads', 
        label: 'Threads', 
        liveColor: 'ice-blue', 
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        ) 
      },
      { 
        id: 'memory', 
        label: 'Memory Vault', 
        liveColor: 'violet', 
        targetTab: 'vault',
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
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
        id: 'journal', 
        label: 'Journal', 
        liveColor: 'gold', 
        targetTab: 'journal',
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
          </svg>
        ) 
      },
    ]
  },
  {
    id: 'environment',
    title: 'Awareness',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <circle cx="12" cy="12" r="9"/>
        <path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>
      </svg>
    ),
    items: [
      { 
        id: 'workspace', 
        label: 'Workspace', 
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
          </svg>
        ) 
      },
      { 
        id: 'awareness', 
        label: 'Privacy & Policy', 
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            <polyline points="9 12 11 14 15 10"/>
          </svg>
        ) 
      }
    ]
  },
  {
    id: 'runtime',
    title: 'Runtime',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
      </svg>
    ),
    items: [
      { 
        id: 'developer_mode', 
        label: 'Diagnostics', 
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
          </svg>
        ) 
      },
      { 
        id: 'agents', 
        label: 'Agents', 
        liveColor: 'sage',
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <circle cx="12" cy="6" r="2.5"/>
            <circle cx="6" cy="16" r="2.5"/>
            <circle cx="18" cy="16" r="2.5"/>
            <path d="M12 8.5 8 13.5M12 8.5l4 5M8 16h8"/>
          </svg>
        ) 
      },
      { 
        id: 'plans', 
        label: 'Plans', 
        liveColor: 'gold',
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <path d="M4 6h16M4 12h12M4 18h8"/>
          </svg>
        ) 
      }
    ]
  }
];

const RailGlyph: React.FC<{ 
  surface: SurfaceType; 
  label: string; 
  icon: React.ReactNode; 
  isActive?: boolean; 
  isChild?: boolean; 
  liveColor?: 'violet' | 'gold' | 'sage' | 'ice-blue';
  targetTab?: string;
}> = ({ surface, label, icon, isActive, isChild, liveColor, targetTab }) => {
  const { openSurface } = useSurfaceState();
  return (
    <button 
      className={`rail-glyph ${isActive ? 'active' : ''} ${isChild ? 'child-glyph' : ''}`} 
      onClick={() => {
        if (surface === 'journal' || targetTab === 'journal') {
          openSurface('memory', 'journal');
        } else {
          openSurface(surface, targetTab);
        }
      }}
      style={{ width: '100%' }}
    >
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
  const { activeSurface, activeTab, openSurface } = useSurfaceState();
  
  const isGroupActive = activeSurface === group.id || group.items.some(i => {
    if (i.id === 'journal') {
      return activeSurface === 'journal' || (activeSurface === 'memory' && activeTab === 'journal');
    }
    if (i.id === 'memory') {
      return activeSurface === 'memory' && activeTab !== 'journal';
    }
    if (i.id === 'developer_mode') {
      return activeSurface === 'developer_mode' || activeSurface === 'diagnostics' || activeSurface === 'runtime';
    }
    return i.id === activeSurface;
  });

  return (
    <div className="rail-group" style={{ width: '100%' }}>
      <button 
        className={`rail-glyph ${isGroupActive ? 'active' : ''}`} 
        onClick={(e) => {
          e.stopPropagation();
          if (group.id === 'cognition') openSurface('threads');
          else if (group.id === 'environment') openSurface('workspace');
          else if (group.id === 'runtime') openSurface('developer_mode');
          else openSurface(group.id);
          onToggle();
        }}
        onMouseEnter={() => {
          if (!isExpanded) onToggle();
        }}
        style={{ width: '100%' }}
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
              {group.items.map(item => {
                const isActive = item.id === 'journal' 
                  ? (activeSurface === 'journal' || (activeSurface === 'memory' && activeTab === 'journal'))
                  : item.id === 'memory'
                  ? (activeSurface === 'memory' && activeTab !== 'journal')
                  : item.id === 'developer_mode'
                  ? (activeSurface === 'developer_mode' || activeSurface === 'diagnostics' || activeSurface === 'runtime')
                  : (activeSurface === item.id);

                return (
                  <RailGlyph
                    key={item.id}
                    surface={item.id}
                    targetTab={item.targetTab}
                    label={item.label}
                    icon={item.icon}
                    liveColor={item.liveColor}
                    isActive={isActive}
                    isChild={true}
                  />
                );
              })}
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
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <circle cx="12" cy="12" r="3.5"/>
            </svg>
          }
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
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
          }
          isActive={activeSurface === 'settings' || activeSurface === 'system'}
        />
      </nav>
    </>
  );
};
