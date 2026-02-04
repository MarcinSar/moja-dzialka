import { motion } from 'motion/react';
import { useMapLayerStore, BASE_LAYERS, WMS_OVERLAYS, type BaseLayer, type OverlayLayer } from '@/stores/mapLayerStore';
import { Layers, Map, Satellite, Mountain } from 'lucide-react';

const BASE_LAYER_ICONS: Record<BaseLayer, React.ReactNode> = {
  carto: <Layers className="w-3.5 h-3.5" />,
  osm: <Map className="w-3.5 h-3.5" />,
  satellite: <Satellite className="w-3.5 h-3.5" />,
  topo: <Mountain className="w-3.5 h-3.5" />,
};

export function MapLayerSwitcherHud() {
  const baseLayer = useMapLayerStore((s) => s.baseLayer);
  const overlays = useMapLayerStore((s) => s.overlays);
  const setBaseLayer = useMapLayerStore((s) => s.setBaseLayer);
  const toggleOverlay = useMapLayerStore((s) => s.toggleOverlay);

  return (
    <motion.div
      className="flex items-center gap-1 px-1.5 py-1 rounded-xl backdrop-blur-md bg-slate-950/40 border border-white/5 pointer-events-auto"
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.4 }}
    >
      {/* Base layers */}
      {(Object.keys(BASE_LAYERS) as BaseLayer[]).map((key) => (
        <button
          key={key}
          onClick={() => setBaseLayer(key)}
          className={`flex items-center gap-1.5 px-2.5 py-2.5 md:py-1.5 rounded-lg text-xs font-medium transition-all
            ${baseLayer === key
              ? 'bg-white/10 text-white'
              : 'text-slate-500 hover:text-slate-300 hover:bg-white/5'
            }`}
        >
          {BASE_LAYER_ICONS[key]}
          <span className="hidden sm:inline">{BASE_LAYERS[key].name}</span>
        </button>
      ))}

      {/* Divider */}
      <div className="w-px h-5 bg-white/10 mx-1" />

      {/* WMS overlays */}
      {(Object.keys(WMS_OVERLAYS) as OverlayLayer[]).map((key) => (
        <button
          key={key}
          onClick={() => toggleOverlay(key)}
          className={`px-2.5 py-2.5 md:py-1.5 rounded-lg text-xs font-medium transition-all
            ${overlays[key]
              ? 'bg-sky-500/20 text-sky-400 ring-1 ring-sky-500/30'
              : 'text-slate-500 hover:text-slate-300 hover:bg-white/5'
            }`}
        >
          {WMS_OVERLAYS[key].name}
        </button>
      ))}
    </motion.div>
  );
}
