import { useEffect, useRef, useMemo } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { MapLayerType } from '@/stores/parcelRevealStore';

interface ParcelMiniMapProps {
  lat: number;
  lon: number;
  layer: MapLayerType;
  parcelId?: string;
  className?: string;
}

// Tile layer configurations - no API key needed
const TILE_LAYERS: Record<MapLayerType, { url: string; attribution: string; maxZoom: number }> = {
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri',
    maxZoom: 19,
  },
  terrain: {
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenTopoMap',
    maxZoom: 17,
  },
  streets: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap',
    maxZoom: 19,
  },
};

export function ParcelMiniMap({ lat, lon, layer, parcelId, className = '' }: ParcelMiniMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const markerRef = useRef<L.Marker | null>(null);

  const tileConfig = useMemo(() => TILE_LAYERS[layer], [layer]);

  // Initialize map
  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;

    const map = L.map(mapRef.current, {
      center: [lat, lon],
      zoom: 15,
      zoomControl: false,
      attributionControl: false,
      dragging: true,
      scrollWheelZoom: true,
    });

    // Add initial tile layer
    const tileLayer = L.tileLayer(tileConfig.url, {
      attribution: tileConfig.attribution,
      maxZoom: tileConfig.maxZoom,
    }).addTo(map);

    // Custom marker icon
    const markerIcon = L.divIcon({
      className: 'parcel-marker-icon',
      html: `
        <div class="w-8 h-8 rounded-full bg-amber-500 border-2 border-white shadow-lg flex items-center justify-center animate-pulse">
          <svg class="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          </svg>
        </div>
      `,
      iconSize: [32, 32],
      iconAnchor: [16, 16],
    });

    // Add marker
    const marker = L.marker([lat, lon], { icon: markerIcon }).addTo(map);

    mapInstanceRef.current = map;
    tileLayerRef.current = tileLayer;
    markerRef.current = marker;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
      tileLayerRef.current = null;
      markerRef.current = null;
    };
  }, []);

  // Update tile layer when layer type changes
  useEffect(() => {
    if (!mapInstanceRef.current || !tileLayerRef.current) return;

    // Remove old tile layer
    mapInstanceRef.current.removeLayer(tileLayerRef.current);

    // Add new tile layer
    const newTileLayer = L.tileLayer(tileConfig.url, {
      attribution: tileConfig.attribution,
      maxZoom: tileConfig.maxZoom,
    }).addTo(mapInstanceRef.current);

    tileLayerRef.current = newTileLayer;
  }, [tileConfig]);

  // Update map position when lat/lon changes
  useEffect(() => {
    if (!mapInstanceRef.current || !markerRef.current) return;

    mapInstanceRef.current.setView([lat, lon], 15, { animate: true });
    markerRef.current.setLatLng([lat, lon]);
  }, [lat, lon, parcelId]);

  return (
    <div
      ref={mapRef}
      className={`w-full h-full rounded-lg overflow-hidden ${className}`}
      style={{ minHeight: '200px' }}
    />
  );
}
