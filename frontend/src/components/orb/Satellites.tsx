import React, { useEffect, useRef } from 'react';

const SATELLITES = [
  { id: 's1', name: 'Memory', speed: 0.0003, offset: 0 },
  { id: 's2', name: 'Planner', speed: 0.00025, offset: Math.PI * 0.66 },
  { id: 's3', name: 'Researcher', speed: 0.00035, offset: Math.PI * 1.33 },
];

export const Satellites: React.FC = () => {
  const refs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    let frameId: number;
    const a = 170; // semi-major axis (horizontal)
    const b = 60;  // semi-minor axis (vertical)

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const animate = (time: number) => {
      SATELLITES.forEach((sat, i) => {
        const el = refs.current[i];
        if (!el) return;
        
        // Lock time to 0 if reduced motion is on
        const t = prefersReducedMotion ? sat.offset : time * sat.speed + sat.offset;
        const x = Math.cos(t) * a;
        const y = Math.sin(t) * b;
        
        // When y < 0, it's behind the orb
        const zIndex = y < 0 ? 1 : 10;
        
        // Scale down slightly when behind to enhance depth
        const scale = y < 0 ? 0.85 : 1;

        el.style.transform = `translate(calc(-50% + ${x}px), calc(-50% + ${y}px)) scale(${scale})`;
        el.style.zIndex = zIndex.toString();
      });
      if (!document.hidden) {
        frameId = requestAnimationFrame(animate);
      }
    };

    const onVisibilityChange = () => {
      if (document.hidden) {
        if (frameId) cancelAnimationFrame(frameId);
      } else {
        frameId = requestAnimationFrame(animate);
      }
    };

    document.addEventListener('visibilitychange', onVisibilityChange);
    frameId = requestAnimationFrame(animate);
    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange);
      cancelAnimationFrame(frameId);
    };
  }, []);

  return (
    <>
      {SATELLITES.map((sat, i) => (
        <div
          key={sat.id}
          ref={el => { refs.current[i] = el; }}
          className={`satellite ${sat.id}`}
          data-name={sat.name}
          style={{ position: 'absolute', top: '50%', left: '50%' }}
        >
          <div className="core"></div>
        </div>
      ))}
    </>
  );
};
