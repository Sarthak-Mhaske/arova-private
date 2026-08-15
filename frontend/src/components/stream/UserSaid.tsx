import React from 'react';
import { motion } from 'framer-motion';
const MDiv: any = motion.div;
const MSpan: any = motion.span;
import { surfaceIn, easeSoft } from '../../motion';
import { UserSaidItem } from '../../state';

export const UserSaid: React.FC<{ item: UserSaidItem }> = ({ item }) => {
  return (
    <MDiv 
      className={`you-said ${item.isLive ? 'is-live' : ''}`}
      variants={surfaceIn}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={{ duration: 0.35, ease: easeSoft.ease }}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        gap: '4px'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span className="label">You said</span>
        {item.isLive && (
          <span style={{ 
            fontSize: '10.5px', 
            color: 'rgba(251, 191, 36, 0.95)', 
            display: 'inline-flex', 
            alignItems: 'center', 
            gap: '5px',
            fontWeight: 500,
            letterSpacing: '0.02em'
          }}>
            <MSpan 
              animate={{ scale: [1, 1.35, 1], opacity: [0.6, 1, 0.6] }}
              transition={{ repeat: Infinity, duration: 1.2, ease: 'easeInOut' }}
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: '#fbbf24',
                display: 'inline-block'
              }} 
            />
            listening...
          </span>
        )}
      </div>
      <div style={{
        color: item.isLive ? 'rgba(255, 255, 255, 0.92)' : undefined,
        lineHeight: 1.5,
        wordBreak: 'break-word'
      }}>
        {item.text}
        {item.isLive && (
          <MSpan
            animate={{ opacity: [0, 1, 0] }}
            transition={{ repeat: Infinity, duration: 0.8 }}
            style={{
              display: 'inline-block',
              width: '2px',
              height: '14px',
              backgroundColor: '#fbbf24',
              marginLeft: '4px',
              verticalAlign: 'middle'
            }}
          />
        )}
      </div>
    </MDiv>
  );
};
