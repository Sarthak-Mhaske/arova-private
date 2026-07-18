import React from 'react';
import { motion } from 'framer-motion';
const MDiv: any = motion.div;
import { surfaceIn, easeSoft } from '../../motion';
import { SurfacingItem, useCognitionState, useSurfaceState } from '../../state';
import { ActionChip } from './ActionChip';

export const Surfacing: React.FC<{ item: SurfacingItem }> = ({ item }) => {
  const { removeItems } = useCognitionState();
  const { openSurface } = useSurfaceState();

  const handleAction = (act: NonNullable<SurfacingItem['actions']>[0]) => {
    if (act.eventType) {
      window.dispatchEvent(new CustomEvent('arova-send', { 
        detail: { type: act.eventType, ...(act.eventPayload || {}) } 
      }));
    }
    
    if (act.clientAction === 'open_timeline') {
      openSurface('timeline');
    }
    
    // Always dismiss the surfacing item if it was interacted with
    if (item.kind === 'momentum') {
      removeItems([item.id]);
    }
  };

  return (
    <MDiv 
      className={`surfacing ${item.kind ? item.kind : ''}`}
      variants={surfaceIn}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={{ duration: 0.9, ease: easeSoft.ease }}
    >
      <div className="from">{item.from}</div>
      {item.lede && <div className="lede">{item.lede}</div>}
      {item.paragraphs.map((p, i) => (
        <p key={i} dangerouslySetInnerHTML={{ __html: p }} />
      ))}
      {item.actions && item.actions.length > 0 && (
        <div className="actions-inline">
          {item.actions.map((act, i) => (
            <ActionChip key={i} primary={act.primary} onClick={() => handleAction(act)}>
              {act.primary && (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
              )}
              {act.label}
            </ActionChip>
          ))}
        </div>
      )}
    </MDiv>
  );
};
