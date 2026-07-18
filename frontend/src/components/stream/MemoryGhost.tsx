import React from 'react';
import { motion } from 'framer-motion';
const MDiv: any = motion.div;
import { ghostIn, easeSoft } from '../../motion';
import { MemoryGhostItem } from '../../state';

export const MemoryGhost: React.FC<{ item: MemoryGhostItem }> = ({ item }) => {
  return (
    <MDiv 
      className="ghost"
      variants={ghostIn}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={{ duration: 1.5, ease: easeSoft.ease }}
    >
      <span className="from">{item.from}</span>
      {item.text}
    </MDiv>
  );
};
