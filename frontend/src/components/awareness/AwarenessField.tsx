import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
const MDiv: any = motion.div;
import { useEnvironmentState } from '../../state';
import { fragmentIn, easeSoft } from '../../motion';
import { getNextSensing } from '../../ipc';

export const AwarenessField: React.FC = () => {
  const { fragments } = useEnvironmentState();
  const [dynamicSensing, setDynamicSensing] = useState<{ key: string; value: string; id: number } | null>(null);

  useEffect(() => {
    if (fragments.length <= 1) return;
    
    // Initial sensing from fragments
    setDynamicSensing({
      key: fragments[1].key,
      value: fragments[1].value,
      id: 0
    });

    let counter = 1;
    let animationFrameId: number;
    let lastTickTime = performance.now();
    let currentDelay = 16000; // Initial delay

    const tick = (time: number) => {
      if (document.hidden) {
        lastTickTime = time; // pause timer progression while hidden
        animationFrameId = requestAnimationFrame(tick);
        return;
      }

      if (time - lastTickTime >= currentDelay) {
        if (Math.random() < 0.2) {
          setDynamicSensing(null);
          currentDelay = 14000; // Wait 14s then try again
        } else {
          const next = getNextSensing();
          setDynamicSensing({ ...next, id: counter++ });
          currentDelay = Math.random() * (22000 - 11000) + 11000;
        }
        lastTickTime = time;
      }
      animationFrameId = requestAnimationFrame(tick);
    };

    animationFrameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animationFrameId);
  }, [fragments]);

  if (fragments.length === 0) return null;

  return (
    <div className="awareness">
      {dynamicSensing && (
        <AnimatePresence mode="wait">
          <MDiv 
            key={dynamicSensing.id}
            className="fragment"
            variants={fragmentIn}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={{ duration: 1.3, ease: easeSoft.ease, delay: 0 }}
          >
            <div className="k">{dynamicSensing.key}</div>
            <div className="v warm">{dynamicSensing.value}</div>
          </MDiv>
        </AnimatePresence>
      )}

      <MDiv 
        className="fragment"
        variants={fragmentIn}
        initial="initial"
        animate="animate"
        transition={{ duration: 1.3, ease: easeSoft.ease, delay: 0.5 }}
      >
        <div className="k">{fragments[0].key}</div>
        <div className={`v ${fragments[0].accent ? fragments[0].accent : ''}`}>{fragments[0].value}</div>
      </MDiv>
      
      {fragments.length > 2 && (
        <MDiv 
          className="fragment"
          variants={fragmentIn}
          initial="initial"
          animate="animate"
          transition={{ duration: 1.3, ease: easeSoft.ease, delay: 1.06 }}
        >
          <div className="k">{fragments[2].key}</div>
          <div className={`v ${fragments[2].accent ? fragments[2].accent : ''}`}>{fragments[2].value}</div>
        </MDiv>
      )}
    </div>
  );
};
