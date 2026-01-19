import { usePotreeStore, PointColorMode } from '@/stores/potreeStore';
import {
  RotateCcw,
  Palette,
  Circle,
  MapPin,
  Minus,
  Plus,
} from 'lucide-react';

interface ViewerControlsProps {
  onResetView: () => void;
}

const COLOR_MODES: { value: PointColorMode; label: string; description: string }[] = [
  { value: 'elevation', label: 'Wysokość', description: 'Kolor wg wysokości n.p.m.' },
  { value: 'rgb', label: 'RGB', description: 'Oryginalne kolory (jeśli dostępne)' },
  { value: 'classification', label: 'Klasyfikacja', description: 'Budynki, roślinność, grunt' },
  { value: 'intensity', label: 'Intensywność', description: 'Siła odbicia lasera' },
];

/**
 * Controls panel for Potree 3D viewer.
 *
 * Features:
 * - Point color mode selector
 * - Point size adjustment
 * - Parcel boundary toggle
 * - Reset view button
 */
export function ViewerControls({ onResetView }: ViewerControlsProps) {
  const {
    pointColorMode,
    pointSize,
    showParcelBoundary,
    setPointColorMode,
    setPointSize,
    toggleParcelBoundary,
  } = usePotreeStore();

  return (
    <div className="absolute bottom-4 left-4 right-4 flex justify-center">
      <div className="bg-slate-900/90 backdrop-blur-sm rounded-xl p-3 flex items-center gap-4 shadow-xl border border-slate-700/50">
        {/* Color mode selector */}
        <div className="flex items-center gap-2">
          <Palette className="w-4 h-4 text-slate-400" />
          <select
            value={pointColorMode}
            onChange={(e) => setPointColorMode(e.target.value as PointColorMode)}
            className="bg-slate-800 text-white text-sm px-2 py-1 rounded border border-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            {COLOR_MODES.map((mode) => (
              <option key={mode.value} value={mode.value}>
                {mode.label}
              </option>
            ))}
          </select>
        </div>

        {/* Separator */}
        <div className="w-px h-6 bg-slate-700" />

        {/* Point size control */}
        <div className="flex items-center gap-2">
          <Circle className="w-4 h-4 text-slate-400" />
          <span className="text-slate-400 text-sm">Punkty:</span>
          <button
            onClick={() => setPointSize(pointSize - 0.5)}
            disabled={pointSize <= 1}
            className="p-1 text-slate-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="Mniejsze punkty"
          >
            <Minus className="w-4 h-4" />
          </button>
          <span className="text-white text-sm w-6 text-center">{pointSize}</span>
          <button
            onClick={() => setPointSize(pointSize + 0.5)}
            disabled={pointSize >= 5}
            className="p-1 text-slate-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="Większe punkty"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        {/* Separator */}
        <div className="w-px h-6 bg-slate-700" />

        {/* Parcel boundary toggle */}
        <button
          onClick={toggleParcelBoundary}
          className={`flex items-center gap-2 px-3 py-1 rounded-lg text-sm transition-colors ${
            showParcelBoundary
              ? 'bg-emerald-500/20 text-emerald-400'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <MapPin className="w-4 h-4" />
          <span>Granica</span>
        </button>

        {/* Separator */}
        <div className="w-px h-6 bg-slate-700" />

        {/* Reset view */}
        <button
          onClick={onResetView}
          className="flex items-center gap-2 px-3 py-1 text-slate-400 hover:text-white rounded-lg text-sm transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
          <span>Reset</span>
        </button>
      </div>
    </div>
  );
}
