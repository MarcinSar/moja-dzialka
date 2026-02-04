/**
 * NeighborhoodAnalysis - Visualization component for neighborhood analysis
 *
 * Displays comprehensive neighborhood data including:
 * - Character assessment (urban/suburban/rural)
 * - Environment scores (quietness, nature, accessibility)
 * - Density metrics
 * - Nearby POI
 * - Strengths/weaknesses assessment
 * - Ideal use cases
 */
import { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import {
  Building2,
  Trees,
  Volume2,
  Bus,
  MapPin,
  Users,
  Home,
  ShoppingBag,
  GraduationCap,
  Plus,
  ThumbsUp,
  ThumbsDown,
  Target,
  Loader2,
  AlertCircle,
  Sparkles,
  Building,
  TreePine,
  Mountain,
} from 'lucide-react';

// Types matching backend schema
interface NeighborhoodPOI {
  type: string;
  name?: string;
  distance_m: number;
}

interface NeighborhoodCharacter {
  type: string;
  description: string;
}

interface NeighborhoodDensity {
  building_pct: number;
  residential_pct: number;
  avg_parcel_size_m2?: number;
  count_buildings_500m?: number;
  gestosc_zabudowy?: string;
}

interface NeighborhoodEnvironment {
  quietness_score: number;
  nature_score: number;
  accessibility_score: number;
}

interface NeighborhoodScores {
  transport: number;
  amenities: number;
  overall_livability: number;
}

interface NeighborhoodNeighbors {
  adjacent_count: number;
  nearby_poi_count: number;
}

interface NeighborhoodAssessment {
  strengths: string[];
  weaknesses: string[];
  ideal_for: string[];
}

interface NeighborhoodData {
  parcel_id: string;
  district?: string;
  city?: string;
  character: NeighborhoodCharacter;
  density: NeighborhoodDensity;
  environment: NeighborhoodEnvironment;
  scores: NeighborhoodScores;
  neighbors: NeighborhoodNeighbors;
  poi: NeighborhoodPOI[];
  assessment: NeighborhoodAssessment;
  summary: string;
  is_premium: boolean;
}

// Character type icons
const CHARACTER_ICONS: Record<string, React.ReactNode> = {
  urban: <Building2 className="w-5 h-5" />,
  suburban: <Home className="w-5 h-5" />,
  peripheral: <TreePine className="w-5 h-5" />,
  transitional: <Mountain className="w-5 h-5" />,
};

// Character type colors
const CHARACTER_COLORS: Record<string, string> = {
  urban: 'from-slate-500 to-slate-400',
  suburban: 'from-amber-500 to-amber-400',
  peripheral: 'from-emerald-500 to-emerald-400',
  transitional: 'from-sky-500 to-sky-400',
};

// POI type icons
const POI_ICONS: Record<string, React.ReactNode> = {
  school: <GraduationCap className="w-4 h-4" />,
  bus_stop: <Bus className="w-4 h-4" />,
  shop: <ShoppingBag className="w-4 h-4" />,
  hospital: <Plus className="w-4 h-4" />,
  default: <MapPin className="w-4 h-4" />,
};

interface NeighborhoodAnalysisProps {
  parcelId: string;
}

// Fetch neighborhood data
async function fetchNeighborhoodData(parcelId: string): Promise<NeighborhoodData> {
  const response = await fetch(`/api/v1/search/neighborhood/${encodeURIComponent(parcelId)}`);
  if (!response.ok) {
    throw new Error('Failed to fetch neighborhood data');
  }
  return response.json();
}

export function NeighborhoodAnalysis({ parcelId }: NeighborhoodAnalysisProps) {
  const [data, setData] = useState<NeighborhoodData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    fetchNeighborhoodData(parcelId)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [parcelId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-sky-400 animate-spin mb-4" />
        <p className="text-slate-400">Analizuję okolice...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-8 h-8 text-red-400 mb-4" />
        <p className="text-slate-400">{error || 'Nie udało się załadować analizy'}</p>
      </div>
    );
  }

  const characterType = data.character.type || 'transitional';
  const characterIcon = CHARACTER_ICONS[characterType] || CHARACTER_ICONS.transitional;
  const characterColor = CHARACTER_COLORS[characterType] || CHARACTER_COLORS.transitional;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4 md:space-y-6"
    >
      {/* Premium badge */}
      {data.is_premium && (
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gradient-to-r from-amber-500/20 to-orange-500/20 text-amber-400 text-sm w-fit">
          <Sparkles className="w-4 h-4" />
          <span>Premium Analiza</span>
        </div>
      )}

      {/* Character Section */}
      <div className="rounded-xl bg-white/5 p-5">
        <div className="flex items-start gap-4">
          <div
            className={`w-12 h-12 rounded-xl bg-gradient-to-br ${characterColor}
                       flex items-center justify-center text-white`}
          >
            {characterIcon}
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-white capitalize">
              {characterType === 'urban'
                ? 'Okolica miejska'
                : characterType === 'suburban'
                ? 'Okolica podmiejska'
                : characterType === 'peripheral'
                ? 'Obrzeża miasta'
                : 'Strefa przejściowa'}
            </h3>
            <p className="text-slate-400 text-sm mt-1">{data.character.description}</p>
          </div>
        </div>
      </div>

      {/* Environment Scores */}
      <div className="rounded-xl bg-white/5 p-5">
        <h4 className="text-sm font-medium text-slate-300 mb-4 flex items-center gap-2">
          <Building className="w-4 h-4" />
          Ocena środowiska
        </h4>
        <div className="grid grid-cols-3 gap-2 md:gap-4">
          <ScoreGauge
            icon={<Volume2 className="w-4 h-4" />}
            label="Cisza"
            value={data.environment.quietness_score}
            color="teal"
          />
          <ScoreGauge
            icon={<Trees className="w-4 h-4" />}
            label="Natura"
            value={data.environment.nature_score}
            color="emerald"
          />
          <ScoreGauge
            icon={<Bus className="w-4 h-4" />}
            label="Dostęp"
            value={data.environment.accessibility_score}
            color="sky"
          />
        </div>
      </div>

      {/* Livability Scores */}
      <div className="rounded-xl bg-white/5 p-5">
        <h4 className="text-sm font-medium text-slate-300 mb-4 flex items-center gap-2">
          <Target className="w-4 h-4" />
          Jakość życia
        </h4>
        <div className="space-y-3">
          <ScoreBar
            label="Transport"
            value={data.scores.transport}
            color="sky"
          />
          <ScoreBar
            label="Usługi"
            value={data.scores.amenities}
            color="amber"
          />
          <ScoreBar
            label="Ogólna ocena"
            value={data.scores.overall_livability}
            color="emerald"
            highlighted
          />
        </div>
      </div>

      {/* Density Info */}
      <div className="rounded-xl bg-white/5 p-5">
        <h4 className="text-sm font-medium text-slate-300 mb-4 flex items-center gap-2">
          <Users className="w-4 h-4" />
          Gęstość zabudowy
        </h4>
        <div className="grid grid-cols-2 gap-2 md:gap-4">
          <StatBox
            label="Zabudowa w dzielnicy"
            value={`${Math.round(data.density.building_pct)}%`}
          />
          <StatBox
            label="Mieszkalna"
            value={`${Math.round(data.density.residential_pct)}%`}
          />
          <StatBox
            label="Budynki w 500m"
            value={
              data.density.count_buildings_500m
                ? `${data.density.count_buildings_500m}`
                : '—'
            }
          />
          <StatBox
            label="Śr. działka"
            value={
              data.density.avg_parcel_size_m2
                ? `${Math.round(data.density.avg_parcel_size_m2)} m²`
                : '—'
            }
          />
        </div>
        {data.density.gestosc_zabudowy && data.density.gestosc_zabudowy !== 'brak danych' && (
          <div className="mt-3 text-xs text-slate-400 text-center">
            Kategoria: <span className="text-slate-300">{data.density.gestosc_zabudowy}</span>
          </div>
        )}
      </div>

      {/* Nearby POI */}
      {data.poi.length > 0 && (
        <div className="rounded-xl bg-white/5 p-5">
          <h4 className="text-sm font-medium text-slate-300 mb-4 flex items-center gap-2">
            <MapPin className="w-4 h-4" />
            Najbliższe obiekty
          </h4>
          <div className="space-y-2">
            {data.poi.slice(0, 5).map((poi, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between py-2 px-3 rounded-lg bg-white/5"
              >
                <div className="flex items-center gap-3">
                  <span className="text-slate-400">
                    {POI_ICONS[poi.type] || POI_ICONS.default}
                  </span>
                  <span className="text-sm text-white">
                    {poi.name || formatPOIType(poi.type)}
                  </span>
                </div>
                <span className="text-sm text-slate-500">
                  {poi.distance_m < 1000
                    ? `${Math.round(poi.distance_m)} m`
                    : `${(poi.distance_m / 1000).toFixed(1)} km`}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Assessment */}
      <div className="rounded-xl bg-white/5 p-5">
        <h4 className="text-sm font-medium text-slate-300 mb-4">Ocena</h4>

        {/* Strengths */}
        {data.assessment.strengths.length > 0 && (
          <div className="mb-4">
            <div className="flex items-center gap-2 text-emerald-400 text-sm mb-2">
              <ThumbsUp className="w-4 h-4" />
              <span>Mocne strony</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {data.assessment.strengths.map((strength, idx) => (
                <span
                  key={idx}
                  className="px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-400 text-xs"
                >
                  {strength}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Weaknesses */}
        {data.assessment.weaknesses.length > 0 && (
          <div className="mb-4">
            <div className="flex items-center gap-2 text-red-400 text-sm mb-2">
              <ThumbsDown className="w-4 h-4" />
              <span>Słabe strony</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {data.assessment.weaknesses.map((weakness, idx) => (
                <span
                  key={idx}
                  className="px-2 py-1 rounded-md bg-red-500/10 text-red-400 text-xs"
                >
                  {weakness}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Ideal for */}
        {data.assessment.ideal_for.length > 0 && (
          <div>
            <div className="flex items-center gap-2 text-sky-400 text-sm mb-2">
              <Target className="w-4 h-4" />
              <span>Idealne dla</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {data.assessment.ideal_for.map((use, idx) => (
                <span
                  key={idx}
                  className="px-2 py-1 rounded-md bg-sky-500/10 text-sky-400 text-xs"
                >
                  {use}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Summary */}
      {data.summary && (
        <div className="rounded-xl bg-gradient-to-r from-sky-500/10 to-cyan-500/10 p-5">
          <h4 className="text-sm font-medium text-sky-400 mb-2">Podsumowanie</h4>
          <p className="text-slate-300 text-sm leading-relaxed">{data.summary}</p>
        </div>
      )}
    </motion.div>
  );
}

// Score gauge component
function ScoreGauge({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  color: 'teal' | 'emerald' | 'sky' | 'amber';
}) {
  const colorClasses = {
    teal: 'text-teal-400 bg-teal-500/20',
    emerald: 'text-emerald-400 bg-emerald-500/20',
    sky: 'text-sky-400 bg-sky-500/20',
    amber: 'text-amber-400 bg-amber-500/20',
  };

  const score = Math.round(value);
  const scoreLevel =
    score >= 80 ? 'Doskonała' : score >= 60 ? 'Dobra' : score >= 40 ? 'Przeciętna' : 'Słaba';

  return (
    <div className={`flex flex-col items-center p-3 rounded-xl ${colorClasses[color]}`}>
      {icon}
      <span className="text-2xl font-bold mt-2">{score}</span>
      <span className="text-xs opacity-70">{label}</span>
      <span className="text-[10px] opacity-50 mt-0.5">{scoreLevel}</span>
    </div>
  );
}

// Score bar component
function ScoreBar({
  label,
  value,
  color,
  highlighted = false,
}: {
  label: string;
  value: number;
  color: 'teal' | 'emerald' | 'sky' | 'amber';
  highlighted?: boolean;
}) {
  const colorClasses = {
    teal: 'from-teal-500 to-teal-400',
    emerald: 'from-emerald-500 to-emerald-400',
    sky: 'from-sky-500 to-sky-400',
    amber: 'from-amber-500 to-amber-400',
  };

  return (
    <div className={highlighted ? 'p-2 -mx-2 rounded-lg bg-white/5' : ''}>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm text-slate-400">{label}</span>
        <span className={`text-sm ${highlighted ? 'text-white font-medium' : 'text-slate-300'}`}>
          {Math.round(value)}
        </span>
      </div>
      <div className="h-2 bg-slate-700/50 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className={`h-full rounded-full bg-gradient-to-r ${colorClasses[color]}`}
        />
      </div>
    </div>
  );
}

// Stat box component
function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <div className="text-lg font-semibold text-white">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}

// Format POI type to Polish
function formatPOIType(type: string): string {
  const translations: Record<string, string> = {
    school: 'Szkoła',
    bus_stop: 'Przystanek',
    shop: 'Sklep',
    hospital: 'Szpital',
    pharmacy: 'Apteka',
    restaurant: 'Restauracja',
  };
  return translations[type] || type;
}
