import { useEffect, useRef, useState } from 'react';
import { Room } from './components/layout/Room';
import { Environment } from './components/layout/Environment';
import { SpatialRail } from './components/layout/SpatialRail';
import { TopAnchors } from './components/layout/TopAnchors';
import { OrbStage } from './components/orb/OrbStage';
import { CognitiveStream } from './components/stream/CognitiveStream';
import { CommandZone } from './components/command/CommandZone';
import { AwarenessField } from './components/awareness/AwarenessField';
import { EmergentSurface } from './components/surfaces/EmergentSurface';
import { ThreadsSurface } from './components/surfaces/ThreadsSurface';
import { CursorBleed } from './components/effects/CursorBleed';
import { MemoryConsentPopup } from './components/effects/MemoryConsentPopup';
import { PersonalMemoryPolicyDialog } from './components/effects/PersonalMemoryPolicyDialog';
import { StartupOverlay } from './components/effects/StartupOverlay';
import { OnboardingModal } from './components/effects/OnboardingModal';
import { useCognitionState, useEnvironmentState, usePresenceState, useSurfaceState } from './state';
import { fetchStreamItems, fetchAwareness } from './ipc';
import { socket } from './runtime/socket';

import { SyncStatusPill } from './components/layout/SyncStatusPill';

const DEMO_MODE = false;

