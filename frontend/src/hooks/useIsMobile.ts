import { useState, useEffect, useSyncExternalStore } from 'react';

// ─── useIsMobile ─────────────────────────────────────────────
const mediaQuery = typeof window !== 'undefined'
  ? window.matchMedia('(max-width: 767px)')
  : null;

function subscribeToMedia(cb: () => void) {
  mediaQuery?.addEventListener('change', cb);
  return () => mediaQuery?.removeEventListener('change', cb);
}

function getMediaSnapshot() {
  return mediaQuery?.matches ?? false;
}

/** Reactive hook: true when viewport <= 767px */
export function useIsMobile(): boolean {
  return useSyncExternalStore(subscribeToMedia, getMediaSnapshot, () => false);
}

// ─── useVisualViewport ───────────────────────────────────────
interface ViewportState {
  keyboardHeight: number;
  isKeyboardOpen: boolean;
}

/** Tracks virtual keyboard height via visualViewport API */
export function useVisualViewport(): ViewportState {
  const [state, setState] = useState<ViewportState>({
    keyboardHeight: 0,
    isKeyboardOpen: false,
  });

  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;

    const update = () => {
      const diff = window.innerHeight - vv.height;
      // Threshold of 150px to distinguish keyboard from address bar changes
      const isOpen = diff > 150;
      setState({ keyboardHeight: isOpen ? diff : 0, isKeyboardOpen: isOpen });
    };

    vv.addEventListener('resize', update);
    vv.addEventListener('scroll', update);
    return () => {
      vv.removeEventListener('resize', update);
      vv.removeEventListener('scroll', update);
    };
  }, []);

  return state;
}
