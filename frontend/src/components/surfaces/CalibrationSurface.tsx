import React from 'react';
import * as Slider from '@radix-ui/react-slider';
import { SurfaceHead } from './SurfaceHead';
import { mockCalibration } from '../../ipc/mock';

const Tune: React.FC<{ label: string; desc: string; value: number; left: string; right: string }> = ({ label, desc, value, left, right }) => (
  <div className="tune">
    <div className="lbl">{label}</div>
    <div className="desc">{desc}</div>
    <div className="scale">
      <span>{left}</span>
      <Slider.Root className="scale-bar" defaultValue={[value]} max={100} step={1}>
        <Slider.Track className="scale-bar" style={{ display: 'block', width: '100%', background: 'transparent' }}>
          <Slider.Range className="fill" />
        </Slider.Track>
        <Slider.Thumb className="knob" />
      </Slider.Root>
      <span>{right}</span>
    </div>
  </div>
);

export const CalibrationSurface: React.FC = () => {
  return (
    <>
      <SurfaceHead title="How I should be with you" sub="Calibration · not preferences" />
      <div className="tuning">
        {mockCalibration.map((c, i) => (
          <Tune key={i} label={c.label} desc={c.desc} value={c.value} left={c.left} right={c.right} />
        ))}
      </div>
    </>
  );
};