function App() {
  const { setItems } = useCognitionState();
  const { setFragments } = useEnvironmentState();
  const { atmosphere, mode } = usePresenceState();
  const [showOnboarding, setShowOnboarding] = useState<boolean>(() => {
    return localStorage.getItem('arova_onboarding_completed') !== 'true';
  });

  useEffect(() => {
    // ONLY load placeholder content if explicit demo mode is on
    if (DEMO_MODE) {
      fetchStreamItems().then(setItems);
      fetchAwareness().then(setFragments);
    }

    // Initialize persistent runtime bridge
    socket.connect();

    // Global external link interceptor (Opens links in default OS browser cleanly without polluting chat)
    const handleGlobalLinkClick = async (e: MouseEvent) => {
      const anchor = (e.target as HTMLElement)?.closest('a');
      if (anchor && anchor.href && (anchor.href.startsWith('http://') || anchor.href.startsWith('https://'))) {
        e.preventDefault();
        const targetUrl = anchor.href;

        // 1. Try Tauri native opener plugin
        try {
          const { openUrl } = await import('@tauri-apps/plugin-opener');
          await openUrl(targetUrl);
          return;
        } catch {
          // not running in Tauri or plugin unavailable
        }

        // 2. Tell backend daemon to open via OS default browser
        socket.sendEvent({
          type: 'client.open_url',
          url: targetUrl
        });

        // 3. Web fallback
        try {
          window.open(targetUrl, '_blank', 'noopener,noreferrer');
        } catch {
          // ignore
        }
      }
    };
    document.addEventListener('click', handleGlobalLinkClick, true);

    // Request config once on boot
    socket.sendEvent({ type: 'config.get_request' });

    return () => {
      document.removeEventListener('click', handleGlobalLinkClick, true);
      socket.disconnect();
    };
  }, [setItems, setFragments]);

  const isInitialMount = useRef(true);

  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      document.documentElement.setAttribute('data-theme', atmosphere);
      document.documentElement.setAttribute('data-mode', mode);
      return;
    }

    document.documentElement.setAttribute('data-theme', atmosphere);
    document.documentElement.setAttribute('data-mode', mode);
  }, [atmosphere, mode]);

  // Page Visibility API & Rest Timer
  useEffect(() => {
    const handleVisibilityChange = () => {
      const decorative = document.querySelectorAll<HTMLElement>('.fog, .particle, .satellite, .orb-shell, .orb-halo, .orb-glow');
      if (document.hidden) {
        decorative.forEach(el => el.style.animationPlayState = 'paused');
      } else {
        decorative.forEach(el => el.style.animationPlayState = 'running');
      }
    };

    let restTimer: number | null = null;
    const resetRest = () => {
      document.documentElement.classList.remove('resting');
      if (restTimer) clearTimeout(restTimer);
      restTimer = setTimeout(() => {
        document.documentElement.classList.add('resting');
      }, 60000) as unknown as number;
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    const events = ['mousemove', 'keydown', 'scroll', 'click'];
    events.forEach(evt => document.addEventListener(evt, resetRest, { passive: true }));
    
    resetRest();

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      events.forEach(evt => document.removeEventListener(evt, resetRest));
      if (restTimer) clearTimeout(restTimer);
    };
  }, []);

  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && (e.code === 'Space' || e.key === ' ')) {
        e.preventDefault();
        const state = useSurfaceState.getState();
        if (state.activeSurface === 'command_palette') {
          state.closeSurface();
        } else {
          state.openSurface('command_palette');
        }
      } else if ((e.ctrlKey || e.metaKey) && (e.code === 'KeyJ' || e.key.toLowerCase() === 'j') && !e.shiftKey) {
        e.preventDefault();
        const state = useSurfaceState.getState();
        if (state.activeSurface === 'journal') {
          state.closeSurface();
        } else {
          state.openSurface('journal');
        }
      } else if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.code === 'KeyD' || e.key.toLowerCase() === 'd')) {
        e.preventDefault();
        const state = useSurfaceState.getState();
        if (state.activeSurface === 'developer_mode') {
          state.closeSurface();
        } else {
          state.openSurface('developer_mode');
        }
      }
    };
    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, []);

  useEffect(() => {
    // Listen for the latest capsule
    const handleLatestCapsule = (e: CustomEvent) => {
      const type = e.detail.type;
      if (type === 'momentum.latest_capsule' || type === 'momentum.capsule_created') {
        const capsule = e.detail.capsule;
        if (!capsule) return;
        
        const now = Date.now() / 1000;
        const ageHours = (now - capsule.timestamp) / 3600;
        
        // If older than 24 hours, don't show it automatically
        if (ageHours > 24) return;
        
        const hasStrongMomentum = capsule.next_action && capsule.progress;
        const hasUnresolved = capsule.blockers && capsule.blockers.length > 0;
        
        let paragraphs: string[] = [];
        let from = "While you were away...";
        
        if (hasUnresolved && !hasStrongMomentum) {
          from = "Unfinished thread detected";
          paragraphs.push(`<strong>${capsule.room || 'Work'}</strong> was left mid-flight.`);
          if (capsule.blockers[0]) paragraphs.push(capsule.blockers[0]);
        } else if (hasStrongMomentum) {
          from = "Yesterday's momentum";
          paragraphs.push(`You were refining <strong>${capsule.room || 'your workspace'}</strong>.`);
          if (capsule.progress) paragraphs.push(`Completed:<br/>• ${capsule.progress}`);
          if (capsule.blockers && capsule.blockers[0]) paragraphs.push(`Pending:<br/>• ${capsule.blockers[0]}`);
        } else {
          from = "Welcome back";
          paragraphs.push("Nothing urgent is carrying over from the last session.");
        }

        const actions = [];
        if (hasStrongMomentum || hasUnresolved) {
          actions.push({ 
            label: hasStrongMomentum ? 'Continue Momentum' : 'Resume Thread', 
            primary: true, 
            eventType: 'momentum.resume', 
            eventPayload: { capsule_id: capsule.id } 
          });
          actions.push({ 
            label: 'Review First', 
            clientAction: 'open_timeline' as const 
          });
        }
        actions.push({ 
          label: 'Start Fresh', 
          eventType: 'momentum.dismiss',
          eventPayload: { capsule_id: capsule.id }
        });

        const surfacingItem: any = {
          id: `capsule_${capsule.id}`,
          type: 'surfacing',
          kind: 'momentum',
          timestamp: Date.now(),
          from,
          paragraphs,
          actions
        };
        
        // Use getState() since we're inside useEffect and don't want to bind to state updates
        useCognitionState.getState().setItems([surfacingItem]);
      }
    };
    window.addEventListener('arova-event', handleLatestCapsule as EventListener);

    // Initial fetch after connection
    setTimeout(() => {
      import('./runtime/socket').then(({ socket }) => {
        socket.sendEvent({ type: 'momentum.get_latest' });
      });
    }, 1000);

    return () => {
      window.removeEventListener('arova-event', handleLatestCapsule as EventListener);
    };
  }, []);

  return (
    <>
      <StartupOverlay />
      <Room />
      <CursorBleed />
      <Environment>
        <SpatialRail />
        <SyncStatusPill />
        <TopAnchors />
        <OrbStage />
        <CognitiveStream />
        <CommandZone />
        <AwarenessField />

        <ThreadsSurface />
        <EmergentSurface />
      </Environment>
      <MemoryConsentPopup />
      <PersonalMemoryPolicyDialog />
      {showOnboarding && (
        <OnboardingModal onComplete={() => setShowOnboarding(false)} />
      )}
    </>
  );
}

export default App;
