import React from 'react';
import { useAwarenessState } from '../../state/awarenessState';
import { useOrbState } from '../../state/orbState';
import { useCognitionState } from '../../state/cognitionState';
import { motion, AnimatePresence } from 'framer-motion';

export const ObservationPill: React.FC = () => {
  const { ambientSnapshot } = useAwarenessState();
  const { mode, details } = useOrbState();
  const { activeAction } = useCognitionState();

  let dotState: 'active' | 'thinking' | 'executing' | 'pulse' = 'active';
  let primaryText = "Observing environment...";
  let subText = "";

  // Priority 1: Active execution capability
  if (activeAction) {
    dotState = 'executing';
    primaryText = `Executing: ${activeAction}`;
  } 
  // Priority 2: Cognitive Reasoning / Thinking / Routing state
  else if (mode === 'thinking' || mode === 'reflecting') {
    dotState = 'thinking';
    primaryText = details ? details : "Reasoning & routing intent...";
  }
  // Priority 4: Streaming / Responding state
  else if (mode === 'streaming') {
    dotState = 'active';
    primaryText = "Synthesizing response...";
  }
  // Priority 5: Active listening (waiting for speech)
  else if (mode === 'listening') {
    dotState = 'pulse';
    primaryText = "Listening to input...";
  }
  // Priority 5: Ambient OS observation & attention trajectory (when idle)
  else if (ambientSnapshot) {
    const { active_app, window_title, playing_media, open_windows, attention_narrative } = ambientSnapshot;
    dotState = 'active';

    if (attention_narrative && attention_narrative.trim() && !attention_narrative.includes("idle")) {
      primaryText = attention_narrative;
      if (active_app) subText = active_app;
    } else if (playing_media && playing_media.length > 0) {
      primaryText = playing_media[0];
    } else if (active_app || window_title) {
      const appName = active_app ? (active_app.charAt(0).toUpperCase() + active_app.slice(1)) : "";
      primaryText = appName || "Desktop";
      subText = window_title ? window_title : "";
    } else if (open_windows && open_windows.length > 0) {
      primaryText = `${open_windows.length} apps active`;
      subText = open_windows.slice(0, 2).join(', ');
    }
  }

  const maxLen = 55;
  const fullText = subText ? `${primaryText} — ${subText}` : primaryText;
  const truncatedText = fullText.length > maxLen ? fullText.substring(0, maxLen) + '...' : fullText;

  return (
    <div className="observation-pill-container">
      <AnimatePresence mode="wait">
        <motion.div
          key={truncatedText}
          initial={{ opacity: 0, y: 6, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -6, scale: 0.96 }}
          transition={{ duration: 0.25, ease: 'easeOut' }}
          className={`observation-pill ${dotState}`}
          title={fullText}
        >
          <span className={`observation-dot ${dotState}`} />
          <span className="observation-text">{truncatedText}</span>
        </motion.div>
      </AnimatePresence>
    </div>
  );
};
