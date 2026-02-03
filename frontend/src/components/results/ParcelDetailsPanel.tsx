import { useEffect, useRef, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { X, School, Bus, TreePine, Droplets, ShoppingCart, Pill, Loader2, Send, CheckCircle, MapPin, ChevronDown } from 'lucide-react';
import { useDetailsPanelStore, type MapLayer, type ParcelData } from '@/stores/detailsPanelStore';
import { NeighborhoodAnalysis } from './NeighborhoodAnalysis';

// Map layer configurations
const MAP_LAYERS: Record<MapLayer, { name: string; url: string; attribution: string }> = {
  ortho: {
    name: 'Ortofoto',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Esri',
  },
  osm: {
    name: 'OSM',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: 'OpenStreetMap',
  },
  topo: {
    name: 'Topo',
    url: 'https://tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: 'OpenTopoMap',
  },
  carto: {
    name: 'CARTO',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: 'CARTO',
  },
};

export function ParcelDetailsPanel() {
  const { isOpen, parcelData, isLoading, error, selectedLayer, closePanel, setLayer } = useDetailsPanelStore();

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
        onClick={closePanel}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          className="relative w-full max-w-3xl max-h-[90vh] overflow-y-auto
                     bg-slate-900/95 backdrop-blur-xl rounded-2xl shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="sticky top-0 z-10 flex items-center justify-between p-4
                          bg-slate-900/95 backdrop-blur-xl border-b border-white/5">
            <h2 className="text-lg font-semibold text-white">Szczegóły działki</h2>
            <button
              onClick={closePanel}
              className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="p-4 space-y-6">
            {isLoading && (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 text-sky-400 animate-spin" />
              </div>
            )}

            {error && (
              <div className="text-center py-8 text-red-400">
                <p>{error}</p>
              </div>
            )}

            {!isLoading && !error && parcelData && (
              <>
                {/* Map with layer switcher */}
                <MapSection
                  parcelData={parcelData}
                  selectedLayer={selectedLayer}
                  onLayerChange={setLayer}
                />

                {/* Basic info */}
                <BasicInfoSection parcelData={parcelData} />

                {/* Scores */}
                <ScoresSection parcelData={parcelData} />

                {/* Distances */}
                <DistancesSection parcelData={parcelData} />

                {/* POG (Planning) */}
                {parcelData.has_pog && <PogSection parcelData={parcelData} />}

                {/* Neighborhood Analysis (Premium) */}
                <NeighborhoodSection parcelId={parcelData.id_dzialki} />

                {/* Lead capture form */}
                <LeadCaptureSection parcelId={parcelData.id_dzialki} />
              </>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

// Map section with layer switcher
function MapSection({
  parcelData,
  selectedLayer,
  onLayerChange,
}: {
  parcelData: ParcelData;
  selectedLayer: MapLayer;
  onLayerChange: (layer: MapLayer) => void;
}) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const parcelLayerRef = useRef<L.GeoJSON | null>(null);

  // Helper function to create tile layer
  const createTileLayer = useCallback((layer: MapLayer): L.TileLayer => {
    const layerConfig = MAP_LAYERS[layer];
    const tileOptions: L.TileLayerOptions = { maxZoom: 19 };
    // CARTO uses {s} placeholder and needs subdomains
    if (layer === 'carto') {
      tileOptions.subdomains = 'abcd';
    }
    return L.tileLayer(layerConfig.url, tileOptions);
  }, []);

  // Initialize map ONCE (no layer dependency to avoid recreation)
  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;

    const lat = parcelData.centroid_lat || 54.35;
    const lon = parcelData.centroid_lon || 18.62;

    console.log('[DetailsMap] Creating map at:', lat, lon);

    const map = L.map(mapRef.current, {
      center: [lat, lon],
      zoom: 16,
      zoomControl: true,
      attributionControl: false,
    });

    mapInstanceRef.current = map;

    return () => {
      console.log('[DetailsMap] Destroying map');
      map.remove();
      mapInstanceRef.current = null;
      tileLayerRef.current = null;
      parcelLayerRef.current = null;
    };
  }, [parcelData.centroid_lat, parcelData.centroid_lon]);

  // Update tile layer when selected layer changes (or on initial mount)
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Remove old tile layer if exists
    if (tileLayerRef.current) {
      map.removeLayer(tileLayerRef.current);
    }

    // Add new tile layer
    console.log('[DetailsMap] Setting tile layer:', selectedLayer);
    const newTileLayer = createTileLayer(selectedLayer);
    newTileLayer.addTo(map);
    tileLayerRef.current = newTileLayer;
  }, [selectedLayer, createTileLayer]);

  // Add parcel geometry and center map
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) {
      console.log('[DetailsMap] No map instance yet');
      return;
    }

    // Remove old parcel layer
    if (parcelLayerRef.current) {
      map.removeLayer(parcelLayerRef.current);
      parcelLayerRef.current = null;
    }

    // If we have geometry, use it
    if (parcelData.geometry_wgs84) {
      console.log('[DetailsMap] Adding parcel geometry');
      const geojson = L.geoJSON(parcelData.geometry_wgs84 as GeoJSON.GeoJsonObject, {
        style: {
          fillColor: '#f59e0b',
          fillOpacity: 0.4,
          color: '#d97706',
          weight: 3,
        },
      }).addTo(map);

      parcelLayerRef.current = geojson;

      // Fit bounds to parcel
      const bounds = geojson.getBounds();
      if (bounds.isValid()) {
        console.log('[DetailsMap] Fitting to bounds:', bounds.toBBoxString());
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 17 });
      }
    } else if (parcelData.centroid_lat && parcelData.centroid_lon) {
      // Fallback to centroid if no geometry
      console.log('[DetailsMap] No geometry, using centroid:', parcelData.centroid_lat, parcelData.centroid_lon);
      map.setView([parcelData.centroid_lat, parcelData.centroid_lon], 16);
    }
  }, [parcelData.geometry_wgs84, parcelData.centroid_lat, parcelData.centroid_lon]);

  return (
    <div className="space-y-2">
      {/* Layer switcher */}
      <div className="flex gap-1">
        {(Object.keys(MAP_LAYERS) as MapLayer[]).map((layer) => (
          <button
            key={layer}
            onClick={() => onLayerChange(layer)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors
                       ${selectedLayer === layer
                         ? 'bg-sky-500 text-white'
                         : 'bg-white/5 text-slate-400 hover:text-white hover:bg-white/10'
                       }`}
          >
            {MAP_LAYERS[layer].name}
          </button>
        ))}
      </div>

      {/* Map container */}
      <div ref={mapRef} className="h-64 rounded-xl overflow-hidden" />
    </div>
  );
}

// Basic info section
function BasicInfoSection({ parcelData }: { parcelData: ParcelData }) {
  return (
    <div className="p-4 rounded-xl bg-white/5">
      <h3 className="text-sm font-medium text-slate-400 mb-3">Dane podstawowe</h3>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <span className="text-xs text-slate-500">ID działki</span>
          <p className="text-white font-mono text-sm">{parcelData.id_dzialki}</p>
        </div>
        <div>
          <span className="text-xs text-slate-500">Powierzchnia</span>
          <p className="text-white font-medium">
            {parcelData.area_m2?.toLocaleString('pl-PL')} m²
          </p>
        </div>
        <div>
          <span className="text-xs text-slate-500">Gmina</span>
          <p className="text-white">{parcelData.gmina || '-'}</p>
        </div>
        <div>
          <span className="text-xs text-slate-500">Dzielnica</span>
          <p className="text-white">{parcelData.dzielnica || parcelData.miejscowosc || '-'}</p>
        </div>
      </div>
    </div>
  );
}

// Scores section with progress bars
function ScoresSection({ parcelData }: { parcelData: ParcelData }) {
  return (
    <div className="p-4 rounded-xl bg-white/5">
      <h3 className="text-sm font-medium text-slate-400 mb-3">Wskaźniki</h3>
      <div className="space-y-3">
        {parcelData.quietness_score != null && (
          <ScoreRow label="Cisza" value={parcelData.quietness_score} color="teal" />
        )}
        {parcelData.nature_score != null && (
          <ScoreRow label="Natura" value={parcelData.nature_score} color="emerald" />
        )}
        {parcelData.accessibility_score != null && (
          <ScoreRow label="Dostępność" value={parcelData.accessibility_score} color="sky" />
        )}
      </div>
    </div>
  );
}

function ScoreRow({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: 'teal' | 'emerald' | 'sky';
}) {
  const colorClasses = {
    teal: 'from-teal-500 to-teal-400',
    emerald: 'from-emerald-500 to-emerald-400',
    sky: 'from-sky-500 to-sky-400',
  };

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-slate-400 w-24">{label}</span>
      <div className="flex-1 h-2 bg-slate-700/50 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className={`h-full rounded-full bg-gradient-to-r ${colorClasses[color]}`}
        />
      </div>
      <span className="text-sm font-medium text-white w-10 text-right">{Math.round(value)}/100</span>
    </div>
  );
}

// Distances section
function DistancesSection({ parcelData }: { parcelData: ParcelData }) {
  const formatDistance = (d: number | null | undefined) => {
    if (d == null) return '-';
    if (d < 1000) return `${Math.round(d)}m`;
    return `${(d / 1000).toFixed(1)}km`;
  };

  const distances = [
    { icon: School, label: 'Szkoła', value: parcelData.dist_to_school },
    { icon: Bus, label: 'Przystanek', value: parcelData.dist_to_bus_stop },
    { icon: TreePine, label: 'Las', value: parcelData.dist_to_forest },
    { icon: Droplets, label: 'Woda', value: parcelData.dist_to_water },
    { icon: ShoppingCart, label: 'Sklep', value: parcelData.dist_to_shop || parcelData.dist_to_supermarket },
    { icon: Pill, label: 'Apteka', value: parcelData.dist_to_pharmacy },
  ].filter((d) => d.value != null);

  if (distances.length === 0) return null;

  return (
    <div className="p-4 rounded-xl bg-white/5">
      <h3 className="text-sm font-medium text-slate-400 mb-3">Odległości</h3>
      <div className="grid grid-cols-3 gap-3">
        {distances.map((item) => (
          <div key={item.label} className="flex items-center gap-2">
            <item.icon className="w-4 h-4 text-slate-500" />
            <div>
              <span className="text-xs text-slate-500">{item.label}</span>
              <p className="text-white text-sm font-medium">{formatDistance(item.value)}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// POG (Plan Ogólny Gminy) section - all fields
function PogSection({ parcelData }: { parcelData: ParcelData }) {
  return (
    <div className="p-4 rounded-xl bg-white/5 space-y-4">
      <h3 className="text-sm font-medium text-slate-400">Plan Ogólny Gminy (POG)</h3>

      {/* Basic info */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <span className="text-xs text-slate-500">Symbol</span>
          <p className="text-white font-medium">{parcelData.pog_symbol || '-'}</p>
        </div>
        {parcelData.pog_oznaczenie && (
          <div>
            <span className="text-xs text-slate-500">Oznaczenie</span>
            <p className="text-white text-sm">{parcelData.pog_oznaczenie}</p>
          </div>
        )}
      </div>

      {/* Nazwa/Przeznaczenie */}
      {parcelData.pog_nazwa && (
        <div>
          <span className="text-xs text-slate-500">Przeznaczenie</span>
          <p className="text-white text-sm">{parcelData.pog_nazwa}</p>
        </div>
      )}

      {/* Profil podstawowy */}
      {(parcelData.pog_profil_podstawowy || parcelData.pog_profil_podstawowy_nazwy) && (
        <div className="p-3 rounded-lg bg-white/5">
          <span className="text-xs text-slate-500 block mb-1">Profil podstawowy</span>
          {parcelData.pog_profil_podstawowy && (
            <p className="text-white font-mono text-sm">{parcelData.pog_profil_podstawowy}</p>
          )}
          {parcelData.pog_profil_podstawowy_nazwy && (
            <p className="text-slate-300 text-sm mt-1">{parcelData.pog_profil_podstawowy_nazwy}</p>
          )}
        </div>
      )}

      {/* Profil dodatkowy */}
      {(parcelData.pog_profil_dodatkowy || parcelData.pog_profil_dodatkowy_nazwy) && (
        <div className="p-3 rounded-lg bg-white/5">
          <span className="text-xs text-slate-500 block mb-1">Profil dodatkowy</span>
          {parcelData.pog_profil_dodatkowy && (
            <p className="text-white font-mono text-sm">{parcelData.pog_profil_dodatkowy}</p>
          )}
          {parcelData.pog_profil_dodatkowy_nazwy && (
            <p className="text-slate-300 text-sm mt-1">{parcelData.pog_profil_dodatkowy_nazwy}</p>
          )}
        </div>
      )}

      {/* Parametry zabudowy */}
      <div className="grid grid-cols-2 gap-4">
        {parcelData.pog_maks_wysokosc_m != null && (
          <div>
            <span className="text-xs text-slate-500">Max wysokość</span>
            <p className="text-white">{parcelData.pog_maks_wysokosc_m} m</p>
          </div>
        )}
        {parcelData.pog_maks_zabudowa_pct != null && (
          <div>
            <span className="text-xs text-slate-500">Max zabudowa</span>
            <p className="text-white">{parcelData.pog_maks_zabudowa_pct}%</p>
          </div>
        )}
        {parcelData.pog_min_bio_pct != null && (
          <div>
            <span className="text-xs text-slate-500">Min tereny biologicznie czynne</span>
            <p className="text-white">{parcelData.pog_min_bio_pct}%</p>
          </div>
        )}
        {parcelData.pog_maks_intensywnosc != null && (
          <div>
            <span className="text-xs text-slate-500">Max intensywność</span>
            <p className="text-white">{parcelData.pog_maks_intensywnosc}</p>
          </div>
        )}
      </div>

      {/* Strefa mieszkaniowa */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-500">Strefa mieszkaniowa:</span>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
          parcelData.is_residential_zone
            ? 'bg-emerald-500/20 text-emerald-400'
            : 'bg-slate-500/20 text-slate-400'
        }`}>
          {parcelData.is_residential_zone ? 'TAK' : 'NIE'}
        </span>
      </div>
    </div>
  );
}

// Neighborhood Analysis section (collapsible)
function NeighborhoodSection({ parcelId }: { parcelId: string }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="rounded-xl bg-white/5 overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-sky-500/20 to-cyan-500/20 flex items-center justify-center">
            <MapPin className="w-5 h-5 text-sky-400" />
          </div>
          <div>
            <h3 className="font-medium text-white">Analiza okolicy</h3>
            <p className="text-sm text-slate-400">Premium - szczegółowa ocena otoczenia</p>
          </div>
        </div>
        <motion.div
          animate={{ rotate: isExpanded ? 180 : 0 }}
          className="text-slate-400"
        >
          <ChevronDown className="w-5 h-5" />
        </motion.div>
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="p-4 pt-0">
              <NeighborhoodAnalysis parcelId={parcelId} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Lead capture form
function LeadCaptureSection({ parcelId }: { parcelId: string }) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [interests, setInterests] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const toggleInterest = (interest: string) => {
    setInterests((prev) =>
      prev.includes(interest)
        ? prev.filter((i) => i !== interest)
        : [...prev, interest]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email) return;

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const response = await fetch('/api/v1/leads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          parcel_id: parcelId,
          name,
          email,
          phone: phone || null,
          interests,
        }),
      });

      if (!response.ok) {
        throw new Error('Nie udało się wysłać zgłoszenia');
      }

      setIsSubmitted(true);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Wystąpił błąd');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSubmitted) {
    return (
      <div className="p-6 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-center">
        <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
        <h3 className="text-lg font-medium text-white mb-1">Dziękujemy za zgłoszenie!</h3>
        <p className="text-slate-400 text-sm">
          Skontaktujemy się z Tobą wkrótce w sprawie tej działki.
        </p>
      </div>
    );
  }

  return (
    <div className="p-4 rounded-xl bg-gradient-to-b from-amber-500/10 to-transparent border border-amber-500/20">
      <h3 className="text-lg font-medium text-white mb-4 text-center">
        Jestem zainteresowany
      </h3>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Imię *</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10
                       text-white placeholder:text-slate-500 focus:outline-none focus:border-sky-500"
            placeholder="Jan"
          />
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1">Email *</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10
                       text-white placeholder:text-slate-500 focus:outline-none focus:border-sky-500"
            placeholder="jan@example.com"
          />
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1">Telefon (opcjonalnie)</label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10
                       text-white placeholder:text-slate-500 focus:outline-none focus:border-sky-500"
            placeholder="+48 123 456 789"
          />
        </div>

        <div className="space-y-2">
          <label className="block text-xs text-slate-400">Zainteresowania</label>
          <div className="flex flex-wrap gap-2">
            {[
              { id: 'wiecej_info', label: 'Więcej informacji o działce' },
              { id: 'pomoc_zakup', label: 'Pomoc w zakupie' },
            ].map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => toggleInterest(opt.id)}
                className={`px-3 py-1.5 text-xs rounded-lg transition-colors
                           ${interests.includes(opt.id)
                             ? 'bg-amber-500 text-slate-900'
                             : 'bg-white/5 text-slate-400 hover:bg-white/10'
                           }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {submitError && (
          <p className="text-red-400 text-sm text-center">{submitError}</p>
        )}

        <button
          type="submit"
          disabled={isSubmitting || !name || !email}
          className="w-full flex items-center justify-center gap-2 py-3 rounded-lg
                     bg-amber-500 text-slate-900 font-medium
                     hover:bg-amber-400 transition-colors
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Wysyłanie...</span>
            </>
          ) : (
            <>
              <Send className="w-4 h-4" />
              <span>Wyślij zgłoszenie</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
}
