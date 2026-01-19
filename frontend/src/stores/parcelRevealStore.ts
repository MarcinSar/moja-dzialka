import { create } from 'zustand';
import type { SearchResultItem } from '@/types';

export interface ParcelWithExplanation {
  parcel: SearchResultItem;
  explanation: string;      // "Działka w Kolbudach, 1,234 m²"
  highlights: string[];     // ["Cisza: 92/100", "Las: 150m", ...]
}

export type MapLayerType = 'satellite' | 'terrain' | 'streets';

interface ParcelRevealState {
  // Wszystkie działki z wyszukiwania
  parcels: ParcelWithExplanation[];

  // Stan wyświetlania
  currentIndex: number;
  isVisible: boolean;  // czy karta z mapą jest widoczna

  // Warstwa mapy
  mapLayer: MapLayerType;

  // Actions
  setParcels: (parcels: ParcelWithExplanation[]) => void;
  showReveal: () => void;      // pokaż kartę
  hideReveal: () => void;      // ukryj kartę (płynnie)
  nextParcel: () => void;
  prevParcel: () => void;
  goToParcel: (index: number) => void;
  setMapLayer: (layer: MapLayerType) => void;
  clear: () => void;           // wyczyść wyniki

  // Computed getters (as functions)
  getCurrentParcel: () => ParcelWithExplanation | null;
  getTotalCount: () => number;
}

export const useParcelRevealStore = create<ParcelRevealState>((set, get) => ({
  // Initial state
  parcels: [],
  currentIndex: 0,
  isVisible: false,
  mapLayer: 'satellite',

  // Actions
  setParcels: (parcels) => set({
    parcels,
    currentIndex: 0,
  }),

  showReveal: () => set({ isVisible: true }),

  hideReveal: () => set({ isVisible: false }),

  nextParcel: () => set((state) => ({
    currentIndex: Math.min(state.currentIndex + 1, state.parcels.length - 1),
  })),

  prevParcel: () => set((state) => ({
    currentIndex: Math.max(state.currentIndex - 1, 0),
  })),

  goToParcel: (index) => set((state) => ({
    currentIndex: Math.max(0, Math.min(index, state.parcels.length - 1)),
  })),

  setMapLayer: (layer) => set({ mapLayer: layer }),

  clear: () => set({
    parcels: [],
    currentIndex: 0,
    isVisible: false,
  }),

  // Computed getters
  getCurrentParcel: () => {
    const state = get();
    return state.parcels[state.currentIndex] || null;
  },

  getTotalCount: () => get().parcels.length,
}));

// Helper function to generate highlights from parcel data
export function generateHighlights(parcel: SearchResultItem): string[] {
  const highlights: string[] = [];

  // Cisza
  if (parcel.quietness_score !== null && parcel.quietness_score >= 85) {
    highlights.push(`Cisza: ${parcel.quietness_score}/100`);
  }

  // Natura
  if (parcel.nature_score !== null && parcel.nature_score >= 70) {
    highlights.push(`Natura: ${parcel.nature_score}/100`);
  }

  // Dostępność
  if (parcel.accessibility_score !== null && parcel.accessibility_score >= 70) {
    highlights.push(`Dostępność: ${parcel.accessibility_score}/100`);
  }

  // MPZP
  if (parcel.has_mpzp && parcel.mpzp_symbol) {
    highlights.push(`MPZP: ${parcel.mpzp_symbol}`);
  } else if (parcel.has_mpzp) {
    highlights.push('Ma MPZP');
  }

  return highlights.slice(0, 4); // Max 4 highlights
}

// Helper function to generate explanation
export function generateExplanation(parcel: SearchResultItem): string {
  const parts: string[] = [];

  if (parcel.miejscowosc) {
    parts.push(parcel.miejscowosc);
  } else if (parcel.gmina) {
    parts.push(parcel.gmina);
  }

  if (parcel.area_m2) {
    parts.push(`${parcel.area_m2.toLocaleString('pl-PL')} m²`);
  }

  return parts.join(', ');
}
