import { motion, AnimatePresence } from 'motion/react';
import { useParcelRevealStore } from '@/stores/parcelRevealStore';
import { ParcelMiniMap } from './ParcelMiniMap';
import { MapLayerSwitcher } from './MapLayerSwitcher';

export function ParcelRevealCard() {
  const {
    currentIndex,
    mapLayer,
    setMapLayer,
    nextParcel,
    prevParcel,
    hideReveal,
    getCurrentParcel,
    getTotalCount,
  } = useParcelRevealStore();

  const currentParcelData = getCurrentParcel();
  const totalCount = getTotalCount();

  if (!currentParcelData) return null;

  const { parcel, explanation, highlights } = currentParcelData;
  const hasCoordinates = parcel.centroid_lat !== null && parcel.centroid_lon !== null;

  return (
    <motion.div
      initial={{ x: 400, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 400, opacity: 0 }}
      transition={{ type: "spring", damping: 25, stiffness: 200 }}
      className="fixed right-4 top-1/2 -translate-y-1/2 w-[340px] max-h-[80vh] z-50 flex flex-col"
    >
      <div className="bg-slate-900/95 backdrop-blur-md border border-slate-700/50 rounded-xl shadow-2xl overflow-hidden">
        {/* Header with close button */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/50">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
            <span className="text-sm font-medium text-slate-200">Znaleziona działka</span>
          </div>
          <button
            onClick={hideReveal}
            className="text-slate-400 hover:text-slate-200 transition-colors p-1"
            aria-label="Zamknij"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Map section */}
        {hasCoordinates && (
          <div className="relative h-[200px]">
            <AnimatePresence mode="wait">
              <motion.div
                key={`map-${parcel.parcel_id}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                className="absolute inset-0"
              >
                <ParcelMiniMap
                  lat={parcel.centroid_lat!}
                  lon={parcel.centroid_lon!}
                  layer={mapLayer}
                  parcelId={parcel.parcel_id}
                />
              </motion.div>
            </AnimatePresence>

            {/* Layer switcher overlay */}
            <div className="absolute bottom-2 left-2 z-10">
              <MapLayerSwitcher
                currentLayer={mapLayer}
                onLayerChange={setMapLayer}
              />
            </div>
          </div>
        )}

        {/* Parcel info section */}
        <AnimatePresence mode="wait">
          <motion.div
            key={`info-${parcel.parcel_id}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="p-4"
          >
            {/* Location and area */}
            <div className="mb-3">
              <h3 className="text-lg font-semibold text-white">
                {parcel.miejscowosc || parcel.gmina || 'Działka'}
              </h3>
              <p className="text-slate-400 text-sm">{explanation}</p>
            </div>

            {/* Highlights */}
            {highlights.length > 0 && (
              <div className="mb-4">
                <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">Dlaczego polecam</p>
                <ul className="space-y-1.5">
                  {highlights.map((highlight, i) => (
                    <motion.li
                      key={highlight}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.1 }}
                      className="flex items-center gap-2 text-sm"
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-teal-400 flex-shrink-0" />
                      <span className="text-slate-300">{highlight}</span>
                    </motion.li>
                  ))}
                </ul>
              </div>
            )}

            {/* Score bars */}
            <div className="space-y-2 mb-4">
              {parcel.quietness_score !== null && (
                <ScoreBar label="Cisza" value={parcel.quietness_score} color="teal" />
              )}
              {parcel.nature_score !== null && (
                <ScoreBar label="Natura" value={parcel.nature_score} color="emerald" />
              )}
              {parcel.accessibility_score !== null && (
                <ScoreBar label="Dostęp" value={parcel.accessibility_score} color="amber" />
              )}
            </div>

            {/* MPZP badge */}
            {parcel.has_mpzp && (
              <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-blue-500/10 border border-blue-500/20 text-xs text-blue-400">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {parcel.mpzp_symbol ? `MPZP: ${parcel.mpzp_symbol}` : 'Ma MPZP'}
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        {/* Navigation */}
        {totalCount > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700/50 bg-slate-800/30">
            <button
              onClick={prevParcel}
              disabled={currentIndex === 0}
              className={`
                flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-all
                ${currentIndex === 0
                  ? 'text-slate-600 cursor-not-allowed'
                  : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
                }
              `}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
              Poprz.
            </button>

            <span className="text-sm text-slate-400">
              <span className="text-white font-medium">{currentIndex + 1}</span>
              <span className="mx-1">/</span>
              <span>{totalCount}</span>
            </span>

            <button
              onClick={nextParcel}
              disabled={currentIndex === totalCount - 1}
              className={`
                flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-all
                ${currentIndex === totalCount - 1
                  ? 'text-slate-600 cursor-not-allowed'
                  : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
                }
              `}
            >
              Nast.
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        )}
      </div>
    </motion.div>
  );
}

// Helper component for score bars
function ScoreBar({ label, value, color }: { label: string; value: number; color: 'teal' | 'emerald' | 'amber' }) {
  const colorClasses = {
    teal: 'from-teal-500 to-teal-400',
    emerald: 'from-emerald-500 to-emerald-400',
    amber: 'from-amber-500 to-amber-400',
  };

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-500 w-12">{label}</span>
      <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className={`h-full rounded-full bg-gradient-to-r ${colorClasses[color]}`}
        />
      </div>
      <span className="text-xs text-slate-400 w-8 text-right">{value}</span>
    </div>
  );
}
