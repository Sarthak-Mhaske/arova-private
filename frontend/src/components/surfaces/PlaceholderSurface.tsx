import React from 'react';
import { useSurfaceState } from '../../state';

export const PlaceholderSurface: React.FC<{ title: string; description?: string }> = ({ title, description }) => {
  const { closeSurface } = useSurfaceState();

  return (
    <div style={{ padding: '3rem', color: '#fff', fontFamily: 'sans-serif', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.8rem', fontWeight: 400 }}>{title}</h1>
          <p style={{ color: '#aaa', margin: '0.5rem 0 0 0' }}>Coming online soon.</p>
        </div>
        <button 
          data-close 
          aria-label="Close"
          onClick={() => closeSurface()}
          style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer', padding: '8px' }}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#666' }}>
        <p style={{ textAlign: 'center', maxWidth: '400px', lineHeight: 1.6 }}>
          {description || `This surface will show how Arova interprets your current ${title.toLowerCase()}.`}
        </p>
      </div>
    </div>
  );
};
