import React from 'react';
import { OrbHalo } from './OrbHalo';
import { OrbGlow } from './OrbGlow';
import { OrbShell } from './OrbShell';
import { Satellites } from './Satellites';
import { OrbCaption } from './OrbCaption';
import { ObservationPill } from './ObservationPill';

export const OrbStage: React.FC = () => {
  return (
    <div className="orb-stage">
      <div className="orb-wrap">
        <div className="orb-light-bleed" />
        <OrbHalo />
        <OrbGlow />
        <OrbShell />
        <Satellites />
      </div>
      <OrbCaption />
      <ObservationPill />
      <div className="voice-transcription-zone" />
    </div>
  );
};

export * from './OrbStage';
