import { useEffect, useRef, useState, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useParcelRevealStore } from '@/stores/parcelRevealStore';
import { useUIPhaseStore } from '@/stores/uiPhaseStore';
import { useMapLayerStore, BASE_LAYERS, WMS_OVERLAYS, type OverlayLayer } from '@/stores/mapLayerStore';
import { useDetailsPanelStore } from '@/stores/detailsPanelStore';
import { useIsMobile } from '@/hooks/useIsMobile';
import { getMapData } from '@/services/api';

// Color palette for parcels
const COLORS = {
  default: {
    fill: '#0ea5e9',    // sky-500
    stroke: '#0284c7',  // sky-600
  },
  spotlight: {
    fill: '#f59e0b',    // amber-500
    stroke: '#d97706',  // amber-600
  },
  details: {
    fill: '#a855f7',    // purple-500
    stroke: '#9333ea',  // purple-600
  },
};

export function MapPanelImmersive() {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const wmsLayersRef = useRef<Map<string, L.TileLayer.WMS>>(new Map());
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  const parcelLayersRef = useRef<Map<string, L.Layer>>(new Map());
  const numberMarkersRef = useRef<L.Marker[]>([]);
  const [isLoadingGeometry, setIsLoadingGeometry] = useState(false);

  const parcels = useParcelRevealStore((s) => s.parcels);
  const currentIndex = useParcelRevealStore((s) => s.currentIndex);
  const spotlightParcelId = useUIPhaseStore((s) => s.spotlightParcelId);
  const setSpotlightParcel = useUIPhaseStore((s) => s.setSpotlightParcel);
  const goToParcel = useParcelRevealStore((s) => s.goToParcel);

  // Map layer store
  const baseLayer = useMapLayerStore((s) => s.baseLayer);
  const overlays = useMapLayerStore((s) => s.overlays);
  const setMapInstance = useMapLayerStore((s) => s.setMapInstance);

  // Details panel store - for flyTo on details open
  const detailsParcelData = useDetailsPanelStore((s) => s.parcelData);
  const isDetailsOpen = useDetailsPanelStore((s) => s.isOpen);
  const isMobile = useIsMobile();
  const mapPadding: [number, number] = isMobile ? [40, 40] : [80, 80];

  // Initialize map once
  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;

    const initialCenter: [number, number] = [54.45, 18.55];

    const map = L.map(mapRef.current, {
      center: initialCenter,
      zoom: 11,
      zoomControl: false,
      attributionControl: false,
    });

    // Initial base layer
    const layerConfig = BASE_LAYERS[baseLayer];
    const opts: L.TileLayerOptions = { maxZoom: 19 };
    if (layerConfig.subdomains) opts.subdomains = layerConfig.subdomains;
    const tile = L.tileLayer(layerConfig.url, opts).addTo(map);
    tileLayerRef.current = tile;

    // Zoom control in bottom right
    L.control.zoom({ position: 'bottomright' }).addTo(map);

    mapInstanceRef.current = map;
    setMapInstance(map);

    return () => {
      map.remove();
      mapInstanceRef.current = null;
      setMapInstance(null);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Switch base layer without resetting zoom/position
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Remove old tile layer
    if (tileLayerRef.current) {
      map.removeLayer(tileLayerRef.current);
    }

    const layerConfig = BASE_LAYERS[baseLayer];
    const opts: L.TileLayerOptions = { maxZoom: 19 };
    if (layerConfig.subdomains) opts.subdomains = layerConfig.subdomains;
    const tile = L.tileLayer(layerConfig.url, opts);
    tile.addTo(map);
    // Ensure base tile is below all other layers
    tile.setZIndex(0);
    tileLayerRef.current = tile;
  }, [baseLayer]);

  // Toggle WMS overlays without resetting zoom/position
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    const overlayKeys: OverlayLayer[] = ['mpzp', 'cadastral', 'ortho'];

    for (const key of overlayKeys) {
      const existing = wmsLayersRef.current.get(key);
      const shouldShow = overlays[key];

      if (shouldShow && !existing) {
        const config = WMS_OVERLAYS[key];
        const wmsLayer = L.tileLayer.wms(config.url, {
          layers: config.layers,
          format: config.format,
          transparent: true,
          opacity: config.opacity,
          maxZoom: 19,
        });
        wmsLayer.addTo(map);
        wmsLayer.setZIndex(1);
        wmsLayersRef.current.set(key, wmsLayer);
      } else if (!shouldShow && existing) {
        map.removeLayer(existing);
        wmsLayersRef.current.delete(key);
      }
    }
  }, [overlays]);

  // Style function for GeoJSON features
  const getFeatureStyle = useCallback((_parcelId: string, isSpotlight: boolean, isDetails: boolean = false) => {
    const colors = isDetails ? COLORS.details : isSpotlight ? COLORS.spotlight : COLORS.default;
    return {
      fillColor: colors.fill,
      fillOpacity: isDetails ? 0.5 : isSpotlight ? 0.5 : 0.3,
      color: colors.stroke,
      weight: isDetails ? 3 : isSpotlight ? 3 : 2,
      opacity: 1,
    };
  }, []);

  // Fetch and display parcel geometries
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Clear existing layers
    if (geoJsonLayerRef.current) {
      map.removeLayer(geoJsonLayerRef.current);
      geoJsonLayerRef.current = null;
    }
    parcelLayersRef.current.clear();

    // Clear number markers
    numberMarkersRef.current.forEach((marker) => map.removeLayer(marker));
    numberMarkersRef.current = [];

    if (parcels.length === 0) return;

    // Get top 3 parcel IDs
    const displayParcels = parcels.slice(0, 3);
    const parcelIds = displayParcels.map((item) => item.parcel.parcel_id);

    setIsLoadingGeometry(true);

    getMapData(parcelIds, true)
      .then((response) => {
        if (!response.geojson || !response.geojson.features) return;

        const geoJsonLayer = L.geoJSON(response.geojson, {
          style: (feature) => {
            const parcelId = feature?.properties?.id_dzialki;
            const isSpotlight = parcelId === spotlightParcelId;
            return getFeatureStyle(parcelId, isSpotlight);
          },
          onEachFeature: (feature, layer) => {
            const parcelId = feature?.properties?.id_dzialki;
            if (!parcelId) return;

            parcelLayersRef.current.set(parcelId, layer);

            const index = displayParcels.findIndex(
              (item) => item.parcel.parcel_id === parcelId
            );

            layer.on('click', () => {
              if (index >= 0) goToParcel(index);
              setSpotlightParcel(parcelId);
            });

            layer.on('mouseover', () => setSpotlightParcel(parcelId));
            layer.on('mouseout', () => setSpotlightParcel(null));

            // Number marker
            if ('getBounds' in layer && typeof (layer as L.Polygon).getBounds === 'function') {
              const center = (layer as L.Polygon).getBounds().getCenter();
              const numberIcon = L.divIcon({
                className: 'parcel-number-marker',
                html: `
                  <div class="flex items-center justify-center w-8 h-8 rounded-full
                              bg-slate-900/80 border-2 border-white/20 shadow-lg
                              text-white font-bold text-sm">
                    ${index + 1}
                  </div>
                `,
                iconSize: [32, 32],
                iconAnchor: [16, 16],
              });
              const numberMarker = L.marker(center, { icon: numberIcon, interactive: false }).addTo(map);
              numberMarkersRef.current.push(numberMarker);
            }

            const props = feature.properties || {};
            const area = props.area_m2 ? `${props.area_m2.toLocaleString('pl-PL')} m²` : '';
            const location = props.dzielnica || props.miejscowosc || props.gmina || '';
            layer.bindPopup(`
              <div class="text-sm">
                <div class="font-semibold">${location}</div>
                <div class="text-slate-400">${area}</div>
                <div class="text-xs text-slate-500 mt-1">ID: ${parcelId}</div>
              </div>
            `);
          },
        });

        geoJsonLayer.addTo(map);
        geoJsonLayerRef.current = geoJsonLayer;

        if (response.bounds) {
          const bounds = L.latLngBounds(
            [response.bounds[0][0], response.bounds[0][1]],
            [response.bounds[1][0], response.bounds[1][1]]
          );
          map.fitBounds(bounds, { padding: mapPadding, maxZoom: 16 });
        } else if (response.center) {
          map.setView([response.center[0], response.center[1]], 14);
        }
      })
      .catch((error) => {
        console.error('[Map] Failed to fetch geometry:', error);
      })
      .finally(() => {
        setIsLoadingGeometry(false);
      });
  }, [parcels, goToParcel, setSpotlightParcel, getFeatureStyle]);

  // Update spotlight styling
  useEffect(() => {
    const displayParcels = parcels.slice(0, 3);
    displayParcels.forEach((item) => {
      const layer = parcelLayersRef.current.get(item.parcel.parcel_id);
      if (!layer) return;
      const isSpotlight = item.parcel.parcel_id === spotlightParcelId;
      if ('setStyle' in layer && typeof layer.setStyle === 'function') {
        (layer as L.Path).setStyle(getFeatureStyle(item.parcel.parcel_id, isSpotlight));
      }
    });
  }, [spotlightParcelId, parcels, getFeatureStyle]);

  // Zoom to current parcel on card click
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || parcels.length === 0) return;

    const currentParcel = parcels[currentIndex];
    if (!currentParcel) return;

    const layer = parcelLayersRef.current.get(currentParcel.parcel.parcel_id);
    if (layer && 'getBounds' in layer) {
      const bounds = (layer as L.Polygon).getBounds();
      map.flyToBounds(bounds, { padding: mapPadding, maxZoom: 16, duration: 0.5 });
      setSpotlightParcel(currentParcel.parcel.parcel_id);
    }
  }, [currentIndex, parcels, setSpotlightParcel]);

  // FlyTo when details panel opens with geometry
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !isDetailsOpen || !detailsParcelData) return;

    if (detailsParcelData.geometry_wgs84) {
      const geojson = L.geoJSON(detailsParcelData.geometry_wgs84 as GeoJSON.GeoJsonObject);
      const bounds = geojson.getBounds();
      if (bounds.isValid()) {
        map.flyToBounds(bounds, { padding: mapPadding, maxZoom: 17, duration: 0.7 });
      }
    } else if (detailsParcelData.centroid_lat && detailsParcelData.centroid_lon) {
      map.flyTo([detailsParcelData.centroid_lat, detailsParcelData.centroid_lon], 16, { duration: 0.7 });
    }
  }, [isDetailsOpen, detailsParcelData]);

  return (
    <div className="relative w-full h-full">
      <div ref={mapRef} className="w-full h-full" />

      {isLoadingGeometry && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50
                        px-4 py-2 rounded-full backdrop-blur-xl bg-slate-900/80
                        text-sm text-slate-300 flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-sky-400 border-t-transparent rounded-full animate-spin" />
          <span>Ładuję działki...</span>
        </div>
      )}
    </div>
  );
}
