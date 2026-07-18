export const surfaceIn = {
  initial: { opacity: 0, y: 10, filter: 'blur(3px)' },
  animate: { opacity: 1, y: 0, filter: 'blur(0px)' },
  exit: { opacity: 0, y: -10, filter: 'blur(3px)' }
};

export const ghostIn = {
  initial: { opacity: 0, x: -12, filter: 'blur(5px)' },
  animate: { opacity: 0.85, x: 0, filter: 'blur(0px)' },
  exit: { opacity: 0, x: 12, filter: 'blur(5px)' }
};

export const eventIn = {
  initial: { opacity: 0, x: -8 },
  animate: { opacity: 0.85, x: 0 },
  exit: { opacity: 0, x: 8 }
};

export const fragmentIn = {
  initial: { opacity: 0, y: 8, filter: 'blur(5px)' },
  animate: { opacity: 1, y: 0, filter: 'blur(0px)' },
  exit: { opacity: 0, y: -8, filter: 'blur(5px)' }
};

export const sheetEnter = {
  initial: { opacity: 0, scale: 0.96, y: '-48%', x: '-50%', filter: 'blur(8px)' },
  animate: { opacity: 1, scale: 1, y: '-50%', x: '-50%', filter: 'blur(0px)' },
  exit: { opacity: 0, scale: 0.96, y: '-48%', x: '-50%', filter: 'blur(8px)' }
};

export const scrimEnter = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 }
};
