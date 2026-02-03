import { create } from 'zustand';

export type UIPhase = 'discovery' | 'search_results' | 'results' | 'transitioning';
export type AvatarMood = 'idle' | 'thinking' | 'speaking' | 'excited';
export type AgentType = 'discovery' | 'search' | 'analyst' | 'narrator' | 'feedback' | 'lead' | 'orchestrator';

interface UIPhaseState {
  phase: UIPhase;
  previousPhase: UIPhase | null;
  avatarMood: AvatarMood;
  hasMapData: boolean;
  isTransitioning: boolean;

  // Multi-agent state (v3.0)
  activeAgentType: AgentType;
  activeSkill: string | null;

  // Spotlight state for hover synchronization
  spotlightParcelId: string | null;

  // Actions
  setPhase: (phase: UIPhase) => void;
  transitionToResults: () => void;
  transitionToSearchResults: () => void;
  transitionToDiscovery: () => void;
  setAvatarMood: (mood: AvatarMood) => void;
  setHasMapData: (has: boolean) => void;
  setSpotlightParcel: (parcelId: string | null) => void;
  setActiveAgent: (agentType: AgentType, skill?: string) => void;
}

export const useUIPhaseStore = create<UIPhaseState>((set, get) => ({
  phase: 'discovery',
  previousPhase: null,
  avatarMood: 'idle',
  hasMapData: false,
  isTransitioning: false,
  activeAgentType: 'orchestrator',
  activeSkill: null,
  spotlightParcelId: null,

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

  transitionToSearchResults: () => {
    const { phase } = get();
    if (phase === 'search_results') return;

    set({
      isTransitioning: true,
      previousPhase: phase
    });

    // Longer delay for dramatic transition animation
    setTimeout(() => {
      set({
        phase: 'search_results',
        isTransitioning: false
      });
    }, 100);
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
        hasMapData: false,
        spotlightParcelId: null
      });
    }, 50);
  },

  setAvatarMood: (mood) => set({ avatarMood: mood }),

  setHasMapData: (has) => set({ hasMapData: has }),

  setSpotlightParcel: (parcelId) => set({ spotlightParcelId: parcelId }),

  setActiveAgent: (agentType, skill) => set({
    activeAgentType: agentType,
    activeSkill: skill || null,
  }),
}));
