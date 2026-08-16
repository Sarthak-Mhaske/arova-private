import React from 'react';
import { motion } from 'framer-motion';
const MDiv: any = motion.div;
import { easeSoft } from '../../motion';
import { useOrbState } from '../../state';

const getHaloColors = (mode: string) => {
  switch (mode) {
    case 'thinking': return 'rgba(168, 157, 200, 0.15)';
    case 'executing': return 'rgba(154, 184, 212, 0.15)';
    case 'present':
    default: return 'rgba(224, 163, 82, 0.12)';
  }
};

export const OrbHalo: React.FC = () => {
  const { mode } = useOrbState();
  const color = getHaloColors(mode);
  
  return (
    <MDiv
      className="orb-halo"
      animate={{ scale: [1, 1.09, 1], opacity: [0.82, 1, 0.82] }}
      transition={{ duration: 7.1, ease: easeSoft.ease, repeat: Infinity }}
      style={{
        background: `radial-gradient(circle, ${color} 0%, transparent 70%)`,
        transition: 'background 2400ms var(--ease-soft) 800ms'
      }}
    />
  );
};
