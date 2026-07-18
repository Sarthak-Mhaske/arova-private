import React from 'react';
import { useOrbState } from '../../state';

export const OrbCaption: React.FC = () => {
  const { mode } = useOrbState();
  
  let mood = "aware · settled";
  if (mode === 'thinking') mood = "connecting · processing";
  if (mode === 'executing') mood = "focused · active";
  
  return (
    <div className="orb-caption">
      <span className="state">{mode}</span>
      <span className="mood">{mood}</span>
    </div>
  );
};
