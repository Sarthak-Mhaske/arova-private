import React, { useEffect, useRef } from 'react';
import { AnimatePresence } from 'framer-motion';
import { useCognitionState, useAwarenessState } from '../../state';
import { Surfacing } from './Surfacing';
import { UserSaid } from './UserSaid';
import { CognitionEvents } from './CognitionEvents';
import { MemoryGhost } from './MemoryGhost';
import { ContinueCard } from '../surfaces/ContinueCard';

export const CognitiveStream: React.FC = () => {
  const { items } = useCognitionState();
  const { activeWorkspace } = useAwarenessState();
  const streamRef = useRef<HTMLDivElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);

  const { continueCardDismissed } = useAwarenessState();
  const initialScrollDone = useRef(false);

  useEffect(() => {
    if (!streamRef.current || !innerRef.current) return;
    
    let rafId: number;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        if (!streamRef.current) return;
        
        // On initial startup with an active recovery card, stay focused at top
        if (!initialScrollDone.current) {
          initialScrollDone.current = true;
          if (activeWorkspace && !continueCardDismissed) {
            streamRef.current.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior });
            return;
          }
        }

        // When user chats or new items are added, scroll smoothly to bottom
        if (items.length > 0) {
          const lastItem = items[items.length - 1];
          if (lastItem.type === 'userSaid' || lastItem.type === 'surfacing') {
            streamRef.current.scrollTo({
              top: streamRef.current.scrollHeight,
              behavior: 'smooth'
            });
          }
        }
      });
    });
    
    observer.observe(innerRef.current);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(rafId);
    };
  }, [items, activeWorkspace, continueCardDismissed]);

  return (
    <>
      <div className="stream" id="stream" ref={streamRef} style={{ overflowAnchor: 'none' }}>
        <div className="stream-inner" ref={innerRef} style={{ gap: 0 }}>
           <AnimatePresence>
            <div style={{ marginBottom: items.length > 0 ? '56px' : '0' }}>
              <ContinueCard workspace={activeWorkspace} />
            </div>
            {items.map((item, idx) => {
              const prev = idx > 0 ? items[idx - 1] : null;
              let marginTop = 48; // Default rhythmic spacing
              if (prev) {
                 if (prev.type === 'userSaid' && item.type === 'surfacing') marginTop = 24;
                 else if (prev.type === 'surfacing' && item.type === 'surfacing') marginTop = 56;
                 else if (prev.type === 'cognitionEvent') marginTop = 32;
                 else if (prev.type === 'memoryGhost') marginTop = 16;
              } else {
                 marginTop = 0;
              }

              const component = (() => {
                switch (item.type) {
                  case 'surfacing': return <Surfacing item={item as any} />;
                  case 'userSaid': return <UserSaid item={item as any} />;
                  case 'cognitionEvent': return <CognitionEvents item={item as any} />;
                  case 'memoryGhost': return <MemoryGhost item={item as any} />;
                  default: return null;
                }
              })();

              return (
                <div key={item.id} style={{ marginTop }}>
                  {component}
                </div>
              );
            })}
          </AnimatePresence>
          {items.length > 0 && (
            <div className="stream-end-marker" />
          )}
        </div>
      </div>
    </>
  );
};
