import React from 'react';
import { motion } from 'framer-motion';
const MDiv: any = motion.div;
import { surfaceIn, easeSoft } from '../../motion';
import { UserSaidItem } from '../../state';

export const UserSaid: React.FC<{ item: UserSaidItem }> = ({ item }) => {
  return (
    <MDiv 
      className="you-said"
      variants={surfaceIn}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={{ duration: 0.76, ease: easeSoft.ease }}
    >
      <span className="label">You said</span>
      {item.text}
    </MDiv>
  );
};
