import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
const MDiv: any = motion.div;
import { useSurfaceState } from '../../state';
import { MemorySurface } from './MemorySurface';
import { WorkspaceSurface } from './WorkspaceSurface';
import { ThreadsSurface } from './ThreadsSurface';
import { CognitionSurface } from './CognitionSurface';
import { AwarenessSurface } from './AwarenessSurface';
import { CommandPaletteSurface } from './CommandPaletteSurface';
import { SessionTimelineSurface } from './SessionTimelineSurface';
import { DeveloperModeSurface } from './DeveloperModeSurface';
import { AgentsSurface } from './AgentsSurface';
import { PlansSurface } from './PlansSurface';
import { SettingsLayout } from '../../surfaces/settings/SettingsLayout';
import { sheetEnter, scrimEnter, easeSpring, easeSoft } from '../../motion';
import { WorkHubSurface } from './WorkHubSurface';

export const EmergentSurface: React.FC = () => {
  const { activeSurface, closeSurface } = useSurfaceState();
  const isOpen = activeSurface !== null && activeSurface !== 'environment';
  const surfaceRef = useRef<HTMLDivElement>(null);
  const lastFocusedRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      lastFocusedRef.current = document.activeElement as HTMLElement;
      
      const timer = setTimeout(() => {
        if (surfaceRef.current) {
          const closeBtn = surfaceRef.current.querySelector('[data-close]') as HTMLElement;
          if (closeBtn) closeBtn.focus();
        }
      }, 200);

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          closeSurface();
          return;
        }
        
        if (e.key === 'Tab' && surfaceRef.current) {
          const focusables = Array.from(surfaceRef.current.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'));
          if (focusables.length === 0) return;
          const first = focusables[0];
          const last = focusables[focusables.length - 1];
          
          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
          } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      };

      document.addEventListener('keydown', handleKeyDown);
      return () => {
        clearTimeout(timer);
        document.removeEventListener('keydown', handleKeyDown);
      };
    } else {
      if (lastFocusedRef.current) {
        lastFocusedRef.current.focus();
        lastFocusedRef.current = null;
      }
    }
  }, [isOpen, closeSurface]);

  return (
    <AnimatePresence>
      {activeSurface && activeSurface !== 'environment' && (
        <div style={{ 
          position: 'fixed', 
          inset: 0, 
          zIndex: 100, 
          display: 'grid', 
          placeItems: 'center', 
          pointerEvents: 'none' 
        }}>
          <MDiv 
            className="surface-scrim"
            onClick={() => closeSurface()}
            variants={scrimEnter}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={{ duration: 0.52, ease: easeSoft.ease }}
            style={{ opacity: 1, pointerEvents: 'auto' }}
          />
          <MDiv 
            className="surface-sheet"
            role="dialog"
            aria-modal="true"
            ref={surfaceRef}
            variants={sheetEnter}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={{ ...easeSpring }}
            style={(activeSurface === 'memory' || activeSurface === 'journal' || activeSurface === 'timeline') ? {
              pointerEvents: 'auto',
              width: 'min(1400px, 94vw)',
              height: 'calc(100vh - 80px)',
              maxHeight: 'calc(100vh - 80px)',
              padding: 0,
              overflow: 'hidden'
            } : { 
              pointerEvents: 'auto', 
              maxHeight: 'calc(100vh - 120px)' 
            }}
          >
            {activeSurface === 'work' && <WorkHubSurface onContinue={() => closeSurface()} />}
            {activeSurface === 'presence' && <WorkHubSurface onContinue={() => closeSurface()} />}
            {activeSurface === 'cognition' && <CognitionSurface />}
            {activeSurface === 'threads' && <ThreadsSurface />}
            {activeSurface === 'memory' && <MemorySurface />}
            {activeSurface === 'journal' && <MemorySurface />}
            {activeSurface === 'timeline' && <MemorySurface />}
            {activeSurface === 'awareness' && <AwarenessSurface />}
            {activeSurface === 'workspace' && <WorkspaceSurface />}
            {activeSurface === 'command_palette' && <CommandPaletteSurface />}
            {activeSurface === 'session_timeline' && <SessionTimelineSurface />}
            {(activeSurface === 'developer_mode' || activeSurface === 'diagnostics' || activeSurface === 'runtime') && <DeveloperModeSurface />}
            {activeSurface === 'agents' && <AgentsSurface />}
            {activeSurface === 'plans' && <PlansSurface />}

            {(activeSurface === 'settings' || activeSurface === 'system') && <SettingsLayout />}
          </MDiv>
        </div>
      )}
    </AnimatePresence>
  );
};
