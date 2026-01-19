import { create } from 'zustand';

export type UIPhase = 'discovery' | 'results' | 'transitioning';
export type AvatarMood = 'idle' | 'thinking' | 'speaking' | 'excited';

interface UIPhaseState {
  phase: UIPhase;
  previousPhase: UIPhase | null;
  avatarMood: AvatarMood;
  hasMapData: boolean;
  isTransitioning: boolean;

  // Actions
  setPhase: (phase: UIPhase) => void;
  transitionToResults: () => void;
  transitionToDiscovery: () => void;
  setAvatarMood: (mood: AvatarMood) => void;
  setHasMapData: (has: boolean) => void;
}

export const useUIPhaseStore = create<UIPhaseState>((set, get) => ({
  phase: 'discovery',
  previousPhase: null,
  avatarMood: 'idle',
  hasMapData: false,
  isTransitioning: false,

  setPhase: (phase) => set({
    phase,
    previousPhase: get().phase !== phase ? get().phase : get().previousPhase
  }),

  transitionToResults: () => {
    const { phase } = get();
    if (phase === 'results') return;

    set({
      isTransitioning: true,
      previousPhase: phase
    });

    // Short delay for transition animation
    setTimeout(() => {
      set({
        phase: 'results',
        isTransitioning: false
      });
    }, 50);
  },

  transitionToDiscovery: () => {
    const { phase } = get();
    if (phase === 'discovery') return;

    set({
      isTransitioning: true,
      previousPhase: phase
    });

    setTimeout(() => {
      set({
        phase: 'discovery',
        isTransitioning: false,
        hasMapData: false
      });
    }, 50);
  },

  setAvatarMood: (mood) => set({ avatarMood: mood }),

  setHasMapData: (has) => set({ hasMapData: has }),
}));
