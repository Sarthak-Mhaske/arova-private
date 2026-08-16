export const surfaceIn = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 }
};

export const ghostIn = {
  initial: { opacity: 0, x: -8 },
  animate: { opacity: 0.85, x: 0 },
  exit: { opacity: 0, x: 8 }
};

export const eventIn = {
  initial: { opacity: 0, x: -8 },
  animate: { opacity: 0.85, x: 0 },
  exit: { opacity: 0, x: 8 }
};

export const fragmentIn = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 }
};

export const sheetEnter = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 6 }
};

export const scrimEnter = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 }
};
