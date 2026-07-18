import React, { useEffect, useRef } from 'react';
import { AnimatePresence } from 'framer-motion';
import { useCognitionState } from '../../state';
import { Surfacing } from './Surfacing';
import { UserSaid } from './UserSaid';
import { CognitionEvents } from './CognitionEvents';
import { MemoryGhost } from './MemoryGhost';

export const CognitiveStream: React.FC = () => {
  const { items } = useCognitionState();
  const streamRef = useRef<HTMLDivElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!streamRef.current || !innerRef.current) return;
    
    let rafId: number;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        if (streamRef.current) {
          streamRef.current.scrollTo({
            top: streamRef.current.scrollHeight,
            behavior: 'smooth'
          });
        }
      });
    });
    
    observer.observe(innerRef.current);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(rafId);
    };
  }, []);

  return (
    <>
      <div className="stream" id="stream" ref={streamRef} style={{ overflowAnchor: 'none' }}>
        <div className="stream-inner" ref={innerRef} style={{ gap: 0 }}>
           <AnimatePresence>
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
