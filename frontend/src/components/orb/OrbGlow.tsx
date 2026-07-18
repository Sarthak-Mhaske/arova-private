import React from 'react';
import { motion } from 'framer-motion';
const MDiv: any = motion.div;
import { easeSoft } from '../../motion';
import { useOrbState } from '../../state';

const getGlowColors = (mode: string) => {
  switch (mode) {
    case 'thinking': return 'rgba(168,157,200, 0.42)';
    case 'executing': return 'rgba(154,184,212, 0.42)';
    case 'present':
    default: return 'rgba(220, 232, 245, 0.32)';
  }
};

export const OrbGlow: React.FC = () => {
  const { mode } = useOrbState();
  const color = getGlowColors(mode);
  
  return (
    <MDiv
      className="orb-glow"
      animate={{ scale: [1, 1.04, 1], opacity: [0.85, 1, 0.85] }}
      transition={{ duration: 5.3, ease: easeSoft.ease, repeat: Infinity }}
      style={{
        background: `radial-gradient(circle, rgba(255, 255, 255, 0.62) 0%, ${color} 40%, transparent 80%)`,
        transition: 'background 800ms var(--ease-soft) 400ms'
      }}
    />
  );
};
