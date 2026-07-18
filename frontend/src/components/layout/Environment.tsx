import React, { ReactNode, useEffect, useRef } from 'react';

export const Environment: React.FC<{ children: ReactNode }> = ({ children }) => {
  const envRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (envRef.current) {
      envRef.current.classList.add('boot');
      const timer = setTimeout(() => {
        if (envRef.current) {
          envRef.current.classList.remove('boot');
        }
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, []);

  return <div className="env" id="env" ref={envRef}>{children}</div>;
};
