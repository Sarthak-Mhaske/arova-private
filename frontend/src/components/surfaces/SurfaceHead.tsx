import React from 'react';
import { useSurfaceState } from '../../state';

export const SurfaceHead: React.FC<{ title: string; sub: string }> = ({ title, sub }) => {
  const { closeSurface } = useSurfaceState();
  return (
    <div className="surface-head">
      <div>
        <h2 className="h">{title}</h2>
        <span className="sub">{sub}</span>
      </div>
      <button className="surface-close" onClick={closeSurface} aria-label="Close">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
};
