import React from 'react';
import { usePresenceState } from '../../state';

export const TopAnchors: React.FC = () => {
  const { mode, setMode } = usePresenceState();

  return (
    <div className="anchors-top">
      <div className="modes">
        <button
          className={mode === 'ambient' ? 'active' : ''}
          onClick={() => setMode('ambient')}
        >
          Ambient
        </button>
        <button
          className={mode === 'focus' ? 'active' : ''}
          onClick={() => setMode('focus')}
        >
          Focus
        </button>
        <button
          className={mode === 'deep' ? 'active' : ''}
          onClick={() => setMode('deep')}
        >
          Deep
        </button>
      </div>

      <div className="modes">
        <button
          className={usePresenceState().atmosphere === 'daylight' ? 'active' : ''}
          onClick={() => usePresenceState.getState().setAtmosphere('daylight')}
        >
          Daylight
        </button>
        <button
          className={usePresenceState().atmosphere === 'nocturne' ? 'active' : ''}
          onClick={() => usePresenceState.getState().setAtmosphere('nocturne')}
        >
          Nocturne
        </button>
      </div>

      <div className="anchor"><span className="dot"></span> Tuesday · 14:08</div>
      <div className="anchor violet"><span className="dot"></span> 2 unresolved threads</div>
    </div>
  );
};
