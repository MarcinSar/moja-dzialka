import type { MapLayerType } from '@/stores/parcelRevealStore';

interface MapLayerSwitcherProps {
  currentLayer: MapLayerType;
  onLayerChange: (layer: MapLayerType) => void;
}

const LAYER_OPTIONS: { value: MapLayerType; label: string; icon: string }[] = [
  { value: 'satellite', label: 'Satelita', icon: '🛰️' },
  { value: 'terrain', label: 'Teren', icon: '🏔️' },
  { value: 'streets', label: 'Mapa', icon: '🗺️' },
];

export function MapLayerSwitcher({ currentLayer, onLayerChange }: MapLayerSwitcherProps) {
  return (
    <div className="flex gap-1 p-1 bg-slate-800/80 backdrop-blur-sm rounded-lg border border-slate-700/50">
      {LAYER_OPTIONS.map((option) => (
        <button
          key={option.value}
          onClick={() => onLayerChange(option.value)}
          className={`
            px-2 py-1 rounded text-xs font-medium transition-all duration-200
            ${currentLayer === option.value
              ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
            }
          `}
          title={option.label}
        >
          <span className="mr-1">{option.icon}</span>
          {option.label}
        </button>
      ))}
    </div>
  );
}
