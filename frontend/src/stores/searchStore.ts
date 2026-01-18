import { create } from 'zustand';
import type { SearchPreferences, SearchResultItem, ParcelDetails, SearchResponse, MapData } from '@/types';

interface SearchState {
  // Search state
  preferences: SearchPreferences;
  results: SearchResultItem[];
  searchResults: SearchResponse | null;
  totalMatching: number;
  isSearching: boolean;
  searchError: string | null;

  // Selection
  selectedParcel: string | null;
  parcelDetails: ParcelDetails | null;
  isLoadingDetails: boolean;

  // Map state
  mapCenter: { lat: number; lng: number };
  mapZoom: number;
  mapData: MapData | null;

  // Gminy list
  gminy: string[];
  isLoadingGminy: boolean;

  // Actions
  setPreferences: (prefs: Partial<SearchPreferences>) => void;
  resetPreferences: () => void;
  setResults: (results: SearchResultItem[], total: number) => void;
  setSearchResults: (response: SearchResponse | null) => void;
  setSearching: (isSearching: boolean) => void;
  setSearchError: (error: string | null) => void;
  setSelectedParcel: (parcelId: string | null) => void;
  setParcelDetails: (details: ParcelDetails | null) => void;
  setLoadingDetails: (loading: boolean) => void;
  setMapCenter: (center: { lat: number; lng: number }) => void;
  setMapZoom: (zoom: number) => void;
  setMapData: (data: MapData | null) => void;
  setGminy: (gminy: string[]) => void;
  setLoadingGminy: (loading: boolean) => void;
}

const defaultPreferences: SearchPreferences = {
  radius_m: 5000,
  quietness_weight: 0.4,
  nature_weight: 0.3,
  accessibility_weight: 0.3,
};

export const useSearchStore = create<SearchState>((set) => ({
  // Initial state
  preferences: defaultPreferences,
  results: [],
  searchResults: null,
  totalMatching: 0,
  isSearching: false,
  searchError: null,
  selectedParcel: null,
  parcelDetails: null,
  isLoadingDetails: false,
  mapCenter: { lat: 54.35, lng: 18.65 }, // Gdańsk area
  mapZoom: 10,
  mapData: null,
  gminy: [],
  isLoadingGminy: false,

  // Actions
  setPreferences: (prefs) =>
    set((state) => ({
      preferences: { ...state.preferences, ...prefs },
    })),

  resetPreferences: () =>
    set({ preferences: defaultPreferences }),

  setResults: (results, total) =>
    set({
      results,
      totalMatching: total,
      searchError: null,
    }),

  setSearchResults: (response) =>
    set({
      searchResults: response,
      results: response?.results || [],
      totalMatching: response?.total_matching || 0,
      searchError: null,
    }),

  setSearching: (isSearching) =>
    set({ isSearching }),

  setSearchError: (error) =>
    set({ searchError: error, isSearching: false }),

  setSelectedParcel: (parcelId) =>
    set({ selectedParcel: parcelId }),

  setParcelDetails: (details) =>
    set({ parcelDetails: details }),

  setLoadingDetails: (loading) =>
    set({ isLoadingDetails: loading }),

  setMapCenter: (center) =>
    set({ mapCenter: center }),

  setMapZoom: (zoom) =>
    set({ mapZoom: zoom }),

  setMapData: (data) =>
    set((state) => ({
      mapData: data,
      // Update center if provided
      mapCenter: data?.center
        ? { lat: data.center.lat, lng: data.center.lon }
        : state.mapCenter,
    })),

  setGminy: (gminy) =>
    set({ gminy, isLoadingGminy: false }),

  setLoadingGminy: (loading) =>
    set({ isLoadingGminy: loading }),
}));
