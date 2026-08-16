import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
const MDiv: any = motion.div;
import { useOrbState } from '../../state';
import { easeSoft } from '../../motion';

const getColorsForMode = (mode: string) => {
  switch (mode) {
    case 'thinking': return { bg: 'rgba(50,45,65,0.9)', waveA: 'rgba(190,175,230,0.95)', waveB: 'rgba(168,157,200,0.7)' };
    case 'streaming': return { bg: 'rgba(40,55,75,0.9)', waveA: 'rgba(120,200,255,0.95)', waveB: 'rgba(80,160,240,0.75)' };
    case 'executing': return { bg: 'rgba(35,50,65,0.9)', waveA: 'rgba(140,190,230,0.95)', waveB: 'rgba(100,160,210,0.7)' };
    case 'listening': return { bg: 'rgba(40,55,40,0.9)', waveA: 'rgba(140,220,150,0.95)', waveB: 'rgba(110,190,120,0.7)' };
    case 'reflecting': return { bg: 'rgba(60,45,35,0.9)', waveA: 'rgba(230,170,130,0.95)', waveB: 'rgba(210,140,100,0.7)' };
    case 'interrupted': return { bg: 'rgba(65,35,35,0.9)', waveA: 'rgba(240,140,140,0.95)', waveB: 'rgba(210,100,100,0.7)' };
    case 'error': return { bg: 'rgba(70,30,30,0.9)', waveA: 'rgba(250,110,110,0.95)', waveB: 'rgba(220,80,80,0.8)' };
    case 'disconnected': return { bg: 'rgba(40,35,30,0.5)', waveA: 'rgba(160,150,140,0.4)', waveB: 'rgba(140,130,120,0.25)' };
    case 'reconnecting': return { bg: 'rgba(50,40,60,0.8)', waveA: 'rgba(200,170,230,0.8)', waveB: 'rgba(170,140,200,0.6)' };
    case 'idle':
    default: return { bg: 'rgba(45,35,25,0.9)', waveA: 'rgba(230,185,115,0.95)', waveB: 'rgba(195,150,85,0.65)' };
  }
};

const OrbFlow: React.FC<{ waveA: string; waveB: string }> = ({ waveA, waveB }) => (
  <div className="orb-flow">
    <svg viewBox="0 0 200 200" preserveAspectRatio="none">
      <defs>
        <linearGradient id="wave-grad-a" x1="0" x2="1" y1="0.5" y2="0.5">
          <stop offset="0" stopColor="rgba(180,200,225,0)"/>
          <stop offset="0.5" stopColor={waveA} style={{ transition: 'stop-color 500ms var(--ease-soft) 200ms' }} />
          <stop offset="1" stopColor="rgba(180,200,225,0)"/>
        </linearGradient>
        <linearGradient id="wave-grad-b" x1="0" x2="1" y1="0.5" y2="0.5">
          <stop offset="0" stopColor="rgba(200,210,230,0)"/>
          <stop offset="0.5" stopColor={waveB} style={{ transition: 'stop-color 500ms var(--ease-soft) 200ms' }} />
          <stop offset="1" stopColor="rgba(200,210,230,0)"/>
        </linearGradient>
      </defs>
      <path className="flow-wave a" d="M 10 100 Q 50 60, 100 100 T 190 100"/>
      <path className="flow-wave b" d="M 10 110 Q 60 130, 100 105 T 190 95"/>
    </svg>
  </div>
);

const OrbParticles: React.FC = () => {
  const [particles, setParticles] = useState<{ id: number; dx: string; dy: string; delay: string; dur: string; size: string }[]>([]);
  useEffect(() => {
    // 4 slow/large, 8 mid, 2 fast/tiny
    const slow = Array.from({ length: 4 }).map((_, i) => ({
      id: i,
      dx: `${(Math.random() - 0.5) * 80}px`,
      dy: `${(Math.random() - 0.5) * 80 - 20}px`,
      delay: `${Math.random() * -20}s`,
      dur: `${15 + Math.random() * 5}s`,
      size: '1.5px'
    }));
    const mid = Array.from({ length: 8 }).map((_, i) => ({
      id: i + 4,
      dx: `${(Math.random() - 0.5) * 140}px`,
      dy: `${(Math.random() - 0.5) * 140 - 40}px`,
      delay: `${Math.random() * -12}s`,
      dur: `${8 + Math.random() * 4}s`,
      size: '1px'
    }));
    const fast = Array.from({ length: 2 }).map((_, i) => ({
      id: i + 12,
      dx: `${(Math.random() - 0.5) * 200}px`,
      dy: `${(Math.random() - 0.5) * 200 - 80}px`,
      delay: `${Math.random() * -6}s`,
      dur: `${4 + Math.random() * 2}s`,
      size: '0.5px'
    }));
    setParticles([...slow, ...mid, ...fast]);
  }, []);

  return (
    <div className="orb-particles">
      {particles.map(p => (
        <div 
          key={p.id} 
          className="particle" 
          style={{ 
            '--dx': p.dx, 
            '--dy': p.dy, 
            animationDelay: p.delay, 
            animationDuration: p.dur,
            width: p.size,
            height: p.size,
            left: '50%', top: '50%'
          } as any} 
        />
      ))}
    </div>
  );
};

export const OrbShell: React.FC = () => {
  const { mode, isPulsing, modulation } = useOrbState();
  const colors = getColorsForMode(mode);

  // Modulation math
  // breathing_rhythm: 0.2 (calm/slow) to 0.8 (brisk/fast)
  const baseDuration = mode === 'disconnected' ? 22 : 11.3;
  const modulatedDuration = baseDuration * (1.5 - modulation.breathing_rhythm); // rhythm 0.8 -> 0.7 * base, rhythm 0.2 -> 1.3 * base

  // turbulence: 0.1 (steady) to 1.0 (turbulent)
  const pulseIntensity = isPulsing ? 1.02 : 1 + (0.014 * modulation.turbulence);

  return (
    <MDiv 
      className={`orb-shell ${mode === 'disconnected' ? 'dormant' : ''}`}
      animate={{ 
        y: mode === 'disconnected' ? [0, -2, 0] : [0, -5 * modulation.turbulence, 0], 
        scale: [1, pulseIntensity, 1],
        filter: isPulsing ? 'brightness(1.08)' : (mode === 'disconnected' ? 'brightness(0.85)' : `brightness(${0.9 + (modulation.warmth * 0.2)})`) 
      }}
      transition={{ duration: modulatedDuration, ease: easeSoft.ease, repeat: Infinity }}
    >
      <div className="orb-nocturne" />
      <div className="orb-specular" />
      <OrbFlow waveA={colors.waveA} waveB={colors.waveB} />
      <OrbParticles />
    </MDiv>
  );
};
