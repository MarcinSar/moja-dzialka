import { useEffect, useRef, useState, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useParcelRevealStore } from '@/stores/parcelRevealStore';
import { useUIPhaseStore } from '@/stores/uiPhaseStore';
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
};

export function MapPanelImmersive() {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  const parcelLayersRef = useRef<Map<string, L.Layer>>(new Map());
  const numberMarkersRef = useRef<L.Marker[]>([]);
  const [isLoadingGeometry, setIsLoadingGeometry] = useState(false);

  const parcels = useParcelRevealStore((s) => s.parcels);
  const currentIndex = useParcelRevealStore((s) => s.currentIndex);
  const spotlightParcelId = useUIPhaseStore((s) => s.spotlightParcelId);
  const setSpotlightParcel = useUIPhaseStore((s) => s.setSpotlightParcel);
  const goToParcel = useParcelRevealStore((s) => s.goToParcel);

  // Initialize map once
  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;

    // Default to Gdańsk/Gdynia area
    const initialCenter: [number, number] = [54.45, 18.55];

    const map = L.map(mapRef.current, {
      center: initialCenter,
      zoom: 11,
      zoomControl: false,
      attributionControl: false,
    });

    // Dark tile layer - Carto Dark Matter
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(map);

    // Zoom control in bottom right
    L.control.zoom({ position: 'bottomright' }).addTo(map);

    mapInstanceRef.current = map;
    console.log('[Map] Initialized');

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Style function for GeoJSON features
  const getFeatureStyle = useCallback((_parcelId: string, isSpotlight: boolean) => {
    const colors = isSpotlight ? COLORS.spotlight : COLORS.default;
    return {
      fillColor: colors.fill,
      fillOpacity: isSpotlight ? 0.5 : 0.3,
      color: colors.stroke,
      weight: isSpotlight ? 3 : 2,
      opacity: 1,
    };
  }, []);

  // Fetch and display parcel geometries
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) {
      console.log('[Map] No map instance yet');
      return;
    }

    // Clear existing layers
    if (geoJsonLayerRef.current) {
      map.removeLayer(geoJsonLayerRef.current);
      geoJsonLayerRef.current = null;
    }
    parcelLayersRef.current.clear();

    // Clear number markers
    numberMarkersRef.current.forEach((marker) => map.removeLayer(marker));
    numberMarkersRef.current = [];

    console.log('[Map] Parcels to display:', parcels.length);
    if (parcels.length === 0) return;

    // Get top 3 parcel IDs
    const displayParcels = parcels.slice(0, 3);
    const parcelIds = displayParcels.map((item) => item.parcel.parcel_id);

    console.log('[Map] Fetching geometry for parcels:', parcelIds);
    setIsLoadingGeometry(true);

    // Fetch actual parcel geometries from PostGIS
    getMapData(parcelIds, true)
      .then((response) => {
        console.log('[Map] Received GeoJSON with', response.parcel_count, 'parcels');

        if (!response.geojson || !response.geojson.features) {
          console.warn('[Map] No features in GeoJSON response');
          return;
        }

        // Create GeoJSON layer
        const geoJsonLayer = L.geoJSON(response.geojson, {
          style: (feature) => {
            const parcelId = feature?.properties?.id_dzialki;
            const isSpotlight = parcelId === spotlightParcelId;
            return getFeatureStyle(parcelId, isSpotlight);
          },
          onEachFeature: (feature, layer) => {
            const parcelId = feature?.properties?.id_dzialki;
            if (!parcelId) return;

            // Store layer reference for later updates
            parcelLayersRef.current.set(parcelId, layer);

            // Find the index for this parcel
            const index = displayParcels.findIndex(
              (item) => item.parcel.parcel_id === parcelId
            );

            // Add click handler
            layer.on('click', () => {
              if (index >= 0) {
                goToParcel(index);
              }
              setSpotlightParcel(parcelId);
            });

            // Add hover handlers
            layer.on('mouseover', () => {
              setSpotlightParcel(parcelId);
            });

            layer.on('mouseout', () => {
              setSpotlightParcel(null);
            });

            // Add popup with parcel info
            const props = feature.properties || {};
            const area = props.area_m2 ? `${props.area_m2.toLocaleString('pl-PL')} m²` : '';
            const location = props.dzielnica || props.miejscowosc || props.gmina || '';

            // Add a number marker in the center
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

        // Fit map to parcels bounds
        // API returns bounds as [[lat, lon], [lat, lon]] - no swap needed
        if (response.bounds) {
          const bounds = L.latLngBounds(
            [response.bounds[0][0], response.bounds[0][1]], // SW [lat, lon]
            [response.bounds[1][0], response.bounds[1][1]]  // NE [lat, lon]
          );
          console.log('[Map] Fitting to bounds:', bounds.toBBoxString());
          map.fitBounds(bounds, {
            padding: [80, 80],
            maxZoom: 16,
          });
        } else if (response.center) {
          // API returns center as [lat, lon]
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

  // Update spotlight styling when spotlight changes (hover)
  // ONLY update styles - NO flyToBounds on hover to prevent view reset
  useEffect(() => {
    const displayParcels = parcels.slice(0, 3);

    displayParcels.forEach((item) => {
      const layer = parcelLayersRef.current.get(item.parcel.parcel_id);
      if (!layer) return;

      const isSpotlight = item.parcel.parcel_id === spotlightParcelId;

      // Update layer style only
      if ('setStyle' in layer && typeof layer.setStyle === 'function') {
        (layer as L.Path).setStyle(getFeatureStyle(item.parcel.parcel_id, isSpotlight));
      }
    });
  }, [spotlightParcelId, parcels, getFeatureStyle]);

  // Zoom to current parcel when currentIndex changes (from card click)
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || parcels.length === 0) return;

    const currentParcel = parcels[currentIndex];
    if (!currentParcel) return;

    const layer = parcelLayersRef.current.get(currentParcel.parcel.parcel_id);
    if (layer && 'getBounds' in layer) {
      const bounds = (layer as L.Polygon).getBounds();
      map.flyToBounds(bounds, {
        padding: [100, 100],
        maxZoom: 16,
        duration: 0.5,
      });
      // Also set spotlight
      setSpotlightParcel(currentParcel.parcel.parcel_id);
    }
  }, [currentIndex, parcels, setSpotlightParcel]);

  return (
    <div className="relative w-full h-full">
      <div ref={mapRef} className="w-full h-full" />

      {/* Loading indicator */}
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
