import React, { useEffect, useRef } from 'react';

export const CursorBleed: React.FC = () => {
  const bleedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cursorRAF: number | null = null;
    let cursorVisible = false;

    const handleMouseMove = (e: MouseEvent) => {
      const mouseX = e.clientX;
      const mouseY = e.clientY;

      if (!cursorVisible && bleedRef.current) {
        bleedRef.current.classList.add('visible');
        cursorVisible = true;
      }

      if (cursorRAF) return;
      
      cursorRAF = requestAnimationFrame(() => {
        if (bleedRef.current) {
          bleedRef.current.style.transform = `translate3d(${mouseX}px, ${mouseY}px, 0)`;
        }
        cursorRAF = null;
      });
    };

    const handleMouseLeave = () => {
      if (bleedRef.current) {
        bleedRef.current.classList.remove('visible');
      }
      cursorVisible = false;
    };

    document.addEventListener('mousemove', handleMouseMove, { passive: true });
    document.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseleave', handleMouseLeave);
      if (cursorRAF) {
        cancelAnimationFrame(cursorRAF);
      }
    };
  }, []);

  return <div id="cursorBleed" className="cursor-bleed" ref={bleedRef}></div>;
};
