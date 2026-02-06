import { useRef, useEffect, useCallback } from 'react';

/**
 * Generates slow, organic (dx, dy) offsets via overlapping sine waves.
 * Attach the returned ref to a wrapper div — it will receive continuous
 * CSS transform updates via requestAnimationFrame (no React re-renders).
 */
export function useFloatingDrift(amplitude = 25) {
  const ref = useRef<HTMLDivElement>(null);
  const frameRef = useRef<number>(0);
  const startTime = useRef(Date.now());

  const animate = useCallback(() => {
    if (!ref.current) {
      frameRef.current = requestAnimationFrame(animate);
      return;
    }
    const t = (Date.now() - startTime.current) / 1000;

    const dx =
      Math.sin(t * 0.23) * amplitude +
      Math.sin(t * 0.37) * (amplitude * 0.4) +
      Math.cos(t * 0.11) * (amplitude * 0.3);
    const dy =
      Math.sin(t * 0.17) * (amplitude * 0.7) +
      Math.cos(t * 0.29) * (amplitude * 0.3) +
      Math.sin(t * 0.07) * (amplitude * 0.5);

    ref.current.style.transform = `translate(${dx}px, ${dy}px)`;
    frameRef.current = requestAnimationFrame(animate);
  }, [amplitude]);

  useEffect(() => {
    frameRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameRef.current);
  }, [animate]);

  return ref;
}
