export const backdropMotion = (isReduced: boolean | null) => ({
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  initial: isReduced ? { opacity: 1 } : { opacity: 0 },
  transition: { duration: isReduced ? 0 : 0.15 },
});

export const popupMotion = (isReduced: boolean | null) => ({
  animate: { opacity: 1, scale: 1 },
  exit: isReduced ? { opacity: 0 } : { opacity: 0, scale: 0.95 },
  initial: isReduced ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.95 },
  transition: isReduced ? { duration: 0 } : { duration: 0.2, ease: [0.16, 1, 0.3, 1] as const },
});
