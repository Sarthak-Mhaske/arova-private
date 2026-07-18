import React from 'react';
import { motion } from 'framer-motion';
const MDiv: any = motion.div;
import { easeSoft } from '../../motion';
import { useOrbState } from '../../state';

const getHaloColors = (mode: string) => {
  switch (mode) {
    case 'thinking': return 'rgba(208, 195, 228, 0.45)';
    case 'executing': return 'rgba(190, 210, 235, 0.45)';
    case 'present':
    default: return 'rgba(220, 232, 245, 0.55)'; // var(--rl-near)
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
