import { create } from 'zustand';
import L from 'leaflet';

export type BaseLayer = 'carto' | 'osm' | 'satellite' | 'topo';
export type OverlayLayer = 'mpzp' | 'cadastral' | 'ortho';

export const BASE_LAYERS: Record<BaseLayer, { name: string; url: string; subdomains?: string }> = {
  carto: {
    name: 'Dark',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    subdomains: 'abcd',
  },
  osm: {
    name: 'Mapa',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  },
  satellite: {
    name: 'Satelita',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  },
  topo: {
    name: 'Teren',
    url: 'https://tile.opentopomap.org/{z}/{x}/{y}.png',
  },
};

export const WMS_OVERLAYS: Record<OverlayLayer, { name: string; url: string; layers: string; format: string; opacity: number }> = {
  mpzp: {
    name: 'MPZP',
    url: 'https://mapy.geoportal.gov.pl/wss/ext/KrajowaIntegracjaMiejscowychPlanowZagospodarowaniaPrzestrzennego',
    layers: 'raster,wektor-linie,wektor-powierzchnie',
    format: 'image/png',
    opacity: 0.6,
  },
  cadastral: {
    name: 'EGiB',
    url: 'https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow',
    layers: 'dzialki,budynki,numery_dzialek',
    format: 'image/png',
    opacity: 0.7,
  },
  ortho: {
    name: 'Ortofoto',
    url: 'https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution',
    layers: 'Raster',
    format: 'image/jpeg',
    opacity: 0.8,
  },
};

interface MapLayerState {
  baseLayer: BaseLayer;
  overlays: Record<OverlayLayer, boolean>;
  mapInstance: L.Map | null;

  setBaseLayer: (layer: BaseLayer) => void;
  toggleOverlay: (layer: OverlayLayer) => void;
  setMapInstance: (map: L.Map | null) => void;
}

export const useMapLayerStore = create<MapLayerState>((set) => ({
  baseLayer: 'carto',
  overlays: {
    mpzp: false,
    cadastral: false,
    ortho: false,
  },
  mapInstance: null,

  setBaseLayer: (layer) => set({ baseLayer: layer }),

  toggleOverlay: (layer) =>
    set((state) => ({
      overlays: {
        ...state.overlays,
        [layer]: !state.overlays[layer],
      },
    })),

  setMapInstance: (map) => set({ mapInstance: map }),
}));
