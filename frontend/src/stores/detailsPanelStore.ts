import { create } from 'zustand';
import { getParcelDetails } from '@/services/api';

export type MapLayer = 'ortho' | 'osm' | 'topo' | 'carto';

export interface ParcelData {
  id_dzialki: string;
  gmina?: string | null;
  dzielnica?: string | null;
  miejscowosc?: string | null;
  area_m2?: number | null;

  // Scores
  quietness_score?: number | null;
  nature_score?: number | null;
  accessibility_score?: number | null;

  // Distances
  dist_to_school?: number | null;
  dist_to_bus_stop?: number | null;
  dist_to_forest?: number | null;
  dist_to_water?: number | null;
  dist_to_shop?: number | null;
  dist_to_supermarket?: number | null;
  dist_to_pharmacy?: number | null;
  dist_to_hospital?: number | null;

  // POG (Plan Ogólny Gminy) - all fields
  has_pog?: boolean | null;
  pog_symbol?: string | null;
  pog_nazwa?: string | null;
  pog_oznaczenie?: string | null;
  pog_profil_podstawowy?: string | null;
  pog_profil_podstawowy_nazwy?: string | null;
  pog_profil_dodatkowy?: string | null;
  pog_profil_dodatkowy_nazwy?: string | null;
  pog_maks_intensywnosc?: number | null;
  pog_maks_wysokosc_m?: number | null;
  pog_maks_zabudowa_pct?: number | null;
  pog_min_bio_pct?: number | null;
  is_residential_zone?: boolean | null;

  // Building
  is_built?: boolean | null;
  building_count?: number | null;
  building_coverage_pct?: number | null;

  // Categories
  kategoria_ciszy?: string | null;
  kategoria_natury?: string | null;
  kategoria_dostepu?: string | null;
  gestosc_zabudowy?: string | null;

  // Coordinates
  centroid_lat?: number | null;
  centroid_lon?: number | null;

  // Geometry for map
  geometry_wgs84?: GeoJSON.Geometry | null;
}

interface DetailsPanelState {
  isOpen: boolean;
  parcelId: string | null;
  parcelData: ParcelData | null;
  isLoading: boolean;
  error: string | null;
  selectedLayer: MapLayer;

  // Actions
  openPanel: (parcelId: string) => Promise<void>;
  closePanel: () => void;
  setLayer: (layer: MapLayer) => void;
}

export const useDetailsPanelStore = create<DetailsPanelState>((set) => ({
  isOpen: false,
  parcelId: null,
  parcelData: null,
  isLoading: false,
  error: null,
  selectedLayer: 'ortho',

  openPanel: async (parcelId: string) => {
    set({ isOpen: true, parcelId, isLoading: true, error: null });

    try {
      const data = await getParcelDetails(parcelId, true);
      set({
        parcelData: data as ParcelData,
        isLoading: false
      });
    } catch (err) {
      console.error('[DetailsPanel] Failed to fetch parcel details:', err);
      set({
        error: err instanceof Error ? err.message : 'Nie udało się pobrać danych działki',
        isLoading: false
      });
    }
  },

  closePanel: () => {
    set({
      isOpen: false,
      parcelId: null,
      parcelData: null,
      error: null
    });
  },

  setLayer: (layer: MapLayer) => {
    set({ selectedLayer: layer });
  },
}));
