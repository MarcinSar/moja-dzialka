import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useSearchStore } from '@/stores/searchStore';
import type { SearchResultItem } from '@/types';

// Custom marker icon
const parcelIcon = L.divIcon({
  className: 'parcel-marker',
  html: `
    <div class="w-8 h-8 bg-primary rounded-full border-2 border-white shadow-lg
                flex items-center justify-center transform -translate-x-1/2 -translate-y-1/2">
      <svg class="w-4 h-4 text-slate-900" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      </svg>
    </div>
  `,
  iconSize: [32, 32],
  iconAnchor: [16, 16],
});

export function MapPanel() {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.LayerGroup | null>(null);

  const { searchResults, selectedParcel, setSelectedParcel, mapCenter, mapZoom, mapData } = useSearchStore();
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);

  // Initialize map
  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;

    const map = L.map(mapRef.current, {
      center: [mapCenter.lat, mapCenter.lng],
      zoom: mapZoom,
      zoomControl: false,
    });

    // Dark tile layer (Carto Dark Matter)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(map);

    // Custom zoom control position
    L.control.zoom({ position: 'topright' }).addTo(map);

    // Create markers layer group
    markersRef.current = L.layerGroup().addTo(map);

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update markers when results change
  useEffect(() => {
    if (!markersRef.current || !mapInstanceRef.current) return;

    // Clear existing markers
    markersRef.current.clearLayers();

    if (!searchResults?.results?.length) return;

    const bounds: L.LatLngBounds = L.latLngBounds([]);

    searchResults.results.forEach((parcel) => {
      if (!parcel.centroid_lat || !parcel.centroid_lon) return;

      const marker = L.marker([parcel.centroid_lat, parcel.centroid_lon], {
        icon: parcelIcon,
      });

      // Popup content
      const popupContent = `
        <div class="parcel-popup p-3 min-w-[200px]">
          <h4 class="font-medium text-sm text-white mb-2">${parcel.parcel_id}</h4>
          <div class="space-y-1 text-xs">
            <div class="flex justify-between">
              <span class="text-slate-400">Powierzchnia:</span>
              <span class="text-white">${parcel.area_m2?.toLocaleString('pl-PL')} m²</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-400">Gmina:</span>
              <span class="text-white">${parcel.gmina || '—'}</span>
            </div>
            ${parcel.quietness_score !== null && parcel.quietness_score !== undefined ? `
              <div class="flex justify-between">
                <span class="text-slate-400">Cisza:</span>
                <span class="text-white">${parcel.quietness_score.toFixed(0)}/100</span>
              </div>
            ` : ''}
            ${parcel.nature_score !== null && parcel.nature_score !== undefined ? `
              <div class="flex justify-between">
                <span class="text-slate-400">Natura:</span>
                <span class="text-white">${parcel.nature_score.toFixed(0)}/100</span>
              </div>
            ` : ''}
          </div>
        </div>
      `;

      marker.bindPopup(popupContent, {
        className: 'dark-popup',
        closeButton: false,
      });

      marker.on('click', () => {
        setSelectedParcel(parcel.parcel_id);
      });

      markersRef.current?.addLayer(marker);
      bounds.extend([parcel.centroid_lat, parcel.centroid_lon]);
    });

    // Fit map to markers
    if (bounds.isValid()) {
      mapInstanceRef.current.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [searchResults, setSelectedParcel]);

  // Update map when mapData (GeoJSON from agent) changes
  useEffect(() => {
    if (!mapInstanceRef.current) return;

    // Remove existing GeoJSON layer
    if (geoJsonLayerRef.current) {
      mapInstanceRef.current.removeLayer(geoJsonLayerRef.current);
      geoJsonLayerRef.current = null;
    }

    if (!mapData?.geojson?.features?.length) return;

    // Create GeoJSON layer with styling
    const geoJsonLayer = L.geoJSON(mapData.geojson as GeoJSON.GeoJsonObject, {
      style: () => ({
        color: '#f59e0b', // amber
        weight: 2,
        opacity: 0.8,
        fillColor: '#f59e0b',
        fillOpacity: 0.3,
      }),
      onEachFeature: (feature, layer) => {
        const props = feature.properties || {};
        const popupContent = `
          <div class="parcel-popup p-3 min-w-[200px]">
            <h4 class="font-medium text-sm text-white mb-2">${props.id || 'Działka'}</h4>
            <div class="space-y-1 text-xs">
              <div class="flex justify-between">
                <span class="text-slate-400">Powierzchnia:</span>
                <span class="text-white">${props.area_m2?.toLocaleString('pl-PL') || '—'} m²</span>
              </div>
              <div class="flex justify-between">
                <span class="text-slate-400">Gmina:</span>
                <span class="text-white">${props.gmina || '—'}</span>
              </div>
              ${props.quietness_score ? `
                <div class="flex justify-between">
                  <span class="text-slate-400">Cisza:</span>
                  <span class="text-white">${props.quietness_score}/100</span>
                </div>
              ` : ''}
            </div>
          </div>
        `;
        layer.bindPopup(popupContent, { className: 'dark-popup' });

        layer.on('click', () => {
          setSelectedParcel(props.id);
        });
      },
    });

    geoJsonLayer.addTo(mapInstanceRef.current);
    geoJsonLayerRef.current = geoJsonLayer;

    // Fit bounds to GeoJSON
    const bounds = geoJsonLayer.getBounds();
    if (bounds.isValid()) {
      mapInstanceRef.current.fitBounds(bounds, { padding: [50, 50] });
    }

    console.log('[Map] Displayed', mapData.geojson.features.length, 'parcels from agent');
  }, [mapData, setSelectedParcel]);

  // Results count - consider both searchResults and mapData
  const resultCount = mapData?.parcel_count || searchResults?.results?.length || 0;
  const totalCount = searchResults?.total_matching || mapData?.parcel_count || 0;

  return (
    <div className="flex flex-col h-full">
      {/* Map Header */}
      <div className="p-4 border-b border-border flex items-center justify-between">
        <h2 className="text-sm font-medium text-white flex items-center gap-2">
          <svg className="w-4 h-4 text-accent" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
            <line x1="8" y1="2" x2="8" y2="18" />
            <line x1="16" y1="6" x2="16" y2="22" />
          </svg>
          Mapa Działek
        </h2>

        {resultCount > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">
              Pokazuję <span className="text-white font-medium">{resultCount}</span>
              {totalCount > resultCount && (
                <> z <span className="text-white font-medium">{totalCount}</span></>
              )}
            </span>
          </div>
        )}
      </div>

      {/* Map Container */}
      <div className="flex-1 relative">
        <div ref={mapRef} className="absolute inset-0" />

        {/* Empty state overlay */}
        {resultCount === 0 && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm">
            <div className="text-center p-8">
              <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-slate-800/50 flex items-center justify-center">
                <svg className="w-8 h-8 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.35-4.35" />
                </svg>
              </div>
              <h3 className="text-white font-medium mb-2">Brak wyników</h3>
              <p className="text-sm text-slate-400 max-w-xs">
                Opisz w chacie, jakiej działki szukasz, a pokażę Ci najlepsze dopasowania na mapie.
              </p>
            </div>
          </div>
        )}

        {/* Map legend */}
        <div className="absolute bottom-4 left-4 bg-slate-900/90 backdrop-blur-sm rounded-lg p-3 text-xs">
          <div className="flex items-center gap-2 text-slate-400">
            <div className="w-3 h-3 rounded-full bg-primary" />
            <span>Działka</span>
          </div>
        </div>
      </div>

      {/* Results Cards (below map) */}
      {resultCount > 0 && (
        <div className="border-t border-border p-4 max-h-[30%] overflow-y-auto">
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
            {searchResults?.results?.slice(0, 6).map((parcel) => (
              <ParcelCard
                key={parcel.parcel_id}
                parcel={parcel}
                isSelected={selectedParcel === parcel.parcel_id}
                onClick={() => setSelectedParcel(parcel.parcel_id)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface ParcelCardProps {
  parcel: SearchResultItem;
  isSelected: boolean;
  onClick: () => void;
}

function ParcelCard({ parcel, isSelected, onClick }: ParcelCardProps) {
  return (
    <button
      onClick={onClick}
      className={`text-left p-3 rounded-xl border transition-all ${
        isSelected
          ? 'bg-primary/10 border-primary/50'
          : 'bg-slate-800/50 border-slate-700/50 hover:border-slate-600/50'
      }`}
    >
      <div className="text-xs font-mono text-slate-400 mb-1 truncate">
        {parcel.parcel_id}
      </div>
      <div className="text-sm font-medium text-white mb-2">
        {parcel.area_m2?.toLocaleString('pl-PL')} m²
      </div>

      {/* Score badges */}
      <div className="flex flex-wrap gap-1">
        {parcel.quietness_score !== null && parcel.quietness_score !== undefined && (
          <ScoreBadge label="Cisza" value={parcel.quietness_score} color="amber" />
        )}
        {parcel.nature_score !== null && parcel.nature_score !== undefined && (
          <ScoreBadge label="Natura" value={parcel.nature_score} color="emerald" />
        )}
        {parcel.accessibility_score !== null && parcel.accessibility_score !== undefined && (
          <ScoreBadge label="Dostęp" value={parcel.accessibility_score} color="sky" />
        )}
      </div>
    </button>
  );
}

function ScoreBadge({ label, value, color }: { label: string; value: number; color: string }) {
  const colorClasses = {
    amber: 'bg-amber-500/20 text-amber-400',
    emerald: 'bg-emerald-500/20 text-emerald-400',
    sky: 'bg-sky-500/20 text-sky-400',
  };

  return (
    <span className={`px-1.5 py-0.5 rounded text-2xs font-medium ${colorClasses[color as keyof typeof colorClasses]}`}>
      {label}: {value.toFixed(0)}
    </span>
  );
}
