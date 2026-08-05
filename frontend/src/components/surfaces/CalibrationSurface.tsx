import React, { useState, useEffect } from 'react';
import * as Slider from '@radix-ui/react-slider';
import { SurfaceHead } from './SurfaceHead';
import { socket } from '../../runtime/socket';

const Tune: React.FC<{ label: string; desc: string; value: number; left: string; right: string; onChange: (v: number) => void }> = ({ label, desc, value, left, right, onChange }) => (
  <div className="tune">
    <div className="lbl">{label}</div>
    <div className="desc">{desc}</div>
    <div className="scale">
      <span>{left}</span>
      <Slider.Root className="scale-bar" value={[value]} onValueChange={([val]) => onChange(val)} max={100} step={1}>
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
  const [config, setConfig] = useState({
    calibration: { presence: 42, autonomy: 28, memory: 82, lighting: 60 }
  });

  useEffect(() => {
    const handleEvent = (event: any) => {
      const ev = event.detail;
      if (ev.type === 'config.sync' && ev.config) {
        setConfig((prev: any) => ({ ...prev, ...ev.config }));
      }
    };
    window.addEventListener('arova-event', handleEvent);
    socket.sendEvent({ type: 'config.get_request' });
    return () => window.removeEventListener('arova-event', handleEvent);
  }, []);

  const handleTune = (key: string, value: number) => {
    const newConfig = { ...config, calibration: { ...config.calibration, [key]: value } };
    setConfig(newConfig);
    socket.sendEvent({ type: 'config.update_request', config: newConfig });
  };

  const cal = config.calibration || { presence: 42, autonomy: 28, memory: 82, lighting: 60 };

  return (
    <>
      <SurfaceHead title="How I should be with you" sub="Calibration · not preferences" />
      <div className="tuning">
        <Tune label="Presence" desc="How often I should surface things on my own." value={cal.presence} left="Quiet · only when asked" right="Forward · proactive" onChange={(v) => handleTune('presence', v)} />
        <Tune label="Autonomy" desc="How much I should act on my own without asking." value={cal.autonomy} left="Always ask" right="Move freely" onChange={(v) => handleTune('autonomy', v)} />
        <Tune label="Memory" desc="How long I should hold what passes between us." value={cal.memory} left="This session only" right="Keep it all" onChange={(v) => handleTune('memory', v)} />
        <Tune label="Lighting" desc="How much the room should respond to my state." value={cal.lighting} left="Still" right="Atmospheric" onChange={(v) => handleTune('lighting', v)} />
      </div>
    </>
  );
};

