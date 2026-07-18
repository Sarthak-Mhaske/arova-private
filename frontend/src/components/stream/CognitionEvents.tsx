import React from 'react';
import { motion } from 'framer-motion';
const MDiv: any = motion.div;
import { eventIn, easeSoft } from '../../motion';
import { CognitionEventItem } from '../../state';

export const CognitionEvents: React.FC<{ item: CognitionEventItem }> = ({ item }) => {
  return (
    <div className="events">
      {item.events.map((ev, i) => (
        <MDiv 
          key={i} 
          className={`event ${ev.state}`}
          variants={eventIn}
          initial="initial"
          animate="animate"
          exit="exit"
          transition={{ duration: 0.9, ease: easeSoft.ease, delay: i * 0.1 }}
        >
          <span className="g"></span>
          <span dangerouslySetInnerHTML={{ __html: ev.text }} />
        </MDiv>
      ))}
    </div>
  );
};
