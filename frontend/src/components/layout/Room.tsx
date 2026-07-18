import React from 'react';

export const Room: React.FC = () => {
  return (
    <>
      <div className="room">
        <div className="fog a" />
        <div className="fog b" />
        <div className="fog c" />
      </div>
      <div className="noise-overlay" />
    </>
  );
};
