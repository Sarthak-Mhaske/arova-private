import React from 'react';
import { motion } from 'framer-motion';
const MDiv: any = motion.div;

export const OrbGlow: React.FC = () => {
  return (
    <MDiv
      className="orb-glow"
      style={{
        background: 'transparent'
      }}
    />
  );
};
